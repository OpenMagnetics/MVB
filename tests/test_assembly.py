import unittest
import os
import json
import copy

import context  # noqa: F401
import builder
import PyMKF


class TestMagneticAssembly(unittest.TestCase):
    output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../output/'
    mas_data_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson'

    @classmethod
    def setUpClass(cls):
        os.makedirs(cls.output_path, exist_ok=True)
        cls.mas_available = os.path.exists(cls.mas_data_path)
        print("Starting tests for magnetic assembly")
        if not cls.mas_available:
            print("Note: MAS data not available, some tests will be skipped")

    @classmethod
    def tearDownClass(cls):
        print("\nFinishing tests for magnetic assembly")

    def get_etd49_core_data(self):
        """Helper to get ETD49 core data from MAS"""
        if not self.mas_available:
            return None
        try:
            with open(self.mas_data_path, 'r') as f:
                for ndjson_line in f:
                    data = json.loads(ndjson_line)
                    if data["name"] == "ETD 49/25/16":
                        return data
        except FileNotFoundError:
            return None  # MAS data file not available

    def get_pq_core_data(self):
        """Helper to get PQ core data from MAS"""
        if not self.mas_available:
            return None
        try:
            with open(self.mas_data_path, 'r') as f:
                for ndjson_line in f:
                    data = json.loads(ndjson_line)
                    if data["name"] == "PQ 40/40":
                        return data
        except FileNotFoundError:
            return None  # MAS data file not available

    def get_simple_e_core_data(self):
        """Helper to create a simple E core data without MAS dependency"""
        return {
            "name": "E 42/21/15",
            "family": "e",
            "familySubtype": "1",
            "type": "standard",
            "dimensions": {
                "A": 0.042,
                "B": 0.021,
                "C": 0.015,
                "D": 0.0135,
                "E": 0.030,
                "F": 0.014
            }
        }

    def test_core_only_assembly(self):
        """Test assembly with only core component"""
        core_shape = self.get_etd49_core_data()
        if core_shape is None:
            self.skipTest("ETD 49 core data not found")

        dummyCore = {
            "functionalDescription": {
                "name": "test_core",
                "type": "two-piece set",
                "material": "N97",
                "shape": core_shape,
                "gapping": [],
                "numberStacks": 1
            }
        }

        core_datum = PyMKF.calculate_core_data(dummyCore, False)

        assembly_data = {
            "name": "core_only_assembly",
            "core": core_datum
        }

        b = builder.Builder("CadQuery")
        result = b.get_magnetic_assembly("test_core_only", assembly_data, output_path=self.output_path)

        self.assertIsNotNone(result)
        if isinstance(result, tuple):
            step_path, stl_path = result
            if step_path:
                self.assertTrue(os.path.exists(step_path))

    def test_core_with_bobbin_assembly(self):
        """Test assembly with core and bobbin"""
        core_shape = self.get_etd49_core_data()
        if core_shape is None:
            self.skipTest("ETD 49 core data not found")

        dummyCore = {
            "functionalDescription": {
                "name": "test_core_bobbin",
                "type": "two-piece set",
                "material": "N97",
                "shape": core_shape,
                "gapping": [],
                "numberStacks": 1
            }
        }

        core_datum = PyMKF.calculate_core_data(dummyCore, False)

        bobbin_data = {
            "family": "standard",
            "material": "nylon",
            "dimensions": {
                "wallThickness": 0.0005,
                "flangeThickness": 0.001,
                "flangeExtension": 0.002,
                "pinCount": 0
            },
            "coordinates": [0, 0, 0],
            "rotation": [0, 0, 0]
        }

        assembly_data = {
            "name": "core_bobbin_assembly",
            "core": core_datum,
            "bobbin": bobbin_data
        }

        b = builder.Builder("CadQuery")
        result = b.get_magnetic_assembly("test_core_bobbin", assembly_data, output_path=self.output_path)

        self.assertIsNotNone(result)

    def test_full_assembly_with_windings(self):
        """Test complete assembly with core, bobbin, and windings"""
        core_shape = self.get_pq_core_data()
        if core_shape is None:
            self.skipTest("PQ 40/40 core data not found")

        dummyCore = {
            "functionalDescription": {
                "name": "test_full",
                "type": "two-piece set",
                "material": "N97",
                "shape": core_shape,
                "gapping": [],
                "numberStacks": 1
            }
        }

        core_datum = PyMKF.calculate_core_data(dummyCore, False)

        bobbin_data = {
            "family": "standard",
            "material": "nylon",
            "dimensions": {
                "wallThickness": 0.0005,
                "flangeThickness": 0.001,
                "flangeExtension": 0.002,
                "pinCount": 0
            }
        }

        primary_winding = {
            "name": "primary",
            "type": "round_wire",
            "wireDiameter": 0.0005,
            "insulationThickness": 0.00005,
            "numberOfTurns": 10,
            "numberOfLayers": 2,
            "windingDirection": "cw",
            "windingWindowIndex": 0,
            "material": "copper"
        }

        secondary_winding = {
            "name": "secondary",
            "type": "round_wire",
            "wireDiameter": 0.0003,
            "insulationThickness": 0.00003,
            "numberOfTurns": 5,
            "numberOfLayers": 1,
            "windingDirection": "cw",
            "windingWindowIndex": 0,
            "material": "copper"
        }

        assembly_data = {
            "name": "full_transformer",
            "core": core_datum,
            "bobbin": bobbin_data,
            "windings": [primary_winding, secondary_winding]
        }

        b = builder.Builder("CadQuery")
        result = b.get_magnetic_assembly("test_full_transformer", assembly_data, output_path=self.output_path)

        self.assertIsNotNone(result)
        if isinstance(result, tuple):
            step_path, stl_path = result
            if step_path:
                self.assertTrue(os.path.exists(step_path))
                print(f"Full assembly exported to: {step_path}")

    def test_assembly_no_export(self):
        """Test assembly returning geometry object"""
        core_shape = self.get_etd49_core_data()
        if core_shape is None:
            self.skipTest("ETD 49 core data not found")

        dummyCore = {
            "functionalDescription": {
                "name": "test_no_export",
                "type": "two-piece set",
                "material": "N97",
                "shape": core_shape,
                "gapping": [],
                "numberStacks": 1
            }
        }

        core_datum = PyMKF.calculate_core_data(dummyCore, False)

        assembly_data = {
            "name": "no_export_assembly",
            "core": core_datum
        }

        b = builder.Builder("CadQuery")
        result = b.get_magnetic_assembly("test_no_export", assembly_data,
                                          output_path=self.output_path, export_files=False)

        # Result should be geometry object or compound, not tuple of paths
        self.assertIsNotNone(result)

    def test_assembly_with_gapped_core(self):
        """Test assembly with gapped core"""
        core_shape = self.get_etd49_core_data()
        if core_shape is None:
            self.skipTest("ETD 49 core data not found")

        dummyGapping = [
            {'length': 0.001, 'type': 'subtractive'},
            {'length': 0.0005, 'type': 'subtractive'},
            {'length': 0.0005, 'type': 'subtractive'}
        ]

        dummyCore = {
            "functionalDescription": {
                "name": "test_gapped",
                "type": "two-piece set",
                "material": "N97",
                "shape": core_shape,
                "gapping": dummyGapping,
                "numberStacks": 1
            }
        }

        core_datum = PyMKF.calculate_core_data(dummyCore, False)

        gapping = []
        for column_index, column in enumerate(core_datum['processedDescription']['columns']):
            if column_index < len(dummyGapping):
                aux = copy.deepcopy(dummyGapping[column_index])
                aux['coordinates'] = column['coordinates']
                gapping.append(aux)

        dummyCore['functionalDescription']['gapping'] = gapping
        core_datum = PyMKF.calculate_core_data(dummyCore, False)

        bobbin_data = {
            "family": "standard",
            "dimensions": {
                "wallThickness": 0.0005,
                "flangeThickness": 0.001,
                "flangeExtension": 0.002,
                "pinCount": 0
            }
        }

        assembly_data = {
            "name": "gapped_assembly",
            "core": core_datum,
            "bobbin": bobbin_data
        }

        b = builder.Builder("CadQuery")
        result = b.get_magnetic_assembly("test_gapped_assembly", assembly_data, output_path=self.output_path)

        self.assertIsNotNone(result)

    def test_standalone_assembly_no_mas(self):
        """Test assembly without MAS dependency using pre-computed core data"""
        # Pre-computed E core geometrical description (simplified)
        core_data = {
            "geometricalDescription": [
                {
                    "type": "half set",
                    "shape": {
                        "name": "E 42/21/15",
                        "family": "e",
                        "familySubtype": "1",
                        "dimensions": {
                            "A": 0.042,
                            "B": 0.021,
                            "C": 0.015,
                            "D": 0.0135,
                            "E": 0.030,
                            "F": 0.014
                        }
                    },
                    "coordinates": [0, 0, 0],
                    "rotation": [3.14159, 0, 0],
                    "material": "N97"
                },
                {
                    "type": "half set",
                    "shape": {
                        "name": "E 42/21/15",
                        "family": "e",
                        "familySubtype": "1",
                        "dimensions": {
                            "A": 0.042,
                            "B": 0.021,
                            "C": 0.015,
                            "D": 0.0135,
                            "E": 0.030,
                            "F": 0.014
                        }
                    },
                    "coordinates": [0, 0, 0],
                    "rotation": [0, 0, 0],
                    "material": "N97"
                }
            ],
            "processedDescription": {
                "windingWindows": [
                    {
                        "width": 0.008,
                        "height": 0.0135,
                        "coordinates": [0.011, 0]
                    }
                ],
                "columns": [
                    {
                        "coordinates": [0, 0, 0],
                        "type": "central"
                    }
                ]
            }
        }

        bobbin_data = {
            "family": "standard",
            "dimensions": {
                "wallThickness": 0.0005,
                "flangeThickness": 0.001,
                "flangeExtension": 0.002,
                "pinCount": 0
            }
        }

        primary_winding = {
            "name": "primary",
            "type": "round_wire",
            "wireDiameter": 0.0004,
            "insulationThickness": 0.00004,
            "numberOfTurns": 8,
            "numberOfLayers": 2,
            "windingDirection": "cw",
            "windingWindowIndex": 0
        }

        assembly_data = {
            "name": "standalone_assembly",
            "core": core_data,
            "bobbin": bobbin_data,
            "windings": [primary_winding]
        }

        b = builder.Builder("CadQuery")
        result = b.get_magnetic_assembly("test_standalone", assembly_data, output_path=self.output_path)

        self.assertIsNotNone(result)
        if isinstance(result, tuple):
            step_path, stl_path = result
            if step_path:
                self.assertTrue(os.path.exists(step_path))
                print(f"Standalone assembly exported to: {step_path}")

    def test_bobbin_only_assembly(self):
        """Test assembly with only bobbin component"""
        # Minimal assembly data with just bobbin and winding window info
        assembly_data = {
            "name": "bobbin_only",
            "core": {
                "processedDescription": {
                    "windingWindows": [
                        {
                            "width": 0.01,
                            "height": 0.02,
                            "coordinates": [0.005, 0]
                        }
                    ]
                }
            },
            "bobbin": {
                "family": "standard",
                "dimensions": {
                    "wallThickness": 0.0005,
                    "flangeThickness": 0.001,
                    "flangeExtension": 0.002,
                    "pinCount": 4,
                    "pinDiameter": 0.0008,
                    "pinLength": 0.003
                }
            }
        }

        b = builder.Builder("CadQuery")
        result = b.get_magnetic_assembly("test_bobbin_only", assembly_data, output_path=self.output_path)

        self.assertIsNotNone(result)


    def test_etd49_full_assembly_from_file(self):
        """Test complete ETD49 assembly from real data file with MAS turnsDescription"""
        data_file = f'{os.path.dirname(os.path.abspath(__file__))}/_data/ETD49_N87_10u_10A_1mm_5T.json'

        if not os.path.exists(data_file):
            self.skipTest("ETD49 test data file not found")

        with open(data_file, 'r') as f:
            magnetic_data = json.load(f)

        # Extract core data
        core_data = magnetic_data["magnetic"]["core"]

        # Extract complete coil data (includes turnsDescription for MAS mode)
        coil_data = magnetic_data["magnetic"]["coil"]

        # Verify turnsDescription is present
        turns_desc = coil_data.get("turnsDescription", [])
        self.assertGreater(len(turns_desc), 0, "Test data should have turnsDescription")

        # Extract bobbin data from coil
        bobbin_processed = coil_data["bobbin"]["processedDescription"]
        bobbin_data = {
            "family": "standard",
            "dimensions": {
                "wallThickness": bobbin_processed.get("wallThickness", 0.0005),
                "flangeThickness": 0.001,
                "flangeExtension": 0.002,
                "pinCount": 0
            }
        }

        # Extract winding data from coil functional description
        windings = []
        for i, winding_func in enumerate(coil_data["functionalDescription"]):
            wire = winding_func.get("wire", {})
            winding_data = {
                "name": winding_func.get("name", f"Winding_{i}"),
                "type": "round_wire",
                "wireDiameter": wire.get("conductingDiameter", {}).get("nominal", 0.0005),
                "insulationThickness": (wire.get("outerDiameter", {}).get("nominal", 0.0006) -
                                        wire.get("conductingDiameter", {}).get("nominal", 0.0005)) / 2,
                "numberOfTurns": winding_func.get("numberTurns", 1),
                "numberOfLayers": 1,
                "windingDirection": "cw",
                "windingWindowIndex": 0,
                "material": wire.get("material", "copper")
            }
            windings.append(winding_data)

        assembly_data = {
            "name": "ETD49_transformer",
            "core": core_data,
            "coil": coil_data,  # Pass complete coil with turnsDescription
            "bobbin": bobbin_data,
            "windings": windings
        }

        b = builder.Builder("CadQuery")
        result = b.get_magnetic_assembly("ETD49_N87_assembly", assembly_data, output_path=self.output_path)

        self.assertIsNotNone(result)
        if isinstance(result, tuple):
            step_path, stl_path = result
            if step_path:
                self.assertTrue(os.path.exists(step_path))
                print(f"ETD49 assembly (MAS mode) exported to: {step_path}")

    def test_etd49_core_only_from_file(self):
        """Test ETD49 core generation from real data file"""
        data_file = f'{os.path.dirname(os.path.abspath(__file__))}/_data/ETD49_N87_10u_10A_1mm_5T.json'

        if not os.path.exists(data_file):
            self.skipTest("ETD49 test data file not found")

        with open(data_file, 'r') as f:
            magnetic_data = json.load(f)

        core_data = magnetic_data["magnetic"]["core"]

        assembly_data = {
            "name": "ETD49_core_only",
            "core": core_data
        }

        b = builder.Builder("CadQuery")
        result = b.get_magnetic_assembly("ETD49_core_only", assembly_data, output_path=self.output_path)

        self.assertIsNotNone(result)
        if isinstance(result, tuple):
            step_path, stl_path = result
            if step_path:
                self.assertTrue(os.path.exists(step_path))
                print(f"ETD49 core exported to: {step_path}")


if __name__ == '__main__':
    unittest.main()
