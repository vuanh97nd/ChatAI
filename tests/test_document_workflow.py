import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from assistant.document_intent import fallback_intent,search_queries,relevance_score,load_glossary,normalize_intent,recent_conversation
from assistant.documents import read_bytes,chunks
from assistant.document_pipeline import summarize_events,prepare_documents_events
from assistant.web import WebTools,source_footer
from assistant.answer_policy import evidence_record
from assistant.context import compact_evidence
from assistant.routing import classify_question
import test_app as fixtures


class DocumentWorkflowTest(unittest.TestCase):
    def test_twenty_cases_clean_queries_and_followup_targets(self):
        cases=json.loads(Path(__file__).with_name('document_cases.json').read_text())
        self.assertEqual(len(cases),20)
        for case in cases:
            with self.subTest(case=case['id']):
                history=[{'role':'user','content':q} for q in case.get('history',[])]+[{'role':'user','content':case['question']}]
                intent=fallback_intent(history,case.get('attached',False))
                if case['id']!=16:self.assertTrue(intent['need_fulltext'])
                for query in search_queries(intent):
                    self.assertFalse(query.casefold().startswith(('tóm tắt','hãy','giải thích','phân tích','so sánh','tìm nguồn','dịch','trích')))
                if case.get('history'):self.assertIn(case['target'],intent['target'])
                if case.get('nonexistent'):self.assertIn(case['target'],intent['target'])

    def test_unknown_acronym_not_invented_and_hot_glossary(self):
        intent=fallback_intent([{'role':'user','content':'Tóm tắt XYZ-ALPHA-UNKNOWN'}])
        self.assertEqual(intent['target'],'XYZ-ALPHA-UNKNOWN')
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'glossary.json';p.write_text('{"ABC":"Tên một"}')
            self.assertEqual(load_glossary(p)['ABC'],'Tên một')
            p.write_text('{"ABC":"Tên hai"}')
            self.assertEqual(load_glossary(p)['ABC'],'Tên hai')
            p.write_text('broken');self.assertEqual(load_glossary(p),{})

    def test_identifiers_model_invented_rejected(self):
        messages=[{'role':'user','content':'Tóm tắt RFC 9110'}]
        result=normalize_intent({'target':'Tóm tắt RFC 9110','identifiers':{
            'codes':['RFC 9110'],'years':['2099'],'authors':['Tác giả bịa'],'issuers':['Cơ quan bịa']}},messages)
        self.assertEqual(result['identifiers']['codes'],['RFC 9110'])
        self.assertFalse(result['identifiers']['years']);self.assertFalse(result['identifiers']['authors'])

    def test_relevance_discards_zalo_wrong_year_and_prefers_official(self):
        intent=fallback_intent([{'role':'user','content':'Tóm tắt TCCS41-2022'}])
        self.assertEqual(relevance_score({'title':'Đăng nhập Zalo','snippet':'Công cụ chat','url':'https://chat.zalo.me'},intent),0)
        self.assertEqual(relevance_score({'title':'TCCS41-2021','url':'https://example.com','snippet':'TCCS41-2021'},intent),0)
        a={'title':'TCCS41-2022','snippet':'TCCS41-2022','url':'https://example.com'}
        b={**a,'url':'https://example.gov.vn'}
        self.assertGreaterEqual(relevance_score(b,intent),relevance_score(a,intent))

    def test_research_retries_and_reads_all_text(self):
        intent=fallback_intent([{'role':'user','content':'Tóm tắt Báo cáo ABC 2024'}]);web=WebTools();queries=[]
        def search(query):
            queries.append(query)
            return {'sources':[{'title':'Báo cáo ABC 2024','url':'https://example.org/abc','snippet':'Báo cáo ABC 2024'}]} if len(queries)>1 else {'sources':[{'title':'Zalo','url':'https://chat.zalo.me'}]}
        web.web_search=search
        web.web_read=lambda url:{'url':url,'text':'Báo cáo ABC 2024 '+('Nội dung '*2000),'units':[{'location':'trang 1','text':'abc'}],'full_text':True}
        result=list(web.research_events('Tóm tắt Báo cáo ABC 2024',intent))[-1]['result']
        self.assertGreaterEqual(len(queries),2);self.assertEqual(len(result['pages']),1)
        self.assertGreater(len(result['pages'][0]['text']),7000)
        self.assertTrue(result['pages'][0]['full_text'])

    def test_no_unrelated_footer_no_fixed_partial_label(self):
        result={'pages':[{'id':'S1','title':'Bài báo','url':'https://example.org'}]}
        self.assertEqual(source_footer(result,'Tóm tắt','Chưa tìm được tài liệu phù hợp.'),'')
        self.assertEqual(source_footer(result,'Tóm tắt','Kiến thức chung.'),'')
        footer=source_footer(result,'Tóm tắt','Kết quả bài báo [S1]')
        self.assertIn('example.org - Bài báo - https://example.org',footer)
        self.assertNotIn('bị cắt',footer)

    def test_real_pdf_first_last_page_and_scan_is_partial(self):
        from pypdf import PdfWriter
        from pypdf.generic import NameObject,DictionaryObject,DecodedStreamObject
        writer=PdfWriter()
        for word in ('BEGIN_DOC','END_DOC'):
            page=writer.add_blank_page(width=300,height=300)
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
            stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 20 200 Td ('+word+') Tj ET').encode())
            page[NameObject('/Contents')]=writer._add_object(stream)
        buffer=io.BytesIO();writer.write(buffer)
        doc=read_bytes(buffer.getvalue(),name='report.pdf')
        self.assertTrue(doc['full_text']);self.assertIn('END_DOC',doc['text']);self.assertEqual(doc['units'][-1]['page'],2)
        writer.add_blank_page(width=300,height=300);buffer=io.BytesIO();writer.write(buffer)
        self.assertFalse(read_bytes(buffer.getvalue(),name='report.pdf')['full_text'])

    def test_full_html_page_not_claimed_complete_book(self):
        state={'prepared_documents':[{'id':'S1','format':'html','processed_full':True,'full_text':True,'text':'All page text'}]}
        self.assertEqual(evidence_record(state,True)['coverage'],'full_page')
        from assistant.answer_policy import guard_answer
        self.assertTrue(guard_answer('Tôi đã đọc toàn văn tài liệu.',state,True)[1])

    def test_direct_url_reads_without_search(self):
        web=WebTools();intent=fallback_intent([{'role':'user','content':'Tóm tắt https://example.org/paper.pdf'}])
        web.web_search=lambda q: (_ for _ in ()).throw(AssertionError('không cần search URL sẵn có'))
        web.web_read=lambda url:{'url':url,'title':'Paper','text':'https://example.org/paper.pdf '*10,'full_text':True}
        result=list(web.research_events(intent['target'],intent))[-1]['result']
        self.assertEqual(result['queries'],[]);self.assertEqual(len(result['pages']),1)

    def test_docx_without_extra_library_and_no_fake_pages(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Đầu văn bản</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cuối bảng</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
        doc=read_bytes(buf.getvalue(),name='test.docx')
        self.assertTrue(doc['full_text']);self.assertIn('Cuối bảng',doc['text'])
        self.assertTrue(all('page' not in u for u in doc['units']))

    def test_html_article_no_script_and_end_is_read(self):
        doc=read_bytes(b'<html><title>Report</title><nav>Login</nav><article><p>Start</p><script>evil()</script><p>END</p></article></html>',kind='text/html')
        self.assertIn('END',doc['text']);self.assertNotIn('Login',doc['text']);self.assertNotIn('evil',doc['text']);self.assertTrue(doc['full_text'])

    def test_chunks_cover_end_and_pages(self):
        doc={'units':[{'text':'A'*2000,'page':1,'location':'trang 1'},{'text':'END_TOKEN','page':2,'location':'trang 2'}]}
        blocks=list(chunks(doc,500))
        self.assertIn('END_TOKEN',blocks[-1]['text']);self.assertIn(2,blocks[-1]['pages'])
        self.assertEqual(sum(x['text'].count('A') for x in blocks),2000)

    def test_map_processes_every_part_valid_quotes_and_full_coverage(self):
        class Client:
            calls=[]
            def chat(self,**kwargs):
                value=json.loads(kwargs['messages'][-1]['content']);self.calls.append(value)
                quote='END_MARKER' if 'END_MARKER' in value['text'] else 'A'*20
                return {'message':{'content':json.dumps({'summary':'Ghi nhận '+quote,'quotes':[quote]})}}
        client=Client();doc={'id':'D1','file':'test.txt','full_text':True,'units':[{'location':'đoạn 1','text':'A'*3000},{'location':'đoạn 2','text':'END_MARKER'}]}
        intent=fallback_intent([{'role':'user','content':'Tóm tắt báo cáo test'}])
        events=list(summarize_events(client,'qwen2.5:7b',doc,intent,{'num_ctx':2048}))
        result=events[-1]['result']
        self.assertEqual(result['parts_processed'],result['parts_total']);self.assertTrue(result['processed_full']);self.assertIn('END_MARKER',result['text'])
        self.assertEqual(evidence_record({'prepared_documents':[result]})['coverage'],'full_document')

    def test_bad_map_quote_and_scanned_partial_never_full(self):
        client=SimpleNamespace(chat=lambda **kw:{'message':{'content':'{"summary":"Bịa","quotes":["không có trong tài liệu"]}'}})
        doc={'id':'D1','file':'x.pdf','full_text':False,'text':'actual','issues':['scan']}
        intent=fallback_intent([{'role':'user','content':'Tóm tắt báo cáo'}])
        result=list(summarize_events(client,'qwen2.5:7b',doc,intent,{'num_ctx':2048}))[-1]['result']
        self.assertFalse(result['processed_full']);self.assertEqual(result['failed_parts'],[1])

    def test_ten_turn_context_and_standalone_classifier(self):
        messages=[{'role':'user','content':f'báo cáo {i}'} for i in range(15)]
        value={'category':'knowledge','creative':False,'complex':False,'high_accuracy':False,
            'intent':{'task':'summarize','target':'báo cáo 14','target_type':'document','identifiers':{},'need_web':True,'need_fulltext':True,'standalone_question':'Tóm tắt báo cáo 14','assumption':''}}
        calls=[]
        def chat(**kw):calls.append(kw);return {'message':{'content':json.dumps(value)}}
        route=classify_question(SimpleNamespace(chat=chat),messages)
        payload=json.loads(calls[0]['messages'][-1]['content'])
        self.assertEqual(len(payload['conversation']),15)
        self.assertEqual(route['intent']['standalone_question'],'Tóm tắt báo cáo 14')
        self.assertNotIn('few-shot',calls[0]['messages'][0]['content'])

    def test_compaction_keeps_processed_metadata_not_mutate_snapshot(self):
        state={'prepared_documents':[{'id':'D1','file':'x','text':'a'*9000,'processed_full':True,'full_text':True}]}
        compact=compact_evidence(state,budget=1000)
        self.assertTrue(compact['prepared_documents'][0]['processed_full'])
        self.assertTrue(compact['prepared_documents'][0]['context_truncated'])
        self.assertEqual(len(state['prepared_documents'][0]['text']),9000)


class DocumentAgentTest(unittest.TestCase):
    setUp=fixtures.AppTest.setUp
    tearDown=fixtures.AppTest.tearDown
    def test_attached_full_document_beats_web_and_sources_only_used(self):
        from assistant.agent import Agent
        class Client:
            def chat(self,**kw):
                if kw.get('format') and 'category' in kw['format']['properties']:
                    return {'message':{'content':json.dumps({'category':'personal_documents','creative':False,'complex':False,'high_accuracy':False})}}
                if kw.get('format'):
                    return {'message':{'content':'{"summary":"Giá trị trong báo cáo là 42.","quotes":["42"]}'}}
                return iter([fixtures.chunk('Giá trị là 42 [D1].')])
        state=self.store.load(self.cid);agent=Agent(Client(),None,self.cfg,self.store,self.cid,tools_enabled=False)
        agent.start(state,'Tóm tắt báo cáo đính kèm','qwen2.5:7b')
        state.update(ui_mode=4,web_search_requested=True,attached_documents=[{'file':'report.pdf','text':'42','units':[{'location':'trang 3','page':3,'text':'42'}],'full_text':True}])
        with patch('assistant.web.WebTools.research_events',side_effect=AssertionError('không tìm khi đã có file')):
            events=list(agent.run(state))
        self.assertIn('report.pdf - trang 3',state['messages'][-1]['content'])
        self.assertNotIn('Nguồn:',state['messages'][-1]['content'])
        self.assertEqual(state['prepared_documents'][0]['parts_processed'],1)
        self.assertIn('Giá trị là 42', ''.join(e.get('text','') for e in events if e['type']=='token'))

    def test_doc_web_off_never_calls_any_search(self):
        from assistant.agent import Agent
        agent=Agent(fixtures.FakeClient([[fixtures.chunk('Mình chưa có văn bản; có thể giải thích kiến thức chung.')]]),None,self.cfg,self.store,self.cid,tools_enabled=False)
        state=self.store.load(self.cid);agent.start(state,'Tóm tắt báo cáo không tồn tại','qwen2.5:7b')
        state.update(ui_mode=0,web_search_requested=False)
        with patch('assistant.web.WebTools.research_events',side_effect=AssertionError('web tắt')):
            list(agent.run(state))
        self.assertFalse(state['running']);self.assertNotIn('Nguồn:',state['messages'][-1]['content'])

if __name__=='__main__':unittest.main()
