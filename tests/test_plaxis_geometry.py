import json
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import Mock
from assistant.plaxis_commands import commands_from_json,execute_commands
from assistant.windows_apps import resume_automation

class GeometryTests(unittest.TestCase):
    def setUp(self):
        resume_automation()
        self.levels=[40,0]
        self.g=Obj(Boreholes=['bh'],Soillayers=['layer'],
                   SoilContour=Obj(BoundingBox=Obj(xMin=0,xMax=75,yMin=0,yMax=40)),
                   getsoillayerlevel=lambda b,i:self.levels[i],Points=[])
        def polygon(*points):
            self.g.Points=[Obj(x=x,y=y) for x,y in points]
            return 'Polygon_1'
        self.g.polygon=Mock(side_effect=polygon)
        self.spec={'x_left':0,'width':18,'depth':2,'source':'Manual fixture'}
    def run_command(self,command,spec=None):
        rows=commands_from_json(json.dumps([{'command':command,'args':[spec or self.spec]}]))
        return execute_commands(Obj(),self.g,rows)
    def test_live_surface_sets_bottom_not_zero(self):
        result=self.run_command('plan_excavation')
        self.assertTrue(result['ok'],result)
        self.assertEqual(result['results'][0]['value']['bottom_level'],38)
        self.g.polygon.assert_not_called()
    def test_draw_recomputes_after_surface_changes_and_reads_points(self):
        self.run_command('plan_excavation')
        self.levels[0]=35
        result=self.run_command('draw_excavation')
        self.assertTrue(result['ok'],result)
        self.g.polygon.assert_called_once_with([0,33],[18,33],[18,35],[0,35])
        self.assertTrue(result['results'][0]['value']['point_coordinates_verified'])
    def test_invalid_regions_block_before_write(self):
        for changes in ({'depth':41},{'width':100},{'width':-1},{'source':''}):
            result=self.run_command('draw_excavation',dict(self.spec,**changes))
            self.assertFalse(result['ok']);self.assertFalse(result['command_started'])
        self.g.polygon.assert_not_called()
    def test_missing_readback_does_not_claim_completion(self):
        self.g.polygon=Mock(return_value='Polygon_1')
        result=self.run_command('draw_excavation')
        self.assertFalse(result['ok']);self.assertTrue(result['command_started'])
        self.assertTrue(result['uncertain']);self.assertIn('không vẽ lại',result['error'])
    def test_no_repeat_after_uncertain_drawing(self):
        session={'aliases':{},'created':{}}
        self.g.polygon=Mock(return_value='Polygon_1')
        rows=commands_from_json(json.dumps([{'command':'draw_excavation','args':[self.spec]}]))
        first=execute_commands(Obj(),self.g,rows,session=session)
        second=execute_commands(Obj(),self.g,rows,session=session)
        self.assertTrue(first['command_started']);self.assertFalse(second['command_started'])
        self.g.polygon.assert_called_once()
    def test_3d_plan_is_rejected_before_connection(self):
        from assistant.plaxis_remote import PlaxisRemoteApp
        with self.assertRaises(ValueError):
            PlaxisRemoteApp(None).prepare('plaxis_commands',{'version':'3d','commands':json.dumps([
                {'command':'plan_excavation','args':[self.spec]}])})

    def test_sloped_surface_requires_another_planner(self):
        self.g.Boreholes=['bh','bh2']
        self.g.getsoillayerlevel=lambda b,i: (40 if b=='bh' else 35) if i==0 else 0
        result=self.run_command('draw_excavation')
        self.assertFalse(result['ok']);self.g.polygon.assert_not_called()
