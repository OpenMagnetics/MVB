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

    def test_all_shapes_generated(self):

        with open(f'{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/shapes.ndjson', 'r') as f:
            for ndjson_line in f.readlines():
                data = json.loads(ndjson_line)
                if data["family"] not in ['ui']:
                    core = builder.Builder().factory(data)
                    core.get_piece(data, save_files=True, export_files=True)
                    filename = f"{data['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.step"))
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj"))

    def test_all_technical_drawings_generated(self):

        with open(f'{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/shapes.ndjson', 'r') as f:
            for ndjson_line in f.readlines():
                data = json.loads(ndjson_line)
                if data["family"] not in ['ui']:
                    core = builder.Builder().factory(data)
                    core.get_piece_technical_drawing(data, save_files=True)
                    filename = f"{data['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    print(f"{self.output_path}/{filename}_TopView.svg")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_scaled_TopView.svg"))
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_scaled_FrontView.svg"))

    def test_get_families(self):
        
        families = builder.Builder().get_families()
        with open(f'{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/shapes.ndjson', 'r') as f:
            for ndjson_line in f.readlines():
                data = json.loads(ndjson_line)
                if data["family"] not in ['ui']:
                    self.assertTrue(data["family"] in list(families.keys()))

    def test_all_subtractive_gapped_cores_generated(self):
        dummyGapping = [
            {
                'length': 0.001,
                'type': 'subtractive'
            },
            {
                'length': 0.002,
                'type': 'subtractive'
            },
            {
                'length': 0,
                'type': 'subtractive'
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
                    core_datum = PyMKF.get_core_data(core, False)
                    for column_index, column in enumerate(core_datum['processedDescription']['columns']):
                        aux = copy.deepcopy(dummyGapping[column_index])
                        aux['coordinates'] = column['coordinates']
                        gapping.append(aux)
                    core['functionalDescription']['gapping'] = gapping
                    core_datum = PyMKF.get_core_data(core, False)
                    core = builder.Builder().get_core(data['name'], core_datum['geometricalDescription'])
                    print(core)
                    filename = f"{data['name']}_core".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.step"))
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj"))

    def test_all_subtractive_distributed_gapped_cores_generated(self):
        dummyGapping = [
            {
                'length': 0.001,
                'type': 'subtractive'
            },
            {
                'length': 0.0005,
                'type': 'subtractive'
            },
            {
                'length': 0.002,
                'type': 'subtractive'
            },
            {
                'length': 0.00005,
                'type': 'residual'
            },
            {
                'length': 0.00005,
                'type': 'residual'
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

                    core_datum = PyMKF.get_core_data(core, False)
                    core = builder.Builder().get_core(data['name'], core_datum['geometricalDescription'])
                    print(core)
                    filename = f"{data['name']}_core".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.step"))
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj"))

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
                    core_datum = PyMKF.get_core_data(core, False)
                    for column_index, column in enumerate(core_datum['processedDescription']['columns']):
                        aux = copy.deepcopy(dummyGapping[column_index])
                        aux['coordinates'] = column['coordinates']
                        gapping.append(aux)
                    core['functionalDescription']['gapping'] = gapping
                    core_datum = PyMKF.get_core_data(core, False)
                    # import pprint
                    # pprint.pprint(core_datum['processedDescription'])
                    # pprint.pprint(core_datum['geometricalDescription'])
                    core = builder.Builder().get_core(data['name'], core_datum['geometricalDescription'])
                    print(core)
                    filename = f"{data['name']}_core".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.step"))
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}.obj"))

    def test_all_additive_technical_drawing_cores_generated(self):
        dummyGapping = [
            {
                'length': 0.001,
                'type': 'additive'
            },
            {
                'length': 0.001,
                'type': 'additive'
            },
            {
                'length': 0.001,
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
                # if data["family"] not in ['ui', 'ut']:
                if data["family"] in ['u']:
                    core = copy.deepcopy(dummyCore)
                    if data['family'] in ['ut']:
                        core['functionalDescription']['type'] = "closed shape"
                    core['functionalDescription']['shape'] = data

                    gapping = []
                    core_datum = PyMKF.get_core_data(core, False)
                    for column_index, column in enumerate(core_datum['processedDescription']['columns']):
                        aux = copy.deepcopy(dummyGapping[column_index])
                        aux['coordinates'] = column['coordinates']
                        gapping.append(aux)
                    core['functionalDescription']['gapping'] = gapping
                    core_datum = PyMKF.get_core_data(core, False)
                    core = builder.Builder().get_core_gapping_technical_drawing(data['name'], core_datum)

                    filename = f"{data['name']}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    print(f"{self.output_path}/{filename}_core_gaps_FrontView.svg")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_core_gaps_FrontView.svg"))

    def test_all_subtractive_technical_drawing_cores_generated(self):
        dummyGapping = [
            {
                'length': 0.001,
                'type': 'subtractive'
            },
            {
                'length': 0.002,
                'type': 'subtractive'
            },
            {
                'length': 0.000005,
                'type': 'subtractive'
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
                    core_datum = PyMKF.get_core_data(core, False)
                    for column_index, column in enumerate(core_datum['processedDescription']['columns']):
                        aux = copy.deepcopy(dummyGapping[column_index])
                        aux['coordinates'] = column['coordinates']
                        gapping.append(aux)
                    core['functionalDescription']['gapping'] = gapping
                    core_datum = PyMKF.get_core_data(core, False)
                    # import pprint
                    # pprint.pprint(core_datum)
                    core = builder.Builder().get_core_gapping_technical_drawing(data['name'], core_datum)

                    filename = f"{data['name']}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    print(f"{self.output_path}/{filename}_core_gaps_FrontView.svg")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_core_gaps_FrontView.svg"))

    def test_all_subtractive_distributed_technical_drawing_cores_generated(self):
        dummyGapping = [
            {
                'length': 0.001,
                'type': 'subtractive'
            },
            {
                'length': 0.0005,
                'type': 'subtractive'
            },
            {
                'length': 0.002,
                'type': 'subtractive'
            },
            {
                'length': 0.00005,
                'type': 'residual'
            },
            {
                'length': 0.00005,
                'type': 'residual'
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

                    core_datum = PyMKF.get_core_data(core, False)
                    core = builder.Builder().get_core_gapping_technical_drawing(data['name'], core_datum)

                    filename = f"{data['name']}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                    print(f"{self.output_path}/{filename}_core_gaps_FrontView.svg")
                    self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_core_gaps_FrontView.svg"))

    def test_all_subtractive_distributed_technical_drawing_cores_generated(self):
        core = {'functionalDescription': {'bobbin': None,
                                           'gapping': [{'area': 0.000315,
                                                        'coordinates': [0.0, 0.0005, 0.0],
                                                        'distanceClosestNormalSurface': 0.009,
                                                        'length': 0.001,
                                                        'sectionDimensions': [0.02, 0.02],
                                                        'shape': 'round',
                                                        'type': 'subtractive'},
                                                       {'area': 0.000238,
                                                        'coordinates': [0.0215, 0.0, 0.0],
                                                        'distanceClosestNormalSurface': 0.0095,
                                                        'length': 1e-05,
                                                        'sectionDimensions': [0.004, 0.059501],
                                                        'shape': 'irregular',
                                                        'type': 'residual'},
                                                       {'area': 0.000238,
                                                        'coordinates': [-0.0215, 0.0, 0.0],
                                                        'distanceClosestNormalSurface': 0.0095,
                                                        'length': 1e-05,
                                                        'sectionDimensions': [0.004, 0.059501],
                                                        'shape': 'irregular',
                                                        'type': 'residual'}],
                                           'material': '3C97',
                                           'name': 'default',
                                           'numberStacks': 1,
                                           'shape': {'aliases': [],
                                                     'dimensions': {'A': 0.047,
                                                                    'B': 0.014,
                                                                    'C': 0.0,
                                                                    'D': 0.0095,
                                                                    'E': 0.039,
                                                                    'F': 0.02,
                                                                    'G': 0.0081,
                                                                    'H': 0.0055},
                                                     'family': 'p',
                                                     'familySubtype': '2',
                                                     'magneticCircuit': None,
                                                     'name': 'Custom',
                                                     'type': 'custom'},
                                           'type': 'two-piece set'},
                         'geometricalDescription': [{'coordinates': [0.0, 0.0, -0.0],
                                                     'dimensions': None,
                                                     'machining': [{'coordinates': [0.0, 0.0005, 0.0],
                                                                    'length': 0.001}],
                                                     'material': '3C97',
                                                     'rotation': [3.141592653589793,
                                                                  3.141592653589793,
                                                                  0.0],
                                                     'shape': {'aliases': [],
                                                               'dimensions': {'A': 0.047,
                                                                              'B': 0.014,
                                                                              'C': 0.0,
                                                                              'D': 0.0095,
                                                                              'E': 0.039,
                                                                              'F': 0.02,
                                                                              'G': 0.0081,
                                                                              'H': 0.0055},
                                                               'family': 'p',
                                                               'familySubtype': '2',
                                                               'magneticCircuit': None,
                                                               'name': 'Custom',
                                                               'type': 'custom'},
                                                     'type': 'half set'},
                                                    {'coordinates': [0.0, -0.0, -0.0],
                                                     'dimensions': None,
                                                     'machining': [{'coordinates': [0.0, 0.0005, 0.0],
                                                                    'length': 0.001}],
                                                     'material': '3C97',
                                                     'rotation': [0.0, 0.0, 0.0],
                                                     'shape': {'aliases': [],
                                                               'dimensions': {'A': 0.047,
                                                                              'B': 0.014,
                                                                              'C': 0.0,
                                                                              'D': 0.0095,
                                                                              'E': 0.039,
                                                                              'F': 0.02,
                                                                              'G': 0.0081,
                                                                              'H': 0.0055},
                                                               'family': 'p',
                                                               'familySubtype': '2',
                                                               'magneticCircuit': None,
                                                               'name': 'Custom',
                                                               'type': 'custom'},
                                                     'type': 'half set'}],
                         'processedDescription': {'columns': [{'area': 0.000315,
                                                               'coordinates': [0.0, 0.0, 0.0],
                                                               'depth': 0.02,
                                                               'height': 0.019,
                                                               'shape': 'round',
                                                               'type': 'central',
                                                               'width': 0.02},
                                                              {'area': 0.000238,
                                                               'coordinates': [0.0215, 0.0, 0.0],
                                                               'depth': 0.059501,
                                                               'height': 0.019,
                                                               'shape': 'irregular',
                                                               'type': 'lateral',
                                                               'width': 0.004},
                                                              {'area': 0.000238,
                                                               'coordinates': [-0.0215, 0.0, 0.0],
                                                               'depth': 0.059501,
                                                               'height': 0.019,
                                                               'shape': 'irregular',
                                                               'type': 'lateral',
                                                               'width': 0.004}],
                                                  'depth': 0.047,
                                                  'effectiveParameters': {'effectiveArea': 0.00035050517966366066,
                                                                          'effectiveLength': 0.07043961692540429,
                                                                          'effectiveVolume': 2.468945058587826e-05,
                                                                          'minimumArea': 0.00028657215486964393},
                                                  'height': 0.028,
                                                  'width': 0.047,
                                                  'windingWindows': [{'angle': None,
                                                                      'area': 0.0001805,
                                                                      'coordinates': [0.01, 0.0],
                                                                      'height': 0.019,
                                                                      'radialHeight': None,
                                                                      'width': 0.0095}]}}
        core = builder.Builder().get_core(core['functionalDescription']['shape']['name'], core['geometricalDescription'])

        # filename = f"{data['name']}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
        # print(f"{self.output_path}/{filename}_core_gaps_FrontView.svg")
        # self.assertTrue(os.path.exists(f"{self.output_path}/{filename}_core_gaps_FrontView.svg"))


if __name__ == '__main__':  # pragma: no cover
    # unittest.main()

    data = {'aliases': [],
             'dimensions': {'A': {'nominal': 0.01475},
                            'B': {'nominal': 0.0067},
                            'C': {'nominal': 0.0096},
                            'D': {'nominal': 0.005},
                            'E': {'nominal': 0.01272},
                            'F': {'nominal': 0.0057},
                            'K': {'nominal': 0.00235}},
             'family': 'epx',
             'magneticCircuit': 'open',
             'name': 'custom EPX',
             'type': 'standard'}
    core = builder.Builder().factory(data)
    import pprint
    pprint.pprint(data)
    core.get_piece(data, save_files=True, export_files=True)
    filename = f"{data['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
    print(filename)
