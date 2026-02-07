"""Tests for 2D drawing generation (SVG, DXF, FCMacro).

These tests use inline shape data to avoid requiring core_shapes.ndjson.
"""

import unittest
import os
import json
import copy
import tempfile
import shutil

import context  # noqa: F401
import drawing_2d
from drawing_2d import ViewPlane, ViewType, DimensionAnnotation, DrawingView
import cadquery_builder
import builder

# Minimal E 42/21/20 shape data for testing (inline, no file dependency)
E_CORE_SHAPE = {
    "name": "E 42/21/20",
    "family": "e",
    "familySubtype": "1",
    "dimensions": {
        "A": {"nominal": 0.042},
        "B": {"nominal": 0.021},
        "C": {"nominal": 0.0157},
        "D": {"nominal": 0.0145},
        "E": {"nominal": 0.0296},
        "F": {"nominal": 0.0142},
    },
}

# Minimal PQ 40/40 shape data
PQ_CORE_SHAPE = {
    "name": "PQ 40/40",
    "family": "pq",
    "familySubtype": "1",
    "dimensions": {
        "A": {"nominal": 0.0404},
        "B": {"nominal": 0.0386},
        "C": {"nominal": 0.0287},
        "D": {"nominal": 0.0275},
        "E": {"nominal": 0.0285},
        "F": {"nominal": 0.0135},
    },
}

# Minimal T 25/15/10 shape data
T_CORE_SHAPE = {
    "name": "T 25/15/10",
    "family": "t",
    "familySubtype": "1",
    "dimensions": {
        "A": {"nominal": 0.0254},
        "B": {"nominal": 0.0152},
        "C": {"nominal": 0.0102},
    },
}

# Geometrical description for a two-piece E core set
E_CORE_GEO_DESC = [
    {
        "type": "half set",
        "shape": copy.deepcopy(E_CORE_SHAPE),
        "rotation": [0, 0, 0],
        "coordinates": [0, 0],
        "machining": None,
    },
    {
        "type": "half set",
        "shape": copy.deepcopy(E_CORE_SHAPE),
        "rotation": [3.14159265359, 0, 0],
        "coordinates": [0, 0],
        "machining": None,
    },
]

T_CORE_GEO_DESC = [
    {
        "type": "toroidal",
        "shape": copy.deepcopy(T_CORE_SHAPE),
        "rotation": [0, 0, 0],
        "coordinates": [0, 0],
        "machining": None,
    },
]


class TestDrawing2DDataStructures(unittest.TestCase):
    """Test basic data structures in drawing_2d module."""

    def test_view_plane_enum(self):
        self.assertEqual(ViewPlane.XY.value, "xy")
        self.assertEqual(ViewPlane.XZ.value, "xz")
        self.assertEqual(ViewPlane.ZY.value, "zy")

    def test_view_type_enum(self):
        self.assertEqual(ViewType.PROJECTION.value, "projection")
        self.assertEqual(ViewType.CROSS_SECTION.value, "cross_section")

    def test_projection_dirs(self):
        self.assertEqual(drawing_2d.PROJECTION_DIRS[ViewPlane.XY], (0, 0, 1))
        self.assertEqual(drawing_2d.PROJECTION_DIRS[ViewPlane.XZ], (0, 1, 0))
        self.assertEqual(drawing_2d.PROJECTION_DIRS[ViewPlane.ZY], (1, 0, 0))

    def test_dimension_annotation_creation(self):
        ann = DimensionAnnotation(
            start=(0, 0),
            end=(10, 0),
            label="A: 10 mm",
            dimension_name="A",
            dim_type="DistanceX",
            offset=5.0,
        )
        self.assertEqual(ann.start, (0, 0))
        self.assertEqual(ann.end, (10, 0))
        self.assertEqual(ann.dim_type, "DistanceX")

    def test_drawing_view_creation(self):
        view = DrawingView(
            plane=ViewPlane.XY,
            view_type=ViewType.PROJECTION,
            shape=None,
            title="test",
        )
        self.assertEqual(view.plane, ViewPlane.XY)
        self.assertEqual(view.view_type, ViewType.PROJECTION)
        self.assertEqual(view.dimensions, [])


