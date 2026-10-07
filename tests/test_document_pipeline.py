import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from assistant.document_intent import fallback_intent, normalize_intent, search_queries, relevance_score, load_glossary, analyze_intent
from assistant.document_pipeline import prepare_events, summarize_events, document_footer
from assistant.documents import read_bytes, chunks
from assistant.answer_policy import evidence_record

class FakeModel:
    def __init__(self,reply='Ý chính có căn cứ.'): self.calls=[];self.reply=reply
    def chat(self,**kwargs):
        self.calls.append(kwargs)
        if kwargs.get('format',{}).get('properties',{}).get('summary'):
            payload=json.loads(kwargs['messages'][-1]['content'])
            return {'message':{'content':json.dumps({'summary':self.reply,'quotes':[payload['text'][:20]]})}}
        return {'message':{'content':self.reply}}
    def list(self): return {'models':[{'model':'qwen2.5:3b'}]}

class DocumentsTest(unittest.TestCase):
    def test_twenty_clean_queries(self):
        cases=json.loads(Path('tests/document_cases.json').read_text())
        self.assertEqual(len(cases),20)
        for case in cases:
            with self.subTest(case=case['question']):
                history=[{'role':'user','content':q} for q in case.get('history',[])]+[{'role':'user','content':case['question']}]
                intent=fallback_intent(history,case.get('attached',False))
                queries=search_queries(intent)
                self.assertGreaterEqual(len(queries),2)
                self.assertLessEqual(len(queries),3)
                for q in queries:
                    self.assertNotRegex(q.casefold(),r'^(?:hãy |tóm tắt |tìm |giải thích |phân tích |so sánh |trích |dịch )')
    def test_followup_fallback(self):
        messages=[{'role':'user','content':'Tóm tắt ISO 9001'},{'role':'assistant','content':'ISO 9001'},{'role':'user','content':'Tóm tắt nó'}]
        self.assertEqual(fallback_intent(messages)['target'],'ISO 9001')
    def test_invented_identifiers_dropped(self):
        m=[{'role':'user','content':'Tóm tắt ISO 9001'}]
        v={'identifiers':{'codes':['ISO 9001'],'years':['2099'],'issuers':['Cơ quan bịa'],'authors':[]}}
        i=normalize_intent(v,m)
        self.assertEqual(i['identifiers']['years'],[])
        self.assertEqual(i['identifiers']['issuers'],[])
    def test_small_model_and_json(self):
        client=FakeModel(json.dumps(fallback_intent([{'role':'user','content':'Tóm tắt ISO 9001'}])))
        analyze_intent(client,[{'role':'user','content':'Tóm tắt ISO 9001'}],'qwen2.5:7b')
        self.assertEqual(client.calls[0]['model'],'qwen2.5:7b')
        self.assertIn('format',client.calls[0])
    def test_glossary_reload(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'glossary.json';p.write_text('{"ABC":"Một"}')
            self.assertEqual(load_glossary(p)['ABC'],'Một')
            p.write_text('{"ABC":"Hai"}')
            self.assertEqual(load_glossary(p)['ABC'],'Hai')
    def test_wrong_code_rejected(self):
        i={'target':'ISO 9001','identifiers':{'codes':['ISO 9001']}}
        self.assertEqual(relevance_score({'title':'ISO 14001','url':'https://iso.org/14001'},i),0)
    def test_official_irrelevant_rejected(self):
        self.assertEqual(relevance_score({'title':'Công cụ tóm tắt online','url':'https://example.gov.vn'}, {'target':'Attention Is All You Need'}),0)
    def test_map_visits_every_page(self):
        client=FakeModel();doc={'id':'D1','file':'long.pdf','pages':[{'page':n,'text':str(n)+'A'*6000} for n in range(1,6)],'full_document':True}
        doc={'id':'D1','file':'long.pdf','units':[{'page':n,'location':f'trang {n}','text':str(n)+'A'*6000} for n in range(1,6)],'full_text':True}
        intent=fallback_intent([{'role':'user','content':'Tóm tắt long.pdf'}])
        result=list(summarize_events(client,'m',doc,intent,{'num_ctx':4096}))[-1]['result']
        self.assertEqual(result['parts_total'],len(list(chunks(doc,5992))))
        self.assertEqual(result['parts_processed'],result['parts_total']);self.assertTrue(result['processed_full'])
        for n in range(1,6): self.assertTrue(any(f'trang {n}' in c['messages'][1]['content'] for c in client.calls))
    def test_map_failure_is_partial(self):
        class Broken(FakeModel):
            def chat(self,**kwargs): raise RuntimeError('No model')
        r=list(summarize_events(Broken(),'m',{'id':'D1','text':'text','full_text':True},fallback_intent([{'role':'user','content':'Tóm tắt báo cáo'}]),{'num_ctx':4096}))[-1]['result']
        self.assertFalse(r['processed_full']);self.assertEqual(r['failed_parts'],[1])
    def test_source_only_if_used(self):
        r={'documents':[{'id':'D1','origin':'web','site':'example.org','title':'Paper','url':'https://example.org/paper'}]}
        self.assertEqual(document_footer(r,'Câu trả lời không dùng nguồn.'),'')
        self.assertIn('example.org - Paper - https://example.org/paper',document_footer(r,'Ý có căn cứ [D1].'))
        self.assertNotIn('bị cắt',document_footer(r,'[D1]'))
    def test_attachment_skips_web(self):
        with patch('assistant.web.WebTools.web_search',side_effect=AssertionError('Should not search')):
            r=list(prepare_events(FakeModel(),'m',[{'role':'user','content':'Tóm tắt tài liệu'}],
                attachments=[{'file':'own.txt','text':'Nội dung riêng.','full_text':True}],use_web=True))[-1]['result']
        self.assertEqual(r['documents'][0]['file'],'own.txt');self.assertIsNone(r['web_results'])
    def test_rag_reads_original(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'full.txt';p.write_text('Entire original '+ 'A'*10000)
            class Rag:
                files=type('Files',(),{'path':lambda _,s:Path(s)})()
                def rag_search(self,q): return {'sources':[{'source':str(p),'text':'tiny hit'}]}
            r=list(prepare_events(FakeModel(),'m',[{'role':'user','content':'Tóm tắt tài liệu full'}],rag=Rag()))[-1]['result']
            self.assertGreater(r['documents'][0]['parts_total'],1)
    def test_no_results_truthful(self):
        with patch('assistant.web.WebTools.web_search',return_value={'sources':[]}):
            r=list(prepare_events(FakeModel(),'m',[{'role':'user','content':'Tóm tắt QXYZ 777:2099'}],use_web=True))[-1]['result']
        self.assertEqual(r['status'],'not_found');self.assertEqual(r['documents'],[])
    def test_full_evidence_status(self):
        self.assertEqual(evidence_record({'messages':[],'prepared_documents':[{'full_text':True,'processed_full':True,'format':'pdf'}]})['coverage'],'full_document')
    def test_reader_html_not_document_claim(self):
        r=read_bytes(b'<html><body><p>A full web page.</p></body></html>','p.html','text/html')
        self.assertEqual(r['format'],'html')
    def test_docx_order(self):
        try: from docx import Document
        except ImportError: self.skipTest('python-docx not installed')
        from io import BytesIO
        doc=Document();doc.add_paragraph('first');doc.add_table(rows=1,cols=1).cell(0,0).text='middle';doc.add_paragraph('last')
        output=BytesIO();doc.save(output);r=read_bytes(output.getvalue(),name='sample.docx')
        self.assertLess(r['text'].index('first'),r['text'].index('middle'));self.assertLess(r['text'].index('middle'),r['text'].index('last'))
        self.assertIsNone(r.get('page_count'))

if __name__=='__main__':unittest.main()

class AgentIntegrationTest(unittest.TestCase):
    def test_file_pipeline_reaches_final_answer(self):
        from types import SimpleNamespace
        from assistant.agent import Agent, bounded_context
        class Client(FakeModel):
            def chat(self,**kw):
                self.calls.append(kw)
                if kw.get('stream'):
                    return iter([SimpleNamespace(done=True,message=SimpleNamespace(content='Ý chính từ tài liệu [D1], trang 1.',tool_calls=[],thinking=None))])
                schema=kw.get('format') or {}
                if 'category' in schema.get('properties',{}):
                    text=json.dumps({'category':'personal_documents','creative':False,'complex':False,'high_accuracy':False})
                elif 'task' in schema.get('properties',{}):
                    text=json.dumps({'task':'summarize','target':'file.pdf','target_type':'document','identifiers':{},'need_web':False,'need_fulltext':True,'standalone_question':'Tóm tắt file.pdf','assumption':''})
                else:text=json.dumps({'summary':'Ý chính, trang 1.','quotes':['Page one']})
                return {'message':{'content':text}}
        class Store:
            def save(self,*args):pass
            def audit(self,*args):pass
        client=Client();agent=Agent(client,None,{'roots':[],'num_ctx':4096,'num_predict':1024,'max_rounds':3},Store(),'cid',tools_enabled=False)
        state={'running':False,'pending':None,'queue':[],'messages':[]}
        agent.start(state,'Tóm tắt tài liệu đính kèm','qwen2.5:7b')
        state['attached_documents']=[{'file':'file.pdf','text':'Text','units':[{'page':1,'location':'trang 1','text':'Page one'}],'full_text':True}]
        events=list(agent.run(state))
        self.assertFalse(state['running'])
        self.assertTrue(state['prepared_documents'][0]['processed_full'])
        self.assertIn('file.pdf',state['messages'][-1]['content'])
        self.assertTrue(any(e.get('text','').startswith('Đang đọc') for e in events))
        self.assertTrue(any('document_processing' not in kw['messages'][0]['content'] and 'file.pdf' in kw['messages'][0]['content'] for kw in client.calls if kw.get('stream')))
        self.assertEqual(len(bounded_context([{'role':'user','content':str(n)} for n in range(12)],9000)),12)
