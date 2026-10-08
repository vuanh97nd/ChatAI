import tempfile
import unittest
from pathlib import Path
from assistant.message_attachments import attachment_records,attachment_html
from assistant.storage import Store
from assistant.document_memory import DocumentMemory

class MessageAttachmentTests(unittest.TestCase):
    def test_sent_file_metadata_survives_reopen_and_is_escaped(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'state.db');cid=store.create(False)
            records=attachment_records([Path(directory)/'Đề <bài>.pdf'])
            state={'account_username':'alice','messages':[{'role':'user','content':'đọc file','documents':records}]}
            store.save(cid,state)
            message=Store(store.path).load(cid)['messages'][0]
            rendered=attachment_html(message['documents'])
            self.assertIn('Đề &lt;bài&gt;.pdf',rendered)
            self.assertIn('chatai-file:',rendered)
    def test_retry_new_topic_does_not_recall_old_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            memory=DocumentMemory(Store(Path(directory)/'state.db'))
            memory.remember('alice',[{'file':'Plaxis.pdf','text':'Bờ đắp cao 4 m'}])
            messages=[{'role':'user','content':'Đọc Plaxis.pdf'}, {'role':'user','content':'hi'}, {'role':'user','content':'thử lại'}]
            self.assertEqual(memory.context('alice','thử lại',messages=messages),'')
            self.assertIn('Bờ đắp',memory.context('alice','thử lại',messages=[{'role':'user','content':'Đọc Plaxis.pdf'},{'role':'user','content':'thử lại'}]))