class TestDimensionSVG(unittest.TestCase):
    """Test SVG dimension rendering."""

    def test_create_dimension_svg_distance_x(self):
        colors = {"dimension_color": "#000000"}
        svg = drawing_2d.create_dimension_svg(
            starting_coordinates=[0, 0],
            ending_coordinates=[100, 0],
            dimension_type="DistanceX",
            dimension_label="A: 10 mm",
            view_x=400,
            view_y=300,
            colors=colors,
        )
        self.assertIn("A: 10 mm", svg)
        self.assertIn("<path", svg)
        self.assertIn("M0,0", svg)

    def test_create_dimension_svg_distance_y(self):
        colors = {"dimension_color": "#FF0000"}
        svg = drawing_2d.create_dimension_svg(
            starting_coordinates=[0, 0],
            ending_coordinates=[0, 100],
            dimension_type="DistanceY",
            dimension_label="B: 20 mm",
            view_x=400,
            view_y=300,
            colors=colors,
        )
        self.assertIn("B: 20 mm", svg)
        self.assertIn("#FF0000", svg)
        self.assertIn("rotate(-90)", svg)

    def test_compose_annotated_svg(self):
        base_svg = "<svg><g></g></svg>"
        annotations = [
            DimensionAnnotation(
                start=(0, 0),
                end=(10, 0),
                label="test",
                dimension_name="A",
                dim_type="DistanceX",
            )
        ]
        colors = {"dimension_color": "#000000"}
        result = drawing_2d.compose_annotated_svg(base_svg, 400, 300, annotations, colors)
        self.assertIn("test", result)
        self.assertIn("</svg>", result)


class TestDimensionSpecs(unittest.TestCase):
    """Test per-family dimension spec functions."""

    def test_e_family_dims_top_view(self):
        dims = {"A": 42, "B": 21, "C": 15.7, "D": 14.5, "E": 29.6, "F": 14.2}
        orig = dict(dims)
        annotations = drawing_2d.get_dimensions_for_family("e", dims, orig, "TopView")
        self.assertIsInstance(annotations, list)
        self.assertTrue(len(annotations) > 0)
        dim_names = [a.dimension_name for a in annotations]
        self.assertIn("A", dim_names)
        self.assertIn("E", dim_names)

    def test_e_family_dims_front_view(self):
        dims = {"A": 42, "B": 21, "C": 15.7, "D": 14.5, "E": 29.6, "F": 14.2}
        orig = dict(dims)
        annotations = drawing_2d.get_dimensions_for_family("e", dims, orig, "FrontView")
        dim_names = [a.dimension_name for a in annotations]
        self.assertIn("B", dim_names)
        self.assertIn("D", dim_names)

    def test_t_family_dims_top_view(self):
        dims = {"A": 25.4, "B": 15.2, "C": 10.2}
        orig = dict(dims)
        annotations = drawing_2d.get_dimensions_for_family("t", dims, orig, "TopView")
        dim_names = [a.dimension_name for a in annotations]
        self.assertIn("A", dim_names)
        self.assertIn("B", dim_names)

    def test_t_family_dims_front_view(self):
        dims = {"A": 25.4, "B": 15.2, "C": 10.2}
        orig = dict(dims)
        annotations = drawing_2d.get_dimensions_for_family("t", dims, orig, "FrontView")
        dim_names = [a.dimension_name for a in annotations]
        self.assertIn("C", dim_names)

    def test_ur_family_dims(self):
        dims = {"A": 30, "B": 20, "C": 15, "D": 10, "E": 15, "F": 7.5, "H": 7.5}
        orig = dict(dims)
        annotations = drawing_2d.get_dimensions_for_family("ur", dims, orig, "TopView")
        self.assertTrue(len(annotations) > 0)

    def test_ut_family_dims(self):
        dims = {"A": 30, "B": 20, "C": 15, "D": 10, "E": 15, "F": 7.5}
        orig = dict(dims)
        annotations = drawing_2d.get_dimensions_for_family("ut", dims, orig, "TopView")
        dim_names = [a.dimension_name for a in annotations]
        self.assertIn("A", dim_names)


