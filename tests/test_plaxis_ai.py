"""Test Plaxis script generation - AI tự tạo script địa kỹ thuật.

Kiểm tra PlaxisApp.prepare() + commit() sinh ra script Python hợp lệ
cho cả ba loại bài toán: foundation_settlement, slope_stability, retaining_wall.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock


def _make_files(tmp_dir):
    """Tạo mock Files object với root thư mục tạm."""
    root = Path(tmp_dir)
    files = Mock()
    files.roots = [root]

    def path_fn(p, exists=True):
        return Path(p)

    files.path = path_fn
    return files


def _make_app(tmp_dir):
    from assistant.plaxis_app import PlaxisApp
    audit = Mock()
    return PlaxisApp(_make_files(tmp_dir), audit)


# ── Dữ liệu đầu vào mẫu ──────────────────────────────────────────────────────

FOUNDATION_PROBLEM = json.dumps({
    "type": "foundation_settlement",
    "footing_width": 2.0,
    "footing_depth": 1.5,
    "load": 500.0,
    "soil_layers": [
        {"name": "Cat pha", "E": 15000, "nu": 0.3, "gamma": 18.5, "c": 5, "phi": 28, "thickness": 4.0},
        {"name": "Set", "E": 8000, "nu": 0.35, "gamma": 17.0, "c": 15, "phi": 20, "thickness": 6.0},
    ],
})

SLOPE_PROBLEM = json.dumps({
    "type": "slope_stability",
    "slope_angle": 35.0,
    "slope_height": 6.0,
    "analysis": "Bishop",
    "soil_layers": [
        {"name": "Dat set", "E": 12000, "nu": 0.3, "gamma": 19.0, "c": 20, "phi": 25, "thickness": 8.0},
    ],
})

EXCAVATION_PROBLEM = json.dumps({
    "type": "excavation_pit",
    "excavation_depth": 6.0,
    "excavation_width": 8.0,
    "wall_thickness": 0.5,
    "embedment_depth": 2.0,
    "surcharge": 20.0,
    "soil_layers": [
        {"name": "Cat pha", "E": 20000, "nu": 0.30, "gamma": 18.5, "c": 5,  "phi": 28, "thickness": 4.0},
        {"name": "Set",     "E": 8000,  "nu": 0.35, "gamma": 17.0, "c": 25, "phi": 18, "thickness": 6.0},
        {"name": "Cat min", "E": 15000, "nu": 0.28, "gamma": 18.0, "c": 2,  "phi": 25, "thickness": 8.0},
    ],
})

RETAINING_PROBLEM = json.dumps({
    "type": "retaining_wall",
    "wall_height": 5.0,
    "wall_thickness": 0.4,
    "surcharge": 20.0,
    "soil_layers": [
        {"name": "Cat", "E": 20000, "nu": 0.28, "gamma": 18.0, "c": 0, "phi": 32, "thickness": 7.0},
    ],
})


# ── Helper ────────────────────────────────────────────────────────────────────

def _run(tmp_dir, problem_json, version="2d", project_name="TestProject"):
    """Chạy prepare + commit, trả về (result, script_text)."""
    app = _make_app(tmp_dir)
    args = {"project_name": project_name, "version": version, "problem": problem_json}
    plan = app.prepare("plaxis_generate_script", args)
    result = app.commit(plan)
    script = Path(result["path"]).read_text(encoding="utf-8")
    return result, script


# ── Test cases ────────────────────────────────────────────────────────────────

class PlaxisFoundationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.result, self.script = _run(self._tmp.name, FOUNDATION_PROBLEM)

    def tearDown(self):
        self._tmp.cleanup()

    def test_result_ok(self):
        self.assertTrue(self.result["ok"])

    def test_problem_type_in_result(self):
        self.assertEqual(self.result["problem_type"], "foundation_settlement")

    def test_file_saved(self):
        self.assertTrue(Path(self.result["path"]).exists())

    def test_script_has_plaxis_import(self):
        self.assertIn("from plxscripting.easy import new_server", self.script)

    def test_script_has_soil_material(self):
        self.assertIn("g.soilmat()", self.script)

    def test_script_has_mesh_call(self):
        self.assertIn("g.mesh(", self.script)

    def test_script_has_calculate(self):
        self.assertIn("g.calculate()", self.script)

    def test_script_has_lineload(self):
        self.assertIn("g.lineload(", self.script)

    def test_soil_names_in_script(self):
        self.assertIn("Cat pha", self.script)
        self.assertIn("Set", self.script)

    def test_not_auto_run(self):
        self.assertFalse(self.result["executed"])

    def test_note_present(self):
        self.assertIn("note", self.result)


class PlaxisSlopeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.result, self.script = _run(self._tmp.name, SLOPE_PROBLEM)

    def tearDown(self):
        self._tmp.cleanup()

    def test_result_ok(self):
        self.assertTrue(self.result["ok"])

    def test_problem_type(self):
        self.assertEqual(self.result["problem_type"], "slope_stability")

    def test_script_mentions_bishop(self):
        self.assertIn("Bishop", self.script)

    def test_script_has_borehole(self):
        self.assertIn("g.borehole(", self.script)

    def test_script_has_gotomesh(self):
        self.assertIn("g.gotomesh()", self.script)

    def test_slope_soil_in_script(self):
        self.assertIn("Dat set", self.script)


class PlaxisRetainingWallTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.result, self.script = _run(self._tmp.name, RETAINING_PROBLEM)

    def tearDown(self):
        self._tmp.cleanup()

    def test_result_ok(self):
        self.assertTrue(self.result["ok"])

    def test_problem_type(self):
        self.assertEqual(self.result["problem_type"], "retaining_wall")

    def test_script_has_plate(self):
        self.assertIn("g.plate(", self.script)

    def test_script_has_platemat(self):
        self.assertIn("g.platemat()", self.script)

    def test_surcharge_in_script(self):
        self.assertIn("uniformload", self.script)

    def test_wall_soil_in_script(self):
        self.assertIn("Cat", self.script)


class PlaxisExcavationPitTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.result, self.script = _run(self._tmp.name, EXCAVATION_PROBLEM)

    def tearDown(self):
        self._tmp.cleanup()

    def test_result_ok(self):
        self.assertTrue(self.result["ok"])

    def test_problem_type(self):
        self.assertEqual(self.result["problem_type"], "excavation_pit")

    def test_file_saved(self):
        self.assertTrue(Path(self.result["path"]).exists())

    def test_script_has_plaxis_import(self):
        self.assertIn("from plxscripting.easy import new_server", self.script)

    def test_script_has_wall_plate(self):
        self.assertIn("g.plate(", self.script)

    def test_script_has_platemat(self):
        self.assertIn("g.platemat()", self.script)

    def test_script_has_mesh(self):
        self.assertIn("g.mesh(", self.script)

    def test_script_has_calculate(self):
        self.assertIn("g.calculate()", self.script)

    def test_script_has_excavation_phase(self):
        self.assertIn("Dao dat", self.script)

    def test_script_has_stability_phase(self):
        self.assertIn("PhiCReduction", self.script)

    def test_script_has_surcharge(self):
        self.assertIn("uniformload", self.script)

    def test_soil_names_in_script(self):
        self.assertIn("Cat pha", self.script)
        self.assertIn("Set", self.script)
        self.assertIn("Cat min", self.script)

    def test_not_auto_run(self):
        self.assertFalse(self.result["executed"])

    def test_note_present(self):
        self.assertIn("note", self.result)


class PlaxisScriptSyntaxTest(unittest.TestCase):
    """Xác minh script sinh ra là Python hợp lệ về mặt cú pháp."""

    def _check_syntax(self, problem_json):
        import ast
        with tempfile.TemporaryDirectory() as tmp:
            _, script = _run(tmp, problem_json)
        try:
            ast.parse(script)
        except SyntaxError as e:
            self.fail(f"Script không hợp lệ về cú pháp Python: {e}\n---\n{script[:500]}")

    def test_foundation_syntax(self):
        self._check_syntax(FOUNDATION_PROBLEM)

    def test_slope_syntax(self):
        self._check_syntax(SLOPE_PROBLEM)

    def test_retaining_syntax(self):
        self._check_syntax(RETAINING_PROBLEM)

    def test_excavation_syntax(self):
        self._check_syntax(EXCAVATION_PROBLEM)


class PlaxisValidationTest(unittest.TestCase):
    """Kiểm tra validation đầu vào."""

    def _app(self, tmp):
        return _make_app(tmp)

    def test_invalid_type_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self._app(tmp)
            with self.assertRaises(ValueError):
                app.prepare("plaxis_generate_script", {
                    "project_name": "Test",
                    "version": "2d",
                    "problem": json.dumps({"type": "unknown_type"}),
                })

    def test_invalid_version_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self._app(tmp)
            with self.assertRaises(ValueError):
                app.prepare("plaxis_generate_script", {
                    "project_name": "Test",
                    "version": "4d",
                    "problem": FOUNDATION_PROBLEM,
                })

    def test_empty_project_name_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self._app(tmp)
            with self.assertRaises(ValueError):
                app.prepare("plaxis_generate_script", {
                    "project_name": "",
                    "version": "2d",
                    "problem": FOUNDATION_PROBLEM,
                })

    def test_slope_angle_out_of_range_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self._app(tmp)
            bad = json.dumps({
                "type": "slope_stability",
                "slope_angle": 95,  # > 89
                "slope_height": 5.0,
                "analysis": "Bishop",
                "soil_layers": [
                    {"name": "Dat", "E": 10000, "nu": 0.3, "gamma": 18, "c": 5, "phi": 25, "thickness": 5},
                ],
            })
            with self.assertRaises(ValueError):
                app.prepare("plaxis_generate_script", {
                    "project_name": "Test",
                    "version": "2d",
                    "problem": bad,
                })

    def test_invalid_excavation_depth_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self._app(tmp)
            with self.assertRaises(ValueError):
                app.prepare("plaxis_generate_script", {
                    "project_name": "Test",
                    "version": "2d",
                    "problem": json.dumps({
                        "type": "excavation_pit",
                        "excavation_depth": -1,
                        "excavation_width": 8.0,
                        "wall_thickness": 0.5,
                        "soil_layers": [
                            {"name": "Cat", "E": 20000, "nu": 0.3, "gamma": 18, "c": 5, "phi": 28, "thickness": 4},
                        ],
                    }),
                })

    def test_missing_soil_layers_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self._app(tmp)
            bad = json.dumps({
                "type": "foundation_settlement",
                "footing_width": 2.0,
                "footing_depth": 1.0,
                "load": 200.0,
                "soil_layers": [],
            })
            with self.assertRaises(ValueError):
                app.prepare("plaxis_generate_script", {
                    "project_name": "Test",
                    "version": "2d",
                    "problem": bad,
                })


class PlaxisAutoRunSkippedTest(unittest.TestCase):
    """auto_run=False (mặc định) không cố kết nối Plaxis."""

    def test_no_connection_attempt_without_auto_run(self):
        import sys
        # Thêm mock plxscripting để đảm bảo import không fail nếu có
        plx_mock = Mock()
        plx_mock.easy.new_server = Mock(side_effect=RuntimeError("Should not be called"))
        sys.modules.setdefault("plxscripting", plx_mock)
        sys.modules.setdefault("plxscripting.easy", plx_mock.easy)

        with tempfile.TemporaryDirectory() as tmp:
            result, _ = _run(tmp, FOUNDATION_PROBLEM)
        self.assertFalse(result["executed"])
        # new_server không nên bị gọi
        plx_mock.easy.new_server.assert_not_called()


# ── Bài toán hố đào v2: thông số giả định chuẩn (2 lớp, MNN, gamma_sat) ─────

EXCAVATION_V2_PROBLEM = json.dumps({
    "type": "excavation_pit",
    "excavation_depth": 6.0,
    "excavation_width": 8.0,
    "wall_thickness": 0.5,
    "embedment_depth": 2.0,
    "surcharge": 75.0,
    "water_table_depth": 3.0,
    "soil_layers": [
        {
            "name": "Cat",
            "E": 50000,
            "nu": 0.30,
            "gamma": 18.0,
            "gamma_sat": 20.0,
            "c": 0,
            "phi": 35,
            "thickness": 4.0,
        },
        {
            "name": "Set",
            "E": 30000,
            "nu": 0.30,
            "gamma": 19.0,
            "gamma_sat": 21.0,
            "c": 15,
            "phi": 28,
            "thickness": 6.0,
        },
    ],
})


class PlaxisExcavationV2Test(unittest.TestCase):
    """Bài toán hố đào v2: 2 lớp Cát + Sét, MNN -3 m, tải 75 kPa."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.result, self.script = _run(self._tmp.name, EXCAVATION_V2_PROBLEM,
                                        project_name="HoDaoV2")

    def tearDown(self):
        self._tmp.cleanup()

    def test_result_ok(self):
        self.assertTrue(self.result["ok"])

    def test_problem_type(self):
        self.assertEqual(self.result["problem_type"], "excavation_pit")

    def test_file_saved(self):
        self.assertTrue(Path(self.result["path"]).exists())

    def test_script_has_plaxis_import(self):
        self.assertIn("from plxscripting.easy import new_server", self.script)

    def test_soil_layer_names(self):
        self.assertIn("'Cat'", self.script)
        self.assertIn("'Set'", self.script)

    def test_gamma_sat_cat_layer(self):
        """gammaSat của lớp Cát phải là 20.0."""
        self.assertIn("20.0", self.script)

    def test_gamma_sat_set_layer(self):
        """gammaSat của lớp Sét phải là 21.0."""
        self.assertIn("21.0", self.script)

    def test_water_level_in_script(self):
        """Script phải khai báo mực nước ngầm tại -3 m."""
        self.assertIn("setwaterlevel", self.script)
        self.assertIn("-3.00", self.script)

    def test_surcharge_75kpa(self):
        """Tải trọng 75 kPa phải xuất hiện trong script."""
        self.assertIn("-75.00", self.script)

    def test_wall_plate_defined(self):
        self.assertIn("g.plate(", self.script)

    def test_platemat_defined(self):
        self.assertIn("g.platemat()", self.script)

    def test_excavation_phase_present(self):
        self.assertIn("Dao dat", self.script)

    def test_phi_c_reduction_phase(self):
        self.assertIn("PhiCReduction", self.script)

    def test_calculate_called(self):
        self.assertIn("g.calculate()", self.script)

    def test_not_auto_run(self):
        self.assertFalse(self.result["executed"])

    def test_python_syntax_valid(self):
        import ast
        try:
            ast.parse(self.script)
        except SyntaxError as e:
            self.fail(f"Script không hợp lệ cú pháp Python: {e}\n---\n{self.script[:500]}")

    def test_e_values_in_script(self):
        """Modulus E của 2 lớp đất phải có trong script."""
        self.assertIn("50000", self.script)
        self.assertIn("30000", self.script)

    def test_phi_values_in_script(self):
        """Góc ma sát phi = 35 và 28 phải có trong script."""
        self.assertIn("35", self.script)
        self.assertIn("28", self.script)

    def test_project_name_in_script(self):
        self.assertIn("HoDaoV2", self.script)


class PlaxisExcavationV2PrintScript(unittest.TestCase):
    """In script ra stdout để dùng làm ví dụ / tài liệu."""

    def test_print_generated_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, script = _run(tmp, EXCAVATION_V2_PROBLEM, project_name="HoDaoV2_Example")
        separator = "=" * 70
        print(f"\n{separator}")
        print("PLAXIS SCRIPT MẪU – Hố đào v2 (2 lớp, MNN -3 m, tải 75 kPa)")
        print(separator)
        print(script)
        print(separator)
        # Đây là test luôn pass – mục đích chỉ để in script ra stdout
        self.assertIsInstance(script, str)
        self.assertGreater(len(script), 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
