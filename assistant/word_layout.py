"""Semantic layout for administrative Word letters, without altering user facts."""
import re


def resignation_paragraphs(title,content):
    def clean(raw):return re.sub(r'\s+',' ',raw.strip().strip('*# ').strip())
    title=clean(title)
    candidates=[clean(raw) for raw in content.splitlines()]
    letter_title=next((line for line in candidates if re.match(r'^đơn\s+\S',line,re.I) and len(line)<=150),None)
    if re.match(r'^đơn\s+\S',title,re.I) and len(title)<=150:letter_title=title
    if not letter_title:return None
    body=[]
    for line in candidates:
        if not line or re.fullmatch(r'[\\\-_=\s]{3,}',line):continue
        if line.casefold()==letter_title.casefold() or line.casefold()==title.casefold():continue
        if re.match(r'CỘNG HÒA|Độc lập\s*[–—-]',line,re.I):continue
        body.append(line)
    return ['CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM','Độc lập – Tự do – Hạnh phúc',letter_title.upper(),*body]


def format_resignation(doc,font_name='Times New Roman',font_size=13):
    from docx.shared import Pt,RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH as Align
    from docx.oxml.ns import qn
    signature=False
    for index,paragraph in enumerate(doc.paragraphs):
        text=paragraph.text
        role='body'
        if index<3:role=('national','motto','title')[index]
        elif re.search(r'\bngày\s+(?:\.{2,}|\d+)\s+tháng\s+',text,re.I):role='date';signature=True
        elif re.match(r'Người làm đơn|Người viết đơn|\(?Ký và ghi rõ',text,re.I):role='signature';signature=True
        elif signature:role='signature'
        elif re.match(r'Kính gửi\s*:',text,re.I):role='recipient'
        elif ':' in text and len(text)<150:role='field'
        paragraph.alignment=Align.CENTER if role in ('national','motto','title') else Align.RIGHT if role in ('date','signature') else Align.LEFT if role in ('recipient','field') else Align.JUSTIFY
        fmt=paragraph.paragraph_format
        fmt.space_before=Pt(14 if role=='title' else 10 if role=='date' else 0)
        fmt.space_after=Pt(14 if role=='title' else 2 if role in ('national','motto','field') else 6)
        fmt.keep_together=True
        fmt.keep_with_next=role in ('national','motto','title','recipient','date') or text.casefold() in ('người làm đơn','người viết đơn')
        if role=='signature' and re.match(r'\(?Ký và ghi rõ',text,re.I):fmt.space_after=Pt(36)
        for run in paragraph.runs:
            run.font.color.rgb=RGBColor(0,0,0)
            run.font.name=font_name;run.font.size=Pt(16 if role=='title' else font_size)
            run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),font_name)
            run.bold=role in ('national','title') or text.casefold() in ('người làm đơn','người viết đơn')
            run.italic=role in ('date',) or bool(re.match(r'\(?Ký và ghi rõ',text,re.I))
