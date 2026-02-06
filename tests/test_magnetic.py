"""
Test cases for magnetic components (toroidal and concentric).

These tests use MAS files to test full magnetic creation with
core, bobbin, and turns.
"""

import pytest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from OpenMagneticsVirtualBuilder.builder import Builder
import cadquery as cq


# =============================================================================
# Helper Functions
# =============================================================================

def get_solid_info(shape):
    """Get detailed information about each solid in a shape."""
    solids = shape.val().Solids()
    info = []
    for i, s in enumerate(solids):
        bb = s.BoundingBox()
        info.append({
            'index': i,
            'volume': s.Volume(),
            'x_span': bb.xmax - bb.xmin,
            'y_span': bb.ymax - bb.ymin,
            'z_span': bb.zmax - bb.zmin,
        })
    return info


# =============================================================================
# Base Test Class
# =============================================================================

class TestMagnetic:
    """Base test class with common utilities."""
    
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
    test_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'testData')

    @classmethod
    def setup_class(cls):
        """Create output directory if needed."""
        os.makedirs(cls.output_path, exist_ok=True)

    def _run_test(self, mas_filename: str, validate_geometry: bool = False):
        """Helper to run a magnetic test from a MAS file.
        
        Args:
            mas_filename: Name of the MAS JSON file in testData/
            validate_geometry: If True, load and return geometry info
            
        Returns:
            Tuple of (step_path, stl_path, solid_info) if validate_geometry else (step_path, stl_path)
        """
        with open(os.path.join(self.test_data_path, mas_filename), 'r') as f:
            mas_data = json.load(f)
        
        magnetic_data = mas_data.get('magnetic', mas_data)
        output_name = mas_filename.replace('.json', '')
        
        builder = Builder()
        step_path, stl_path = builder.get_magnetic(
            magnetic_data, output_name,
            output_path=self.output_path, export_files=True
        )
        
        # Verify files were created
        assert step_path is not None, "STEP path should not be None"
        assert stl_path is not None, "STL path should not be None"
        assert os.path.exists(step_path), f"STEP file should exist at {step_path}"
        assert os.path.exists(stl_path), f"STL file should exist at {stl_path}"
        
        if validate_geometry:
            shape = cq.importers.importStep(step_path)
            solid_info = get_solid_info(shape)
            return step_path, stl_path, solid_info
        
        return step_path, stl_path


# =============================================================================
# Toroidal Tests
# =============================================================================