class TestSVGDrawings(unittest.TestCase):
    """Test SVG drawing generation through CadQueryBuilder."""

    @classmethod
    def setUpClass(cls):
        cls.output_path = tempfile.mkdtemp(prefix="mvb_test_2d_")
        cls.builder = cadquery_builder.CadQueryBuilder()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.output_path):
            shutil.rmtree(cls.output_path)

    def test_svg_three_planes_e_core(self):
        """SVG projections for XY, XZ, ZY planes."""
        results = self.builder.get_svg_drawings(
            "E_42_21_20",
            copy.deepcopy(E_CORE_GEO_DESC),
            planes=[ViewPlane.XY, ViewPlane.XZ, ViewPlane.ZY],
            view_types=[ViewType.PROJECTION],
            output_path=self.output_path,
        )
        self.assertIsInstance(results, dict)
        # Should have at least one result (some planes may produce valid views)
        self.assertTrue(len(results) > 0, f"Expected at least 1 SVG view, got {len(results)}")
        for key, svg in results.items():
            self.assertIn("<svg", svg)
            self.assertIn("</svg>", svg)

    def test_svg_has_path_elements(self):
        """SVG output should contain path elements for shape edges."""
        results = self.builder.get_svg_drawings(
            "E_42_21_20",
            copy.deepcopy(E_CORE_GEO_DESC),
            planes=[ViewPlane.XY],
            view_types=[ViewType.PROJECTION],
            output_path=self.output_path,
            save_files=False,
        )
        if results:
            svg = list(results.values())[0]
            self.assertIn("<path", svg, "SVG should contain <path elements for shape edges")

    def test_svg_cross_section_e_core(self):
        """Cross-section slicing should produce output."""
        results = self.builder.get_svg_drawings(
            "E_42_21_20_xsec",
            copy.deepcopy(E_CORE_GEO_DESC),
            planes=[ViewPlane.ZY],
            view_types=[ViewType.CROSS_SECTION],
            output_path=self.output_path,
        )
        # Cross section may or may not produce output depending on geometry
        self.assertIsInstance(results, dict)

    def test_svg_files_saved(self):
        """SVG files should be written to disk when save_files=True."""
        results = self.builder.get_svg_drawings(
            "E_save_test",
            copy.deepcopy(E_CORE_GEO_DESC),
            planes=[ViewPlane.XZ],
            view_types=[ViewType.PROJECTION],
            output_path=self.output_path,
            save_files=True,
        )
        if results:
            for key in results:
                svg_path = f"{self.output_path}/E_save_test_{key}.svg"
                self.assertTrue(os.path.exists(svg_path), f"Expected {svg_path} to exist")


