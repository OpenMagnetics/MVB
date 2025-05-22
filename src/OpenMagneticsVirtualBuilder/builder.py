import contextlib
import sys
import math
import os
import json
from abc import ABCMeta, abstractmethod
import copy
import pathlib
import platform
sys.path.append(os.path.dirname(__file__))
import utils

file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)


def flatten_dimensions(data):
    dimensions = data["dimensions"]
    for k, v in dimensions.items():
        if isinstance(v, dict):
            if "nominal" not in v or v["nominal"] is None:
                if "maximum" not in v or v["maximum"] is None:
                    v["nominal"] = v["minimum"]
                elif "minimum" not in v or v["minimum"] is None:
                    v["nominal"] = v["maximum"]
                else:
                    v["nominal"] = round((v["maximum"] + v["minimum"]) / 2, 6)
        else:
            dimensions[k] = {"nominal": v}
    return {k: v["nominal"] * 1000 for k, v in dimensions.items() if k != 'alpha'}


class Builder:
    """
    Class for calculating the different areas and length of every shape according to EN 60205.
    Each shape will create a daughter of this class and define their own equations
    """

    def __init__(self, engine="FreeCAD"):
        if engine == "FreeCAD":
            import freecad_builder
            self.engine = freecad_builder.FreeCADBuilder()
        else:
            import cadquery_builder
            self.engine = cadquery_builder.CadQueryBuilder()

    def factory(self, data):
        return self.engine.factory(data)

    def get_families(self):
        return {
            shaper.name.lower()
            .replace("_", " "): self.factory({'family': shaper.name})
            .get_dimensions_and_subtypes()
            for shaper in self.engine.shapers
        }

    def get_spacer(self, geometrical_data):
        return self.engine.get_spacer(geometrical_data)

    def get_core(self, project_name, geometrical_description, output_path=f'{os.path.dirname(os.path.abspath(__file__))}/../../output/', save_files=True, export_files=True):
        return self.engine.get_core(project_name, geometrical_description, output_path, save_files, export_files)

    def get_core_gapping_technical_drawing(self, project_name, core_data, colors=None, output_path=f'{os.path.dirname(os.path.abspath(__file__))}/../../output/', save_files=True, export_files=True):
        return self.engine.get_core_gapping_technical_drawing(project_name, core_data, colors, output_path, save_files, export_files)


if __name__ == '__main__':  # pragma: no cover

    with open(f'{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson', 'r') as f:
        for ndjson_line in f.readlines():
            data = json.loads(ndjson_line)
            if data["name"] == "PQ 40/40":
            # if data["family"] in ['pm']:
            # if data["family"] not in ['ui']:
                core = Builder().factory(data)
                core.get_core(data, None)
                # break