class TestToroidal(TestMagnetic):
    """Tests for toroidal core and turn geometry."""

    def test_toroidal_single_turn_with_core(self):
        """Test creating a toroidal core with a single turn."""
        step_path, stl_path, solid_info = self._run_test(
            'toroidal_one_turn.json', validate_geometry=True
        )
        
        print(f"\n=== Geometry Validation ===")
        print(f"Total solids: {len(solid_info)}")
        
        cores = [s for s in solid_info if s['volume'] >= 1000]
        turns = [s for s in solid_info if s['volume'] < 1000]
        print(f"Cores: {len(cores)}, Turn components: {len(turns)}")
        
        # 1 core + 10 components per turn
        assert len(cores) == 1, f"Expected 1 core, got {len(cores)}"
        assert len(turns) == 10, f"Expected 10 turn components for 1 turn, got {len(turns)}"

    def test_toroidal_two_turns_spread(self):
        """Test creating a toroidal core with two turns spread apart (90° and 270°)."""
        step_path, stl_path, solid_info = self._run_test(
            'toroidal_two_turns_spread.json', validate_geometry=True
        )
        
        print(f"\n=== Geometry Validation ===")
        print(f"Total solids: {len(solid_info)}")
        
        cores = [s for s in solid_info if s['volume'] >= 100]
        turns = [s for s in solid_info if s['volume'] < 100]
        print(f"Cores: {len(cores)}, Turn components: {len(turns)}")

        # 1 core + 20 components for 2 turns
        assert len(cores) == 1, f"Expected 1 core, got {len(cores)}"
        assert len(turns) == 20, f"Expected 20 turn components for 2 turns, got {len(turns)}"

    def test_toroidal_two_turns_centered(self):
        """Test creating a toroidal core with two turns centered near 180°."""
        step_path, stl_path, solid_info = self._run_test(
            'toroidal_two_turns_centered.json', validate_geometry=True
        )
        
        print(f"\n=== Geometry Validation ===")
        print(f"Total solids: {len(solid_info)}")
        
        cores = [s for s in solid_info if s['volume'] >= 100]
        turns = [s for s in solid_info if s['volume'] < 100]
        print(f"Cores: {len(cores)}, Turn components: {len(turns)}")

        # 1 core + 20 components for 2 turns
        assert len(cores) == 1, f"Expected 1 core, got {len(cores)}"
        assert len(turns) == 20, f"Expected 20 turn components for 2 turns, got {len(turns)}"

    def test_toroidal_full_layer(self):
        """Test creating a toroidal core with a full layer of turns."""
        with open(os.path.join(self.test_data_path, 'toroidal_full_layer.json'), 'r') as f:
            mas_data = json.load(f)
        expected_turns = len(mas_data['magnetic']['coil'].get('turnsDescription', []))
        
        step_path, stl_path, solid_info = self._run_test(
            'toroidal_full_layer.json', validate_geometry=True
        )
        
        print(f"\n=== Geometry Validation ===")
        print(f"Total solids: {len(solid_info)}")
        print(f"Expected turns: {expected_turns}")
        
        cores = [s for s in solid_info if s['volume'] >= 100]
        turns = [s for s in solid_info if s['volume'] < 100]
        print(f"Cores: {len(cores)}, Turn components: {len(turns)}")

        # 1 core + expected_turns*10 components
        assert len(cores) == 1, f"Expected 1 core, got {len(cores)}"
        assert len(turns) == expected_turns * 10, \
            f"Expected {expected_turns * 10} turn components, got {len(turns)}"

    def test_toroidal_multilayer(self):
        """Test creating a toroidal core with multilayer turns."""
        test_file = 'test_wind_three_sections_two_layer_toroidal_contiguous_spread_top_additional_coordinates.json'
        with open(os.path.join(self.test_data_path, test_file), 'r') as f:
            mas_data = json.load(f)
        expected_turns = len(mas_data['magnetic']['coil'].get('turnsDescription', []))
        
        step_path, stl_path, solid_info = self._run_test(
            test_file, validate_geometry=True
        )
        
        print(f"\n=== Geometry Validation ===")
        print(f"Total solids: {len(solid_info)}")
        print(f"Expected turns: {expected_turns}")
        
        cores = [s for s in solid_info if s['volume'] >= 100]
        turns = [s for s in solid_info if s['volume'] < 100]
        print(f"Cores: {len(cores)}, Turn components: {len(turns)}")

        # 1 core + expected_turns*10 components
        assert len(cores) == 1, f"Expected 1 core, got {len(cores)}"
        assert len(turns) == expected_turns * 10, \
            f"Expected {expected_turns * 10} turn components, got {len(turns)}"

    def test_toroidal_two_layers_not_compact(self):
        """Test creating a toroidal core with two non-compact layers."""
        test_file = 'toroidal_two_layers_not_compact.json'
        with open(os.path.join(self.test_data_path, test_file), 'r') as f:
            mas_data = json.load(f)
        expected_turns = len(mas_data['magnetic']['coil'].get('turnsDescription', []))
        
        step_path, stl_path, solid_info = self._run_test(
            test_file, validate_geometry=True
        )
        
        print(f"\n=== Geometry Validation ===")
        print(f"Total solids: {len(solid_info)}")
        print(f"Expected turns: {expected_turns}")
        
        cores = [s for s in solid_info if s['volume'] >= 100]
        turns = [s for s in solid_info if s['volume'] < 100]
        print(f"Cores: {len(cores)}, Turn components: {len(turns)}")

        # 1 core + expected_turns*10 components
        assert len(cores) == 1, f"Expected 1 core, got {len(cores)}"
        assert len(turns) == expected_turns * 10, \
            f"Expected {expected_turns * 10} turn components, got {len(turns)}"

    def test_toroidal_full_layer_rectangular_wires(self):
        """Test creating a toroidal core with full layer of rectangular wire turns."""
        self._run_test('toroidal_full_layer_rectangular_wires.json')

    def test_toroidal_one_turn_rectangular_wire(self):
        """Test creating a toroidal core with one rectangular wire turn."""
        self._run_test('toroidal_one_turn_rectangular_wire.json')


