"""Tests for cad_tracdoc longitudinal profile DXF generation."""
import unittest
from assistant.cad_tracdoc import build_tracdoc_dxf


SAMPLE_POINTS = [
    {"station":    0, "ground_elev": 2.50, "design_elev": 3.00, "pile_name": "A0"},
    {"station":   50, "ground_elev": 2.30, "design_elev": 3.25, "pile_name": "1"},
    {"station":  100, "ground_elev": 2.10, "design_elev": 3.50, "pile_name": "2"},
    {"station":  200, "ground_elev": 1.80, "design_elev": 4.20, "pile_name": "3"},
    {"station":  368, "ground_elev": 1.50, "design_elev": 4.80, "pile_name": "CT"},
]


class TracDocTest(unittest.TestCase):
    def _build(self, pts=None, **kw):
        return build_tracdoc_dxf(pts or SAMPLE_POINTS, **kw)

    def test_dxf_created(self):
        doc = self._build()
        self.assertIsNotNone(doc)

    def test_has_ground_and_design_polylines(self):
        doc = self._build()
        msp = doc.modelspace()
        polys = [e for e in msp if e.dxftype() == 'LWPOLYLINE']
        self.assertGreaterEqual(len(polys), 2)

    def test_profile_layers_present(self):
        doc = self._build()
        layer_names = {l.dxf.name for l in doc.layers}
        self.assertIn('KS-TUY-2401-Trắc dọc tự nhiên', layer_names)
        self.assertIn('TK-DBO-1601-Đtk tim tuyến', layer_names)
        self.assertIn('TK-ADS-9302-Bảng trắc dọc', layer_names)

    def test_station_text_present(self):
        doc = self._build()
        msp = doc.modelspace()
        texts = [e.dxf.text for e in msp if e.dxftype() == 'TEXT']
        joined = ' '.join(texts)
        self.assertIn('Km0+', joined)

    def test_elevation_values_in_table(self):
        doc = self._build()
        msp = doc.modelspace()
        texts = [e.dxf.text for e in msp if e.dxftype() == 'TEXT']
        joined = ' '.join(texts)
        # Design elevation of last point
        self.assertIn('4.80', joined)
        # Ground elevation of first point
        self.assertIn('2.50', joined)

    def test_units_set(self):
        doc = self._build(units='m')
        self.assertEqual(doc.units, 6)  # 6 = metres

    def test_requires_at_least_two_points(self):
        with self.assertRaises((ValueError, Exception)):
            build_tracdoc_dxf([SAMPLE_POINTS[0]])

    def test_empty_points_raises(self):
        with self.assertRaises((ValueError, Exception)):
            build_tracdoc_dxf([])

    def test_tools_registry(self):
        from assistant.tools import EXTRA_TOOLS, WRITES
        names = [t['function']['name'] for _, t in EXTRA_TOOLS]
        self.assertIn('cad_tracdoc_stations', names)
        self.assertIn('cad_tracdoc_stations', WRITES)


if __name__ == '__main__':
    unittest.main()
