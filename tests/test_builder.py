import unittest
import os
import json
import glob

import context  # noqa: F401
import builder
import copy
import PyMKF


class Tests(unittest.TestCase):
    output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../output/'

    @classmethod
    def setUpClass(cls):

        files = glob.glob(f"{cls.output_path}/*")
        for f in files:
            os.remove(f)
        print("Starting tests for builder")

    @classmethod
    def tearDownClass(cls):
        print("\nFinishing tests for builder")

    # def test_all_shapes_generated(self):

    #     with open(f'{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/shapes.ndjson', 'r') as f:
    #         for ndjson_line in f.readlines():
    #             data = json.loads(ndjson_line)
    #             if data["family"] not in ['ui']:
    #                 core = builder.Builder().factory(data)
    #                 core.get_piece(data)
    #                 filename = f"{data['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
    #                 self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.step"))
    #                 self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj"))

    # def test_all_technical_drawings_generated(self):

    #     with open(f'{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/shapes.ndjson', 'r') as f:
    #         for ndjson_line in f.readlines():
    #             data = json.loads(ndjson_line)
    #             if data["family"] not in ['ui']:
    #                 core = builder.Builder().factory(data)
    #                 core.get_piece_technical_drawing(data, save_files=True)
    #                 filename = f"{data['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
    #                 print(f"{self.output_path}/{filename}_TopView.svg")
    #                 self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_scaled_TopView.svg"))
    #                 self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_scaled_FrontView.svg"))

    # def test_get_families(self):
        
    #     families = builder.Builder().get_families()
    #     with open(f'{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/shapes.ndjson', 'r') as f:
    #         for ndjson_line in f.readlines():
    #             data = json.loads(ndjson_line)
    #             if data["family"] not in ['ui']:
    #                 self.assertTrue(data["family"] in list(families.keys()))

    # def test_all_subtractive_gapped_cores_generated(self):
    #     dummyGapping = [
    #         {
    #             'length': 0.001,
    #             'type': 'subtractive'
    #         },
    #         {
    #             'length': 0.002,
    #             'type': 'subtractive'
    #         },
    #         {
    #             'length': 0,
    #             'type': 'subtractive'
    #         }
    #     ]

    #     dummyCore = {
    #         "functionalDescription": {
    #             "name": "dummy",
    #             "type": "two-piece set",
    #             "material": "N97",
    #             "shape": None,
    #             "gapping": dummyGapping,
    #             "numberStacks": 1
    #         }
    #     }
    #     with open(f'{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/shapes.ndjson', 'r') as f:
    #         for ndjson_line in f.readlines():
    #             data = json.loads(ndjson_line)
    #             if data["family"] not in ['ui']:

    #                 core = copy.deepcopy(dummyCore)
    #                 if data['family'] in ['ut']:
    #                     core['functionalDescription']['type'] = "closed shape"
    #                 core['functionalDescription']['shape'] = data

    #                 gapping = []
    #                 core_datum = PyMKF.get_core_data(core)
    #                 for column_index, column in enumerate(core_datum['processedDescription']['columns']):
    #                     aux = copy.deepcopy(dummyGapping[column_index])
    #                     aux['coordinates'] = column['coordinates']
    #                     gapping.append(aux)
    #                 core['functionalDescription']['gapping'] = gapping
    #                 core_datum = PyMKF.get_core_data(core)
    #                 core = builder.Builder().get_core(data['name'], core_datum['geometricalDescription'])
    #                 print(core)
    #                 filename = f"{data['name']}_core".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
    #                 self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.step"))
    #                 self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj"))

    def test_all_additive_gapped_cores_generated(self):
        dummyGapping = [
            {
                'length': 0.0001,
                'type': 'additive'
            },
            {
                'length': 0.0001,
                'type': 'additive'
            },
            {
                'length': 0.0001,
                'type': 'additive'
            }
        ]

        dummyCore = {
            "functionalDescription": {
                "name": "dummy",
                "type": "two-piece set",
                "material": "N97",
                "shape": None,
                "gapping": dummyGapping,
                "numberStacks": 1
            }
        }
        with open(f'{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/shapes.ndjson', 'r') as f:
            for ndjson_line in f.readlines():
                data = json.loads(ndjson_line)
                if data["family"] not in ['ui', 'ut']:

                    core = copy.deepcopy(dummyCore)
                    if data['family'] in ['ut']:
                        core['functionalDescription']['type'] = "closed shape"
                    core['functionalDescription']['shape'] = data

                    gapping = []
                    core_datum = PyMKF.get_core_data(core)
                    for column_index, column in enumerate(core_datum['processedDescription']['columns']):
                        aux = copy.deepcopy(dummyGapping[column_index])
                        aux['coordinates'] = column['coordinates']
                        gapping.append(aux)
                    core['functionalDescription']['gapping'] = gapping
                    core_datum = PyMKF.get_core_data(core)
                    # import pprint
                    # pprint.pprint(core_datum['geometricalDescription'])
                    core = builder.Builder().get_core(data['name'], core_datum['geometricalDescription'])
                    print(core)
                    filename = f"{data['name']}_core".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.step"))
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj"))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