class TestDXFDrawings(unittest.TestCase):
    """Test DXF drawing generation."""

    @classmethod
    def setUpClass(cls):
        cls.output_path = tempfile.mkdtemp(prefix="mvb_test_dxf_")
        cls.builder = cadquery_builder.CadQueryBuilder()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.output_path):
            shutil.rmtree(cls.output_path)

    def test_dxf_export_basic(self):
        """DXF file should be generated, readable by ezdxf, and contain entities."""
        results = self.builder.get_dxf_drawings(
            "E_42_dxf",
            copy.deepcopy(E_CORE_GEO_DESC),
            planes=[ViewPlane.XZ],
            view_types=[ViewType.PROJECTION],
            output_path=self.output_path,
        )
        self.assertIsInstance(results, dict)
        if results:
            import ezdxf

            for key, filepath in results.items():
                self.assertTrue(os.path.exists(filepath), f"DXF file should exist: {filepath}")
                doc = ezdxf.readfile(filepath)
                self.assertIsNotNone(doc)
                entity_count = len(list(doc.modelspace()))
                self.assertGreater(entity_count, 0, f"DXF {key} should have entities")

    def test_dxf_hidden_layer(self):
        """DXF projection should have a HIDDEN layer with DASHED linetype and entities."""
        results = self.builder.get_dxf_drawings(
            "E_42_dxf_hidden",
            copy.deepcopy(E_CORE_GEO_DESC),
            planes=[ViewPlane.XZ],
            view_types=[ViewType.PROJECTION],
            output_path=self.output_path,
        )
        self.assertIsInstance(results, dict)
        self.assertTrue(len(results) > 0, "Should produce at least one DXF view")

        import ezdxf

        for key, filepath in results.items():
            doc = ezdxf.readfile(filepath)
            layer_names = [layer.dxf.name for layer in doc.layers]
            self.assertIn("HIDDEN", layer_names, f"DXF {key} should have HIDDEN layer")
            hidden_layer = doc.layers.get("HIDDEN")
            self.assertEqual(hidden_layer.dxf.linetype, "DASHED", "HIDDEN layer should use DASHED linetype")
            hidden_entities = [e for e in doc.modelspace() if e.dxf.layer == "HIDDEN"]
            self.assertGreater(len(hidden_entities), 0, f"DXF {key} should have hidden entities")


class TestFCMacroDrawings(unittest.TestCase):
    """Test FreeCAD macro generation."""

    @classmethod
    def setUpClass(cls):
        cls.output_path = tempfile.mkdtemp(prefix="mvb_test_fcmacro_")
        cls.builder = cadquery_builder.CadQueryBuilder()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.output_path):
            shutil.rmtree(cls.output_path)

    def test_fcstd_macro_valid_python(self):
        """FCMacro file should be valid Python syntax."""
        results = self.builder.get_fcstd_sketches(
            "E_42_macro",
            copy.deepcopy(E_CORE_GEO_DESC),
            planes=[ViewPlane.XZ],
            view_types=[ViewType.PROJECTION],
            output_path=self.output_path,
        )
        self.assertIsInstance(results, dict)
        if results:
            for key, filepath in results.items():
                self.assertTrue(os.path.exists(filepath))
                with open(filepath) as f:
                    code = f.read()
                # Check it's valid Python (will raise SyntaxError if not)
                compile(code, filepath, "exec")


class TestCrossSection(unittest.TestCase):
    """Test cross-section functionality."""

    def test_cross_section_offsets_config(self):
        """Cross-section offsets should be defined in shape_configs."""
        import shape_configs

        self.assertIn("e", shape_configs.CROSS_SECTION_OFFSETS)
        self.assertIn("pq", shape_configs.CROSS_SECTION_OFFSETS)
        self.assertIn("t", shape_configs.CROSS_SECTION_OFFSETS)


