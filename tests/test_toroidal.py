"""Test toroidal core and turn creation."""
import pytest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from OpenMagneticsVirtualBuilder.builder import Builder
import cadquery as cq


def count_solids(shape):
    """Count the number of separate solids in a shape."""
    try:
        solids = shape.val().Solids()
        return len(solids)
    except:
        return 1


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


def validate_turn_continuity(solid_info, expected_count=1):
    """Validate that we have the expected components for turns.
    
    A single toroidal turn is made of 10 components:
    - 2 tubes (inner and outer radii)
    - 4 inner corners (quarter torus at inner radius)
    - 4 outer corners (quarter torus at outer radius)
    
    So for N turns, expect N*10 turn components.
    """
    # Sort by volume - largest is core
    sorted_solids = sorted(solid_info, key=lambda x: x['volume'], reverse=True)
    
    core_count = 0
    turn_component_count = 0
    
    for s in sorted_solids:
        # Core is typically much larger than turns
        if s['volume'] > 1000:  # > 1000 mm³ is likely a core
            core_count += 1
        else:
            turn_component_count += 1
    
    # 10 components per turn
    expected_components = expected_count * 10
    
    return {
        'is_valid': turn_component_count == expected_components,
        'core_count': core_count,
        'turn_count': turn_component_count,
        'expected_components': expected_components
    }