# =============================================================================
# Concentric Tests
# =============================================================================

class TestConcentric(TestMagnetic):
    """Tests for concentric (E-core, PQ, RM, etc.) geometry."""

    def test_concentric_rectangular_column_one_turn(self):
        """Test E-core with one concentric turn."""
        self._run_test('concentric_rectangular_column_one_turn.json')

    def test_concentric_rectangular_column_two_turns(self):
        """Test E-core with two concentric turns."""
        self._run_test('concentric_rectangular_column_two_turns.json')

    def test_concentric_rectangular_column_full_layer(self):
        """Test E-core with full layer of concentric turns."""
        self._run_test('concentric_rectangular_column_full_layer.json')

    def test_concentric_rectangular_column_two_layers(self):
        """Test E-core with two layers of concentric turns."""
        self._run_test('concentric_rectangular_column_two_layers.json')

    def test_concentric_rectangular_column_two_layers_with_bobbin(self):
        """Test E-core with two layers of concentric turns and bobbin."""
        self._run_test('concentric_rectangular_column_two_layers_with_bobbin.json')

    def test_concentric_round_column_four_layers(self):
        """Test PQ/RM core with round column and four layers."""
        self._run_test('concentric_round_column_four_layers.json')

    def test_concentric_round_column_one_rectangular_turn(self):
        """Test round column core with one rectangular wire turn."""
        self._run_test('concentric_round_column_one_rectangular_turn.json')

    def test_concentric_round_column_two_layers_rectangular_turns(self):
        """Test round column core with two layers of rectangular wire turns."""
        self._run_test('concentric_round_column_two_layers_rectangular_turns.json')


# =============================================================================
# Full Magnetic Assembly Tests (real MAS files)
# =============================================================================

class TestFullMagnetic(TestMagnetic):
    """Tests for complete magnetic assemblies from real MAS design files."""

    def test_etd49_round_wire_5_turns(self):
        """Test ETD49 core with 6 round wire turns and bobbin."""
        step_path, stl_path, solid_info = self._run_test(
            'ETD49_N87_10uH_5T.json', validate_geometry=True
        )

        print(f"\n=== ETD49 Geometry ===")
        print(f"Total solids: {len(solid_info)}")
        for s in solid_info:
            print(f"  Solid {s['index']}: vol={s['volume']:.1f}")

        # 2 core halves + 1 bobbin + 6 turns = 9
        assert len(solid_info) == 9, f"Expected 9 solids, got {len(solid_info)}"

    def test_pq4040_foil_wire_6_turns(self):
        """Test PQ40/40 core with 6 rectangular foil turns and bobbin."""
        step_path, stl_path, solid_info = self._run_test(
            'PQ4040_10u_6T_foil.json', validate_geometry=True
        )

        print(f"\n=== PQ4040 Geometry ===")
        print(f"Total solids: {len(solid_info)}")
        for s in solid_info:
            print(f"  Solid {s['index']}: vol={s['volume']:.1f}")

        # 2 core halves + 1 bobbin + 6 turns = 9
        assert len(solid_info) == 9, f"Expected 9 solids, got {len(solid_info)}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
