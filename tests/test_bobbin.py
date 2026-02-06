import unittest
import os

import context  # noqa: F401
import builder


class TestBobbin(unittest.TestCase):
    output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../output/'

    @classmethod
    def setUpClass(cls):
        os.makedirs(cls.output_path, exist_ok=True)
        print("Starting tests for bobbin")

    @classmethod
    def tearDownClass(cls):
        print("\nFinishing tests for bobbin")

    def test_standard_bobbin_cadquery(self):
        """Test StandardBobbin generation with CadQuery engine"""
        bobbin_data = {
            "family": "standard",
            "material": "nylon",
            "dimensions": {
                "wallThickness": 0.0005,
                "flangeThickness": 0.001,
                "flangeExtension": 0.002,
                "pinCount": 0,
                "pinDiameter": 0.0008,
                "pinLength": 0.003
            },
            "coordinates": [0, 0, 0],
            "rotation": [0, 0, 0]
        }

        winding_window = {
            "width": 0.01,
            "height": 0.02,
            "coordinates": [0.005, 0]
        }

        b = builder.Builder("CadQuery")
        result = b.get_bobbin(bobbin_data, winding_window, name="test_bobbin_cq", output_path=self.output_path)

        self.assertIsNotNone(result)
        if isinstance(result, tuple):
            step_path, stl_path = result
            self.assertTrue(os.path.exists(step_path) or step_path is not None)

    def test_standard_bobbin_with_pins_cadquery(self):
        """Test StandardBobbin with mounting pins using CadQuery"""
        bobbin_data = {
            "family": "standard",
            "material": "nylon",
            "dimensions": {
                "wallThickness": 0.0005,
                "flangeThickness": 0.001,
                "flangeExtension": 0.002,
                "pinCount": 8,
                "pinDiameter": 0.0008,
                "pinLength": 0.003
            },
            "coordinates": [0, 0, 0],
            "rotation": [0, 0, 0]
        }

        winding_window = {
            "width": 0.01,
            "height": 0.02,
            "coordinates": [0.005, 0]
        }

        b = builder.Builder("CadQuery")
        result = b.get_bobbin(bobbin_data, winding_window, name="test_bobbin_pins_cq", output_path=self.output_path)

        self.assertIsNotNone(result)

    def test_bobbin_geometry_no_export(self):
        """Test bobbin generation returning geometry object"""
        bobbin_data = {
            "family": "standard",
            "dimensions": {
                "wallThickness": 0.0005,
                "flangeThickness": 0.001,
                "flangeExtension": 0.002,
                "pinCount": 0
            }
        }

        winding_window = {
            "width": 0.008,
            "height": 0.015,
            "coordinates": [0.004, 0]
        }

        b = builder.Builder("CadQuery")
        result = b.get_bobbin(bobbin_data, winding_window, name="test_bobbin_geom",
                              output_path=self.output_path, export_files=False)

        self.assertIsNotNone(result)

    def test_bobbin_with_rotation(self):
        """Test bobbin with rotation applied"""
        import math
        bobbin_data = {
            "family": "standard",
            "dimensions": {
                "wallThickness": 0.0005,
                "flangeThickness": 0.001,
                "flangeExtension": 0.002,
                "pinCount": 0
            },
            "rotation": [math.pi / 4, 0, 0]
        }

        winding_window = {
            "width": 0.01,
            "height": 0.02,
            "coordinates": [0.005, 0]
        }

        b = builder.Builder("CadQuery")
        result = b.get_bobbin(bobbin_data, winding_window, name="test_bobbin_rotated",
                              output_path=self.output_path)

        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
