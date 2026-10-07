"""Tìm kiếm web chuẩn-library (Bing RSS, dự phòng DuckDuckGo/Bing HTML), lọc theo đối tượng
và đọc HTML/PDF/DOCX qua reader chung.

Bản 2026-10-06: thêm công cụ tìm dự phòng khi Bing RSS trả rỗng/lỗi và tự sinh biến thể
mã tài liệu (TCCS41-2022 -> TCCS 41:2022, TCCS 41-2022) để tìm được tiêu chuẩn/văn bản.
"""
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit, urlencode, parse_qs, unquote
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from html import unescape
import xml.etree.ElementTree as ET
import re
from .document_intent import fallback_intent, search_queries, relevance_score, load_glossary
from .documents import read_bytes, MAX_BYTES

BROWSER_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')


def public_url(url):
    parsed=urlsplit(url)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.port not in {None,80,443}:
        raise ValueError('URL web không hợp lệ.')
    for record in socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80),type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(record[4][0]).is_global:raise PermissionError('Không truy cập địa chỉ local/private từ tool web.')
    return url


def _strip_tags(text):
    return re.sub(r'\s+',' ',unescape(re.sub(r'<[^>]+>',' ',text or ''))).strip()


def _fetch(url,accept='text/html'):
    request=Request(url,headers={'User-Agent':BROWSER_UA,'Accept':accept,'Accept-Language':'vi-VN,vi;q=0.9,en;q=0.8'})
    with urlopen(request,timeout=15) as response:
        raw=response.read(2*1024**2+1)
    if len(raw)>2*1024**2:raise ValueError('Phản hồi tìm kiếm quá lớn.')
    return raw


def code_variants(text):
    """Biến thể cách viết mã tài liệu: chèn khoảng trắng giữa chữ và số, đổi -/: trước năm."""
    variants=[]
    spaced=re.sub(r'(?<=[A-Za-zĐđ])(?=\d)',' ',text)
    for candidate in (spaced,
                      re.sub(r'(?<=\d)[-:](?=(?:19|20)\d{2}\b)',':',spaced),
                      re.sub(r'(?<=\d)[-:](?=(?:19|20)\d{2}\b)','-',spaced)):
        candidate=re.sub(r'\s+',' ',candidate).strip()
        if candidate and candidate!=text and candidate not in variants:variants.append(candidate)
    return variants


