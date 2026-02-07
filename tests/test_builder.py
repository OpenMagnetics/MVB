import unittest
import os
import json
import glob

import context  # noqa: F401
import builder
import copy
import PyMKF


class Tests(unittest.TestCase):
    output_path = f"{os.path.dirname(os.path.abspath(__file__))}/../output/"

    @classmethod
    def setUpClass(cls):

        files = glob.glob(f"{cls.output_path}/*")
        for f in files:
            os.remove(f)
        print("Starting tests for builder")

    @classmethod
    def tearDownClass(cls):
        print("\nFinishing tests for builder")

    def test_all_shapes_generated(self):

        with open(f"{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson", "r") as f:
            for ndjson_line in f:
                data = json.loads(ndjson_line)
                if data["family"] not in ["ui", "pqi", "ut"]:
                    # if data['name'] != "RM 4":
                    # if data['family'] != "c":
                    # if data['family'] != "ur":
                    # continue

                    print(data["name"])
                    core = builder.Builder().factory(data)
                    core.get_piece(data, save_files=True, export_files=True)
                    filename = f"{data['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    # self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.step"))
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj") or os.path.exists(f"{self.output_path}/{filename}.stl"))

    def test_all_technical_drawings_generated(self):
        colors = {"projection_color": "#d4d4d4", "dimension_color": "#d4d4d4"}
        with open(f"{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson", "r") as f:
            for ndjson_line in f:
                data = json.loads(ndjson_line)
                if data["family"] not in ["ui", "pqi"]:
                    if data["family"] != "pq":
                        continue
                    if data["name"] in ["PQ 32/15", "PQ 32/25", "PQ 32/35", "PQ 35/20", "PQ 35/30"]:
                        continue
                    core = builder.Builder("CadQuery").factory(data)
                    print(data["name"])
                    core.get_piece_technical_drawing(data, colors=colors, save_files=True)
                    filename = f"{data['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_scaled_TopView.svg"))
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_scaled_FrontView.svg"))

    def test_get_families(self):

        families = builder.Builder("CadQuery").get_families()
        with open(f"{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson", "r") as f:
            for ndjson_line in f:
                data = json.loads(ndjson_line)
                if data["family"] not in ["ui", "pqi"]:
                    self.assertTrue(data["family"] in list(families.keys()))

    def test_all_subtractive_gapped_cores_generated(self):
        dummyGapping = [{"length": 0.001, "type": "subtractive"}, {"length": 0.002, "type": "subtractive"}, {"length": 0, "type": "subtractive"}]

        dummyCore = {"functionalDescription": {"name": "dummy", "type": "two-piece set", "material": "N97", "shape": None, "gapping": dummyGapping, "numberStacks": 3}}
        with open(f"{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson", "r") as f:
            for ndjson_line in f:
                data = json.loads(ndjson_line)
                if data["family"] not in ["ui", "ut", "pqi"]:
                    # if data['family'] != "c":
                    # if data['name'] != "T 22/14/13":
                    # continue

                    core = copy.deepcopy(dummyCore)
                    core["functionalDescription"]["shape"] = data

                    gapping = []
                    core_datum = PyMKF.calculate_core_data(core, False)
                    for column_index, column in enumerate(core_datum["processedDescription"]["columns"]):
                        aux = copy.deepcopy(dummyGapping[column_index])
                        aux["coordinates"] = column["coordinates"]
                        gapping.append(aux)

                    core["functionalDescription"]["gapping"] = gapping
                    core_datum = PyMKF.calculate_core_data(core, False)
                    result = builder.Builder("CadQuery").get_core(data["name"], core_datum["geometricalDescription"])
                    print(result)
                    filename = f"{data['name']}_core".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.step"))
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj") or os.path.exists(f"{self.output_path}/{filename}.stl"))

    def test_all_subtractive_distributed_gapped_cores_generated(self):
        dummyGapping = [
            {"length": 0.001, "type": "subtractive"},
            {"length": 0.0005, "type": "subtractive"},
            {"length": 0.002, "type": "subtractive"},
            {"length": 0.00005, "type": "residual"},
            {"length": 0.00005, "type": "residual"},
        ]

        dummyCore = {"functionalDescription": {"name": "dummy", "type": "two-piece set", "material": "N97", "shape": None, "gapping": dummyGapping, "numberStacks": 1}}
        with open(f"{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson", "r") as f:
            for ndjson_line in f:
                data = json.loads(ndjson_line)
                if data["family"] not in ["ui", "ut", "pqi"]:
                    core = copy.deepcopy(dummyCore)
                    core["functionalDescription"]["shape"] = data

                    core_datum = PyMKF.calculate_core_data(core, False)
                    result = builder.Builder("CadQuery").get_core(data["name"], core_datum["geometricalDescription"])
                    print(result)
                    filename = f"{data['name']}_core".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.step"))
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj") or os.path.exists(f"{self.output_path}/{filename}.stl"))

    def test_all_additive_gapped_cores_generated(self):
        dummyGapping = [{"length": 0.0001, "type": "additive"}, {"length": 0.0001, "type": "additive"}, {"length": 0.0001, "type": "additive"}]

        dummyCore = {"functionalDescription": {"name": "dummy", "type": "two-piece set", "material": "N97", "shape": None, "gapping": dummyGapping, "numberStacks": 1}}
        with open(f"{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson", "r") as f:
            for ndjson_line in f:
                data = json.loads(ndjson_line)
                if data["family"] not in ["ui", "ut", "pqi"]:
                    core = copy.deepcopy(dummyCore)
                    core["functionalDescription"]["shape"] = data

                    gapping = []
                    core_datum = PyMKF.calculate_core_data(core, False)
                    core_datum["processedDescription"] = PyMKF.calculate_core_processed_description(core)
                    for column_index, column in enumerate(core_datum["processedDescription"]["columns"]):
                        aux = copy.deepcopy(dummyGapping[column_index])
                        aux["coordinates"] = column["coordinates"]
                        gapping.append(aux)
                    core["functionalDescription"]["gapping"] = gapping

                    core_datum = PyMKF.calculate_core_data(core, False)
                    # import pprint
                    # pprint.pprint(core_datum['processedDescription'])
                    # pprint.pprint(core_datum['geometricalDescription'])
                    result = builder.Builder("CadQuery").get_core(data["name"], core_datum["geometricalDescription"])
                    print(result)
                    filename = f"{data['name']}_core".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.step"))
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj") or os.path.exists(f"{self.output_path}/{filename}.stl"))

    def test_all_additive_technical_drawing_cores_generated(self):
        dummyGapping = [{"length": 0.001, "type": "additive"}, {"length": 0.001, "type": "additive"}, {"length": 0.001, "type": "additive"}]

        dummyCore = {"functionalDescription": {"name": "dummy", "type": "two-piece set", "material": "N97", "shape": None, "gapping": dummyGapping, "numberStacks": 1}}
        with open(f"{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson", "r") as f:
            for ndjson_line in f:
                data = json.loads(ndjson_line)
                if data["family"] not in ["ui", "ut", "pqi", "t"]:
                    core = copy.deepcopy(dummyCore)
                    core["functionalDescription"]["shape"] = data

                    gapping = []
                    core_datum = PyMKF.calculate_core_data(core, False)
                    for column_index, column in enumerate(core_datum["processedDescription"]["columns"]):
                        aux = copy.deepcopy(dummyGapping[column_index])
                        aux["coordinates"] = column["coordinates"]
                        gapping.append(aux)
                    core["functionalDescription"]["gapping"] = gapping

                    print(data["name"])
                    core_datum = PyMKF.calculate_core_data(core, False)
                    builder.Builder("CadQuery").get_core_gapping_technical_drawing(data["name"], core_datum)

                    filename = f"{data['name']}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    print(f"{self.output_path}/{filename}_core_gaps_FrontView.svg")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_core_gaps_FrontView.svg"))

    def test_all_subtractive_technical_drawing_cores_generated(self):
        dummyGapping = [{"length": 0.001, "type": "subtractive"}, {"length": 0.002, "type": "subtractive"}, {"length": 0.000005, "type": "subtractive"}]

        dummyCore = {"functionalDescription": {"name": "dummy", "type": "two-piece set", "material": "N97", "shape": None, "gapping": dummyGapping, "numberStacks": 1}}
        with open(f"{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson", "r") as f:
            for ndjson_line in f:
                data = json.loads(ndjson_line)
                if data["family"] not in ["ui", "ut", "pqi"]:
                    core = copy.deepcopy(dummyCore)
                    core["functionalDescription"]["shape"] = data

                    gapping = []
                    core_datum = PyMKF.calculate_core_data(core, False)
                    for column_index, column in enumerate(core_datum["processedDescription"]["columns"]):
                        aux = copy.deepcopy(dummyGapping[column_index])
                        aux["coordinates"] = column["coordinates"]
                        gapping.append(aux)
                    core["functionalDescription"]["gapping"] = gapping

                    core_datum = PyMKF.calculate_core_data(core, False)
                    builder.Builder("CadQuery").get_core_gapping_technical_drawing(data["name"], core_datum)

                    filename = f"{data['name']}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    print(f"{self.output_path}/{filename}_core_gaps_FrontView.svg")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_core_gaps_FrontView.svg"))

    def test_all_subtractive_distributed_technical_drawing_cores_generated(self):
        dummyGapping = [
            {"length": 0.001, "type": "subtractive"},
            {"length": 0.0005, "type": "subtractive"},
            {"length": 0.002, "type": "subtractive"},
            {"length": 0.00005, "type": "residual"},
            {"length": 0.00005, "type": "residual"},
        ]

        dummyCore = {"functionalDescription": {"name": "dummy", "type": "two-piece set", "material": "N97", "shape": None, "gapping": dummyGapping, "numberStacks": 1}}
        with open(f"{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson", "r") as f:
            for ndjson_line in f:
                data = json.loads(ndjson_line)
                if data["family"] not in ["ui", "ut", "pqi"]:
                    # if data["family"] in ['p']:
                    print(data["name"])
                    core = copy.deepcopy(dummyCore)
                    core["functionalDescription"]["shape"] = data

                    core_datum = PyMKF.calculate_core_data(core, False)
                    builder.Builder("CadQuery").get_core_gapping_technical_drawing(data["name"], core_datum)

                    filename = f"{data['name']}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    # print(f"{self.output_path}/{filename}_core_gaps_FrontView.svg")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_core_gaps_FrontView.svg"))

    def test_0(self):
        core = {
            "functionalDescription": {
                "bobbin": None,
                "gapping": [
                    {
                        "area": 0.000315,
                        "coordinates": [0.0, 0.0005, 0.0],
                        "distanceClosestNormalSurface": 0.009,
                        "length": 0.001,
                        "sectionDimensions": [0.02, 0.02],
                        "shape": "round",
                        "type": "subtractive",
                    },
                    {
                        "area": 0.000238,
                        "coordinates": [0.0215, 0.0, 0.0],
                        "distanceClosestNormalSurface": 0.0095,
                        "length": 1e-05,
                        "sectionDimensions": [0.004, 0.059501],
                        "shape": "irregular",
                        "type": "residual",
                    },
                    {
                        "area": 0.000238,
                        "coordinates": [-0.0215, 0.0, 0.0],
                        "distanceClosestNormalSurface": 0.0095,
                        "length": 1e-05,
                        "sectionDimensions": [0.004, 0.059501],
                        "shape": "irregular",
                        "type": "residual",
                    },
                ],
                "material": "3C97",
                "name": "default",
                "numberStacks": 1,
                "shape": {
                    "aliases": [],
                    "dimensions": {"A": 0.047, "B": 0.014, "C": 0.0, "D": 0.0095, "E": 0.039, "F": 0.02, "G": 0.0081, "H": 0.0055},
                    "family": "p",
                    "familySubtype": "2",
                    "magneticCircuit": None,
                    "name": "Custom",
                    "type": "custom",
                },
                "type": "two-piece set",
            },
            "geometricalDescription": [
                {
                    "coordinates": [0.0, 0.0, -0.0],
                    "dimensions": None,
                    "machining": [{"coordinates": [0.0, 0.0005, 0.0], "length": 0.001}],
                    "material": "3C97",
                    "rotation": [3.141592653589793, 3.141592653589793, 0.0],
                    "shape": {
                        "aliases": [],
                        "dimensions": {"A": 0.047, "B": 0.014, "C": 0.0, "D": 0.0095, "E": 0.039, "F": 0.02, "G": 0.0081, "H": 0.0055},
                        "family": "p",
                        "familySubtype": "2",
                        "magneticCircuit": None,
                        "name": "Custom",
                        "type": "custom",
                    },
                    "type": "half set",
                },
                {
                    "coordinates": [0.0, -0.0, -0.0],
                    "dimensions": None,
                    "machining": [{"coordinates": [0.0, 0.0005, 0.0], "length": 0.001}],
                    "material": "3C97",
                    "rotation": [0.0, 0.0, 0.0],
                    "shape": {
                        "aliases": [],
                        "dimensions": {"A": 0.047, "B": 0.014, "C": 0.0, "D": 0.0095, "E": 0.039, "F": 0.02, "G": 0.0081, "H": 0.0055},
                        "family": "p",
                        "familySubtype": "2",
                        "magneticCircuit": None,
                        "name": "Custom",
                        "type": "custom",
                    },
                    "type": "half set",
                },
            ],
            "processedDescription": {
                "columns": [
                    {"area": 0.000315, "coordinates": [0.0, 0.0, 0.0], "depth": 0.02, "height": 0.019, "shape": "round", "type": "central", "width": 0.02},
                    {"area": 0.000238, "coordinates": [0.0215, 0.0, 0.0], "depth": 0.059501, "height": 0.019, "shape": "irregular", "type": "lateral", "width": 0.004},
                    {"area": 0.000238, "coordinates": [-0.0215, 0.0, 0.0], "depth": 0.059501, "height": 0.019, "shape": "irregular", "type": "lateral", "width": 0.004},
                ],
                "depth": 0.047,
                "effectiveParameters": {
                    "effectiveArea": 0.00035050517966366066,
                    "effectiveLength": 0.07043961692540429,
                    "effectiveVolume": 2.468945058587826e-05,
                    "minimumArea": 0.00028657215486964393,
                },
                "height": 0.028,
                "width": 0.047,
                "windingWindows": [{"angle": None, "area": 0.0001805, "coordinates": [0.01, 0.0], "height": 0.019, "radialHeight": None, "width": 0.0095}],
            },
        }
        builder.Builder("CadQuery").get_core(core["functionalDescription"]["shape"]["name"], core["geometricalDescription"])

        # filename = f"{data['name']}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
        # print(f"{self.output_path}/{filename}_core_gaps_FrontView.svg")
        # self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_core_gaps_FrontView.svg"))

    def test_1(self):
        core_shape = {
            "family": "p",
            "type": "standard",
            "aliases": [],
            "dimensions": {"A": 0.0424, "B": 0.0147, "C": 0.0319, "D": 0.010249999999999999, "E": 0.0363, "F": 0.0174, "G": 0.0051, "H": 0.006500000000000001, "M": 0.0, "N": 0.0, "r1": 0.0},
            "familySubtype": "2",
            "magneticCircuit": "open",
            "name": "P 42/29",
        }
        core_builder = builder.Builder("CadQuery").factory(core_shape)
        colors = {"projection_color": "#d4d4d4", "dimension_color": "#d4d4d4"}
        views = core_builder.get_piece_technical_drawing(core_shape, colors, save_files=True)

        # filename = f"{data['name']}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
        # print(f"{self.output_path}/{filename}_core_gaps_FrontView.svg")
        # self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_core_gaps_FrontView.svg"))

    def test_2(self):
        core_shape = {
            "magneticCircuit": "open",
            "type": "standard",
            "family": "ur",
            "aliases": [],
            "name": "UR 64/40/20-D",
            "dimensions": {
                "A": {"nominal": 0.06400},
                "D": {"nominal": 0.02650},
                "C": {"nominal": 0.02400},
                "E": {"minimum": 0.02320},
                "H": {"nominal": 0.02000},
                "B": {"nominal": 0.04050},
                "G": {"nominal": 0.00510},
                "F": {"nominal": 0.02000},
                "S": {"nominal": 0.00200},
            },
            "familySubtype": "4",
        }
        core_builder = builder.Builder().factory(core_shape)
        colors = {"projection_color": "#d4d4d4", "dimension_color": "#d4d4d4"}
        core_builder.get_piece(core_shape, save_files=True, export_files=True)

        # filename = f"{data['name']}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
        # print(f"{self.output_path}/{filename}_core_gaps_FrontView.svg")
        # self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_core_gaps_FrontView.svg"))

    def test_3(self):
        core_shape = {
            "magneticCircuit": "open",
            "type": "standard",
            "family": "ur",
            "aliases": [],
            "name": "UR type 2",
            "dimensions": {
                "A": {"nominal": 0.0595},
                "D": {"nominal": 0.0215},
                "C": {"nominal": 0.0170},
                "E": {"minimum": 0.0255},
                "H": {"nominal": 0.017},
                "B": {"nominal": 0.036},
                "G": {"nominal": 0},
                "F": {"nominal": 0},
                "S": {"nominal": 0.0045},
            },
            "familySubtype": "2",
        }
        core_builder = builder.Builder("CadQuery").factory(core_shape)
        core_builder.get_piece(core_shape, save_files=True, export_files=True)
        filename = f"{core_shape['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
        self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj") or os.path.exists(f"{self.output_path}/{filename}.stl"))

    def test_4(self):
        core_shape = {  # UR 35/27.5/13
            "name": "core",
            "family": "ur",
            "familySubtype": "1",
            "dimensions": {
                "A": {"nominal": 0.0354},
                "B": {"nominal": 0.0275},
                "C": {"nominal": 0.013},
                "D": {"nominal": 0.0175},
                "E": {"minimum": 0.012},
                "H": {"nominal": 0.01},
                "S": {"nominal": 0.0015},
            },
        }
        core_builder = builder.Builder("CadQuery").factory(core_shape)
        core_builder.get_piece(core_shape, save_files=True, export_files=True)
        filename = f"{core_shape['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
        print(filename)
        self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj") or os.path.exists(f"{self.output_path}/{filename}.stl"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

    # data = {'aliases': [],
    #         'dimensions': {'A': 0.0094,
    #                        'B': 0.0046,
    #                        'C': 0.0088,
    #                        'D': 0.0035,
    #                        'E': 0.0072,
    #                        'F': 0.003,
    #                        'G': 0.0,
    #                        'H': 0.0,
    #                        'K': 0.0015},
    #         'family': 'epx',
    #         'familySubtype': '1',
    #         'magneticCircuit': None,
    #         'name': 'Custom',
    #         'type': 'custom'}
    # core = builder.Builder("CadQuery").factory(data)
    # import pprint
    # pprint.pprint(data)
    # print("ea")
    # ea = core.get_piece_technical_drawing(data, save_files=True)
    # print("ea2")
    # filename = f"{data['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
    # # print(ea)
    # # print(filename)