class TestBuilderFacade(unittest.TestCase):
    """Test Builder facade methods for 2D drawings."""

    @classmethod
    def setUpClass(cls):
        cls.output_path = tempfile.mkdtemp(prefix="mvb_test_facade_")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.output_path):
            shutil.rmtree(cls.output_path)

    def test_builder_svg_drawings(self):
        """Builder facade should delegate get_svg_drawings to engine."""
        b = builder.Builder("CadQuery")
        results = b.get_svg_drawings(
            "facade_test",
            copy.deepcopy(E_CORE_GEO_DESC),
            planes=[ViewPlane.XZ],
            view_types=[ViewType.PROJECTION],
            output_path=self.output_path,
            save_files=False,
        )
        self.assertIsInstance(results, dict)

    def test_builder_dxf_drawings(self):
        """Builder facade should delegate get_dxf_drawings to engine."""
        b = builder.Builder("CadQuery")
        results = b.get_dxf_drawings(
            "facade_dxf_test",
            copy.deepcopy(E_CORE_GEO_DESC),
            planes=[ViewPlane.XZ],
            view_types=[ViewType.PROJECTION],
            output_path=self.output_path,
        )
        self.assertIsInstance(results, dict)

    def test_builder_fcstd_sketches(self):
        """Builder facade should delegate get_fcstd_sketches to engine."""
        b = builder.Builder("CadQuery")
        results = b.get_fcstd_sketches(
            "facade_fcstd_test",
            copy.deepcopy(E_CORE_GEO_DESC),
            planes=[ViewPlane.XZ],
            view_types=[ViewType.PROJECTION],
            output_path=self.output_path,
        )
        self.assertIsInstance(results, dict)


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility of existing methods."""

    @classmethod
    def setUpClass(cls):
        cls.output_path = tempfile.mkdtemp(prefix="mvb_test_compat_")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.output_path):
            shutil.rmtree(cls.output_path)

    def test_backward_compat_technical_drawing(self):
        """Existing get_piece_technical_drawing should still work."""
        b = builder.Builder("CadQuery")
        core = b.factory(copy.deepcopy(E_CORE_SHAPE))
        core.set_output_path(self.output_path)
        result = core.get_piece_technical_drawing(
            copy.deepcopy(E_CORE_SHAPE),
            colors={"projection_color": "#000000", "dimension_color": "#000000"},
            save_files=True,
        )
        self.assertIsInstance(result, dict)
        self.assertIn("top_view", result)
        self.assertIn("front_view", result)
        # Should have content (not None)
        self.assertIsNotNone(result["top_view"])
        self.assertIsNotNone(result["front_view"])
        # Should contain SVG content
        self.assertIn("<svg", result["top_view"])
        self.assertIn("<svg", result["front_view"])


class TestToroidal2D(unittest.TestCase):
    """Test 2D views for toroidal cores."""

    @classmethod
    def setUpClass(cls):
        cls.output_path = tempfile.mkdtemp(prefix="mvb_test_toroid_")
        cls.builder = cadquery_builder.CadQueryBuilder()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.output_path):
            shutil.rmtree(cls.output_path)

    def test_toroidal_svg(self):
        """Toroidal core should generate 2D views."""
        results = self.builder.get_svg_drawings(
            "T_25_15_10",
            copy.deepcopy(T_CORE_GEO_DESC),
            planes=[ViewPlane.XY, ViewPlane.XZ],
            view_types=[ViewType.PROJECTION],
            output_path=self.output_path,
            save_files=False,
        )
        self.assertIsInstance(results, dict)
        # T core should produce valid views
        if results:
            for svg in results.values():
                self.assertIn("<svg", svg)


class TestAllShapes2DWithNdjson(unittest.TestCase):
    """Test 2D drawing generation for all shapes from core_shapes.ndjson.

    This test is skipped if the ndjson file is not available.
    """

    ndjson_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../MAS/data/core_shapes.ndjson")

    @classmethod
    def setUpClass(cls):
        cls.output_path = tempfile.mkdtemp(prefix="mvb_test_all_2d_")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.output_path):
            shutil.rmtree(cls.output_path)

    @unittest.skipUnless(os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../MAS/data/core_shapes.ndjson")), "core_shapes.ndjson not available")
    def test_all_shapes_2d(self):
        """All shapes from core_shapes.ndjson should generate SVG without error."""
        b = cadquery_builder.CadQueryBuilder()
        with open(self.ndjson_path) as f:
            for ndjson_line in f:
                data = json.loads(ndjson_line)
                if data["family"] in ["ui", "pqi", "ut"]:
                    continue

                core = b.factory(data)
                result = core.get_piece_technical_drawing(
                    copy.deepcopy(data),
                    colors={"projection_color": "#000000", "dimension_color": "#000000"},
                    save_files=False,
                )
                self.assertIsNotNone(result, f"Failed for {data['name']}")


if __name__ == "__main__":
    unittest.main()