class WebTools:
    def _bing_rss(self,query):
        raw=_fetch('https://www.bing.com/search?'+urlencode({'q':query,'format':'rss','setlang':'vi'}),'application/rss+xml')
        root=ET.fromstring(raw);sources=[]
        for item in root.findall('./channel/item')[:20]:
            link=item.findtext('link','')
            if urlsplit(link).scheme not in ('http','https'):continue
            sources.append({'title':unescape(item.findtext('title','')),
                'url':link,'snippet':unescape(item.findtext('description',''))[:1000],
                'site':urlsplit(link).hostname or ''})
        return sources

    def _duckduckgo(self,query):
        html=_fetch('https://html.duckduckgo.com/html/?'+urlencode({'q':query,'kl':'vn-vi'})).decode('utf-8','replace')
        sources=[]
        for block in re.split(r'<div[^>]+class="[^"]*result[ _]',html)[1:]:
            link=re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',block,re.S)
            if not link:continue
            url=unescape(link.group(1))
            if url.startswith('//'):url='https:'+url
            if 'duckduckgo.com/l/' in url:
                target=parse_qs(urlsplit(url).query).get('uddg',[''])[0]
                url=unquote(target) if target else url
            if urlsplit(url).scheme not in ('http','https') or 'duckduckgo.com' in (urlsplit(url).hostname or ''):continue
            snippet=re.search(r'class="result__snippet"[^>]*>(.*?)</a>',block,re.S)
            sources.append({'title':_strip_tags(link.group(2)),'url':url,
                'snippet':_strip_tags(snippet.group(1) if snippet else '')[:1000],'site':urlsplit(url).hostname or ''})
            if len(sources)>=20:break
        return sources

    def _bing_html(self,query):
        html=_fetch('https://www.bing.com/search?'+urlencode({'q':query,'setlang':'vi'})).decode('utf-8','replace')
        sources=[]
        for block in re.findall(r'<li class="b_algo"(.*?)</li>',html,re.S):
            link=re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',block,re.S)
            if not link:continue
            url=unescape(link.group(1))
            if urlsplit(url).scheme not in ('http','https'):continue
            snippet=re.search(r'<p[^>]*>(.*?)</p>',block,re.S)
            sources.append({'title':_strip_tags(link.group(2)),'url':url,
                'snippet':_strip_tags(snippet.group(1) if snippet else '')[:1000],'site':urlsplit(url).hostname or ''})
            if len(sources)>=20:break
        return sources

    def web_search(self,query):
        if not isinstance(query,str) or not query.strip() or len(query)>500:raise ValueError('Query tối đa 500 ký tự.')
        errors=[]
        for engine,method in (('Bing',self._bing_rss),('DuckDuckGo',self._duckduckgo),('Bing',self._bing_html)):
            try:
                sources=method(query)
            except Exception as error:
                errors.append(f'{engine}: {str(error)[:120]}');continue
            if sources:
                return {'query':query,'engine':engine,'sources':sources,'note':'Đây là kết quả tìm kiếm, chưa phải nội dung tài liệu.'}
        if errors and len(errors)==3:
            raise RuntimeError('Không lấy được kết quả tìm kiếm: '+' | '.join(errors))
        return {'query':query,'engine':'Bing/DuckDuckGo','sources':[],'note':'Không có kết quả cho truy vấn này.'}

    def web_read(self,url):
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        opener=build_opener(NoRedirect());current=url
        for _ in range(5):
            public_url(current)
            try:
                with opener.open(Request(current,headers={'User-Agent':BROWSER_UA}),timeout=20) as response:
                    kind=response.headers.get('Content-Type','').lower()
                    if not any(x in kind for x in ('html','text/plain','pdf','wordprocessingml','octet-stream')):
                        raise ValueError('Chỉ đọc HTML/text/PDF/DOCX.')
                    raw=response.read(MAX_BYTES+1)
                    charset=response.headers.get_content_charset()
                if len(raw)>MAX_BYTES:raise ValueError('Tài liệu web vượt 20 MiB.')
                if charset and charset.lower() not in ('utf-8','utf8') and ('html' in kind or 'text/plain' in kind):
                    raw=raw.decode(charset,errors='replace').encode('utf-8')
                name=urlsplit(current).path.rsplit('/',1)[-1]
                if raw.startswith(b'PK') and not name.lower().endswith('.docx'):name='document.docx'
                result=read_bytes(raw,kind,name)
                return {**result,'url':current,'extraction':result['format']}
            except HTTPError as error:
                if error.code in (301,302,303,307,308):
                    location=error.headers.get('Location')
                    if not location:raise ValueError('Redirect không có URL.')
                    current=urljoin(current,location);continue
                raise
        raise ValueError('Trang redirect quá nhiều lần.')

    def research_events(self,query,intent=None):
        intent=intent or fallback_intent([{'role':'user','content':query}])
        queries=search_queries(intent,load_glossary())
        # Thêm biến thể mã (TCCS41-2022 -> TCCS 41:2022) và câu hỏi gốc làm phương án cuối.
        extra=[]
        for phrase in list(queries)[:1]:
            extra+=code_variants(phrase)
        queries=list(dict.fromkeys(extra[:2]+list(queries)+[query.strip()[:450]]))[:5]
        yield {'type':'status','text':'Đang tìm kiếm trên web…'}
        seen=set();candidates=[];errors=[];attempted=[];rejected=0;loose=[]
        direct=intent.get('target','').strip()
        if re.fullmatch(r'https?://\S+',direct):
            candidates=[{'title':direct,'url':direct,'snippet':'','score':100}];queries=[]
        for phrase in queries:
            if not phrase:continue
            attempted.append(phrase)
            try:
                for item in self.web_search(phrase).get('sources',[]):
                    url=item.get('url','')
                    if url in seen or urlsplit(url).scheme not in ('http','https'):continue
                    seen.add(url)
                    score=relevance_score(item,intent)
                    if score<40:
                        rejected+=1
                        # Giữ lại ứng viên có chứa mã tài liệu để không bỏ sót do cách viết khác.
                        compact=re.sub(r'\W','',(item.get('title','')+item.get('snippet','')+url).casefold())
                        codes=[re.sub(r'\W','',c.casefold()) for c in intent.get('identifiers',{}).get('codes',[])]
                        if codes and any(c and c in compact for c in codes):loose.append({**item,'score':40,'site':urlsplit(url).hostname or ''})
                        continue
                    candidates.append({**item,'score':score,'site':urlsplit(url).hostname or ''})
            except Exception as error:errors.append(str(error)[:200])
            # Đã có nhiều ứng viên mạnh: không thêm truy vấn chỉ để tăng độ trễ.
            if len([x for x in candidates if x['score']>=75])>=3:break
        if not candidates and loose:candidates=loose
        sources=sorted(candidates,key=lambda x:x['score'],reverse=True)[:5];pages=[]
        for index,source in enumerate(sources,1):
            source['id']=f'S{index}'
            source.setdefault('site',urlsplit(source['url']).hostname or '')
            if len(pages)>=3:break
            yield {'type':'status','text':'Đang đọc '+source['site']+'…'}
            try:
                page=self.web_read(source['url'])
                if len(page.get('text','').strip())<80:raise ValueError('Trang không đủ nội dung chữ.')
                if intent.get('target_type')=='document':
                    check={'title':page.get('title') or source['title'],'snippet':page['text'],'url':page.get('url',source['url'])}
                    if relevance_score(check,intent)<40 and source['score']>40:raise ValueError('Nội dung chưa khớp đối tượng tài liệu.')
                if intent.get('need_fulltext'):
                    pages.append({**source,**page,'url':page.get('url',source['url']),
                        'full_text':bool(page.get('full_text',False))})
                else:
                    pages.append({**source,'text':page['text'][:2200],
                        'url':page.get('url',source['url']),'full_text':False,'truncated':len(page['text'])>2200,
                        'coverage':'partial'})
                source['read']=True
            except Exception as error:source.update(read=False,read_error=str(error)[:200])
        note=''
        if not sources:
            note=('Đã tìm trên web nhưng chưa thấy tài liệu khớp mã/tên này. '
                  'Gợi ý người dùng kiểm tra lại số hiệu, cơ quan ban hành, hoặc đính kèm file nếu có.'
                  if intent.get('target_type')=='document' else 'Đã tìm trên web nhưng chưa thấy nguồn phù hợp.')
        elif not pages:note='Chỉ có trích đoạn tìm kiếm; chưa đọc được nội dung nguồn.'
        yield {'type':'research_result','result':{'query':intent.get('target',''),
            'queries':attempted,'engine':'Bing/DuckDuckGo','sources':sources,'pages':pages,
            'errors':errors,'rejected_count':rejected,'note':note,'web_search_done':True}}


def source_footer(result,question,answer=None):
    """Trong chat chỉ thêm nguồn có ID/URL được dùng trong câu trả lời."""
    if not result or (re.search(r'thời tiết|nhiệt độ|mưa',question,re.I) and not re.search(r'nguồn|link|url|tài liệu|tin tức',question,re.I)):return ''
    sources=result.get('pages') or result.get('sources',[]);lines=[];seen=set()
    for item in sources:
        url=item.get('url','');sid=item.get('id','')
        if urlsplit(url).scheme not in ('https','http') or url in seen:continue
        if answer is not None and not ((sid and '['+sid+']' in answer) or url in answer):continue
        seen.add(url)
        title=re.sub(r'[\r\n\[\]<>]',' ',item.get('title','Trang web'))[:200]
        site=urlsplit(url).hostname or 'Web'
        lines.append(f'- {site} - {title} - {url}')
    return '\n\nNguồn:\n'+'\n'.join(lines) if lines else ''


def cited_source_ids(answer):
    return set(re.findall(r'\[(S\d+|D\d+)\]',answer))
