"""Test AI sinh Plaxis script từ bài toán trong test_scenario_foundation.md.

Đọc thông số từ file scenario, gọi PlaxisApp, kiểm tra script đầu ra
theo đúng yêu cầu ghi trong file scenario đó.
"""
import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

# Thông số từ tests/test_scenario_foundation.md
SCENARIO_PROBLEM = json.dumps({
    "type": "foundation_settlement",
    "footing_width": 4.0,
    "footing_depth": 2.0,
    "load": 100.0,
    "soil_layers": [
        {
            "name": "Cat pha",
            "E": 18000,
            "nu": 0.30,
            "gamma": 18.5,
            "c": 8,
            "phi": 28,
            "thickness": 5.0,
        },
        {
            "name": "Set deo",
            "E": 6000,
            "nu": 0.35,
            "gamma": 17.0,
            "c": 20,
            "phi": 18,
            "thickness": 7.0,
        },
    ],
})

PROJECT_NAME = "LunMongNong_TwoLayer"


def _make_app(tmp_dir):
    from assistant.plaxis_app import PlaxisApp
    root = Path(tmp_dir)
    files = Mock()
    files.roots = [root]
    files.path = lambda p, exists=True: Path(p)
    audit = Mock()
    return PlaxisApp(files, audit)


def _run_scenario(tmp_dir):
    app = _make_app(tmp_dir)
    args = {
        "project_name": PROJECT_NAME,
        "version": "2d",
        "problem": SCENARIO_PROBLEM,
    }
    plan = app.prepare("plaxis_generate_script", args)
    result = app.commit(plan)
    script = Path(result["path"]).read_text(encoding="utf-8")
    return result, script


class ScenarioFoundationAITest(unittest.TestCase):
    """AI tạo Plaxis script theo bài toán lún móng nông hai lớp đất."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.result, cls.script = _run_scenario(cls._tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    # ── Kết quả trả về ──────────────────────────────────────────────────────

    def test_result_ok(self):
        """result["ok"] phải là True."""
        self.assertTrue(self.result["ok"])

    def test_problem_type(self):
        """problem_type phải là foundation_settlement."""
        self.assertEqual(self.result["problem_type"], "foundation_settlement")

    def test_not_executed(self):
        """Script chỉ được lưu file, không tự kết nối Plaxis."""
        self.assertFalse(self.result["executed"])

    def test_file_exists(self):
        """File script phải được ghi ra đĩa."""
        self.assertTrue(Path(self.result["path"]).exists())

    # ── Nội dung script ─────────────────────────────────────────────────────

    def test_python_syntax_valid(self):
        """Script sinh ra phải là Python hợp lệ về cú pháp."""
        try:
            ast.parse(self.script)
        except SyntaxError as e:
            self.fail(f"SyntaxError trong script Plaxis: {e}\n---\n{self.script[:600]}")

    def test_has_plaxis_import(self):
        """Script phải import new_server từ plxscripting."""
        self.assertIn("from plxscripting.easy import new_server", self.script)

    def test_has_soil_material_call(self):
        """Script phải gọi g.soilmat() để khai báo vật liệu."""
        self.assertIn("g.soilmat()", self.script)

    def test_has_lineload(self):
        """Script phải đặt tải trọng móng bằng g.lineload(."""
        self.assertIn("g.lineload(", self.script)

    def test_has_mesh(self):
        """Script phải chia lưới phần tử bằng g.mesh(."""
        self.assertIn("g.mesh(", self.script)

    def test_has_calculate(self):
        """Script phải chạy tính toán bằng g.calculate()."""
        self.assertIn("g.calculate()", self.script)

    def test_layer_names_in_script(self):
        """Tên hai lớp đất phải xuất hiện trong script."""
        self.assertIn("Cat pha", self.script)
        self.assertIn("Set deo", self.script)

    def test_load_intensity_in_script(self):
        """Cường độ tải = 100 / 4 = 25.00 kPa/m phải xuất hiện trong script."""
        self.assertIn("25.00", self.script)

    def test_scenario_file_exists(self):
        """File mô tả bài toán phải tồn tại trong thư mục tests/."""
        scenario = Path(__file__).parent / "test_scenario_foundation.md"
        self.assertTrue(scenario.exists(), "tests/test_scenario_foundation.md không tìm thấy")

    def test_scenario_file_has_json_block(self):
        """File scenario phải chứa JSON đầu vào cho AI."""
        scenario = Path(__file__).parent / "test_scenario_foundation.md"
        content = scenario.read_text(encoding="utf-8")
        self.assertIn("foundation_settlement", content)
        self.assertIn("Cat pha", content)
        self.assertIn("Set deo", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
