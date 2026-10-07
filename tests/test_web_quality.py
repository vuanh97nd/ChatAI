import unittest
from assistant.web import WebTools, source_footer

class ResearchTest(unittest.TestCase):
    def test_unique_five_search_results_three_pages_and_failure(self):
        web=WebTools()
        web.web_search=lambda q: {'sources':[{'title':'Tin mới '+str(i),'url':f'https://example.com/{i}','snippet':'Thông tin tin mới'} for i in [0,0,1,2,3,4,5]]}
        def read(url):
            if url.endswith('/0'):raise OSError('blocked')
            return {'url':url,'text':'main content '*400}
        web.web_read=read
        events=list(web.research_events('tin mới'))
        result=events[-1]['result']
        self.assertEqual(len(result['sources']),5)
        self.assertEqual(len(result['pages']),3)
        self.assertFalse(result['sources'][0]['read'])
        self.assertTrue(all(len(p['text'])<=2200 for p in result['pages']))
        footer=source_footer(result,'tin mới')
        self.assertIn('example.com - Tin mới 1 - https://example.com/1',footer)
        self.assertNotIn('https://example.com/0',footer)

    def test_no_fabricated_sources_and_weather_preference(self):
        web=WebTools();web.web_search=lambda q: (_ for _ in ()).throw(OSError('offline'))
        result=list(web.research_events('x'))[-1]['result']
        self.assertEqual(result['sources'],[])
        self.assertEqual(source_footer(result,'x'),'')
        result={'sources':[{'url':'https://example.com','title':'Thời tiết'}]}
        self.assertEqual(source_footer(result,'thời tiết hôm nay'),'')
        self.assertIn('https://example.com',source_footer(result,'thời tiết nguồn ở đâu'))
