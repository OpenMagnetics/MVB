"""
End-to-end pipeline tests: MAS → 3D (STEP/STL) → 2D (SVG/DXF/FCMacro).

Tests run against real MAS design files:
- ETD49_N87_10uH_5T.json          (E-family, round wire, concentric)
- PQ4040_10u_6T_foil.json         (PQ-family, foil wire, concentric)
- toroidal_two_turns_spread.json   (T-family, litz wire, toroidal, 2 turns)
- T402416_edge40_4uH_8T.json      (T-family, round wire, toroidal, 8 turns)
- C20_30u_8T_5mm.json             (C-family, round wire, half-set)

Each test generates:
- 3D: STEP + STL assembly
- 2D SVG: 3 planes × 2 view types (projection + cross-section) × 2 components (assembly + core)
- 2D DXF: same matrix
- 2D FCMacro: same matrix
"""

import pytest
import os
import json

import context  # noqa: F401
import builder as builder_mod
from drawing_2d import ViewPlane, ViewType

TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testData")

ALL_PLANES = [ViewPlane.XY, ViewPlane.XZ, ViewPlane.ZY]
ALL_VIEW_TYPES = [ViewType.PROJECTION, ViewType.CROSS_SECTION]
COMPONENTS = ["assembly", "core"]


@pytest.mark.slow
class TestFullPipeline:
    """Full MAS → 3D → 2D pipeline for real magnetic designs."""

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")

    @classmethod
    def setup_class(cls):
        os.makedirs(cls.output_path, exist_ok=True)

    def _load_mas(self, filename):
        filepath = os.path.join(TEST_DATA_DIR, filename)
        if not os.path.exists(filepath):
            pytest.skip(f"{filename} not found")
        with open(filepath) as f:
            return json.load(f)

    def _run_pipeline(self, filename, label):
        """Run the complete pipeline for one MAS file.

        Returns dict with all output paths/data keyed by stage.
        """
        mas_data = self._load_mas(filename)
        magnetic_data = mas_data.get("magnetic", mas_data)
        b = builder_mod.Builder("CadQuery")
        results = {"label": label}

        # --- Stage 1: 3D geometry ---
        step_path, stl_path = b.get_magnetic(magnetic_data, label, output_path=self.output_path, export_files=True)
        assert step_path is not None, f"{label}: STEP export failed"
        assert stl_path is not None, f"{label}: STL export failed"
        assert os.path.exists(step_path), f"{label}: STEP file missing"
        assert os.path.exists(stl_path), f"{label}: STL file missing"
        results["step"] = step_path
        results["stl"] = stl_path
        print(f"\n  3D: {os.path.basename(step_path)}, {os.path.basename(stl_path)}")

        # Get geometrical description for core-only 2D drawings
        core_data = magnetic_data.get("core", {})
        geo_desc = core_data.get("geometricalDescription", [])
        assert len(geo_desc) > 0, f"{label}: no geometrical description in core"

        # --- Stage 2: 2D SVG (assembly + core) ---
        svg_results = b.get_assembly_svg_drawings(
            f"{label}_2d",
            magnetic_data,
            planes=ALL_PLANES,
            view_types=ALL_VIEW_TYPES,
            colors={"projection_color": "#333333", "dimension_color": "#0066cc"},
            output_path=self.output_path,
            save_files=True,
            components=COMPONENTS,
        )
        results["svg"] = svg_results
        svg_count = len(svg_results)
        print(f"  SVG: {svg_count} views generated")
        for key in sorted(svg_results.keys()):
            svg_file = f"{self.output_path}/{label}_2d_{key}.svg"
            size = os.path.getsize(svg_file) if os.path.exists(svg_file) else 0
            print(f"    {key}: {size:,} bytes")

        # Also generate core-only SVGs with full dimension annotations
        core_svg_results = b.get_svg_drawings(
            f"{label}_core_dims",
            geo_desc,
            planes=ALL_PLANES,
            view_types=[ViewType.PROJECTION],
            colors={"projection_color": "#333333", "dimension_color": "#cc0000"},
            output_path=self.output_path,
            save_files=True,
        )
        results["core_svg"] = core_svg_results
        print(f"  Core SVG: {len(core_svg_results)} views")

        # --- Stage 3: 2D DXF (assembly + core) ---
        dxf_results = b.get_assembly_dxf_drawings(
            f"{label}_2d",
            magnetic_data,
            planes=ALL_PLANES,
            view_types=ALL_VIEW_TYPES,
            output_path=self.output_path,
            components=COMPONENTS,
        )
        results["dxf"] = dxf_results
        print(f"  DXF: {len(dxf_results)} views generated")
        for key, path in sorted(dxf_results.items()):
            size = os.path.getsize(path) if os.path.exists(path) else 0
            print(f"    {key}: {size:,} bytes")

        # --- Stage 4: 2D FCMacro (assembly + core) ---
        macro_results = b.get_assembly_fcstd_sketches(
            f"{label}_2d",
            magnetic_data,
            planes=ALL_PLANES,
            view_types=ALL_VIEW_TYPES,
            output_path=self.output_path,
            components=COMPONENTS,
        )
        results["fcmacro"] = macro_results
        print(f"  FCMacro: {len(macro_results)} views generated")
        for key, path in sorted(macro_results.items()):
            size = os.path.getsize(path) if os.path.exists(path) else 0
            print(f"    {key}: {size:,} bytes")

        return results

    # =====================================================================
    # ETD49 (E-family, round wire)
    # =====================================================================

    def test_etd49_full_pipeline(self):
        """ETD49 N87 10µH 5T: MAS → 3D → SVG/DXF/FCMacro, all planes, projection + cross-section."""
        r = self._run_pipeline("ETD49_N87_10uH_5T.json", "ETD49")

        # 3D assertions
        assert os.path.getsize(r["step"]) > 1000, "STEP file too small"
        assert os.path.getsize(r["stl"]) > 1000, "STL file too small"

        # SVG: 2 components × 3 planes × 2 view types = 12 views
        assert len(r["svg"]) == 12, f"Expected 12 SVG views, got {len(r['svg'])}: {sorted(r['svg'].keys())}"
        for key, svg in r["svg"].items():
            assert "<svg" in svg, f"SVG {key} missing <svg> tag"
            assert len(svg) > 100, f"SVG {key} too small ({len(svg)} chars)"

        # Core SVG should have path elements
        for key, svg in r["core_svg"].items():
            assert "<path" in svg, f"Core SVG {key} should have <path elements"

        # DXF: verify files exist and are readable
        if r["dxf"]:
            import ezdxf

            for key, path in r["dxf"].items():
                assert os.path.exists(path), f"DXF {key} file missing"
                doc = ezdxf.readfile(path)
                assert doc is not None

        # FCMacro: verify valid Python
        if r["fcmacro"]:
            for key, path in r["fcmacro"].items():
                assert os.path.exists(path), f"FCMacro {key} file missing"
                with open(path) as f:
                    code = f.read()
                compile(code, path, "exec")

    # =====================================================================
    # PQ4040 (PQ-family, foil wire)
    # =====================================================================

    def test_pq4040_full_pipeline(self):
        """PQ40/40 10µH 6T foil: MAS → 3D → SVG/DXF/FCMacro, all planes, projection + cross-section."""
        r = self._run_pipeline("PQ4040_10u_6T_foil.json", "PQ4040")

        # 3D assertions
        assert os.path.getsize(r["step"]) > 1000, "STEP file too small"
        assert os.path.getsize(r["stl"]) > 1000, "STL file too small"

        # SVG: 2 components × 3 planes × 2 view types = 12 views
        assert len(r["svg"]) == 12, f"Expected 12 SVG views, got {len(r['svg'])}: {sorted(r['svg'].keys())}"
        for key, svg in r["svg"].items():
            assert "<svg" in svg, f"SVG {key} missing <svg> tag"

        # Core SVG with path elements
        for key, svg in r["core_svg"].items():
            assert "<path" in svg, f"Core SVG {key} should have <path elements"

        # DXF
        if r["dxf"]:
            import ezdxf

            for key, path in r["dxf"].items():
                assert os.path.exists(path)
                doc = ezdxf.readfile(path)
                assert doc is not None

        # FCMacro
        if r["fcmacro"]:
            for key, path in r["fcmacro"].items():
                assert os.path.exists(path)
                with open(path) as f:
                    code = f.read()
                compile(code, path, "exec")

    # =====================================================================
    # Toroidal T25 (T-family, litz wire, 2 turns)
    # =====================================================================

    def test_toroidal_full_pipeline(self):
        """T25 toroidal 2 litz turns: MAS → 3D → SVG/DXF/FCMacro, all planes, projection + cross-section."""
        r = self._run_pipeline("toroidal_two_turns_spread.json", "T25_toroidal")

        # 3D assertions
        assert os.path.getsize(r["step"]) > 1000, "STEP file too small"
        assert os.path.getsize(r["stl"]) > 1000, "STL file too small"

        # SVG: 2 components × 3 planes × 2 view types = 12 views
        assert len(r["svg"]) == 12, f"Expected 12 SVG views, got {len(r['svg'])}: {sorted(r['svg'].keys())}"
        for key, svg in r["svg"].items():
            assert "<svg" in svg, f"SVG {key} missing <svg> tag"

        # Core SVG with path elements
        for key, svg in r["core_svg"].items():
            assert "<path" in svg, f"Core SVG {key} should have <path> elements"

        # DXF
        if r["dxf"]:
            import ezdxf

            for key, path in r["dxf"].items():
                assert os.path.exists(path), f"DXF {key} file missing"
                doc = ezdxf.readfile(path)
                assert doc is not None

        # FCMacro
        if r["fcmacro"]:
            for key, path in r["fcmacro"].items():
                assert os.path.exists(path), f"FCMacro {key} file missing"
                with open(path) as f:
                    code = f.read()
                compile(code, path, "exec")

    # =====================================================================
    # T402416 (T-family, round wire, 8 turns)
    # =====================================================================

    def test_t402416_full_pipeline(self):
        """T402416 4µH 8T round wire: MAS → 3D → SVG/DXF/FCMacro, all planes, projection + cross-section."""
        r = self._run_pipeline("T402416_edge40_4uH_8T.json", "T402416")

        # 3D assertions
        assert os.path.getsize(r["step"]) > 1000, "STEP file too small"
        assert os.path.getsize(r["stl"]) > 1000, "STL file too small"

        # SVG: 2 components × 3 planes × 2 view types = 12 views
        assert len(r["svg"]) == 12, f"Expected 12 SVG views, got {len(r['svg'])}: {sorted(r['svg'].keys())}"
        for key, svg in r["svg"].items():
            assert "<svg" in svg, f"SVG {key} missing <svg> tag"

        # Core SVG with path elements
        for key, svg in r["core_svg"].items():
            assert "<path" in svg, f"Core SVG {key} should have <path> elements"

        # DXF
        if r["dxf"]:
            import ezdxf

            for key, path in r["dxf"].items():
                assert os.path.exists(path), f"DXF {key} file missing"
                doc = ezdxf.readfile(path)
                assert doc is not None

        # FCMacro
        if r["fcmacro"]:
            for key, path in r["fcmacro"].items():
                assert os.path.exists(path), f"FCMacro {key} file missing"
                with open(path) as f:
                    code = f.read()
                compile(code, path, "exec")

    # =====================================================================
    # C20 (C-family, round wire, 8 turns)
    # =====================================================================

    def test_c20_full_pipeline(self):
        """C20 30µH 8T round wire: MAS → 3D → SVG/DXF/FCMacro, all planes, projection + cross-section."""
        r = self._run_pipeline("C20_30u_8T_5mm.json", "C20")

        # 3D assertions
        assert os.path.getsize(r["step"]) > 1000, "STEP file too small"
        assert os.path.getsize(r["stl"]) > 1000, "STL file too small"

        # SVG: 2 components × 3 planes × 2 view types = 12 views
        assert len(r["svg"]) == 12, f"Expected 12 SVG views, got {len(r['svg'])}: {sorted(r['svg'].keys())}"
        for key, svg in r["svg"].items():
            assert "<svg" in svg, f"SVG {key} missing <svg> tag"

        # Core SVG with path elements
        for key, svg in r["core_svg"].items():
            assert "<path" in svg, f"Core SVG {key} should have <path> elements"

        # DXF
        if r["dxf"]:
            import ezdxf

            for key, path in r["dxf"].items():
                assert os.path.exists(path), f"DXF {key} file missing"
                doc = ezdxf.readfile(path)
                assert doc is not None

        # FCMacro
        if r["fcmacro"]:
            for key, path in r["fcmacro"].items():
                assert os.path.exists(path), f"FCMacro {key} file missing"
                with open(path) as f:
                    code = f.read()
                compile(code, path, "exec")

    # =====================================================================
    # Summary test: file count validation
    # =====================================================================

    def test_etd49_output_file_count(self):
        """Verify ETD49 produces the expected number of output files."""
        r = self._run_pipeline("ETD49_N87_10uH_5T.json", "ETD49_count")

        total_files = 2  # STEP + STL
        total_files += len(r["svg"])
        total_files += len(r["core_svg"])
        total_files += len(r["dxf"])
        total_files += len(r["fcmacro"])

        print(f"\n  Total output files: {total_files}")
        print("    3D: 2 (STEP + STL)")
        print(f"    SVG (assembly+core): {len(r['svg'])}")
        print(f"    SVG (core w/ dims):  {len(r['core_svg'])}")
        print(f"    DXF: {len(r['dxf'])}")
        print(f"    FCMacro: {len(r['fcmacro'])}")

        # At minimum: 2 (3D) + 3 projections = 5
        assert total_files >= 5, f"Expected at least 5 output files, got {total_files}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
