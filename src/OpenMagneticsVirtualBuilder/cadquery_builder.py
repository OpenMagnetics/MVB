import contextlib
import sys
import math
import os
import json
from abc import ABCMeta, abstractmethod
import copy
import pathlib
import platform
from dataclasses import dataclass
from typing import List, Optional
sys.path.append(os.path.dirname(__file__))
import utils
import cadquery as cq


@dataclass
class TurnDescription:
    """Description of a single turn from MAS turnsDescription."""
    coordinates: List[float]  # [radial_pos, height_pos] in meters
    winding: str = ""
    section: str = ""
    layer: str = ""
    parallel: int = 0
    turn_index: int = 0
    dimensions: Optional[List[float]] = None  # [width, height] of wire
    rotation: float = 0.0
    orientation: str = "clockwise"

    @classmethod
    def from_dict(cls, data: dict) -> 'TurnDescription':
        return cls(
            coordinates=data.get('coordinates', [0, 0]),
            winding=data.get('winding', ''),
            section=data.get('section', ''),
            layer=data.get('layer', ''),
            parallel=data.get('parallel', 0),
            turn_index=data.get('turnIndex', 0),
            dimensions=data.get('dimensions'),
            rotation=data.get('rotation', 0.0),
            orientation=data.get('orientation', 'clockwise')
        )

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
    return {k: v["nominal"] for k, v in dimensions.items() if k != 'alpha'}


def convert_axis(coordinates):
    if len(coordinates) == 2:
        return [0, coordinates[0], coordinates[1]]
    elif len(coordinates) == 3:
        return [coordinates[0], coordinates[2], coordinates[1]]
    else:
        assert False, "Invalid coordinates length"


