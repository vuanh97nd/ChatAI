import unittest
from unittest.mock import patch
from assistant.plaxis_tutorials import tutorial_guide,CATALOG
from assistant.plaxis_remote import PlaxisRemoteApp
from assistant.tools import EXTRA_TOOLS,WRITES

class TutorialTests(unittest.TestCase):
    def test_all_chapters_have_consistent_page_ranges(self):
        for version,count,end in [('2d',19,295),('3d',9,177)]:
            entries=CATALOG[version]
            self.assertEqual(len(entries),count)
            self.assertEqual([x['chapter'] for x in entries],list(range(1,count+1)))
            self.assertEqual(entries[-1]['end'],end)
            for left,right in zip(entries,entries[1:]):self.assertEqual(left['end']+1,right['start'])
    def test_circular_footing_and_building_are_separate(self):
        two=tutorial_guide('2d',1);three=tutorial_guide('3d',1)
        self.assertIn('Axisymmetric',two['chapter']['note'])
        self.assertIn('volume Building',three['chapter']['note'])
        self.assertFalse(two['execution_verified'])
    def test_read_guide_does_not_connect_or_write(self):
        app=PlaxisRemoteApp(None)
        with patch('assistant.plaxis_remote._connect') as connect:
            result=app.commit(app.prepare('plaxis_tutorial_guide',{'version':'2d','chapter':1}))
        connect.assert_not_called();self.assertTrue(result['ok'])
        self.assertNotIn('plaxis_tutorial_guide',WRITES)
        self.assertTrue(any(s['function']['name']=='plaxis_tutorial_guide' for _,s in EXTRA_TOOLS))
    def test_bad_product_or_chapter_never_chooses_another_recipe(self):
        for version,chapter in [('2d',20),('3d',10),('2d',True),('2d','1'),('other',1)]:
            with self.assertRaises(ValueError):tutorial_guide(version,chapter)
