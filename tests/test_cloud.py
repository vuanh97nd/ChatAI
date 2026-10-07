import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from io import BytesIO
from assistant.cloud import guest_token,parse_events,cloud_events,CloudError
from assistant.storage import Store

class CloudTest(unittest.TestCase):
    def test_sse_unicode_and_error(self):
        frames=[b'event: delta\n',('data: '+json.dumps({'text':'Xin chào'},ensure_ascii=False)+'\n').encode(),b'\n',b'event: done\n',b'data: {"success":true}\n',b'\n']
        self.assertEqual(list(parse_events(frames))[0],('delta',{'text':'Xin chào'}))
        with self.assertRaisesRegex(CloudError,'Ngắt'):
            list(parse_events(['event: error\n','data: {"message":"Ngắt"}\n','\n']))

    def test_guest_token_persists_and_is_not_account_password(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'db.sqlite3');token=guest_token(store)
            self.assertEqual(len(token),64);self.assertEqual(guest_token(Store(Path(temp)/'db.sqlite3')),token)

    def test_quota_error_preserves_machine_readable_code(self):
        def opener(request,timeout):
            raise HTTPError(request.full_url,409,'limit',{},BytesIO(b'{"message":"Choose model","code":"CLOUD_LIMIT"}'))
        with self.assertRaises(CloudError) as caught:list(cloud_events('https://server.example',{'text':'Hello'},opener))
        self.assertEqual(caught.exception.code,'CLOUD_LIMIT')

    def test_invalid_endpoint_does_not_send_data(self):
        with self.assertRaises(ValueError):list(cloud_events('http://example.com',{},lambda *a,**k:self.fail('Network must not run')))
