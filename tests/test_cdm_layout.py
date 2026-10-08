"""Tests for CDM pile layout DXF generation."""
import unittest
from assistant.cdm_layout import build_cdm_dxf


class CdmLayoutTest(unittest.TestCase):
    def _build(self, **kwargs):
        defaults = dict(b_road=12, l_treatment=100, d_pile=0.8,
                        pile_depth=12, spacing_x=2, spacing_y=2, units='m')
        defaults.update(kwargs)
        return build_cdm_dxf(**defaults)

    def test_dxf_created_and_has_circles(self):
        doc = self._build()
        msp = doc.modelspace()
        circles = [e for e in msp if e.dxftype() == 'CIRCLE']
        # Cross-section: 7 cols × 15 rings = 105; Plan: 50 × 6 = 300
        self.assertGreater(len(circles), 100)

    def test_correct_pile_radius(self):
        doc = self._build(d_pile=0.8)
        msp = doc.modelspace()
        radii = {round(e.dxf.radius, 4) for e in msp if e.dxftype() == 'CIRCLE'}
        self.assertIn(0.4, radii)

    def test_units_set(self):
        doc = self._build(units='m')
        self.assertEqual(doc.units, 6)  # 6 = metres

    def test_title_texts_present(self):
        doc = self._build()
        msp = doc.modelspace()
        texts = [e.dxf.text for e in msp if e.dxftype() == 'TEXT']
        joined = ' '.join(texts)
        self.assertIn('MẶT CẮT', joined)
        self.assertIn('MẶT BẰNG', joined)

    def test_different_spacings(self):
        doc = self._build(spacing_x=1.5, spacing_y=1.5)
        msp = doc.modelspace()
        circles = [e for e in msp if e.dxftype() == 'CIRCLE']
        self.assertGreater(len(circles), 200)

    def test_tools_registry(self):
        from assistant.tools import EXTRA_TOOLS, WRITES
        names = [t['function']['name'] for _, t in EXTRA_TOOLS]
        self.assertIn('cad_cdm_layout', names)
        self.assertIn('cad_cdm_layout', WRITES)


if __name__ == '__main__':
    unittest.main()