class CadQueryBuilder:
    """
    Class for calculating the different areas and length of every shape according to EN 60205.
    Each shape will create a daughter of this class and define their own equations
    """

    def __init__(self):
        self.shapers = {
            utils.ShapeFamily.ETD: self.Etd(),
            utils.ShapeFamily.ER: self.Er(),
            utils.ShapeFamily.EP: self.Ep(),
            utils.ShapeFamily.EPX: self.Epx(),
            utils.ShapeFamily.PQ: self.Pq(),
            utils.ShapeFamily.E: self.E(),
            utils.ShapeFamily.PM: self.Pm(),
            utils.ShapeFamily.P: self.P(),
            utils.ShapeFamily.RM: self.Rm(),
            utils.ShapeFamily.EQ: self.Eq(),
            utils.ShapeFamily.LP: self.Lp(),
            utils.ShapeFamily.PLANAR_ER: self.Er(),
            utils.ShapeFamily.PLANAR_E: self.E(),
            utils.ShapeFamily.PLANAR_EL: self.El(),
            utils.ShapeFamily.EC: self.Ec(),
            utils.ShapeFamily.EFD: self.Efd(),
            utils.ShapeFamily.U: self.U(),
            utils.ShapeFamily.UR: self.Ur(),
            utils.ShapeFamily.T: self.T(),
            utils.ShapeFamily.C: self.C()
        }

    def factory(self, data):
        family = utils.ShapeFamily[data['family'].upper().replace(" ", "_")]
        return self.shapers[family]

    def get_families(self):
        return {
            shaper.name.lower()
            .replace("_", " "): self.factory({'family': shaper.name})
            .get_dimensions_and_subtypes()
            for shaper in self.shapers
        }

    def get_spacer(self, geometrical_data):
        spacer = (
            cq.Workplane()
            .box(geometrical_data["dimensions"][0], geometrical_data["dimensions"][2], geometrical_data["dimensions"][1])
            .translate(convert_axis(geometrical_data["coordinates"]))
        )
        return spacer

    def get_core(self, project_name, geometrical_description, output_path=f'{os.path.dirname(os.path.abspath(__file__))}/../../output/', save_files=True, export_files=True):
        try:
            pieces_to_export = []
            project_name = f"{project_name}_core".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")

            os.makedirs(output_path, exist_ok=True)

            for index, geometrical_part in enumerate(geometrical_description):
                if geometrical_part['type'] == 'spacer':
                    spacer = self.get_spacer(geometrical_part)
                    pieces_to_export.append(spacer)
                elif geometrical_part['type'] in ['half set', 'toroidal']:
                    shape_data = geometrical_part['shape']
                    part_builder = CadQueryBuilder().factory(shape_data)

                    piece = part_builder.get_piece(data=copy.deepcopy(shape_data),
                                                   name=f"Piece_{index}",
                                                   save_files=False,
                                                   export_files=False)

                    piece = piece.rotate((1, 0, 0), (-1, 0, 0), geometrical_part['rotation'][0] / math.pi * 180)
                    piece = piece.rotate((0, 1, 0), (0, -1, 0), geometrical_part['rotation'][2] / math.pi * 180)
                    piece = piece.rotate((0, 0, 1), (0, 0, -1), geometrical_part['rotation'][1] / math.pi * 180)

                    if 'machining' in geometrical_part and geometrical_part['machining'] is not None:
                        for machining in geometrical_part['machining']:
                            piece = part_builder.apply_machining(piece=piece,
                                                                 machining=machining,
                                                                 dimensions=flatten_dimensions(shape_data))

                    piece = piece.translate(convert_axis(geometrical_part['coordinates']))

                    # if the piece is half a set, we add a residual gap between the pieces
                    if geometrical_part['type'] in ['half set']:
                        residual_gap = 5e-6
                        if geometrical_part['rotation'][0] > 0:
                            piece = piece.translate((0, 0, residual_gap / 2))
                        else:
                            piece = piece.translate((0, 0, -residual_gap / 2))

                    pieces_to_export.append(piece)

            if export_files:
                from cadquery import exporters
                scaled_pieces_to_export = []
                for piece in pieces_to_export:
                    for o in piece.objects:
                        scaled_pieces_to_export.append(o.scale(1000))

                scaled_pieces_to_export = cq.Compound.makeCompound(scaled_pieces_to_export)

                exporters.export(scaled_pieces_to_export, f"{output_path}/{project_name}.step", "STEP")
                exporters.export(scaled_pieces_to_export, f"{output_path}/{project_name}.stl", "STL")
                return f"{output_path}/{project_name}.step", f"{output_path}/{project_name}.stl",
            else:
                return pieces_to_export

        except:  # noqa: E722
            return None, None
    
    def get_core_gapping_technical_drawing(self, project_name, core_data, colors=None, output_path=f'{os.path.dirname(os.path.abspath(__file__))}/../../output/', save_files=True, export_files=True):
        raise NotImplementedError

    def get_bobbin(self, bobbin_data, winding_window, name="Bobbin", output_path=None, save_files=False, export_files=True):
        if output_path is None:
            output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../output/'

        bobbin_family = bobbin_data.get("family", "standard").upper()
        if bobbin_family == "STANDARD":
            bobbin_builder = self.StandardBobbin()
        else:
            bobbin_builder = self.StandardBobbin()

        bobbin_builder.set_output_path(output_path)
        return bobbin_builder.get_bobbin(bobbin_data, winding_window, name, save_files, export_files)

    def get_winding(self, winding_data, bobbin_dims, name="Winding", output_path=None, save_files=False, export_files=True):
        if output_path is None:
            output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../output/'

        winding_type = winding_data.get("type", "round_wire").upper().replace(" ", "_")
        if winding_type == "ROUND_WIRE":
            winding_builder = self.RoundWireWinding()
        else:
            winding_builder = self.RoundWireWinding()

        winding_builder.set_output_path(output_path)
        return winding_builder.get_winding(winding_data, bobbin_dims, name, save_files, export_files)

    def get_magnetic_assembly(self, project_name, assembly_data, output_path=None, save_files=True, export_files=True):
        if output_path is None:
            output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../output/'

        assembly_builder = self.AssemblyBuilder()
        assembly_builder.set_output_path(output_path)
        return assembly_builder.get_magnetic_assembly(project_name, assembly_data, output_path, save_files, export_files)

    class IPiece(metaclass=ABCMeta):
        def __init__(self):
            self.output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../output/'

        def set_output_path(self, output_path):
            self.output_path = output_path

        @staticmethod
        def create_sketch():
            return cq.Sketch()

        @staticmethod
        def extrude_sketch(sketch, part_name, height):
            result = (
                cq.Workplane()
                .placeSketch(sketch)
                .extrude(height)
            )

            return result

        @abstractmethod
        def get_shape_extras(self, data, piece):
            return piece

        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F"]}

        def get_plate(self, data, save_files=False, export_files=True):
            import FreeCAD
            try:
                project_name = f"{data['name']}_plate".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                data["dimensions"] = flatten_dimensions(data)

                close_file_after_finishing = False
                if FreeCAD.ActiveDocument is None:
                    close_file_after_finishing = True
                    FreeCAD.newDocument(project_name)
                document = FreeCAD.ActiveDocument

                sketch = self.get_shape_base(data)

                document = FreeCAD.ActiveDocument
                document.recompute()

                part_name = "plate"

                plate = self.extrude_sketch(
                    sketch=sketch,
                    part_name=part_name,
                    height=data["dimensions"]["B"] - data["dimensions"]["D"]
                )

                document.recompute()
                if export_files:
                    from cadquery import exporters
                    scaled_pieces_to_export = []
                    for piece in [plate]:
                        for o in piece.objects:
                            scaled_pieces_to_export.append(o.scale(1000))

                    scaled_pieces_to_export = cq.Compound.makeCompound(scaled_pieces_to_export)

                    exporters.export(scaled_pieces_to_export, f"{self.output_path}/{project_name}.step", "STEP")
                    exporters.export(scaled_pieces_to_export, f"{self.output_path}/{project_name}.stl", "STL")
                    return f"{self.output_path}/{project_name}.step", f"{self.output_path}/{project_name}.stl"

                if save_files:
                    document.saveAs(f"{self.output_path}/{project_name}.FCStd")

                if not close_file_after_finishing:
                    return plate
            except:  # noqa: E722
                return None, None

        def get_piece(self, data, name="Piece", save_files=False, export_files=True):
            try:
                project_name = f"{data['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")

                data["dimensions"] = flatten_dimensions(data)

                sketch = self.get_shape_base(data)

                part_name = "piece"

                base = self.extrude_sketch(
                    sketch=sketch,
                    part_name=part_name,
                    height=data["dimensions"]["B"] if data["family"] != 't' else data["dimensions"]["C"]
                )

                negative_winding_window = self.get_negative_winding_window(data["dimensions"])

                if negative_winding_window is None:
                    piece = base
                else:
                    piece = base - negative_winding_window

                piece_with_extra = self.get_shape_extras(data, piece)


                pathlib.Path(self.output_path).mkdir(parents=True, exist_ok=True)

                if export_files:
                    from cadquery import exporters
                    scaled_piece_with_extra = piece_with_extra.newObject([o.scale(1000) for o in piece_with_extra.objects])
                    exporters.export(scaled_piece_with_extra, f"{self.output_path}/{project_name}.step", "STEP")
                    exporters.export(scaled_piece_with_extra, f"{self.output_path}/{project_name}.stl", "STL")
                    return f"{self.output_path}/{project_name}.step", f"{self.output_path}/{project_name}.stl"
                else:
                    return piece_with_extra

            except:  # noqa: E722
                return (None, None) if export_files else None

        def add_dimensions_and_export_view(self, data, original_dimensions, view, project_name, margin, colors, save_files, piece):
            raise NotImplementedError

        @abstractmethod
        def get_shape_base(self, data):
            raise NotImplementedError

        @abstractmethod
        def get_negative_winding_window(self, dimensions):
            raise NotImplementedError

        def apply_machining(self, piece, machining, dimensions):
            length = dimensions["A"]
            x_coordinate = dimensions["A"] / 2
            if machining['coordinates'][0] == 0:
                width = dimensions["F"]
                length = dimensions["F"]
                y_coordinate = 0
                x_coordinate = 0
            else:
                width = dimensions["A"] / 2
                if machining['coordinates'][0] < 0:
                    y_coordinate = 0
                if machining['coordinates'][0] > 0:
                    y_coordinate = 0

            height = machining['length']
            original_tool = cq.Workplane().box(width, length, height).translate((x_coordinate, y_coordinate, machining['coordinates'][1]))

            if machining['coordinates'][0] == 0:
                tool = original_tool
            else:
                central_column_width = dimensions["F"] * 1.001
                length = central_column_width
                width = central_column_width
                height = machining['length']
                central_column_tool = cq.Workplane().box(width, length, height).translate((0, 0, (machining['coordinates'][1] - machining['length'] / 2)))

                tool = original_tool - central_column_tool

            machined_piece = piece - tool

            return machined_piece

    class P(IPiece):

        def get_dimensions_and_subtypes(self):
            return {
                1: ["A", "B", "C", "D", "E", "F", "G", "H"],
                2: ["A", "B", "C", "D", "E", "F", "G", "H"],
                3: ["A", "B", "D", "E", "F", "G", "H"],
                4: ["A", "B", "C", "D", "E", "F", "G", "H"]
            }

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            familySubtype = data["familySubtype"]

            if familySubtype == '1' or familySubtype == '2':

                length = (dimensions["A"] - dimensions["F"]) / 2
                width = dimensions["G"]
                height = dimensions["D"]
                translate = (length / 2 + dimensions["F"] / 2, 0, height / 2 + dimensions["B"] - dimensions["D"])

                lateral_right_cut_box = (
                    cq.Workplane()
                    .box(length, width, height)
                    .tag("lateral_right_cut_box")
                    .translate(translate)
                )

                translate = (-(length / 2 + dimensions["F"] / 2), 0, height / 2 + dimensions["B"] - dimensions["D"])
                lateral_left_cut_box = (
                    cq.Workplane()
                    .box(length, width, height)
                    .tag("lateral_left_cut_box")
                    .translate(translate)
                )

                piece = piece - lateral_right_cut_box
                piece = piece - lateral_left_cut_box

                if familySubtype == '2':

                    if "C" in dimensions and dimensions["C"] > 0:
                        c = dimensions["C"] / 2
                    else:
                        c = utils.decimal_floor(dimensions["E"] * math.cos(math.asin(dimensions["G"] / dimensions["E"])) / 2, 6) * 0.95

                    length = dimensions["A"] / 2 - c
                    width = dimensions["G"]
                    height = dimensions["B"]
                    translate = (length / 2 + c, 0, height / 2)

                    right_dent_box = (
                        cq.Workplane()
                        .box(length, width, height)
                        .tag("right_dent_box")
                        .translate(translate)
                    )
                    piece = piece - right_dent_box

                    translate = (-(length / 2 + c), 0, height / 2)
                    left_dent_box = (
                        cq.Workplane()
                        .box(length, width, height)
                        .tag("left_dent_box")
                        .translate(translate)
                    )
                    piece = piece - left_dent_box
            elif familySubtype == '3':
                hole_width = (dimensions["G"]) / 2
                hole_length = (dimensions["E"] - dimensions["F"]) / 2 - hole_width
                hole_height = dimensions["B"]
                translate = (hole_width / 2 + hole_length / 2 + dimensions["F"] / 2, 0, 0)
                hole = (
                    cq.Workplane()
                    .box(hole_length, hole_width, hole_height)
                    .tag("hole")
                    .translate(translate)
                )
                translate = (hole_width / 2 + dimensions["F"] / 2, 0, 0)
                hole_round_1 = (
                    cq.Workplane()
                    .cylinder(hole_height, hole_width / 2)
                    .tag("hole_round_1")
                    .translate(translate)
                )
                hole = hole + hole_round_1
                translate = (hole_width / 2 + hole_length + dimensions["F"] / 2, 0, 0)
                hole_round_2 = (
                    cq.Workplane()
                    .cylinder(hole_height, hole_width / 2)
                    .tag("hole_round_2")
                    .translate(translate)
                )
                hole = hole + hole_round_1
                hole = hole + hole_round_2
                piece = piece - hole

                translate = (-(hole_width + hole_length + dimensions["F"]), 0, 0)
                hole = hole.translate(translate)
                piece = piece - hole

            if 'H' in dimensions and dimensions['H'] > 0:
                hole = (
                    cq.Workplane()
                    .cylinder(dimensions['B'], dimensions['H'] / 2)
                    .tag("hole")
                    .translate((0, 0, dimensions["B"] / 2))
                )
                piece = piece - hole

            piece = piece.translate((0, 0, -dimensions["B"]))

            return piece

        def get_shape_base(self, data):
            dimensions = data["dimensions"]

            a = dimensions["A"] / 2

            sketch = (
                cq.Sketch()
                .circle(a, mode="a", tag="central_circle")
            )
            return sketch

        def get_negative_winding_window(self, dimensions):

            winding_window_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['E'] / 2)
                .tag("winding_window_cylinder")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )

            central_column_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['F'] / 2)
                .tag("central_column_cylinder")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )
            negative_winding_window = winding_window_cylinder - central_column_cylinder
            return negative_winding_window

    class Pq(P):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "G"]} 

        def get_shape_base(self, data):
            dimensions = data["dimensions"]

            if "L" not in dimensions or dimensions["L"] == 0:
                dimensions["L"] = dimensions["F"] + (dimensions["C"] - dimensions["F"]) / 3

            if "J" not in dimensions or dimensions["J"] == 0:
                dimensions["J"] = dimensions["F"] / 2

            if "G" in dimensions:
                g_angle = math.asin(dimensions["G"] / dimensions["E"])
            else:
                g_angle = math.asin((dimensions["E"] - ((dimensions["E"] - dimensions["F"]) / 2)) / dimensions["E"])

            c = dimensions["C"] / 2
            a = dimensions["A"] / 2
            e = dimensions["E"] / 2
            f = dimensions["F"] / 2

            sketch = (
                cq.Sketch()
                .circle(f, mode="a", tag="central_circle")

                .segment((a, -c), (a, c), "top_line")
                .segment((a, c), (e * math.sin(g_angle), c), "side_top_right_line")
                .segment((a, -c), (e * math.sin(g_angle), -c), "side_top_left_line")
                .segment((e * math.sin(g_angle), c), (e * math.sin(g_angle), e * math.cos(g_angle)), "side_corner_top_right_line")
                .segment((e * math.sin(g_angle), -c), (e * math.sin(g_angle), -e * math.cos(g_angle)), "side_corner_top_left_line")

                .segment((e * math.sin(g_angle), e * math.cos(g_angle)), (dimensions["J"] / 2, dimensions["L"] / 2), "long_top_right_line")
                .segment((e * math.sin(g_angle), -e * math.cos(g_angle)), (dimensions["J"] / 2, -dimensions["L"] / 2), "long_top_left_line")
                .segment((dimensions["J"] / 2, dimensions["L"] / 2), (dimensions["J"] / 4, dimensions["L"] / 4), "short_top_right_line")
                .segment((dimensions["J"] / 2, -dimensions["L"] / 2), (dimensions["J"] / 4, -dimensions["L"] / 4), "short_top_left_line")
                .segment((dimensions["J"] / 4, dimensions["L"] / 4), (dimensions["J"] / 4, -dimensions["L"] / 4), "join_right")

                .constrain("top_line", "Fixed", None)
                .constrain("top_line", 'Orientation', (0, 1))
                .constrain("long_top_right_line", "short_top_right_line", 'Coincident', None)
                .constrain("long_top_left_line", "short_top_left_line", 'Coincident', None)

                .segment((-a, -c), (-a, c), "bottom_line")
                .segment((-a, c,), (-e * math.sin(g_angle), c), "side_bottom_right_line")
                .segment((-a, -c,), (-e * math.sin(g_angle), -c), "side_bottom_left_line")
                .segment((-e * math.sin(g_angle), c), (-e * math.sin(g_angle), e * math.cos(g_angle)), "side_corner_bottom_right_line")
                .segment((-e * math.sin(g_angle), -c), (-e * math.sin(g_angle), -e * math.cos(g_angle)), "side_corner_bottom_left_line")
                .segment((-e * math.sin(g_angle), e * math.cos(g_angle)), (-dimensions["J"] / 2, dimensions["L"] / 2), "long_bottom_right_line")
                .segment((-e * math.sin(g_angle), -e * math.cos(g_angle)), (-dimensions["J"] / 2, -dimensions["L"] / 2), "long_bottom_left_line")
                .segment((-dimensions["J"] / 2, dimensions["L"] / 2), (-dimensions["J"] / 4, dimensions["L"] / 4), "short_bottom_right_line")
                .segment((-dimensions["J"] / 2, -dimensions["L"] / 2), (-dimensions["J"] / 4, -dimensions["L"] / 4), "short_bottom_left_line")
                .segment((-dimensions["J"] / 4, dimensions["L"] / 4), (-dimensions["J"] / 4, -dimensions["L"] / 4), "join_left")
                .constrain("bottom_line", "Fixed", None)
                .constrain("bottom_line", 'Orientation', (0, 1))
                .constrain("long_bottom_right_line", "short_bottom_right_line", 'Coincident', None)
                .constrain("long_bottom_left_line", "short_bottom_left_line", 'Coincident', None)

                .constrain("short_top_right_line", "Fixed", None)
                .constrain("short_top_left_line", "Fixed", None)
                .constrain("short_bottom_right_line", "Fixed", None)
                .constrain("short_bottom_left_line", "Fixed", None)
            )

            sketch = sketch.solve().assemble()
            return sketch

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            piece = piece.translate((0, 0, -dimensions["B"]))
            return piece

    class Rm(P):
        def get_dimensions_and_subtypes(self):
            return {
                1: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
                2: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
                3: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
                4: ["A", "B", "C", "D", "E", "F", "G", "H", "J"]
            }

        def get_shape_base(self, data):
            dimensions = data["dimensions"]
            familySubtype = data["familySubtype"]

            p = math.sqrt(2) * dimensions["J"] - dimensions["A"]
            alpha = math.asin(dimensions["G"] / dimensions["E"])
            z = dimensions["E"] / 2 * math.cos(alpha)
            c = dimensions["C"] / 2
            g = dimensions["G"] / 2
            a = dimensions["A"] / 2
            e = dimensions["E"] / 2
            f = dimensions["F"] / 2

            if familySubtype == '1':
                t = 0
                n = (z - c) / g
                r = (a + p / 2 - c + n * t) / (n + 1)
                s = n * r + c
            elif familySubtype == '2':
                t = f * math.sin(math.acos(c / f))
                n = (z - c) / g
                r = (a + p / 2 - c + n * t) / (n + 1)
                s = n * r + c
            elif familySubtype == '3':
                t = c - e * math.cos(math.asin(g / e)) + g
                n = (z - c) / g
                r = (a + p / 2 - c + n * t) / (n + 1)
                s = n * r + c
            elif familySubtype == '4':
                t = 0
                n = 1
                r = (a + p / 2 - c + n * t) / (n + 1)
                s = n * r + c

            sketch = (
                cq.Sketch()

                .segment((a, -p / 2), (a, p / 2), "top_line")
                .segment((a, p / 2), (r, s), "top_right_line_45_degrees")
                .segment((r, s), (t, c), "top_right_line_x_degrees")
                .segment((-t, c), (-r, s), "bottom_right_line_x_degrees")
                .segment((-r, s), (-a, p / 2), "bottom_right_line_45_degrees")
                .segment((-a, p / 2), (-a, -p / 2), "bottom_line")
                .segment((-a, -p / 2), (-r, -s), "bottom_left_line_45_degrees")
                .segment((-r, -s), (-t, -c), "bottom_left_line_x_degrees")
                .segment((t, -c), (r, -s), "top_left_line_x_degrees")
                .segment((r, -s), (a, -p / 2), "top_left_line_45_degrees")
                .constrain("top_line", "Fixed", None)
                .constrain("bottom_line", "Fixed", None)
                .constrain("top_line", 'Orientation', (0, 1))
                .constrain("bottom_line", 'Orientation', (0, 1))
                .constrain("top_right_line_45_degrees", "top_right_line_x_degrees", 'Coincident', None)
                .constrain("bottom_right_line_x_degrees", "bottom_right_line_45_degrees", 'Coincident', None)
                .constrain("top_left_line_x_degrees", "top_left_line_45_degrees", 'Coincident', None)
                .constrain("bottom_left_line_45_degrees", "bottom_left_line_x_degrees", 'Coincident', None)
            )

            if familySubtype == '3':
                sketch = sketch.segment((t, c), (-t, c), "right_line")
                sketch = sketch.segment((-t, -c), (t, -c), "left_line")
                sketch = sketch.constrain("right_line", "Fixed", None)
                sketch = sketch.constrain("left_line", "Fixed", None)
                sketch = sketch.constrain("right_line", "left_line", 'Angle', 0)
                sketch = sketch.constrain("top_right_line_x_degrees", "right_line", 'Coincident', None)
                sketch = sketch.constrain("right_line", "bottom_right_line_x_degrees", 'Coincident', None)
                sketch = sketch.constrain("left_line", "top_left_line_x_degrees", 'Coincident', None)
                sketch = sketch.constrain("bottom_left_line_x_degrees", "left_line", 'Coincident', None)
            if familySubtype == '4':
                sketch = sketch.constrain("bottom_left_line_x_degrees", "top_left_line_x_degrees", 'Coincident', None)
                sketch = sketch.constrain("top_right_line_x_degrees", "bottom_right_line_x_degrees", 'Coincident', None)

            if familySubtype == '3' or familySubtype == '4':
                sketch = sketch.constrain("top_line", "top_right_line_45_degrees", 'Coincident', None)
                sketch = sketch.constrain("top_left_line_45_degrees", "top_line", 'Coincident', None)
                sketch = sketch.constrain("bottom_right_line_45_degrees", "bottom_line", 'Coincident', None)
                sketch = sketch.constrain("bottom_line", "bottom_left_line_45_degrees", 'Coincident', None)
                sketch = sketch.constrain("top_right_line_45_degrees", "top_right_line_x_degrees", 'Angle', 90)
                sketch = sketch.constrain("bottom_right_line_45_degrees", "bottom_right_line_x_degrees", 'Angle', 90)
                sketch = sketch.constrain("top_left_line_45_degrees", "top_left_line_x_degrees", 'Angle', 90)
                sketch = sketch.constrain("bottom_left_line_45_degrees", "bottom_left_line_x_degrees", 'Angle', 90)
                sketch = sketch.constrain("top_right_line_45_degrees", "top_line", 'Angle', 270)
                sketch = sketch.constrain("top_left_line_45_degrees", "top_line", 'Angle', 270)
                sketch = sketch.constrain("bottom_right_line_45_degrees", "bottom_line", 'Angle', 270)
                sketch = sketch.constrain("bottom_left_line_45_degrees", "bottom_line", 'Angle', 270)

            if c < f:
                assert 0
                sketch = sketch.circle(f, mode="a")

            sketch = sketch.solve().assemble()

            return sketch

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            if 'H' in dimensions and dimensions['H'] > 0:
                hole = (
                    cq.Workplane()
                    .cylinder(dimensions['B'], dimensions['H'] / 2)
                    .tag("hole")
                    .translate((0, 0, dimensions["B"] / 2))
                )
                piece = piece - hole

            piece = piece.translate((0, 0, -dimensions["B"]))
            return piece

    class Pm(P):
        def get_dimensions_and_subtypes(self):
            return {
                1: ["A", "B", "C", "D", "E", "F", "G", "H", "b", "t", "alpha"],
                2: ["A", "B", "C", "D", "E", "F", "G", "H", "b", "t", "alpha"]
            }

        def get_shape_base(self, data):
            dimensions = data["dimensions"]
            familySubtype = data["familySubtype"]

            h = dimensions["H"] / 2
            c = dimensions["C"] / 2
            g = dimensions["G"] / 2
            a = dimensions["A"] / 2
            e = dimensions["E"] / 2
            f = dimensions["F"] / 2
            b = dimensions["b"] / 2
            t = dimensions["t"]

            if 'alpha' not in dimensions or dimensions["alpha"] == 0:
                if familySubtype == '1':
                    dimensions["alpha"] = 120
                else:
                    dimensions["alpha"] = 90

            alpha = dimensions["alpha"] / 180 * math.pi

            beta = math.asin(g / e)
            gcos = e * math.cos(beta)

            wall_thickness = a - e
            # asin = a * math.sin(beta)
            # acos = a * math.cos(beta)

            external_slope = (gcos - c) / g
            a_corner_x = g + wall_thickness * math.sin(alpha / 2)
            a_corner_y = gcos + a_corner_x * external_slope
            alpha = dimensions["alpha"]

            if familySubtype == '1':
                sketch = (
                    cq.Sketch()
                    .arc((a_corner_x, -a_corner_y), (a, 0), (a_corner_x, a_corner_y), "top_arc")
                    .segment((a_corner_x, a_corner_y), (0, c), "side_top_left_line")
                    .segment((0, c), (-a_corner_x, a_corner_y), "side_bottom_left_line")
                    .arc((-a_corner_x, a_corner_y), (-a, 0), (-a_corner_x, -a_corner_y), "bottom_arc")
                    .segment((-a_corner_x, -a_corner_y), (0, -c), "side_bottom_right_line")
                    .segment((0, -c), (a_corner_x, -a_corner_y), "side_top_right_line")

                    .constrain("side_top_left_line", "side_top_right_line", "Angle", -alpha)
                    .constrain("side_bottom_left_line", "side_bottom_right_line", "Angle", alpha)
                    .constrain("top_arc", "Radius", a)
                    .constrain("bottom_arc", "Radius", a)
                    .constrain("bottom_arc", "top_arc", "Distance", (None, None, 0))
                    .constrain("top_arc", "side_top_left_line", 'Coincident', None)
                    .constrain("side_top_right_line", "top_arc", 'Coincident', None)
                    .constrain("side_bottom_left_line", "bottom_arc", 'Coincident', None)
                    .constrain("bottom_arc", "side_bottom_right_line", 'Coincident', None)
                    .constrain("side_top_left_line", "side_bottom_left_line", 'Coincident', None)
                    .constrain("side_bottom_right_line", "side_top_right_line", 'Coincident', None)
                )
            else:
                sketch = (
                    cq.Sketch()
                    .arc((a_corner_x, -a_corner_y / 1.3), (a, 0), (a_corner_x, a_corner_y / 1.3), "top_arc")
                    .segment((a_corner_x, a_corner_y / 1.3), (f / 2, c), "side_top_left_line")
                    .segment((f / 2, c), (0, c), "left_top_line")
                    .segment((0, c), (-f / 2, c), "left_bottom_line")
                    .segment((-f / 2, c), (-a_corner_x, a_corner_y / 1.3), "side_bottom_left_line")
                    .arc((-a_corner_x, a_corner_y / 1.3), (-a, 0), (-a_corner_x, -a_corner_y / 1.3), "bottom_arc")
                    .segment((-a_corner_x, -a_corner_y / 1.3), (-f / 2, -c), "side_bottom_right_line")
                    .segment((-f / 2, -c), (0, -c), "right_bottom_line")
                    .segment((0, -c), (f / 2, -c), "right_top_line")
                    .segment((f / 2, -c), (a_corner_x, -a_corner_y / 1.3), "side_top_right_line")

                    # .constrain("top_arc", "right_top_line", "Distance", (None, 0, c))

                    .constrain("top_arc", "side_top_left_line", 'Coincident', None)
                    .constrain("side_top_left_line", "left_top_line", 'Coincident', None)
                    .constrain("left_top_line", "left_bottom_line", 'Coincident', None)
                    .constrain("left_bottom_line", "side_bottom_left_line", 'Coincident', None)
                    .constrain("side_bottom_left_line", "bottom_arc", 'Coincident', None)
                    .constrain("bottom_arc", "side_bottom_right_line", 'Coincident', None)
                    .constrain("side_bottom_right_line", "right_bottom_line", 'Coincident', None)
                    .constrain("right_bottom_line", "right_top_line", 'Coincident', None)
                    .constrain("right_top_line", "side_top_right_line", 'Coincident', None)
                    .constrain("side_top_right_line", "top_arc", 'Coincident', None)

                    .constrain("top_arc", "Radius", a)
                    .constrain("bottom_arc", "Radius", a)
                    .constrain("bottom_arc", "top_arc", "Distance", (None, None, 0))

                    .constrain("side_bottom_right_line", "right_bottom_line", "Angle", 45)
                    .constrain("side_bottom_left_line", "left_bottom_line", "Angle", -45)
                    .constrain("side_top_right_line", "right_top_line", "Angle", -45)
                    .constrain("side_top_left_line", "left_top_line", "Angle", 45)
                    .constrain("side_top_left_line", "side_bottom_left_line", "Angle", alpha)
                    .constrain("side_top_right_line", "side_bottom_right_line", "Angle", alpha)

                    .constrain("left_top_line", "FixedPoint", 1)
                    .constrain("left_bottom_line", "FixedPoint", 0)
                    .constrain("right_bottom_line", "FixedPoint", 1)
                    .constrain("right_top_line", "FixedPoint", 0)

                    # .constrain("right_top_line", "left_top_line", "Distance", (0, 0, 2 * c))
                    # .constrain("right_bottom_line", "left_bottom_line", "Distance", (0, 0, 2 * c))

                    # .constrain("right_top_line", "right_bottom_line", "Angle", 0)
                    # .constrain("left_top_line", "left_bottom_line", "Angle", 0)
                    # .constrain("left_top_line", "right_top_line", "Angle", 0)

                    .constrain("left_top_line", 'Orientation', (1, 0))
                    .constrain("left_bottom_line", 'Orientation', (1, 0))
                    .constrain("right_bottom_line", 'Orientation', (1, 0))
                    .constrain("right_top_line", 'Orientation', (1, 0))


                )

            sketch = sketch.solve().assemble()
            return sketch

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            column = (
                cq.Workplane()
                .cylinder(dimensions['B'], dimensions['F'] / 2)
                .tag("column")
                .translate((0, 0, dimensions["B"] / 2))
            )
            piece = piece + column
            if 'H' in dimensions and dimensions['H'] > 0:
                hole = (
                    cq.Workplane()
                    .cylinder(dimensions['B'], dimensions['H'] / 2)
                    .tag("hole")
                    .translate((0, 0, dimensions["B"] / 2))
                )
                piece = piece - hole

            piece = piece.translate((0, 0, -dimensions["B"]))
            return piece

    class E(IPiece):
        def get_negative_winding_window(self, dimensions):

            winding_window_cube = (
                cq.Workplane()
                .box(dimensions["E"], dimensions["C"], dimensions["D"])
                .tag("winding_window_cube")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )

            central_column_cube = (
                cq.Workplane()
                .box(dimensions["F"], dimensions["C"], dimensions["D"])
                .tag("central_column_cube")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )
            negative_winding_window = winding_window_cube - central_column_cube

            return negative_winding_window

        def get_shape_base(self, data):
            dimensions = data["dimensions"]

            c = dimensions["C"] / 2
            a = dimensions["A"] / 2

            result = (
                cq.Sketch()
                .segment((-a, c), (a, c), "top_line")
                .segment((a, c), (a, -c), "right_line")
                .segment((a, -c), (-a, -c), "bottom_line")
                .segment((-a, -c), (-a, c), "left_line")

                .constrain("top_line", "right_line", 'Coincident', None)
                .constrain("right_line", "bottom_line", 'Coincident', None)
                .constrain("bottom_line", "left_line", 'Coincident', None)
                .constrain("left_line", "top_line", 'Coincident', None)
                .constrain("right_line", 'Orientation', (0, 1))
                .constrain("left_line", 'Orientation', (0, 1))
                .constrain("top_line", 'Orientation', (1, 0))
                .constrain("bottom_line", 'Orientation', (1, 0))
                .solve()
                .assemble()
            )

            return result

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]

            piece = piece.translate((0, 0, -dimensions["B"]))

            return piece

        def apply_machining(self, piece, machining, dimensions):
            length = dimensions["A"]
            if machining['coordinates'][0] == 0:
                width = dimensions["F"]
                length = dimensions["C"]
                y_coordinate = 0
                x_coordinate = 0
                if 'K' in dimensions:
                    length = dimensions["C"] - dimensions['K']
                    x_coordinate += dimensions['K']
            else:
                width = dimensions["A"] / 2
                if machining['coordinates'][0] < 0:
                    x_coordinate = -dimensions["A"] / 2
                if machining['coordinates'][0] > 0:
                    x_coordinate = dimensions["A"] / 2
                y_coordinate = 0

            height = machining['length']

            original_tool = cq.Workplane().box(width, length, height).translate((x_coordinate, y_coordinate, machining['coordinates'][1]))

            if machining['coordinates'][0] == 0:
                tool = original_tool
            else:
                # central_column_tool = document.addObject("Part::Box", "central_column_tool")
                central_column_width = dimensions["F"] * 1.001
                central_column_length = dimensions["C"] * 1.001
                if 'K' in dimensions:
                    central_column_length = (dimensions["C"] - dimensions['K'] * 2) * 1.001
                length = central_column_length
                width = central_column_width
                height = machining['length']
                central_column_tool = cq.Workplane().box(width, length, height).translate((0, 0, (machining['coordinates'][1] - machining['length'] / 2)))

                tool = original_tool - central_column_tool

            machined_piece = piece - tool

            return machined_piece

    class Er(E):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "G"]}

        def get_negative_winding_window(self, dimensions):
            winding_window_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['E'] / 2)
                .tag("winding_window_cylinder")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )

            central_column_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['F'] / 2)
                .tag("central_column_cylinder")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )
            winding_window = winding_window_cylinder - central_column_cylinder
            cuts = []

            if 'G' in dimensions and dimensions["G"] > dimensions["F"]:
                if dimensions["C"] > dimensions["F"]:
                    length = dimensions["G"]
                    width = dimensions["C"]
                    height = dimensions["D"]
                    translate = (0, 0, height / 2 + dimensions["B"] - dimensions["D"])
                    cube = (
                        cq.Workplane()
                        .box(length, width, height)
                        .tag("cube")
                        .translate(translate)
                    )

                    cube = cube - central_column_cylinder

                    cuts = [cube]
                else:
                    assert 0

            for cut in cuts:
                winding_window = winding_window + cut
            return winding_window

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            piece = piece.translate((0, 0, -dimensions["B"]))
            return piece

    class El(E):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "F2"]}

        def get_negative_winding_window(self, dimensions):

            column_width = dimensions["F2"] - dimensions["F"]
            column_length = dimensions["F"]
            column_height = dimensions["D"]
            translate = (0, 0, column_height / 2 + dimensions["B"] - dimensions["D"])
            column = (
                cq.Workplane()
                .box(column_length, column_width, column_height)
                .tag("column")
                .translate(translate)
            )
            translate = (0, dimensions["F2"] / 2 - dimensions["F"] / 2, column_height / 2 + dimensions["B"] - dimensions["D"])
            column_round_right = (
                cq.Workplane()
                .cylinder(column_height, dimensions["F"] / 2)
                .tag("column_round_right")
                .translate(translate)
            )
            translate = (0, -dimensions["F2"] / 2 + dimensions["F"] / 2, column_height / 2 + dimensions["B"] - dimensions["D"])
            column_round_left = (
                cq.Workplane()
                .cylinder(column_height, dimensions["F"] / 2)
                .tag("column_round_left")
                .translate(translate)
            )
            column = column + column_round_right
            column = column + column_round_left

            winding_window_cube = (
                cq.Workplane()
                .box(dimensions["E"], dimensions["C"], dimensions["D"])
                .tag("winding_window_cube")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )

            negative_winding_window = winding_window_cube - column

            return negative_winding_window

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            piece = piece.translate((0, 0, -dimensions["B"]))
            return piece

    class Etd(Er):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F"]}

    class Lp(Er):
        def get_dimensions_and_subtypes(self):
            return {
                1: ["A", "B", "C", "D", "E", "F", "G"],
            }

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            piece = piece.translate((0, 0, -dimensions["B"]))
            # fillet_radius = (dimensions["B"] - dimensions["D"]) / 2
            # piece = piece.edges("|X").edges("<Y").edges("<Z").fillet(fillet_radius)
            return piece

        def get_negative_winding_window(self, dimensions):

            winding_window_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['E'] / 2)
                .tag("winding_window_cylinder")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )

            central_column_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['F'] / 2)
                .tag("central_column_cylinder")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )
            negative_winding_window = winding_window_cylinder - central_column_cylinder

            length = dimensions["G"]
            width = dimensions["C"]
            height = dimensions["D"]
            translate = (0, width / 2 + dimensions["F"] / 2, height / 2 + (dimensions["B"] - dimensions["D"]))
            lateral_top_cube = (
                cq.Workplane()
                .box(length, width, height)
                .tag("lateral_top_cube")
                .translate(translate)
            )
            negative_winding_window = negative_winding_window + lateral_top_cube

            length = dimensions["E"]
            width = dimensions["C"]
            height = dimensions["D"]
            translate = (0, -width / 2, height / 2 + (dimensions["B"] - dimensions["D"]))
            lateral_bottom_cube = (
                cq.Workplane()
                .box(length, width, height)
                .tag("lateral_bottom_cube")
                .translate(translate)
            )
            lateral_bottom_cube = lateral_bottom_cube - central_column_cylinder
            negative_winding_window = negative_winding_window + lateral_bottom_cube
            return negative_winding_window

    class Eq(Er):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "G"]}

        def get_negative_winding_window(self, dimensions):
            winding_window_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['E'] / 2)
                .tag("winding_window_cylinder")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )

            central_column_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['F'] / 2)
                .tag("central_column_cylinder")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )
            winding_window = winding_window_cylinder - central_column_cylinder

            return winding_window

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            piece = piece.translate((0, 0, -dimensions["B"]))
            # fillet_radius = (dimensions["B"] - dimensions["D"]) / 2

            # piece = piece.edges("|X").edges("<Y").all()[2].fillet(fillet_radius)
            # piece = piece.edges("|X").edges(">Y").all()[0].fillet(fillet_radius)
            return piece

    class Ec(Er):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "T", "s"]}

        def get_shape_base(self, data):
            dimensions = data["dimensions"]

            c = dimensions["C"] / 2
            a = dimensions["A"] / 2
            t = dimensions["T"] / 2
            s = dimensions["s"] / 2

            result = (
                cq.Sketch()
                .segment((-a, c), (a, c), "top_line")
                .segment((a, c), (a, s), "right_line_top")
                .segment((a, s), (t + s, s), "right_dent_top")
                .arc((t + s, s), (t, 0), (t + s, -s), "right_dent_arc")
                .segment((t + s, -s), (a, -s), "right_dent_bottom")
                .segment((a, -s), (a, -c), "right_line_bottom")
                .segment((a, -c), (-a, -c), "bottom_line")

                .segment((-a, -c), (-a, -s), "left_line_bottom")
                .segment((-a, -s), (-(t + s), -s), "left_dent_bottom")
                .arc((-(t + s), -s), (-t, 0), (-(t + s), s), "left_dent_arc")
                .segment((-(t + s), s), (-a, s), "left_dent_bottom")
                .segment((-a, s), (-a, c), "left_line_top")

                .constrain("top_line", "right_line_top", 'Coincident', None)
                .constrain("right_line_top", "right_dent_top", 'Coincident', None)
                .constrain("right_dent_top", "right_dent_arc", 'Coincident', None)
                .constrain("right_dent_arc", "right_dent_bottom", 'Coincident', None)
                .constrain("right_dent_bottom", "right_line_bottom", 'Coincident', None)
                .constrain("right_line_bottom", "bottom_line", 'Coincident', None)
                .constrain("bottom_line", "left_line_bottom", 'Coincident', None)
                .constrain("left_line_bottom", "left_dent_bottom", 'Coincident', None)
                .constrain("left_dent_bottom", "left_dent_arc", 'Coincident', None)
                .constrain("left_dent_arc", "left_dent_bottom", 'Coincident', None)
                .constrain("left_dent_arc", "left_dent_bottom", 'Coincident', None)
                .constrain("left_dent_bottom", "left_line_top", 'Coincident', None)
                .constrain("left_line_top", "top_line", 'Coincident', None)

                .constrain("left_line_bottom", 'Orientation', (0, 1))
                .constrain("left_line_top", 'Orientation', (0, 1))
                .constrain("right_line_top", 'Orientation', (0, 1))
                .constrain("right_line_bottom", 'Orientation', (0, 1))
                .constrain("top_line", 'Orientation', (1, 0))
                .constrain("bottom_line", 'Orientation', (1, 0))
                .solve()
                .assemble()
            )

            return result

    class Ep(E):

        def get_shape_base(self, data):
            dimensions = data["dimensions"]

            a = dimensions["A"] / 2

            top_c = dimensions["C"] - dimensions["K"]
            bottom_c = dimensions["K"]

            sketch = (
                cq.Sketch()
                .segment((-a, top_c), (a, top_c), "top_line")
                .segment((a, top_c), (a, -bottom_c), "right_line")
                .segment((a, -bottom_c), (-a, -bottom_c), "bottom_line")
                .segment((-a, -bottom_c), (-a, top_c), "left_line")

                .constrain("top_line", "right_line", 'Coincident', None)
                .constrain("right_line", "bottom_line", 'Coincident', None)
                .constrain("bottom_line", "left_line", 'Coincident', None)
                .constrain("left_line", "top_line", 'Coincident', None)
                .constrain("right_line", 'Orientation', (0, 1))
                .constrain("left_line", 'Orientation', (0, 1))
                .constrain("top_line", 'Orientation', (1, 0))
                .constrain("bottom_line", 'Orientation', (1, 0))
                .solve()
                .assemble()
            )

            return sketch

        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "G", "K"]}

        def get_negative_winding_window(self, dimensions):

            winding_window_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['E'] / 2)
                .tag("winding_window_cylinder")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )

            central_column_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['F'] / 2)
                .tag("central_column_cylinder")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )
            negative_winding_window = winding_window_cylinder - central_column_cylinder

            if "G" in dimensions and dimensions['G'] > 0:
                length = dimensions["G"]
                width = dimensions["C"]
                height = dimensions["D"]
                translate = (0, width / 2 + dimensions["F"] / 2, height / 2 + (dimensions["B"] - dimensions["D"]))
                top_cube = (
                    cq.Workplane()
                    .box(length, width, height)
                    .tag("top_cube")
                    .translate(translate)
                )
                negative_winding_window = negative_winding_window + top_cube

            length = dimensions["E"]
            width = dimensions["C"]
            height = dimensions["D"]
            translate = (0, -width / 2, height / 2 + (dimensions["B"] - dimensions["D"]))
            bottom_cube = (
                cq.Workplane()
                .box(length, width, height)
                .tag("bottom_cube")
                .translate(translate)
            )
            bottom_cube = bottom_cube - central_column_cylinder
            negative_winding_window = negative_winding_window + bottom_cube
            return negative_winding_window

        def apply_machining(self, piece, machining, dimensions):
            if machining['coordinates'][0] == 0 and machining['coordinates'][2] == 0:
                # Gap in central column
                width = dimensions["F"]
                length = dimensions["F"]
                x_coordinate = 0
                y_coordinate = 0
            elif machining['coordinates'][0] != 0 and machining['coordinates'][2] == 0:
                # Gap in lateral column because they are not connected
                width = dimensions["A"] / 2
                length = dimensions["C"] * 2
                y_coordinate = 0
                if machining['coordinates'][0] < 0:
                    x_coordinate = -width / 2
                if machining['coordinates'][0] > 0:
                    x_coordinate = width / 2
            else:
                # Gap in lateral column but they are connected
                length = dimensions["C"] * 2
                width = dimensions["A"]
                x_coordinate = 0
                y_coordinate = 0

            height = machining['length']

            original_tool = cq.Workplane().box(width, length, height).translate((x_coordinate, y_coordinate, machining['coordinates'][1]))

            if machining['coordinates'][0] == 0 and machining['coordinates'][2] == 0:
                tool = original_tool
            else:
                central_column_tool = cq.Workplane().cylinder(dimensions["D"] * 2, dimensions["F"] / 2 * 1.2).translate((0, 0, (machining['coordinates'][1] - machining['length'] / 2)))

                tool = original_tool - central_column_tool

            machined_piece = piece - tool

            return machined_piece

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            piece = piece.translate((0, 0, -dimensions["B"]))
            return piece

    class Epx(E):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "G", "K"]}

        def get_shape_base(self, data):
            dimensions = data["dimensions"]

            a = dimensions["A"] / 2

            column_length = dimensions["K"] + dimensions["F"] / 2
            top_c = dimensions["C"] - column_length / 2
            bottom_c = column_length / 2

            sketch = (
                cq.Sketch()
                .segment((-a, top_c), (a, top_c), "top_line")
                .segment((a, top_c), (a, -bottom_c), "right_line")
                .segment((a, -bottom_c), (-a, -bottom_c), "bottom_line")
                .segment((-a, -bottom_c), (-a, top_c), "left_line")

                .constrain("top_line", "right_line", 'Coincident', None)
                .constrain("right_line", "bottom_line", 'Coincident', None)
                .constrain("bottom_line", "left_line", 'Coincident', None)
                .constrain("left_line", "top_line", 'Coincident', None)
                .constrain("right_line", 'Orientation', (0, 1))
                .constrain("left_line", 'Orientation', (0, 1))
                .constrain("top_line", 'Orientation', (1, 0))
                .constrain("bottom_line", 'Orientation', (1, 0))
                .solve()
                .assemble()
            )

            return sketch

        def get_negative_winding_window(self, dimensions):
            rectangular_part_width = dimensions["K"] - dimensions["F"] / 2

            winding_window_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['E'] / 2)
                .tag("winding_window_cylinder")
                .translate((0, rectangular_part_width / 2, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )

            column_width = dimensions["K"] + dimensions["F"] / 2
            length = dimensions["F"]
            height = dimensions["D"]
            translate = (0, 0, height / 2 + (dimensions["B"] - dimensions["D"]))
            central_column_center = (
                cq.Workplane()
                .box(length, rectangular_part_width, height)
                .tag("central_column_center")
                .translate(translate)
            )
            central_column_top_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['F'] / 2)
                .tag("central_column_top_cylinder")
                .translate((0, rectangular_part_width / 2, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )
            central_column_bottom_cylinder = (
                cq.Workplane()
                .cylinder(dimensions['D'], dimensions['F'] / 2)
                .tag("central_column_bottom_cylinder")
                .translate((0, -rectangular_part_width / 2, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )
            central_column = central_column_center + central_column_top_cylinder + central_column_bottom_cylinder

            negative_winding_window = winding_window_cylinder - central_column

            if "G" in dimensions and dimensions['G'] > 0:
                length = dimensions["G"]
                width = dimensions["C"]
                height = dimensions["D"]
                translate = (0, width / 2 + column_width / 2, height / 2 + (dimensions["B"] - dimensions["D"]))
                top_cube = (
                    cq.Workplane()
                    .box(length, width, height)
                    .tag("top_cube")
                    .translate(translate)
                )
                negative_winding_window = negative_winding_window + top_cube

            length = dimensions["E"]
            width = dimensions["C"]
            height = dimensions["D"]
            translate = (0, -width / 2 + rectangular_part_width / 2, height / 2 + (dimensions["B"] - dimensions["D"]))
            bottom_cube = (
                cq.Workplane()
                .box(length, width, height)
                .tag("bottom_cube")
                .translate(translate)
            )
            bottom_cube = bottom_cube - central_column
            negative_winding_window = negative_winding_window + bottom_cube
            return negative_winding_window

        def apply_machining(self, piece, machining, dimensions):
            if machining['coordinates'][0] == 0 and machining['coordinates'][2] == 0:
                # Gap in central column
                width = dimensions["F"]
                length = dimensions["K"] + dimensions["F"] / 2
                x_coordinate = 0
                y_coordinate = 0
            elif machining['coordinates'][0] != 0 and machining['coordinates'][2] == 0:
                # Gap in lateral column because they are not connected
                width = dimensions["A"] / 2
                length = dimensions["C"] * 2
                y_coordinate = 0
                if machining['coordinates'][0] < 0:
                    x_coordinate = -width / 2
                if machining['coordinates'][0] > 0:
                    x_coordinate = width / 2
            else:
                # Gap in lateral column but they are connected
                length = dimensions["C"] * 2
                width = dimensions["A"]
                x_coordinate = 0
                y_coordinate = 0

            height = machining['length']

            original_tool = cq.Workplane().box(width, length, height).translate((x_coordinate, y_coordinate, machining['coordinates'][1]))

            if machining['coordinates'][0] == 0 and machining['coordinates'][2] == 0:
                tool = original_tool
            else:
                rectangular_part_width = dimensions["K"] - dimensions["F"] / 2

                length = dimensions["F"]
                height = dimensions["D"] * 2
                translate = (0, 0, 0)
                central_column_center = (
                    cq.Workplane()
                    .box(length, rectangular_part_width, height)
                    .tag("central_column_center")
                    .translate(translate)
                )
                central_column_top_cylinder = (
                    cq.Workplane()
                    .cylinder(dimensions['D'], dimensions['F'] / 2)
                    .tag("central_column_top_cylinder")
                    .translate((0, rectangular_part_width / 2, 0))
                )
                central_column_bottom_cylinder = (
                    cq.Workplane()
                    .cylinder(dimensions['D'], dimensions['F'] / 2)
                    .tag("central_column_bottom_cylinder")
                    .translate((0, -rectangular_part_width / 2, 0))
                )
                central_column_tool = central_column_center + central_column_top_cylinder + central_column_bottom_cylinder
                tool = original_tool - central_column_tool

            machined_piece = piece - tool

            return machined_piece

    class Efd(E):
        def get_dimensions_and_subtypes(self):
            return {
                1: ["A", "B", "C", "D", "E", "F", "F2", "K", "q"],
                2: ["A", "B", "C", "D", "E", "F", "F2", "K", "q"]
            }

        def get_shape_base(self, data):
            dimensions = data["dimensions"]

            a = dimensions["A"] / 2

            top_c = dimensions["C"] - dimensions["K"] - dimensions["F2"] / 2
            bottom_c = dimensions["K"] + dimensions["F2"] / 2
            dent_height = dimensions["C"] * 2 / 5
            dent_top_width = dimensions["F"] / 2
            dent_bottom_width = dimensions["F"] / 2 - dimensions["q"]

            if dimensions["K"] > 0:
                minident_semiwidth = dimensions["F"] / 2 - dimensions["q"]
                minident_depth = dimensions["K"]
                sketch = (
                    cq.Sketch()
                    .segment((-a, top_c), (-dent_top_width, top_c), "top_line_left")
                    .segment((-dent_top_width, top_c), (-dent_bottom_width, top_c - dent_height), "dent_line_left")
                    .segment((-dent_bottom_width, top_c - dent_height), (dent_bottom_width, top_c - dent_height), "dent_line_bottom")
                    .segment((dent_bottom_width, top_c - dent_height), (dent_top_width, top_c), "dent_line_right")
                    .segment((dent_top_width, top_c), (a, top_c), "top_line_right")
                    .segment((a, top_c), (a, -bottom_c), "right_line")
                    .segment((a, -bottom_c), (minident_semiwidth, -bottom_c), "bottom_line_left")
                    .segment((minident_semiwidth, -bottom_c), (minident_semiwidth, -bottom_c + minident_depth), "minident_left_side")
                    .segment((minident_semiwidth, -bottom_c + minident_depth), (-minident_semiwidth, -bottom_c + minident_depth), "minident_bottom")
                    .segment((-minident_semiwidth, -bottom_c + minident_depth), (-minident_semiwidth, -bottom_c), "minident_right_side")
                    .segment((-minident_semiwidth, -bottom_c), (-a, -bottom_c), "bottom_line_right")
                    .segment((-a, -bottom_c), (-a, top_c), "left_line")

                    .constrain("top_line_left", "dent_line_left", 'Coincident', None)
                    .constrain("dent_line_left", "dent_line_bottom", 'Coincident', None)
                    .constrain("dent_line_bottom", "dent_line_right", 'Coincident', None)
                    .constrain("dent_line_right", "top_line_right", 'Coincident', None)
                    .constrain("top_line_right", "right_line", 'Coincident', None)
                    .constrain("right_line", "bottom_line_left", 'Coincident', None)
                    .constrain("bottom_line_left", "minident_left_side", 'Coincident', None)
                    .constrain("minident_left_side", "minident_bottom", 'Coincident', None)
                    .constrain("minident_bottom", "minident_right_side", 'Coincident', None)
                    .constrain("minident_right_side", "bottom_line_right", 'Coincident', None)
                    .constrain("bottom_line_right", "left_line", 'Coincident', None)
                    .constrain("left_line", "top_line_left", 'Coincident', None)
                    .constrain("right_line", 'Orientation', (0, 1))
                    .constrain("left_line", 'Orientation', (0, 1))
                    .constrain("top_line_left", 'Orientation', (1, 0))
                    .constrain("top_line_right", 'Orientation', (1, 0))
                    .constrain("bottom_line_left", 'Orientation', (1, 0))
                    .constrain("minident_bottom", 'Orientation', (1, 0))
                    .constrain("bottom_line_right", 'Orientation', (1, 0))
                    .constrain("minident_left_side", 'Orientation', (0, 1))
                    .constrain("minident_right_side", 'Orientation', (0, 1))
                    .constrain("dent_line_bottom", 'Orientation', (1, 0))
                    .solve()
                    .assemble()
                )
            else:
                sketch = (
                    cq.Sketch()
                    .segment((-a, top_c), (-dent_top_width, top_c), "top_line_left")
                    .segment((-dent_top_width, top_c), (-dent_bottom_width, top_c - dent_height), "dent_line_left")
                    .segment((-dent_bottom_width, top_c - dent_height), (dent_bottom_width, top_c - dent_height), "dent_line_bottom")
                    .segment((dent_bottom_width, top_c - dent_height), (dent_top_width, top_c), "dent_line_right")
                    .segment((dent_top_width, top_c), (a, top_c), "top_line_right")
                    .segment((a, top_c), (a, -bottom_c), "right_line")
                    .segment((a, -bottom_c), (-a, -bottom_c), "bottom_line")
                    .segment((-a, -bottom_c), (-a, top_c), "left_line")

                    .constrain("top_line_left", "dent_line_left", 'Coincident', None)
                    .constrain("dent_line_left", "dent_line_bottom", 'Coincident', None)
                    .constrain("dent_line_bottom", "dent_line_right", 'Coincident', None)
                    .constrain("dent_line_right", "top_line_right", 'Coincident', None)
                    .constrain("top_line_right", "right_line", 'Coincident', None)
                    .constrain("right_line", "bottom_line", 'Coincident', None)
                    .constrain("bottom_line", "left_line", 'Coincident', None)
                    .constrain("left_line", "top_line_left", 'Coincident', None)
                    .constrain("right_line", 'Orientation', (0, 1))
                    .constrain("left_line", 'Orientation', (0, 1))
                    .constrain("top_line_left", 'Orientation', (1, 0))
                    .constrain("top_line_right", 'Orientation', (1, 0))
                    .constrain("bottom_line", 'Orientation', (1, 0))
                    .constrain("dent_line_bottom", 'Orientation', (1, 0))
                    .solve()
                    .assemble()
                )

            return sketch

        def get_negative_winding_window(self, dimensions):

            winding_window_cube = (
                cq.Workplane()
                .box(dimensions["E"], dimensions["C"] * 2, dimensions["D"])
                .tag("winding_window_cube")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )
            return winding_window_cube

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]

            column = (
                cq.Workplane()
                .sketch()
                .rect(dimensions["F"], dimensions["F2"])
                .vertices()
                .chamfer(dimensions["q"])
                .finalize()
                .extrude(dimensions["B"])
                .translate((0, 0, 0))
            )
            piece = piece + column
            piece = piece.translate((0, 0, -dimensions["B"]))
            return piece

        def apply_machining(self, piece, machining, dimensions):
            length = dimensions["A"]
            if machining['coordinates'][0] == 0:
                width = dimensions["F"]
                length = dimensions["F2"]
                y_coordinate = 0
                x_coordinate = 0
            else:
                width = dimensions["A"] / 2
                if machining['coordinates'][0] < 0:
                    x_coordinate = -dimensions["A"] / 2
                if machining['coordinates'][0] > 0:
                    x_coordinate = dimensions["A"] / 2
                y_coordinate = 0

            height = machining['length']

            original_tool = cq.Workplane().box(width, length, height).translate((x_coordinate, y_coordinate, machining['coordinates'][1]))

            if machining['coordinates'][0] == 0:
                tool = original_tool
            else:
                central_column_width = dimensions["F"] * 1.001
                central_column_length = dimensions["F2"] * 1.001

                length = central_column_length
                width = central_column_width
                height = dimensions["D"] * 2
                central_column_tool = cq.Workplane().box(width, length, height).translate((0, 0, 0))

                tool = original_tool - central_column_tool

            machined_piece = piece - tool

            return machined_piece

    class U(IPiece):
        def get_shape_base(self, data):
            dimensions = data["dimensions"]

            c = dimensions["C"] / 2
            winding_column_width = (dimensions["A"] - dimensions["E"]) / 2
            left_a = dimensions["A"] - winding_column_width / 2
            right_a = winding_column_width / 2

            result = (
                cq.Sketch()
                .segment((right_a, c), (-left_a, c), "top_line")
                .segment((-left_a, c), (-left_a, -c), "left_line")
                .segment((-left_a, -c), (right_a, -c), "bottom_line")
                .segment((right_a, -c), (right_a, c), "right_line")

                .constrain("top_line", "left_line", 'Coincident', None)
                .constrain("left_line", "bottom_line", 'Coincident', None)
                .constrain("bottom_line", "right_line", 'Coincident', None)
                .constrain("right_line", "top_line", 'Coincident', None)
                .constrain("right_line", 'Orientation', (0, 1))
                .constrain("left_line", 'Orientation', (0, 1))
                .constrain("top_line", 'Orientation', (1, 0))
                .constrain("bottom_line", 'Orientation', (1, 0))
                .solve()
                .assemble()
            )

            return result

        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E"]}

        def get_negative_winding_window(self, dimensions):
            winding_column_width = (dimensions["A"] - dimensions["E"]) / 2
            negative_winding_window = (
                cq.Workplane()
                .box(dimensions["E"], dimensions["C"] * 2, dimensions["D"])
                .tag("negative_winding_window")
                .translate((-(winding_column_width / 2 + dimensions["E"] / 2), 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )
            return negative_winding_window

        def apply_machining(self, piece, machining, dimensions):
            winding_column_width = (dimensions["A"] - dimensions["E"]) / 2
            translate = convert_axis(machining['coordinates'])
            gap = (
                cq.Workplane()
                .box(winding_column_width, dimensions["C"], machining['length'])
                .tag("gap")
                .translate(translate)
            )

            machined_piece = piece - gap

            return machined_piece

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]

            piece = piece.translate((0, 0, -dimensions["B"]))
            return piece

    class Ur(IPiece):
        def get_dimensions_and_subtypes(self):
            return {
                1: ["A", "B", "C", "D", "H"],
                2: ["A", "B", "C", "D", "H"],
                3: ["A", "B", "C", "D", "F", "H"],
                4: ["A", "B", "C", "D", "F", "G", "H"]
            }

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            familySubtype = data["familySubtype"]
            if familySubtype == '1':
                winding_column_width = dimensions["C"]
                translate = (0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"]))
                winding_column = (
                    cq.Workplane()
                    .cylinder(dimensions["D"], dimensions["C"] / 2)
                    .tag("winding_column")
                    .translate(translate)
                )
                winding_column = winding_column.rotate((0, 0, 1), (0, 0, -1), 90)
                translate = (-(dimensions["A"] - winding_column_width / 2 - dimensions["H"] / 2), 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"]))
                lateral_column = (
                    cq.Workplane()
                    .box(dimensions["H"], dimensions["C"], dimensions["D"])
                    .tag("lateral_column")
                    .translate(translate)
                )
                piece += winding_column + lateral_column
            elif familySubtype == "2":
                winding_column_width = dimensions["C"]
                translate = (0, 0, dimensions["B"] / 2)
                winding_column = (
                    cq.Workplane()
                    .cylinder(dimensions["B"], dimensions["C"] / 2)
                    .tag("winding_column")
                    .translate(translate)
                )
                translate = (-(dimensions["A"] - winding_column_width), 0, dimensions["B"] / 2)
                lateral_column = (
                    cq.Workplane()
                    .cylinder(dimensions["B"], dimensions["C"] / 2)
                    .tag("lateral_column")
                    .translate(translate)
                )
                piece += winding_column + lateral_column
            elif familySubtype == "3":
                winding_column_width = dimensions["F"]
                translate = (0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"]))
                winding_column = (
                    cq.Workplane()
                    .cylinder(dimensions["D"], dimensions["F"] / 2)
                    .tag("winding_column")
                    .translate(translate)
                )
                translate = (-(dimensions["A"] - winding_column_width / 2 - dimensions["H"] / 2), 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"]))
                lateral_column = (
                    cq.Workplane()
                    .box(dimensions["H"], dimensions["C"], dimensions["D"])
                    .tag("lateral_column")
                    .translate(translate)
                )
                piece += winding_column + lateral_column
            elif familySubtype == "4":
                winding_column_width = dimensions["C"]
                translate = (0, 0, dimensions["B"] / 2)
                winding_column = (
                    cq.Workplane()
                    .cylinder(dimensions["B"], dimensions["F"] / 2)
                    .tag("winding_column")
                    .translate(translate)
                )
                translate = (-(dimensions["A"] - dimensions["F"] / 2 - dimensions["F"] / 2), 0, dimensions["B"] / 2)
                lateral_column = (
                    cq.Workplane()
                    .cylinder(dimensions["B"], dimensions["F"] / 2)
                    .tag("lateral_column")
                    .translate(translate)
                )
                piece += winding_column + lateral_column

            if "S" in dimensions and dimensions["S"] > 0:
                if "F" in dimensions and dimensions["F"] > 0:
                    winding_column_width = dimensions["F"]
                else:
                    winding_column_width = dimensions["C"]

                if "H" in dimensions and dimensions["H"] > 0:
                    lateral_column_width = dimensions["H"]
                else:
                    lateral_column_width = dimensions["F"]

                if familySubtype == '1':
                    lateral_column_width += dimensions["C"] - dimensions["H"]

                translate = (-(dimensions["A"] - lateral_column_width / 2 - dimensions["S"] / 2), 0, dimensions["B"] / 2)
                lateral_hole_round_left = (
                    cq.Workplane()
                    .cylinder(dimensions["B"], dimensions["S"] / 2)
                    .tag("lateral_hole_round_left")
                    .translate(translate)
                )

                translate = (-(dimensions["A"] - lateral_column_width / 2 - dimensions["S"] / 4), 0, dimensions["B"] / 2)
                lateral_hole_rectangular_left = (
                    cq.Workplane()
                    .box(dimensions["S"] / 2, dimensions["S"], dimensions["B"])
                    .tag("lateral_hole_rectangular_left")
                    .translate(translate)
                )
                piece -= lateral_hole_round_left + lateral_hole_rectangular_left

                translate = (winding_column_width / 2 - dimensions["S"] / 2, 0, dimensions["B"] / 2)
                lateral_hole_round_right = (
                    cq.Workplane()
                    .cylinder(dimensions["B"], dimensions["S"] / 2)
                    .tag("lateral_hole_round_right")
                    .translate(translate)
                )

                translate = (winding_column_width / 2 - dimensions["S"] / 4, 0, dimensions["B"] / 2)
                lateral_hole_rectangular_right = (
                    cq.Workplane()
                    .box(dimensions["S"] / 2, dimensions["S"], dimensions["B"])
                    .tag("lateral_hole_rectangular_right")
                    .translate(translate)
                )
                piece -= lateral_hole_round_right + lateral_hole_rectangular_right

            piece = piece.translate((0, 0, -dimensions["B"]))
            return piece

        def get_shape_base(self, data):
            dimensions = data["dimensions"]
            familySubtype = data["familySubtype"]
            if familySubtype == "1":
                c = dimensions["C"] / 2
                winding_column_width = dimensions["C"]
                left_a = dimensions["A"] - winding_column_width / 2
                right_a = winding_column_width / 2

                result = (
                    cq.Sketch()
                    .segment((0, c), (-left_a, c), "top_line")
                    .segment((-left_a, c), (-left_a, -c), "left_line")
                    .segment((-left_a, -c), (0, -c), "bottom_line")
                    .arc((0, -c), (right_a, 0), (0, c), "right_arc")

                    .constrain("top_line", "left_line", 'Coincident', None)
                    .constrain("left_line", "bottom_line", 'Coincident', None)
                    .constrain("bottom_line", "right_arc", 'Coincident', None)
                    .constrain("right_arc", "top_line", 'Coincident', None)
                    .constrain("left_line", 'Orientation', (0, 1))
                    .constrain("top_line", 'Orientation', (1, 0))
                    .constrain("bottom_line", 'Orientation', (1, 0))
                    .solve()
                    .assemble()
                )
            elif familySubtype == "2" or familySubtype == "4":
                c = dimensions["C"] / 2
                if familySubtype == "4":
                    winding_column_width = dimensions["F"]
                else:
                    winding_column_width = dimensions["C"]
                left_a = dimensions["A"] - winding_column_width

                result = (
                    cq.Sketch()
                    .segment((0, c), (-left_a, c), "top_line")
                    .segment((-left_a, c), (-left_a, -c), "left_line")
                    .segment((-left_a, -c), (0, -c), "bottom_line")
                    .segment((0, c), (0, -c), "right_line")

                    .constrain("top_line", "left_line", 'Coincident', None)
                    .constrain("left_line", "bottom_line", 'Coincident', None)
                    .constrain("bottom_line", "right_line", 'Coincident', None)
                    .constrain("right_line", "top_line", 'Coincident', None)
                    .constrain("right_line", 'Orientation', (0, 1))
                    .constrain("left_line", 'Orientation', (0, 1))
                    .constrain("top_line", 'Orientation', (1, 0))
                    .constrain("bottom_line", 'Orientation', (1, 0))
                    .solve()
                    .assemble()
                )
            elif familySubtype == "3":
                c = dimensions["C"] / 2
                winding_column_width = dimensions["F"]
                left_a = dimensions["A"] - winding_column_width / 2
                right_a = winding_column_width / 2

                result = (
                    cq.Sketch()
                    .segment((0, c), (-left_a, c), "top_line")
                    .segment((-left_a, c), (-left_a, -c), "left_line")
                    .segment((-left_a, -c), (0, -c), "bottom_line")
                    .arc((0, -c), (right_a, 0), (0, c), "right_arc")

                    .constrain("top_line", "left_line", 'Coincident', None)
                    .constrain("left_line", "bottom_line", 'Coincident', None)
                    .constrain("bottom_line", "right_arc", 'Coincident', None)
                    .constrain("right_arc", "top_line", 'Coincident', None)
                    .constrain("left_line", 'Orientation', (0, 1))
                    .constrain("top_line", 'Orientation', (1, 0))
                    .constrain("bottom_line", 'Orientation', (1, 0))
                    .solve()
                    .assemble()
                )

            return result

        def get_negative_winding_window(self, dimensions):
            negative_winding_window = (
                cq.Workplane()
                .box(dimensions["A"] * 2, dimensions["C"] * 2, dimensions["D"])
                .tag("negative_winding_window")
                .translate((0, 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )
            return negative_winding_window

        def apply_machining(self, piece, machining, dimensions):
            winding_column_width = max([dimensions["C"], dimensions["H"]])
            translate = convert_axis(machining['coordinates'])
            gap = (
                cq.Workplane()
                .box(winding_column_width, dimensions["C"] * 2, machining['length'])
                .tag("gap")
                .translate(translate)
            )

            machined_piece = piece - gap

            return machined_piece

        def add_dimensions_and_export_view(self, data, original_dimensions, view, project_name, margin, colors, save_files, piece):
            raise NotImplementedError

    class T(IPiece):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C"]}

        def get_negative_winding_window(self, dimensions):
            return None

        def get_shape_base(self, data):
            dimensions = data["dimensions"]

            b = dimensions["B"] / 2
            a = dimensions["A"] / 2

            result = (
                cq.Sketch()
                .circle(a)
                .circle(b, mode="s")
            )

            return result

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            c = dimensions["C"] / 2

            piece = piece.translate((0, 0, -c))
            piece = piece.rotate((0, 1, 0), (0, -1, 0), 90)
            return piece

    class C(IPiece):
        def get_shape_base(self, data):
            dimensions = data["dimensions"]

            c = dimensions["C"] / 2
            winding_column_width = (dimensions["A"] - dimensions["E"]) / 2
            left_a = dimensions["A"] - winding_column_width / 2
            right_a = winding_column_width / 2

            result = (
                cq.Sketch()
                .segment((right_a, c), (-left_a, c), "top_line")
                .segment((-left_a, c), (-left_a, -c), "left_line")
                .segment((-left_a, -c), (right_a, -c), "bottom_line")
                .segment((right_a, -c), (right_a, c), "right_line")

                .constrain("top_line", "left_line", 'Coincident', None)
                .constrain("left_line", "bottom_line", 'Coincident', None)
                .constrain("bottom_line", "right_line", 'Coincident', None)
                .constrain("right_line", "top_line", 'Coincident', None)
                .constrain("right_line", 'Orientation', (0, 1))
                .constrain("left_line", 'Orientation', (0, 1))
                .constrain("top_line", 'Orientation', (1, 0))
                .constrain("bottom_line", 'Orientation', (1, 0))
                .solve()
                .assemble()
            )

            return result

        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E"]}

        def get_negative_winding_window(self, dimensions):
            winding_column_width = (dimensions["A"] - dimensions["E"]) / 2
            negative_winding_window = (
                cq.Workplane()
                .box(dimensions["E"], dimensions["C"] * 2, dimensions["D"])
                .tag("negative_winding_window")
                .translate((-(winding_column_width / 2 + dimensions["E"] / 2), 0, dimensions["D"] / 2 + (dimensions["B"] - dimensions["D"])))
            )
            return negative_winding_window

        def apply_machining(self, piece, machining, dimensions):
            winding_column_width = (dimensions["A"] - dimensions["E"]) / 2
            translate = convert_axis(machining['coordinates'])
            gap = (
                cq.Workplane()
                .box(winding_column_width, dimensions["C"], machining['length'])
                .tag("gap")
                .translate(translate)
            )

            machined_piece = piece - gap

            return machined_piece

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            fillet_radius = (dimensions["A"] - dimensions["E"]) / 2

            piece = piece.translate((0, 0, -(dimensions["B"] - dimensions["D"]) / 2))
            # piece = piece.edges("|Y").edges("<Z").all().fillet(fillet_radius)
            piece = piece.edges("|Y").edges("<Z").fillet(fillet_radius)
            piece = piece.translate((0, 0, (dimensions["B"] - dimensions["D"]) / 2))

            piece = piece.translate((0, 0, -dimensions["B"]))
            return piece


    class IBobbin(metaclass=ABCMeta):
        def __init__(self):
            self.output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../output/'

        def set_output_path(self, output_path):
            self.output_path = output_path

        @abstractmethod
        def get_bobbin_body(self, data, winding_window):
            raise NotImplementedError

        @abstractmethod
        def get_bobbin_flanges(self, data, winding_window):
            raise NotImplementedError

        @abstractmethod
        def get_mounting_pins(self, data, outer_radius):
            raise NotImplementedError

        def get_bobbin(self, data, winding_window, name="Bobbin", save_files=False, export_files=True):
            try:
                project_name = f"{name}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                dims = data.get("dimensions", {})

                body = self.get_bobbin_body(data, winding_window)
                flanges = self.get_bobbin_flanges(data, winding_window)

                bobbin = body
                if flanges is not None:
                    bobbin = bobbin + flanges

                if dims.get("pinCount", 0) > 0:
                    ww_width = winding_window.get("width", 0)
                    ww_height = winding_window.get("height", 0)
                    flange_extension = dims.get("flangeExtension", 0.002)  # 2mm in meters
                    if ww_width > ww_height:
                        outer_radius = ww_width / 2 + dims.get("wallThickness", 0.0005) + flange_extension
                    else:
                        outer_radius = ww_height / 2 + dims.get("wallThickness", 0.0005) + flange_extension
                    pins = self.get_mounting_pins(data, outer_radius)
                    if pins is not None:
                        bobbin = bobbin + pins

                coords = data.get("coordinates", [0, 0, 0])
                rotation = data.get("rotation", [0, 0, 0])

                if rotation[0] != 0:
                    bobbin = bobbin.rotate((1, 0, 0), (-1, 0, 0), rotation[0] / math.pi * 180)
                if rotation[1] != 0:
                    bobbin = bobbin.rotate((0, 1, 0), (0, -1, 0), rotation[1] / math.pi * 180)
                if rotation[2] != 0:
                    bobbin = bobbin.rotate((0, 0, 1), (0, 0, -1), rotation[2] / math.pi * 180)

                bobbin = bobbin.translate(convert_axis(coords))

                pathlib.Path(self.output_path).mkdir(parents=True, exist_ok=True)

                if export_files:
                    from cadquery import exporters
                    scaled_bobbin = bobbin.newObject([o.scale(1000) for o in bobbin.objects])
                    exporters.export(scaled_bobbin, f"{self.output_path}/{project_name}.step", "STEP")
                    exporters.export(scaled_bobbin, f"{self.output_path}/{project_name}.stl", "STL")
                    return f"{self.output_path}/{project_name}.step", f"{self.output_path}/{project_name}.stl"
                else:
                    return bobbin

            except Exception:
                return (None, None) if export_files else None

    class StandardBobbin(IBobbin):
        def get_bobbin_body(self, data, winding_window):
            # All dimensions in meters (same as core) - will be scaled at export
            dims = data.get("dimensions", {})
            wall_thickness = dims.get("wallThickness", 0.0005)
            ww_width = winding_window.get("width", 0)
            ww_height = winding_window.get("height", 0)
            column_shape = winding_window.get("columnShape", "rectangular")
            column_width = winding_window.get("columnWidth", 0)
            column_depth = winding_window.get("columnDepth", column_width)

            # Bobbin tube height (along core axis)
            tube_height = ww_height

            if column_shape == "round":
                # For round columns, create cylindrical bobbin
                # Inner radius = column radius (half of column width/diameter)
                # If column width not provided, estimate from winding window X coordinate
                if column_width > 0:
                    inner_radius = column_width / 2
                else:
                    # Fallback: use winding window X coordinate as column radius
                    ww_coords = winding_window.get("coordinates", [0, 0])
                    inner_radius = abs(ww_coords[0]) if ww_coords[0] != 0 else ww_width * 0.5

                # Outer radius limited by core depth if needed
                max_outer_radius = column_depth / 2 if column_depth > 0 else inner_radius + wall_thickness
                outer_radius = min(inner_radius + wall_thickness, max_outer_radius)

                # Create cylindrical tube
                outer_cyl = (
                    cq.Workplane("XY")
                    .cylinder(tube_height, outer_radius)
                    .translate((0, 0, 0))
                )

                inner_cyl = (
                    cq.Workplane("XY")
                    .cylinder(tube_height * 1.1, inner_radius)
                    .translate((0, 0, 0))
                )

                body = outer_cyl - inner_cyl
            else:
                # Rectangular bobbin for E-cores etc.
                depth = winding_window.get("radialHeight", ww_width) if winding_window.get("radialHeight") else ww_width

                outer_width = ww_width + wall_thickness * 2
                outer_depth = depth + wall_thickness * 2

                outer_box = (
                    cq.Workplane("XY")
                    .box(outer_width, outer_depth, tube_height)
                )

                inner_box = (
                    cq.Workplane("XY")
                    .box(ww_width, depth, tube_height * 1.1)
                )

                central_hole_width = depth * 0.8
                central_hole_depth = depth * 0.8

                central_hole = (
                    cq.Workplane("XY")
                    .box(central_hole_width, central_hole_depth, tube_height * 1.2)
                )

                body = outer_box - inner_box - central_hole

            # Bobbin tube is created along Z axis which matches the core's vertical axis
            # No rotation needed

            return body

        def get_bobbin_flanges(self, data, winding_window):
            # All dimensions in meters (same as core) - will be scaled at export
            dims = data.get("dimensions", {})
            wall_thickness = dims.get("wallThickness", 0.0005)
            flange_thickness = dims.get("flangeThickness", 0.001)
            flange_extension = dims.get("flangeExtension", 0.002)

            ww_width = winding_window.get("width", 0)
            ww_height = winding_window.get("height", 0)
            column_shape = winding_window.get("columnShape", "rectangular")
            column_width = winding_window.get("columnWidth", 0)
            column_depth = winding_window.get("columnDepth", column_width)

            if column_shape == "round":
                # Use column dimensions if available
                if column_width > 0:
                    inner_radius = column_width / 2
                else:
                    ww_coords = winding_window.get("coordinates", [0, 0])
                    inner_radius = abs(ww_coords[0]) if ww_coords[0] != 0 else ww_width * 0.5
                outer_radius = inner_radius + wall_thickness

                # Flange dimensions - rectangular to fit core geometry
                # X direction: extends to fill winding window
                flange_outer_x = inner_radius + ww_width + flange_extension
                # Y direction: limited by core depth (column_depth), no extension to fit inside core
                flange_half_y = column_depth / 2 if column_depth > 0 else inner_radius

                # Top flange (rectangular box with cylindrical hole for column)
                top_flange_solid = (
                    cq.Workplane("XY")
                    .box(flange_outer_x * 2, flange_half_y * 2, flange_thickness)
                    .translate((0, 0, ww_height / 2 + flange_thickness / 2))
                )

                top_hole = (
                    cq.Workplane("XY")
                    .cylinder(flange_thickness * 1.1, inner_radius)
                    .translate((0, 0, ww_height / 2 + flange_thickness / 2))
                )

                top_flange = top_flange_solid - top_hole

                # Bottom flange
                bottom_flange_solid = (
                    cq.Workplane("XY")
                    .box(flange_outer_x * 2, flange_half_y * 2, flange_thickness)
                    .translate((0, 0, -(ww_height / 2 + flange_thickness / 2)))
                )

                bottom_hole = (
                    cq.Workplane("XY")
                    .cylinder(flange_thickness * 1.1, inner_radius)
                    .translate((0, 0, -(ww_height / 2 + flange_thickness / 2)))
                )

                bottom_flange = bottom_flange_solid - bottom_hole

                flanges = top_flange + bottom_flange
            else:
                depth = winding_window.get("radialHeight", ww_width) if winding_window.get("radialHeight") else ww_width

                outer_width = ww_width + wall_thickness * 2
                outer_depth = depth + wall_thickness * 2

                flange_width = outer_width + flange_extension * 2
                flange_depth = outer_depth + flange_extension * 2

                central_hole_width = depth * 0.8
                central_hole_depth = depth * 0.8

                top_flange_solid = (
                    cq.Workplane("XY")
                    .box(flange_width, flange_depth, flange_thickness)
                    .translate((0, 0, ww_height / 2 + flange_thickness / 2))
                )

                top_hole = (
                    cq.Workplane("XY")
                    .box(central_hole_width, central_hole_depth, flange_thickness * 1.1)
                    .translate((0, 0, ww_height / 2 + flange_thickness / 2))
                )

                top_flange = top_flange_solid - top_hole

                bottom_flange_solid = (
                    cq.Workplane("XY")
                    .box(flange_width, flange_depth, flange_thickness)
                    .translate((0, 0, -(ww_height / 2 + flange_thickness / 2)))
                )

                bottom_hole = (
                    cq.Workplane("XY")
                    .box(central_hole_width, central_hole_depth, flange_thickness * 1.1)
                    .translate((0, 0, -(ww_height / 2 + flange_thickness / 2)))
                )

                bottom_flange = bottom_flange_solid - bottom_hole

                flanges = top_flange + bottom_flange

            # Flanges are created along Z axis which matches the core's vertical axis
            # No rotation needed

            return flanges

        def get_mounting_pins(self, data, outer_radius):
            # All dimensions in meters (same as core) - will be scaled at export
            dims = data.get("dimensions", {})
            pin_count = dims.get("pinCount", 0)
            if pin_count == 0:
                return None

            pin_diameter = dims.get("pinDiameter", 0.0008)
            pin_length = dims.get("pinLength", 0.003)
            flange_thickness = dims.get("flangeThickness", 0.001)
            ww_height = outer_radius

            pins = None
            angle_step = 360 / pin_count

            for i in range(pin_count):
                angle = math.radians(i * angle_step)
                x = ww_height * 0.8 * math.cos(angle)
                z = ww_height * 0.8 * math.sin(angle)

                pin = (
                    cq.Workplane("XZ")
                    .cylinder(pin_length, pin_diameter / 2)
                    .translate((x, -(flange_thickness + pin_length / 2), z))
                )

                if pins is None:
                    pins = pin
                else:
                    pins = pins + pin

            return pins

    class IWinding(metaclass=ABCMeta):
        def __init__(self):
            self.output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../output/'

        def set_output_path(self, output_path):
            self.output_path = output_path

        @abstractmethod
        def get_single_turn(self, data, position, turn_index):
            raise NotImplementedError

        @abstractmethod
        def get_layer(self, data, layer_index, bobbin_inner_dims):
            raise NotImplementedError

        def calculate_turn_positions(self, data, bobbin_inner_height):
            # All dimensions in meters (same as core) - will be scaled at export
            wire_diameter = data.get("wireDiameter", 0.0005)
            insulation = data.get("insulationThickness", 0.00005)
            total_wire_diameter = wire_diameter + 2 * insulation
            num_turns = data.get("numberOfTurns", 1)
            num_layers = data.get("numberOfLayers", 1)

            turns_per_layer = num_turns // num_layers
            positions = []

            for layer in range(num_layers):
                for turn in range(turns_per_layer):
                    y_pos = -bobbin_inner_height / 2 + total_wire_diameter / 2 + turn * total_wire_diameter
                    positions.append({
                        "layer": layer,
                        "turn": turn,
                        "y": y_pos,
                        "layer_offset": layer * total_wire_diameter
                    })

            return positions

        def get_winding(self, data, bobbin_dims, name="Winding", save_files=False, export_files=True):
            try:
                project_name = f"{name}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")

                # Check for MAS turnsDescription data
                turns_description = data.get("turnsDescription", [])
                winding_name = data.get("windingName", name)

                if turns_description:
                    # MAS Mode: Use exact coordinates from turnsDescription
                    wire_diameter = data.get("wireDiameter")
                    winding = self.get_winding_from_mas(turns_description, winding_name, wire_diameter)

                    if winding is None:
                        # Fall through to calculation if no matching turns
                        turns_description = []

                if not turns_description:
                    # Fallback Mode: Calculate positions
                    num_turns = data.get("numberOfTurns", 1)

                    if num_turns > 100:
                        winding = self.get_bulk_winding(data, bobbin_dims)
                    else:
                        winding = self.get_detailed_winding(data, bobbin_dims)

                if winding is None:
                    return (None, None) if export_files else None

                coords = data.get("coordinates", [0, 0, 0])
                rotation = data.get("rotation", [0, 0, 0])

                if rotation[0] != 0:
                    winding = winding.rotate((1, 0, 0), (-1, 0, 0), rotation[0] / math.pi * 180)
                if rotation[1] != 0:
                    winding = winding.rotate((0, 1, 0), (0, -1, 0), rotation[1] / math.pi * 180)
                if rotation[2] != 0:
                    winding = winding.rotate((0, 0, 1), (0, 0, -1), rotation[2] / math.pi * 180)

                winding = winding.translate(convert_axis(coords))

                pathlib.Path(self.output_path).mkdir(parents=True, exist_ok=True)

                if export_files:
                    from cadquery import exporters
                    scaled_winding = winding.newObject([o.scale(1000) for o in winding.objects])
                    exporters.export(scaled_winding, f"{self.output_path}/{project_name}.step", "STEP")
                    exporters.export(scaled_winding, f"{self.output_path}/{project_name}.stl", "STL")
                    return f"{self.output_path}/{project_name}.step", f"{self.output_path}/{project_name}.stl"
                else:
                    return winding

            except Exception:
                return (None, None) if export_files else None

        def get_bulk_winding(self, data, bobbin_dims):
            # All dimensions in meters (same as core) - will be scaled at export
            wire_diameter = data.get("wireDiameter", 0.0005)
            insulation = data.get("insulationThickness", 0.00005)
            num_turns = data.get("numberOfTurns", 1)
            num_layers = data.get("numberOfLayers", 1)
            total_wire_diameter = wire_diameter + 2 * insulation

            ww_height = bobbin_dims.get("height", 0.01)
            ww_width = bobbin_dims.get("width", 0.005)

            layer_thickness = total_wire_diameter * num_layers
            winding_length = ww_height * 0.9

            # Create bulk as a toroidal approximation around Z axis (core column axis)
            bulk = (
                cq.Workplane("XY")
                .box(layer_thickness, ww_width * 0.8, winding_length)
                .translate((ww_width / 2 + layer_thickness / 2, 0, 0))
            )

            return bulk

        @abstractmethod
        def get_detailed_winding(self, data, bobbin_dims):
            raise NotImplementedError

    class RoundWireWinding(IWinding):
        def get_single_turn(self, data, position, turn_index):
            # All dimensions in meters (same as core) - will be scaled at export
            wire_diameter = data.get("wireDiameter", 0.0005)
            winding_direction = data.get("windingDirection", "cw")

            radius = position.get("radius", 0.005)
            y_pos = position.get("y", 0)
            layer_offset = position.get("layer_offset", 0)

            turn_radius = radius + layer_offset

            if winding_direction == "cw":
                direction = 1
            else:
                direction = -1

            # Create circle path in XY plane (perpendicular to Z axis, which is the core column axis)
            path = (
                cq.Workplane("XY")
                .center(0, 0)
                .circle(turn_radius)
            )

            # Wire profile perpendicular to the path
            wire_profile = (
                cq.Workplane("XZ")
                .center(turn_radius, 0)
                .circle(wire_diameter / 2)
            )

            turn = wire_profile.sweep(path, isFrenet=True)
            # Stack turns along Z axis (core column axis)
            turn = turn.translate((0, 0, y_pos))

            return turn

        def create_turn_from_description(self, turn_desc: TurnDescription, wire_diameter: float = None):
            """
            Create a single turn from MAS TurnDescription.

            Coordinate mapping (from full-magnetic branch):
            - coordinates[0] = radial position from center axis
            - coordinates[1] = vertical position (Z axis)

            Args:
                turn_desc: TurnDescription object with exact coordinates
                wire_diameter: Override wire diameter (uses dimensions if None)

            Returns:
                CadQuery Workplane with turn geometry
            """
            # Extract coordinates
            radial_pos = turn_desc.coordinates[0]  # Distance from Z axis
            z_pos = turn_desc.coordinates[1]       # Height along Z axis

            # Get wire diameter from dimensions or fallback
            if wire_diameter is None:
                if turn_desc.dimensions:
                    wire_diameter = turn_desc.dimensions[0]
                else:
                    wire_diameter = 0.0005  # Default 0.5mm

            # Create circular path in XY plane around Z axis
            path = (
                cq.Workplane("XY")
                .center(0, 0)
                .circle(radial_pos)
            )

            # Create wire cross-section profile
            wire_profile = (
                cq.Workplane("XZ")
                .center(radial_pos, 0)
                .circle(wire_diameter / 2)
            )

            # Sweep and position
            turn = wire_profile.sweep(path, isFrenet=True)
            turn = turn.translate((0, 0, z_pos))

            return turn

        def get_winding_from_mas(self, turns_description: list, winding_name: str, wire_diameter: float = None):
            """
            Create winding geometry from MAS turnsDescription array.

            Args:
                turns_description: List of turn dicts from MAS coil.turnsDescription
                winding_name: Name to filter turns (e.g., "Primary", "Secondary")
                wire_diameter: Override wire diameter for all turns

            Returns:
                CadQuery Workplane with all turns, or None if no matching turns
            """
            # Convert dicts to TurnDescription objects and filter by winding name
            all_turns = [TurnDescription.from_dict(t) for t in turns_description]
            winding_turns = [t for t in all_turns if t.winding == winding_name]

            if not winding_turns:
                # Try partial match (e.g., "Primary" matches "Primary section 0")
                winding_turns = [t for t in all_turns if winding_name in t.winding]

            if not winding_turns:
                return None

            winding = None
            for turn_desc in winding_turns:
                turn = self.create_turn_from_description(turn_desc, wire_diameter)

                if winding is None:
                    winding = turn
                else:
                    winding = winding + turn

            return winding

        def get_layer(self, data, layer_index, bobbin_inner_dims):
            # All dimensions in meters (same as core) - will be scaled at export
            wire_diameter = data.get("wireDiameter", 0.0005)
            insulation = data.get("insulationThickness", 0.00005)
            total_wire_diameter = wire_diameter + 2 * insulation
            num_turns = data.get("numberOfTurns", 1)
            num_layers = data.get("numberOfLayers", 1)

            ww_height = bobbin_inner_dims.get("height", 0.01)
            ww_width = bobbin_inner_dims.get("width", 0.005)
            column_width = bobbin_inner_dims.get("columnWidth", 0)
            column_shape = bobbin_inner_dims.get("columnShape", "rectangular")

            turns_per_layer = num_turns // num_layers
            layer = None

            # Calculate base radius - for round columns use column radius + bobbin wall + wire offset
            if column_shape == "round" and column_width > 0:
                # Winding wraps around the bobbin which wraps around the column
                wall_thickness = 0.0005  # Default bobbin wall thickness in meters
                base_radius = column_width / 2 + wall_thickness + total_wire_diameter / 2
            else:
                base_radius = ww_width / 2 + total_wire_diameter / 2

            for turn_idx in range(turns_per_layer):
                # Stack turns along Z axis (core column axis)
                z_pos = -ww_height / 2 + total_wire_diameter / 2 + turn_idx * total_wire_diameter

                if z_pos > ww_height / 2 - total_wire_diameter / 2:
                    break

                position = {
                    "radius": base_radius,
                    "y": z_pos,  # Using 'y' key for backward compatibility, but it's actually Z position
                    "layer_offset": layer_index * total_wire_diameter
                }

                turn = self.get_single_turn(data, position, turn_idx)

                if layer is None:
                    layer = turn
                else:
                    layer = layer + turn

            return layer

        def get_detailed_winding(self, data, bobbin_dims):
            num_layers = data.get("numberOfLayers", 1)
            winding = None

            for layer_idx in range(num_layers):
                layer = self.get_layer(data, layer_idx, bobbin_dims)
                if layer is not None:
                    if winding is None:
                        winding = layer
                    else:
                        winding = winding + layer

            # Winding is created with coils in XZ plane (around Y axis)
            # This already matches the core's vertical Y axis - no rotation needed

            return winding

    class AssemblyBuilder:
        def __init__(self):
            self.output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../output/'
            self._bobbin_builder = None
            self._winding_builder = None

        @property
        def bobbin_builder(self):
            if self._bobbin_builder is None:
                self._bobbin_builder = CadQueryBuilder.StandardBobbin()
                self._bobbin_builder.set_output_path(self.output_path)
            return self._bobbin_builder

        @property
        def winding_builder(self):
            if self._winding_builder is None:
                self._winding_builder = CadQueryBuilder.RoundWireWinding()
                self._winding_builder.set_output_path(self.output_path)
            return self._winding_builder

        def set_output_path(self, output_path):
            self.output_path = output_path
            if self._bobbin_builder is not None:
                self._bobbin_builder.set_output_path(output_path)
            if self._winding_builder is not None:
                self._winding_builder.set_output_path(output_path)

        def create_assembly(self, assembly_data, core_pieces):
            components = list(core_pieces) if core_pieces else []
            return components

        def position_components(self, components, bobbin, windings):
            if bobbin is not None:
                components.append(bobbin)

            for winding in windings:
                if winding is not None:
                    components.append(winding)

            return components

        def export_assembly(self, components, project_name, export_files=True):
            if not components:
                return None, None

            try:
                from cadquery import exporters
                scaled_components = []
                for component in components:
                    if hasattr(component, 'objects'):
                        for o in component.objects:
                            scaled_components.append(o.scale(1000))
                    else:
                        scaled_components.append(component.scale(1000))

                assembly = cq.Compound.makeCompound(scaled_components)

                pathlib.Path(self.output_path).mkdir(parents=True, exist_ok=True)

                if export_files:
                    exporters.export(assembly, f"{self.output_path}/{project_name}_assembly.step", "STEP")
                    exporters.export(assembly, f"{self.output_path}/{project_name}_assembly.stl", "STL")
                    return f"{self.output_path}/{project_name}_assembly.step", f"{self.output_path}/{project_name}_assembly.stl"
                else:
                    return assembly

            except Exception:
                return None, None

        def get_magnetic_assembly(self, project_name, assembly_data, output_path=None, save_files=True, export_files=True):
            if output_path:
                self.set_output_path(output_path)

            project_name = f"{project_name}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")

            components = []

            if "core" in assembly_data and assembly_data["core"].get("geometricalDescription"):
                core_builder = CadQueryBuilder()
                core_pieces = core_builder.get_core(
                    project_name,
                    assembly_data["core"]["geometricalDescription"],
                    self.output_path,
                    save_files=False,
                    export_files=False
                )
                if core_pieces:
                    if isinstance(core_pieces, (list, tuple)):
                        components.extend(core_pieces)
                    else:
                        components.append(core_pieces)

            # Get column shape and dimensions from processedDescription.columns if available
            column_shape = "rectangular"
            column_width = 0
            column_depth = 0
            columns = assembly_data.get("core", {}).get("processedDescription", {}).get("columns", [])
            if columns:
                central_column = next((c for c in columns if c.get("type") == "central"), columns[0])
                column_shape = central_column.get("shape", "rectangular")
                column_width = central_column.get("width", 0)
                column_depth = central_column.get("depth", column_width)

            bobbin = None
            if "bobbin" in assembly_data and assembly_data["bobbin"]:
                winding_windows = assembly_data.get("core", {}).get("processedDescription", {}).get("windingWindows", [])
                if winding_windows:
                    winding_window = copy.deepcopy(winding_windows[0])
                    # Add column shape and dimensions to winding window for bobbin builder
                    winding_window["columnShape"] = column_shape
                    winding_window["columnWidth"] = column_width
                    winding_window["columnDepth"] = column_depth
                    bobbin = self.bobbin_builder.get_bobbin(
                        assembly_data["bobbin"],
                        winding_window,
                        name=f"{project_name}_bobbin",
                        save_files=False,
                        export_files=False
                    )
                    # Bobbin is centered at origin (around central column), no translation needed
                    # The bobbin wraps around the central column which is at (0,0,0)

            windings = []
            if "windings" in assembly_data:
                winding_windows = assembly_data.get("core", {}).get("processedDescription", {}).get("windingWindows", [])
                # Get complete coil data for MAS mode
                coil_data = assembly_data.get("coil", {})
                for i, winding_data in enumerate(assembly_data.get("windings", [])):
                    ww_index = winding_data.get("windingWindowIndex", 0)
                    if ww_index < len(winding_windows):
                        winding_window = copy.deepcopy(winding_windows[ww_index])
                        # Add column shape and dimensions to winding window for winding builder
                        winding_window["columnShape"] = column_shape
                        winding_window["columnWidth"] = column_width
                        winding_window["columnDepth"] = column_depth

                        # Create extended winding data with MAS fields
                        extended_winding_data = copy.deepcopy(winding_data)
                        # Add MAS turnsDescription if available
                        extended_winding_data["turnsDescription"] = coil_data.get("turnsDescription", [])
                        extended_winding_data["layersDescription"] = coil_data.get("layersDescription", [])
                        extended_winding_data["sectionsDescription"] = coil_data.get("sectionsDescription", [])
                        # Use winding name for filtering turnsDescription
                        extended_winding_data["windingName"] = winding_data.get("name", f"Winding_{i}")

                        winding = self.winding_builder.get_winding(
                            extended_winding_data,
                            winding_window,
                            name=f"{project_name}_winding_{i}",
                            save_files=False,
                            export_files=False
                        )
                        if winding is not None:
                            # Winding is centered at origin (around central column), no translation needed
                            windings.append(winding)

            components = self.position_components(components, bobbin, windings)

            return self.export_assembly(components, project_name, export_files)


if __name__ == '__main__':  # pragma: no cover

    with open(f'{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson', 'r') as f:
        for ndjson_line in f.readlines():
            data = json.loads(ndjson_line)
            if data["name"] == "PQ 40/40":
                # if data["family"] in ['pm']:
                # if data["family"] not in ['ui']:
                core = CadQueryBuilder().factory(data)
                core.get_core(data, None)
                # break
