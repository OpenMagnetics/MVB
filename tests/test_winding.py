import unittest
import os
import json

import context  # noqa: F401
import builder


class TestWinding(unittest.TestCase):
    output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../output/'

    @classmethod
    def setUpClass(cls):
        os.makedirs(cls.output_path, exist_ok=True)
        print("Starting tests for winding")

    @classmethod
    def tearDownClass(cls):
        print("\nFinishing tests for winding")

    def test_round_wire_winding_cadquery(self):
        """Test RoundWireWinding generation with CadQuery engine"""
        winding_data = {
            "name": "primary",
            "type": "round_wire",
            "wireDiameter": 0.0005,
            "insulationThickness": 0.00005,
            "numberOfTurns": 10,
            "numberOfLayers": 2,
            "windingDirection": "cw",
            "windingWindowIndex": 0,
            "material": "copper",
            "coordinates": [0, 0, 0],
            "rotation": [0, 0, 0]
        }

        bobbin_dims = {
            "width": 0.008,
            "height": 0.015
        }

        b = builder.Builder("CadQuery")
        result = b.get_winding(winding_data, bobbin_dims, name="test_winding_cq", output_path=self.output_path)

        self.assertIsNotNone(result)

    def test_winding_ccw_direction(self):
        """Test winding with counter-clockwise direction"""
        winding_data = {
            "name": "secondary",
            "type": "round_wire",
            "wireDiameter": 0.0003,
            "insulationThickness": 0.00003,
            "numberOfTurns": 20,
            "numberOfLayers": 4,
            "windingDirection": "ccw",
            "coordinates": [0, 0, 0],
            "rotation": [0, 0, 0]
        }

        bobbin_dims = {
            "width": 0.006,
            "height": 0.012
        }

        b = builder.Builder("CadQuery")
        result = b.get_winding(winding_data, bobbin_dims, name="test_winding_ccw",
                               output_path=self.output_path)

        self.assertIsNotNone(result)

    def test_bulk_winding_high_turn_count(self):
        """Test bulk winding representation for high turn counts"""
        winding_data = {
            "name": "high_turn_winding",
            "type": "round_wire",
            "wireDiameter": 0.0001,
            "insulationThickness": 0.00001,
            "numberOfTurns": 200,
            "numberOfLayers": 4,
            "windingDirection": "cw",
            "coordinates": [0, 0, 0],
            "rotation": [0, 0, 0]
        }

        bobbin_dims = {
            "width": 0.01,
            "height": 0.02
        }

        b = builder.Builder("CadQuery")
        result = b.get_winding(winding_data, bobbin_dims, name="test_winding_bulk",
                               output_path=self.output_path)

        self.assertIsNotNone(result)

    def test_winding_no_export(self):
        """Test winding generation returning geometry object"""
        winding_data = {
            "name": "test_winding",
            "type": "round_wire",
            "wireDiameter": 0.0005,
            "insulationThickness": 0.00005,
            "numberOfTurns": 5,
            "numberOfLayers": 1,
            "windingDirection": "cw"
        }

        bobbin_dims = {
            "width": 0.008,
            "height": 0.015
        }

        b = builder.Builder("CadQuery")
        result = b.get_winding(winding_data, bobbin_dims, name="test_winding_geom",
                               output_path=self.output_path, export_files=False)

        self.assertIsNotNone(result)

    def test_single_layer_winding(self):
        """Test single layer winding"""
        winding_data = {
            "name": "single_layer",
            "type": "round_wire",
            "wireDiameter": 0.001,
            "insulationThickness": 0.0001,
            "numberOfTurns": 8,
            "numberOfLayers": 1,
            "windingDirection": "cw"
        }

        bobbin_dims = {
            "width": 0.01,
            "height": 0.015
        }

        b = builder.Builder("CadQuery")
        result = b.get_winding(winding_data, bobbin_dims, name="test_winding_single_layer",
                               output_path=self.output_path)

        self.assertIsNotNone(result)

    def test_winding_from_mas_turnsDescription(self):
        """Test winding generation using MAS turnsDescription coordinates"""
        # Load test data with turnsDescription
        data_file = f'{os.path.dirname(os.path.abspath(__file__))}/_data/ETD49_N87_10u_10A_1mm_5T.json'

        if not os.path.exists(data_file):
            self.skipTest("ETD49 test data file not found")

        with open(data_file, 'r') as f:
            magnetic_data = json.load(f)

        coil_data = magnetic_data["magnetic"]["coil"]
        turns_description = coil_data.get("turnsDescription", [])

        self.assertGreater(len(turns_description), 0, "Test data should have turnsDescription")

        # Get wire info from functional description
        winding_func = coil_data["functionalDescription"][0]
        wire = winding_func.get("wire", {})

        winding_data = {
            "name": "Primary",
            "windingName": "Primary",
            "type": "round_wire",
            "wireDiameter": wire.get("conductingDiameter", {}).get("nominal", 0.0005),
            "numberOfTurns": winding_func.get("numberTurns", 1),
            "turnsDescription": turns_description,
        }

        bobbin_dims = {
            "width": 0.008,
            "height": 0.033
        }

        b = builder.Builder("CadQuery")
        result = b.get_winding(winding_data, bobbin_dims, name="test_winding_mas",
                               output_path=self.output_path)

        self.assertIsNotNone(result)
        if isinstance(result, tuple):
            step_path, stl_path = result
            if step_path:
                self.assertTrue(os.path.exists(step_path))
                print(f"MAS winding exported to: {step_path}")

    def test_winding_fallback_without_turnsDescription(self):
        """Test that winding falls back to calculation when no turnsDescription"""
        winding_data = {
            "name": "fallback_test",
            "windingName": "NonExistent",
            "type": "round_wire",
            "wireDiameter": 0.0005,
            "insulationThickness": 0.00005,
            "numberOfTurns": 6,
            "numberOfLayers": 1,
            "windingDirection": "cw",
            "turnsDescription": [],  # Empty turnsDescription
        }

        bobbin_dims = {
            "width": 0.008,
            "height": 0.015
        }

        b = builder.Builder("CadQuery")
        result = b.get_winding(winding_data, bobbin_dims, name="test_winding_fallback",
                               output_path=self.output_path)

        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