class TestToroidalTurns:
    """Tests for toroidal core and turn geometry."""

    def test_toroidal_single_turn_with_core(self):
        """Test creating a toroidal core with a single turn from JSON file."""
        output_path = os.path.join(os.path.dirname(__file__), '..', 'output')
        os.makedirs(output_path, exist_ok=True)

        # Load test data from JSON file
        test_data_path = os.path.join(os.path.dirname(__file__), 'testData', 'toroidal_one_turn.json')
        with open(test_data_path, 'r') as f:
            mas_data = json.load(f)

        # Build the magnetic using the Builder class
        builder = Builder()
        result = builder.get_magnetic(
            mas_data,
            project_name='toroidal_single_turn_test',
            output_path=output_path,
            export_files=True
        )

        # Result is a tuple of (step_path, stl_path)
        assert result is not None, "Result should not be None"
        step_file, stl_file = result
        
        # Check files were created
        assert os.path.exists(step_file), f"STEP file should exist at {step_file}"
        print(f"\nExported STEP to: {step_file}")
        assert os.path.exists(stl_file), f"STL file should exist at {stl_file}"
        print(f"Exported STL to: {stl_file}")

        # Validate geometry
        shape = cq.importers.importStep(step_file)
        solid_info = get_solid_info(shape)
        
        # Print solid info
        print(f"\n=== Geometry Validation ===")
        print(f"Total solids: {len(solid_info)}")
        
        # Check that we have turns
        turns = [s for s in solid_info if s['volume'] < 1000]  # Turns are smaller than cores
        cores = [s for s in solid_info if s['volume'] >= 1000]
        print(f"Cores: {len(cores)}, Turns: {len(turns)}")
        
        for i, t in enumerate(turns):
            print(f"\nTurn {i+1}:")
            print(f"  Volume: {t['volume']:.2f} mm³")
            print(f"  X span: {t['x_span']*1000:.3f} mm")
            print(f"  Y span: {t['y_span']*1000:.3f} mm")
            print(f"  Z span: {t['z_span']*1000:.3f} mm")

        # Should have exactly 1 core + 10 components for 1 turn
        validation = validate_turn_continuity(solid_info, expected_count=1)
        assert validation['is_valid'], \
            f"Expected 1 core + {validation['expected_components']} turn components, got {validation['core_count']} cores + {validation['turn_count']} components"

    def test_toroidal_two_turns_spread(self):
        """Test creating a toroidal core with two turns spread apart (90° and 270°)."""
        output_path = os.path.join(os.path.dirname(__file__), '..', 'output')
        os.makedirs(output_path, exist_ok=True)

        test_data_path = os.path.join(os.path.dirname(__file__), 'testData', 'toroidal_two_turns_spread.json')
        with open(test_data_path, 'r') as f:
            mas_data = json.load(f)

        builder = Builder()
        result = builder.get_magnetic(
            mas_data,
            project_name='toroidal_two_turns_spread_test',
            output_path=output_path,
            export_files=True
        )

        assert result is not None, "Result should not be None"
        step_file, stl_file = result
        
        assert os.path.exists(step_file), f"STEP file should exist at {step_file}"
        assert os.path.exists(stl_file), f"STL file should exist at {stl_file}"
        print(f"\nExported STEP to: {step_file}")

        # Validate geometry
        shape = cq.importers.importStep(step_file)
        solid_info = get_solid_info(shape)
        
        print(f"\n=== Geometry Validation ===")
        print(f"Total solids: {len(solid_info)}")
        
        cores = [s for s in solid_info if s['volume'] >= 100]
        turns = [s for s in solid_info if s['volume'] < 100]
        print(f"Cores: {len(cores)}, Turn components: {len(turns)}")

        # Should have 1 core + 20 components for 2 turns
        assert len(cores) == 1, f"Expected 1 core, got {len(cores)}"
        assert len(turns) == 20, f"Expected 20 turn components for 2 turns, got {len(turns)}"

    def test_toroidal_two_turns_centered(self):
        """Test creating a toroidal core with two turns centered near 180°."""
        output_path = os.path.join(os.path.dirname(__file__), '..', 'output')
        os.makedirs(output_path, exist_ok=True)

        test_data_path = os.path.join(os.path.dirname(__file__), 'testData', 'toroidal_two_turns_centered.json')
        with open(test_data_path, 'r') as f:
            mas_data = json.load(f)

        builder = Builder()
        result = builder.get_magnetic(
            mas_data,
            project_name='toroidal_two_turns_centered_test',
            output_path=output_path,
            export_files=True
        )

        assert result is not None, "Result should not be None"
        step_file, stl_file = result
        
        assert os.path.exists(step_file), f"STEP file should exist at {step_file}"
        assert os.path.exists(stl_file), f"STL file should exist at {stl_file}"
        print(f"\nExported STEP to: {step_file}")

        # Validate geometry
        shape = cq.importers.importStep(step_file)
        solid_info = get_solid_info(shape)
        
        print(f"\n=== Geometry Validation ===")
        print(f"Total solids: {len(solid_info)}")
        
        cores = [s for s in solid_info if s['volume'] >= 100]
        turns = [s for s in solid_info if s['volume'] < 100]
        print(f"Cores: {len(cores)}, Turn components: {len(turns)}")

        # Should have 1 core + 20 components for 2 turns
        assert len(cores) == 1, f"Expected 1 core, got {len(cores)}"
        assert len(turns) == 20, f"Expected 20 turn components for 2 turns, got {len(turns)}"

    def test_toroidal_full_layer(self):
        """Test creating a toroidal core with a full layer of 35 turns."""
        output_path = os.path.join(os.path.dirname(__file__), '..', 'output')
        os.makedirs(output_path, exist_ok=True)

        test_data_path = os.path.join(os.path.dirname(__file__), 'testData', 'toroidal_full_layer.json')
        with open(test_data_path, 'r') as f:
            mas_data = json.load(f)

        # Get expected turn count from data
        expected_turns = len(mas_data['magnetic']['coil'].get('turnsDescription', []))
        print(f"\nBuilding {expected_turns} turns...")

        builder = Builder()
        result = builder.get_magnetic(
            mas_data,
            project_name='toroidal_full_layer_test',
            output_path=output_path,
            export_files=True
        )

        assert result is not None, "Result should not be None"
        step_file, stl_file = result
        
        assert os.path.exists(step_file), f"STEP file should exist at {step_file}"
        assert os.path.exists(stl_file), f"STL file should exist at {stl_file}"
        print(f"Exported STEP to: {step_file}")
        print(f"STEP file size: {os.path.getsize(step_file)} bytes")

        # Validate geometry
        shape = cq.importers.importStep(step_file)
        solid_info = get_solid_info(shape)
        
        print(f"\n=== Geometry Validation ===")
        print(f"Total solids: {len(solid_info)}")
        
        cores = [s for s in solid_info if s['volume'] >= 100]  # Lower threshold for smaller core
        turns = [s for s in solid_info if s['volume'] < 100]
        print(f"Cores: {len(cores)}, Turn components: {len(turns)}")
        print(f"Expected turn components: {expected_turns} x 10 = {expected_turns * 10}")

        # Should have 1 core + expected_turns*10 components
        assert len(cores) == 1, f"Expected 1 core, got {len(cores)}"
        assert len(turns) == expected_turns * 10, \
            f"Expected {expected_turns * 10} turn components, got {len(turns)}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
