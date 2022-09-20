import sys
import math
import os
import json
from abc import ABCMeta, abstractmethod
import utils

sys.path.insert(0, "/usr/lib/python3/dist-packages")
sys.path.append("/usr/lib/freecad-daily/lib")
sys.path.append("/usr/share/freecad-daily/Ext")
sys.path.append("/usr/share/freecad-daily/Mod")
sys.path.append("/usr/share/freecad-daily/Mod/Part")
sys.path.append("/usr/share/freecad-daily/Mod/PartDesign")
sys.path.append("/usr/share/freecad-daily/Mod/Sketcher")
import FreeCAD  # noqa: E402
import Import  # noqa: E402
import Sketcher  # noqa: E402
import Part  # noqa: E402
from BasicShapes import Shapes  # noqa: E402


class Builder:
    """
    Class for calculating the different areas and length of every shape according to EN 60205.
    Each shape will create a daughter of this class and define their own equations
    """

    def __init__(self):
        self.shapers = {
            utils.ShapeFamily.ETD: Etd(),
            utils.ShapeFamily.ER: Er(),
            utils.ShapeFamily.EP: Ep(),
            utils.ShapeFamily.EPX: Epx(),
            utils.ShapeFamily.PQ: Pq(),
            utils.ShapeFamily.E: E(),
            utils.ShapeFamily.PM: Pm(),
            utils.ShapeFamily.P: P(),
            utils.ShapeFamily.RM: Rm(),
            utils.ShapeFamily.EQ: Eq(),
            utils.ShapeFamily.LP: Lp(),
            utils.ShapeFamily.PLANAR_ER: Er(),
            utils.ShapeFamily.PLANAR_E: E(),
            utils.ShapeFamily.PLANAR_EL: E(),
            utils.ShapeFamily.EC: Ec(),
            utils.ShapeFamily.EFD: Efd(),
            utils.ShapeFamily.U: U(),
            utils.ShapeFamily.UR: Ur(),
            utils.ShapeFamily.T: T()
        }

    def factory(self, data):
        family = utils.ShapeFamily[data['family'].upper().replace(" ", "_")]
        return self.shapers[family]

    def get_data(self, reference, stacks, custom_dimensions=None, family=None):
        return self.factory(reference=reference, family=family).get_data(reference, stacks, custom_dimensions)


class IShaper(metaclass=ABCMeta):
    def __init__(self):
        self.output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../output/'

    def set_output_path(self, output_path):
        self.output_path = output_path

    @staticmethod
    def edges_in_boundbox(part, xmin, ymin, zmin, xmax, ymax, zmax):
        bb = FreeCAD.BoundBox(xmin, ymin, zmin, xmax, ymax, zmax)

        vertexes = []
        for i, edge in enumerate(part.Shape.Edges):
            if bb.isInside(edge.BoundBox):
                vertexes.append(i)
        return vertexes

    @staticmethod
    def flatten_dimensions(data):
        dimensions = data["dimensions"]
        for k, v in dimensions.items():
            if "nominal" not in v:
                if "maximum" not in v:
                    v["nominal"] = v["minimum"]
                elif "minimum" not in v:
                    v["nominal"] = v["maximum"]
                else:
                    v["nominal"] = round((v["maximum"] + v["minimum"]) / 2, 6)
        dim = {}
        for k, v in dimensions.items():
            dim[k] = v["nominal"] * 1000

        return dim

    @staticmethod
    def create_sketch(project_name):
        FreeCAD.newDocument(project_name)
        document = FreeCAD.getDocument(project_name)

        document.addObject('PartDesign::Body', 'Body')
        document.recompute()

        sketch = document.getObject('Body').newObject('Sketcher::SketchObject', 'Sketch')
        sketch.Support = (document.getObject('XY_Plane'), [''])
        sketch.MapMode = 'FlatFace'
        document.recompute()
        return sketch

    @staticmethod
    def extruce_sketch(sketch, part_name, height):
        document = FreeCAD.ActiveDocument
        part = document.addObject('Part::Extrusion', part_name)
        part.Base = sketch
        part.DirMode = "Custom"
        part.Dir = FreeCAD.Vector(0., 0., 1.)
        part.DirLink = None
        part.LengthFwd = height
        part.LengthRev = 0.
        part.Solid = True
        part.Reversed = False
        part.Symmetric = False
        part.TaperAngle = 0.
        part.TaperAngleRev = 0.

        return part

    @abstractmethod
    def get_shape_extras(self, data, piece):
        return piece

    def get_plate(self, data):
        project_name = f"{data['name']}_plate".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
        data["dimensions"] = self.flatten_dimensions(data)

        sketch = self.create_sketch(project_name)
        self.get_shape_base(data, sketch)

        document = FreeCAD.ActiveDocument
        document.recompute()

        part_name = "plate"

        plate = self.extruce_sketch(
            sketch=sketch,
            part_name=part_name,
            height=data["dimensions"]["B"] - data["dimensions"]["D"]
        )

        document.recompute()
        Import.export([plate], f"{self.output_path}/{project_name}.step")
        FreeCAD.closeDocument(project_name)

        return f"{self.output_path}/{project_name}.step"

    def get_piece(self, data):
        project_name = f"{data['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
        data["dimensions"] = self.flatten_dimensions(data)

        sketch = self.create_sketch(project_name)
        self.get_shape_base(data, sketch)

        document = FreeCAD.ActiveDocument
        document.recompute()

        part_name = "piece"

        base = self.extruce_sketch(
            sketch=sketch,
            part_name=part_name,
            height=data["dimensions"]["B"]
        )
        
        document.recompute()

        negative_winding_window = self.get_negative_winding_window(data["dimensions"])

        piece_cut = document.addObject("Part::Cut", "Cut")
        piece_cut.Base = base
        piece_cut.Tool = negative_winding_window
        document.recompute()

        piece_with_extra = self.get_shape_extras(data, piece_cut)

        piece = document.addObject('Part::Refine', 'Refine')
        piece.Source = piece_with_extra

        document.recompute()

        Import.export([piece], f"{self.output_path}/{project_name}.step")
        document.saveAs(f"{self.output_path}/{project_name}.FCStd")
        FreeCAD.closeDocument(project_name)

        return f"{self.output_path}/{project_name}.step"

    @abstractmethod
    def get_shape_base(self, data, sketch):
        raise NotImplementedError

    @abstractmethod
    def get_negative_winding_window(self, dimensions):
        raise NotImplementedError


class P(IShaper):

    def get_shape_extras(self, data, piece):
        dimensions = data["dimensions"]
        familySubtype = data["familySubtype"]
        document = FreeCAD.ActiveDocument
        if familySubtype == '3' or familySubtype == '4':
            return piece
        elif familySubtype == '1' or familySubtype == '2':
            lateral_right_cut_box = document.addObject("Part::Box", "lateral_right_cut_box")
            document.recompute()
            lateral_right_cut_box.Length = (dimensions["A"] - dimensions["F"]) / 2
            lateral_right_cut_box.Width = dimensions["G"]
            lateral_right_cut_box.Height = dimensions["D"]
            lateral_right_cut_box.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["F"] / 2, -dimensions["G"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            lateral_left_cut_box = document.addObject("Part::Box", "lateral_left_cut_box")
            document.recompute()
            lateral_left_cut_box.Length = (dimensions["A"] - dimensions["F"]) / 2
            lateral_left_cut_box.Width = dimensions["G"]
            lateral_left_cut_box.Height = dimensions["D"]
            lateral_left_cut_box.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["F"] / 2 - (dimensions["A"] - dimensions["F"]) / 2, -dimensions["G"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            piece_cut_only_right = document.addObject("Part::Cut", "lateral_right_cut")
            piece_cut_only_right.Base = piece
            piece_cut_only_right.Tool = lateral_right_cut_box
            document.recompute()

            piece_cut = document.addObject("Part::Cut", "lateral_right_cut")
            piece_cut.Base = piece_cut_only_right
            piece_cut.Tool = lateral_left_cut_box
            document.recompute()

            piece = document.addObject('Part::Refine', 'Cut')
            piece.Source = piece_cut

            document.recompute()
            if familySubtype == '1':
                zmin = dimensions["B"] - dimensions["D"]
                internal_xmin = dimensions["F"] / 2 + dimensions["E"] / 8
            elif familySubtype == '2':
                zmin = 0
                if "C" in dimensions:
                    internal_xmin = dimensions["C"] / 2 + (dimensions["E"] - dimensions["C"]) / 4
                else:
                    aux_c = dimensions["E"] * math.cos(math.asin(dimensions["G"] / dimensions["E"])) * 0.9
                    internal_xmin = aux_c / 2 + (dimensions["E"] - aux_c) / 4

            external_top_right_vertex = self.edges_in_boundbox(part=piece,
                                                               xmin=dimensions["E"] / 2,
                                                               xmax=dimensions["A"] / 2,
                                                               ymin=dimensions["G"] / 4,
                                                               ymax=3 * dimensions["G"] / 4,
                                                               zmin=zmin,
                                                               zmax=dimensions["B"])[0]
            external_bottom_right_vertex = self.edges_in_boundbox(part=piece,
                                                                  xmin=dimensions["E"] / 2,
                                                                  xmax=dimensions["A"] / 2,
                                                                  ymax=-dimensions["G"] / 4,
                                                                  ymin=-3 * dimensions["G"] / 4,
                                                                  zmin=zmin,
                                                                  zmax=dimensions["B"])[0]
            external_top_left_vertex = self.edges_in_boundbox(part=piece,
                                                              xmin=-dimensions["A"] / 2,
                                                              xmax=-dimensions["E"] / 2,
                                                              ymin=dimensions["G"] / 4,
                                                              ymax=3 * dimensions["G"] / 4,
                                                              zmin=zmin,
                                                              zmax=dimensions["B"])[0]
            external_bottom_left_vertex = self.edges_in_boundbox(part=piece,
                                                                 xmin=-dimensions["A"] / 2,
                                                                 xmax=-dimensions["E"] / 2,
                                                                 ymax=-dimensions["G"] / 4,
                                                                 ymin=-3 * dimensions["G"] / 4,
                                                                 zmin=zmin,
                                                                 zmax=dimensions["B"])[0]

            external_vertexes = [external_top_left_vertex, external_bottom_left_vertex, external_top_right_vertex, external_bottom_right_vertex]

            internal_top_right_vertex = self.edges_in_boundbox(part=piece,
                                                               xmin=internal_xmin,
                                                               xmax=dimensions["E"] / 2,
                                                               ymin=dimensions["G"] / 4,
                                                               ymax=3 * dimensions["G"] / 4,
                                                               zmin=dimensions["B"] - dimensions["D"],
                                                               zmax=dimensions["B"])[0]
            internal_bottom_right_vertex = self.edges_in_boundbox(part=piece,
                                                                  xmin=internal_xmin,
                                                                  xmax=dimensions["E"] / 2,
                                                                  ymax=-dimensions["G"] / 4,
                                                                  ymin=-3 * dimensions["G"] / 4,
                                                                  zmin=dimensions["B"] - dimensions["D"],
                                                                  zmax=dimensions["B"])[0]
            internal_top_left_vertex = self.edges_in_boundbox(part=piece,
                                                              xmin=-dimensions["E"] / 2,
                                                              xmax=-internal_xmin,
                                                              ymin=dimensions["G"] / 4,
                                                              ymax=3 * dimensions["G"] / 4,
                                                              zmin=dimensions["B"] - dimensions["D"],
                                                              zmax=dimensions["B"])[0]
            internal_bottom_left_vertex = self.edges_in_boundbox(part=piece,
                                                                 xmin=-dimensions["E"] / 2,
                                                                 xmax=-internal_xmin,
                                                                 ymax=-dimensions["G"] / 4,
                                                                 ymin=-3 * dimensions["G"] / 4,
                                                                 zmin=dimensions["B"] - dimensions["D"],
                                                                 zmax=dimensions["B"])[0]

            internal_vertexes = [internal_top_right_vertex, internal_bottom_right_vertex, internal_top_left_vertex, internal_bottom_left_vertex]

            if familySubtype == '2':
                if "C" not in dimensions:
                    internal_xmax = dimensions["E"] / 2 + (dimensions["A"] - dimensions["E"]) / 4
                else:
                    internal_xmax = internal_xmin
                base_cut_bottom_right_vertex = self.edges_in_boundbox(part=piece,
                                                                      xmin=dimensions["F"] / 2,
                                                                      xmax=internal_xmax,
                                                                      ymin=-3 * dimensions["G"] / 4,
                                                                      ymax=-dimensions["G"] / 4,
                                                                      zmin=0,
                                                                      zmax=dimensions["B"] - dimensions["D"])[0]
                base_cut_top_right_vertex = self.edges_in_boundbox(part=piece,
                                                                   xmin=dimensions["F"] / 2,
                                                                   xmax=internal_xmax,
                                                                   ymin=dimensions["G"] / 4,
                                                                   ymax=3 * dimensions["G"] / 4,
                                                                   zmin=0,
                                                                   zmax=dimensions["B"] - dimensions["D"])[0]
                base_cut_bottom_left_vertex = self.edges_in_boundbox(part=piece,
                                                                     xmin=-internal_xmax,
                                                                     xmax=-dimensions["F"] / 2,
                                                                     ymin=-3 * dimensions["G"] / 4,
                                                                     ymax=-dimensions["G"] / 4,
                                                                     zmin=0,
                                                                     zmax=dimensions["B"] - dimensions["D"])[0]
                base_cut_top_left_vertex = self.edges_in_boundbox(part=piece,
                                                                  xmin=-internal_xmax,
                                                                  xmax=-dimensions["F"] / 2,
                                                                  ymin=dimensions["G"] / 4,
                                                                  ymax=3 * dimensions["G"] / 4,
                                                                  zmin=0,
                                                                  zmax=dimensions["B"] - dimensions["D"])[0]
                base_vertexes = [base_cut_bottom_right_vertex,
                                 base_cut_top_right_vertex,
                                 base_cut_bottom_left_vertex,
                                 base_cut_top_left_vertex]

            fillet_external_radius = utils.decimal_floor((dimensions['A'] - dimensions["E"]) / 4, 2)
            fillet_internal_radius = min(utils.decimal_floor((dimensions['A'] - dimensions["E"]) / 4, 2), (dimensions["E"] - dimensions["E"] * math.cos(math.asin(dimensions["G"] / dimensions["E"]))))
            fillet_base_radius = min(0.1 * dimensions["G"], (dimensions["E"] - dimensions["E"] * math.cos(math.asin(dimensions["G"] / dimensions["E"]))) / 4)
            fillet = document.addObject("Part::Fillet", "Fillet")
            fillet.Base = piece
            __fillets__ = []
            for i in external_vertexes:  
                __fillets__.append((i + 1, fillet_external_radius, fillet_external_radius))
            for i in internal_vertexes:  
                __fillets__.append((i + 1, fillet_internal_radius, fillet_internal_radius))
            if familySubtype == '2':
                for i in base_vertexes:  
                    __fillets__.append((i + 1, fillet_base_radius, fillet_base_radius))
            fillet.Edges = __fillets__
            document.recompute()
            return fillet

    def get_shape_base(self, data, sketch):
        dimensions = data["dimensions"]
        familySubtype = data["familySubtype"]

        external_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["A"] / 2), False)
        sketch.addConstraint(Sketcher.Constraint('Coincident', external_circle, 3, -1, 1))
        sketch.addConstraint(Sketcher.Constraint('Diameter', external_circle, dimensions["A"]))
        if dimensions["H"] > 0:
            internal_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["H"] / 2), False)
            sketch.addConstraint(Sketcher.Constraint('Coincident', internal_circle, 3, -1, 1))
            sketch.addConstraint(Sketcher.Constraint('Diameter', internal_circle, dimensions["H"]))

        if familySubtype == '1':
            pass    
        elif familySubtype == '2': 
            a = dimensions["A"] / 2
            if "C" in dimensions:
                c = dimensions["C"] / 2
            else:
                c = utils.decimal_floor(dimensions["E"] * math.cos(math.asin(dimensions["G"] / dimensions["E"])) / 2, 2) * 0.95
            g = dimensions["G"] / 2
            right_dent_top = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(a, g, 0), FreeCAD.Vector(c, g, 0)), False)
            sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, g, 0), FreeCAD.Vector(c, -g, 0)), False)
            right_dent_bottom = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, -g, 0), FreeCAD.Vector(a, -g, 0)), False)
            sketch.trim(right_dent_top, FreeCAD.Vector(a, g, 0))
            sketch.trim(right_dent_bottom, FreeCAD.Vector(a, -g, 0))

            left_dent_top = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-a, g, 0), FreeCAD.Vector(-c, g, 0)), False)
            sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-c, g, 0), FreeCAD.Vector(-c, -g, 0)), False)
            left_dent_bottom = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-c, -g, 0), FreeCAD.Vector(-a, -g, 0)), False)
            sketch.trim(left_dent_top, FreeCAD.Vector(-a, g, 0))
            sketch.trim(left_dent_bottom, FreeCAD.Vector(-a, -g, 0))
            
            sketch.addConstraint(Sketcher.Constraint('DistanceX', left_dent_top, 2, right_dent_top, 2, c * 2))
            sketch.addConstraint(Sketcher.Constraint('DistanceX', left_dent_bottom, 1, right_dent_bottom, 1, c * 2))

            sketch.trim(external_circle, FreeCAD.Vector(-dimensions["A"] / 2, 0, 0))
            sketch.trim(external_circle, FreeCAD.Vector(dimensions["A"] / 2, 0, 0))

        elif familySubtype == '3':
            e = dimensions["E"] / 2
            f = dimensions["F"] / 2
            g = dimensions["G"] / 2
            sketch.addGeometry(Part.ArcOfCircle(Part.Circle(FreeCAD.Vector(e - g, 0, 0), FreeCAD.Vector(0, 0, 1), g), -math.pi / 2, math.pi / 2))
            sketch.addGeometry(Part.ArcOfCircle(Part.Circle(FreeCAD.Vector(f + g, 0, 0), FreeCAD.Vector(0, 0, 1), g), math.pi / 2, -math.pi / 2))
            sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(f + g, g, 0), FreeCAD.Vector(e - g, g, 0)), False)
            sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(f + g, -g, 0), FreeCAD.Vector(e - g, -g, 0)), False)
            sketch.addGeometry(Part.ArcOfCircle(Part.Circle(FreeCAD.Vector(-(e - g), 0, 0), FreeCAD.Vector(0, 0, 1), g), math.pi / 2, -math.pi / 2))
            sketch.addGeometry(Part.ArcOfCircle(Part.Circle(FreeCAD.Vector(-(f + g), 0, 0), FreeCAD.Vector(0, 0, 1), g), -math.pi / 2, math.pi / 2))
            sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-(f + g), g, 0), FreeCAD.Vector(-(e - g), g, 0)), False)
            sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-(f + g), -g, 0), FreeCAD.Vector(-(e - g), -g, 0)), False)
        elif familySubtype == '4':
            g = dimensions["G"] / 2
            c = dimensions["C"]
            sketch.addGeometry(Part.Circle(FreeCAD.Vector(c, 0, 0), FreeCAD.Vector(0, 0, 1), g))

    def get_negative_winding_window(self, dimensions):
        document = FreeCAD.ActiveDocument
        tube = Shapes.addTube(FreeCAD.ActiveDocument, "winding_window")
        tube.Height = dimensions["D"]
        tube.InnerRadius = dimensions["F"] / 2
        tube.OuterRadius = dimensions["E"] / 2
        tube.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(90, 0, 0))
        document.recompute()

        return tube


class Pq(P):

    def get_shape_base(self, data, sketch):
        dimensions = data["dimensions"]

        if "L" not in dimensions:
            dimensions["L"] = dimensions["F"] + (dimensions["C"] - dimensions["F"]) / 3

        if "J" not in dimensions:
            dimensions["J"] = dimensions["F"] / 2

        g_angle = math.asin(dimensions["G"] / dimensions["E"])

        top_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-dimensions["C"] / 2, dimensions["A"] / 2, 0), FreeCAD.Vector(dimensions["C"] / 2, dimensions["A"] / 2, 0)), False)

        sketch.addConstraint(Sketcher.Constraint('DistanceY', top_line, 1, dimensions["A"] / 2))
        sketch.addConstraint(Sketcher.Constraint('Block', top_line))

        bottom_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["A"] / 2, 0), FreeCAD.Vector(dimensions["C"] / 2, -dimensions["A"] / 2, 0)), False)
        sketch.addConstraint(Sketcher.Constraint('Horizontal', bottom_line))
        sketch.addConstraint(Sketcher.Constraint('DistanceY', bottom_line, 1, -dimensions["A"] / 2))
        sketch.addConstraint(Sketcher.Constraint('Block', bottom_line))

        long_top_right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(dimensions["E"] / 2 * math.cos(g_angle), dimensions["E"] / 2 * math.sin(g_angle), 0), FreeCAD.Vector(dimensions["L"] / 2, dimensions["J"] / 2, 0)), False)
        long_top_left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-dimensions["E"] / 2 * math.cos(g_angle), dimensions["E"] / 2 * math.sin(g_angle), 0), FreeCAD.Vector(-dimensions["L"] / 2, dimensions["J"] / 2, 0)), False)

        side_top_right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(dimensions["C"] / 2, dimensions["A"] / 2, 0), FreeCAD.Vector(dimensions["C"] / 2, dimensions["E"] / 2 * math.sin(g_angle), 0)), False)
        side_corner_top_right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(dimensions["C"] / 2, dimensions["E"] / 2 * math.sin(g_angle), 0), FreeCAD.Vector(dimensions["E"] / 2 * math.cos(g_angle), dimensions["E"] / 2 * math.sin(g_angle), 0)), False)
        sketch.addConstraint(Sketcher.Constraint('Coincident', side_top_right_line, 2, side_corner_top_right_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', side_corner_top_right_line, 2, long_top_right_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Vertical', side_top_right_line))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', side_corner_top_right_line))

        side_top_left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-dimensions["C"] / 2, dimensions["A"] / 2, 0), FreeCAD.Vector(-dimensions["C"] / 2, dimensions["E"] / 2 * math.sin(g_angle), 0)), False)
        side_corner_top_left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-dimensions["C"] / 2, dimensions["E"] / 2 * math.sin(g_angle), 0), FreeCAD.Vector(-dimensions["E"] / 2 * math.cos(g_angle), dimensions["E"] / 2 * math.sin(g_angle), 0)), False)
        sketch.addConstraint(Sketcher.Constraint('Coincident', side_top_left_line, 2, side_corner_top_left_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', side_corner_top_left_line, 2, long_top_left_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Vertical', side_top_left_line))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', side_corner_top_left_line))

        long_bottom_right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(dimensions["E"] / 2 * math.cos(g_angle), -dimensions["E"] / 2 * math.sin(g_angle), 0), FreeCAD.Vector(dimensions["L"] / 2, -dimensions["J"] / 2, 0)), False)
        long_bottom_left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-dimensions["E"] / 2 * math.cos(g_angle), -dimensions["E"] / 2 * math.sin(g_angle), 0), FreeCAD.Vector(-dimensions["L"] / 2, -dimensions["J"] / 2, 0)), False)

        side_bottom_right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(dimensions["C"] / 2, -dimensions["A"] / 2, 0), FreeCAD.Vector(dimensions["C"] / 2, -dimensions["E"] / 2 * math.sin(g_angle), 0)), False)
        side_corner_bottom_right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(dimensions["C"] / 2, -dimensions["E"] / 2 * math.sin(g_angle), 0), FreeCAD.Vector(dimensions["E"] / 2 * math.cos(g_angle), -dimensions["E"] / 2 * math.sin(g_angle), 0)), False)
        sketch.addConstraint(Sketcher.Constraint('Coincident', side_bottom_right_line, 2, side_corner_bottom_right_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', side_corner_bottom_right_line, 2, long_bottom_right_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Vertical', side_bottom_right_line))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', side_corner_bottom_right_line))

        sketch.addConstraint(Sketcher.Constraint('Horizontal', long_bottom_right_line, 2, long_bottom_left_line, 2))

        side_bottom_left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["A"] / 2, 0), FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["E"] / 2 * math.sin(g_angle), 0)), False)
        side_corner_bottom_left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["E"] / 2 * math.sin(g_angle), 0), FreeCAD.Vector(-dimensions["E"] / 2 * math.cos(g_angle), -dimensions["E"] / 2 * math.sin(g_angle), 0)), False)
        sketch.addConstraint(Sketcher.Constraint('Coincident', side_bottom_left_line, 2, side_corner_bottom_left_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', side_corner_bottom_left_line, 2, long_bottom_left_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Vertical', side_bottom_left_line))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', side_corner_bottom_left_line))

        sketch.addConstraint(Sketcher.Constraint('Horizontal', side_bottom_left_line, 2, side_bottom_right_line, 2))

        sketch.addConstraint(Sketcher.Constraint('Coincident', side_top_right_line, 1, top_line, 2))
        sketch.addConstraint(Sketcher.Constraint('Coincident', side_top_left_line, 1, top_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', side_bottom_right_line, 1, bottom_line, 2))
        sketch.addConstraint(Sketcher.Constraint('Coincident', side_bottom_left_line, 1, bottom_line, 1))
        fillet_radius = 0.9 * (dimensions["C"] / 2 - dimensions["E"] / 2 * math.cos(g_angle))
        sketch.fillet(side_corner_top_right_line, side_top_right_line, FreeCAD.Vector(dimensions["C"] / 2 - fillet_radius, dimensions["E"] / 2 * math.sin(g_angle), 0), FreeCAD.Vector(dimensions["C"] / 2, dimensions["E"] / 2 * math.sin(g_angle) + fillet_radius, 0), fillet_radius, True, False)
        sketch.fillet(side_corner_top_left_line, side_top_left_line, FreeCAD.Vector(-dimensions["C"] / 2 + fillet_radius, dimensions["E"] / 2 * math.sin(g_angle), 0), FreeCAD.Vector(-dimensions["C"] / 2, dimensions["E"] / 2 * math.sin(g_angle) + fillet_radius, 0), fillet_radius, True, False)

        sketch.fillet(side_corner_bottom_right_line, side_bottom_right_line, FreeCAD.Vector(dimensions["C"] / 2 - fillet_radius, -dimensions["E"] / 2 * math.sin(g_angle), 0), FreeCAD.Vector(dimensions["C"] / 2, -dimensions["E"] / 2 * math.sin(g_angle) - fillet_radius, 0), fillet_radius, True, False)
        sketch.fillet(side_corner_bottom_left_line, side_bottom_left_line, FreeCAD.Vector(-dimensions["C"] / 2 + fillet_radius, -dimensions["E"] / 2 * math.sin(g_angle), 0), FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["E"] / 2 * math.sin(g_angle) - fillet_radius, 0), fillet_radius, True, False)
        sketch.addConstraint(Sketcher.Constraint('Block', long_top_right_line))
        sketch.addConstraint(Sketcher.Constraint('Block', long_top_left_line))
        sketch.addConstraint(Sketcher.Constraint('Block', long_bottom_right_line))
        sketch.addConstraint(Sketcher.Constraint('Block', long_bottom_left_line))

        central_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["F"] / 2), False)
        sketch.addConstraint(Sketcher.Constraint('Block', central_circle))
        short_top_right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(dimensions["L"] / 2, dimensions["J"] / 2, 0), FreeCAD.Vector(dimensions["L"] / 4, dimensions["J"] / 2, 0)), False)
        short_bottom_right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(dimensions["L"] / 2, -dimensions["J"] / 2, 0), FreeCAD.Vector(dimensions["L"] / 4, -dimensions["J"] / 2, 0)), False)
        sketch.addConstraint(Sketcher.Constraint('PointOnObject', short_top_right_line, 2, central_circle))
        sketch.addConstraint(Sketcher.Constraint('PointOnObject', short_bottom_right_line, 2, central_circle))
        sketch.addConstraint(Sketcher.Constraint('Coincident', short_top_right_line, 1, long_top_right_line, 2))
        sketch.addConstraint(Sketcher.Constraint('Coincident', short_bottom_right_line, 1, long_bottom_right_line, 2))
        sketch.addConstraint(Sketcher.Constraint('Perpendicular', central_circle, short_top_right_line)) 
        sketch.addConstraint(Sketcher.Constraint('Perpendicular', central_circle, short_bottom_right_line)) 

        short_top_left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-dimensions["L"] / 2, dimensions["J"] / 2, 0), FreeCAD.Vector(-dimensions["L"] / 4, dimensions["J"] / 2, 0)), False)
        short_bottom_left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-dimensions["L"] / 2, -dimensions["J"] / 2, 0), FreeCAD.Vector(-dimensions["L"] / 4, -dimensions["J"] / 2, 0)), False)
        sketch.addConstraint(Sketcher.Constraint('PointOnObject', short_top_left_line, 2, central_circle))
        sketch.addConstraint(Sketcher.Constraint('PointOnObject', short_bottom_left_line, 2, central_circle))
        sketch.addConstraint(Sketcher.Constraint('Coincident', short_top_left_line, 1, long_top_left_line, 2))
        sketch.addConstraint(Sketcher.Constraint('Coincident', short_bottom_left_line, 1, long_bottom_left_line, 2))
        sketch.addConstraint(Sketcher.Constraint('Perpendicular', central_circle, short_top_left_line)) 
        sketch.addConstraint(Sketcher.Constraint('Perpendicular', central_circle, short_bottom_left_line)) 

        sketch.addConstraint(Sketcher.Constraint('Distance', short_bottom_left_line, 2, short_top_right_line, 2, dimensions["F"]))

        sketch.trim(central_circle, FreeCAD.Vector(0, dimensions["F"] / 2, 0))
        sketch.trim(central_circle, FreeCAD.Vector(0, -dimensions["F"] / 2, 0))

        # internal_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["E"] / 2), False)
        # sketch.addConstraint(Sketcher.Constraint('Diameter', internal_circle, dimensions["E"]))
        # sketch.addConstraint(Sketcher.Constraint('Coincident', internal_circle, 1, -1, 1))
        # sketch.addConstraint(Sketcher.Constraint('PointOnObject', long_bottom_left_line, 1, internal_circle))
        # sketch.addConstraint(Sketcher.Constraint('PointOnObject', long_bottom_right_line, 1, internal_circle))
        # sketch.addConstraint(Sketcher.Constraint('PointOnObject', long_top_left_line, 1, internal_circle))
        # sketch.addConstraint(Sketcher.Constraint('PointOnObject', long_top_right_line, 1, internal_circle))

        for index, constraint in enumerate(sketch.Constraints):
            if constraint.Type == "Equal":
                sketch.delConstraint(index)

    def get_shape_extras(self, data, piece):
        return piece


class Rm(P):

    def get_shape_base(self, data, sketch):
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

        top_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-p / 2, dimensions["A"] / 2, 0), FreeCAD.Vector(p / 2, dimensions["A"] / 2, 0)), False)
        top_right_line_45_degrees = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(p / 2, a, 0), FreeCAD.Vector(s, r, 0)), False)
        bottom_right_line_45_degrees = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(p / 2, -a, 0), FreeCAD.Vector(s, -r, 0)), False)
        top_left_line_45_degrees = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-p / 2, a, 0), FreeCAD.Vector(-s, r, 0)), False)
        bottom_left_line_45_degrees = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-p / 2, -a, 0), FreeCAD.Vector(-s, -r, 0)), False)

        top_right_line_x_degrees = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(s, r, 0), FreeCAD.Vector(c, t, 0)), False)
        bottom_right_line_x_degrees = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(s, -r, 0), FreeCAD.Vector(c, -t, 0)), False)
        top_left_line_x_degrees = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-s, r, 0), FreeCAD.Vector(-c, t, 0)), False)
        bottom_left_line_x_degrees = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-s, -r, 0), FreeCAD.Vector(-c, -t, 0)), False)
        sketch.addConstraint(Sketcher.Constraint('Coincident', top_right_line_45_degrees, 2, top_right_line_x_degrees, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_right_line_45_degrees, 2, bottom_right_line_x_degrees, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', top_left_line_45_degrees, 2, top_left_line_x_degrees, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_left_line_45_degrees, 2, bottom_left_line_x_degrees, 1))
        if c < f:
            central_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["F"] / 2), False)
            sketch.addConstraint(Sketcher.Constraint('Block', central_circle))

            sketch.trim(central_circle, FreeCAD.Vector(0, dimensions["F"] / 2, 0))
            sketch.trim(central_circle, FreeCAD.Vector(0, -dimensions["F"] / 2, 0))

        if 'H' in dimensions and dimensions['H'] > 0:
            hole_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["H"] / 2), False)
            sketch.addConstraint(Sketcher.Constraint('Block', hole_circle))

        sketch.addConstraint(Sketcher.Constraint('DistanceY', top_line, 1, dimensions["A"] / 2))
        sketch.addConstraint(Sketcher.Constraint('Block', top_line))

        bottom_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-p / 2, -dimensions["A"] / 2, 0), FreeCAD.Vector(p / 2, -dimensions["A"] / 2, 0)), False)
        sketch.addConstraint(Sketcher.Constraint('Horizontal', bottom_line))
        sketch.addConstraint(Sketcher.Constraint('DistanceY', bottom_line, 1, -dimensions["A"] / 2))
        sketch.addConstraint(Sketcher.Constraint('Block', bottom_line))

        if familySubtype == '3':
            right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, t, 0), FreeCAD.Vector(c, -t, 0)), False)
            left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-c, t, 0), FreeCAD.Vector(-c, -t, 0)), False)
            sketch.addConstraint(Sketcher.Constraint('Equal', right_line, left_line)) 
            sketch.addConstraint(Sketcher.Constraint('Coincident', top_right_line_x_degrees, 2, right_line, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_right_line_x_degrees, 2, right_line, 2))
            sketch.addConstraint(Sketcher.Constraint('DistanceX', right_line, 2, dimensions["C"] / 2))
            sketch.addConstraint(Sketcher.Constraint('Block', right_line))
            if 'H' in dimensions and dimensions['H'] > 0:
                sketch.addConstraint(Sketcher.Constraint('Symmetric', left_line, 1, right_line, 2, hole_circle, 3)) 
            sketch.addConstraint(Sketcher.Constraint('Coincident', top_left_line_x_degrees, 2, left_line, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_left_line_x_degrees, 2, left_line, 2))
            sketch.addConstraint(Sketcher.Constraint('Block', left_line))
        if familySubtype == '4':
            sketch.addConstraint(Sketcher.Constraint('Coincident', top_left_line_x_degrees, 2, bottom_left_line_x_degrees, 2))
            sketch.addConstraint(Sketcher.Constraint('Coincident', top_right_line_x_degrees, 2, bottom_right_line_x_degrees, 2))
            sketch.addConstraint(Sketcher.Constraint('DistanceX', top_right_line_x_degrees, 2, c))

        if familySubtype == '3' or familySubtype == '4':
            sketch.addConstraint(Sketcher.Constraint('Coincident', top_right_line_45_degrees, 1, top_line, 2))
            sketch.addConstraint(Sketcher.Constraint('Coincident', top_left_line_45_degrees, 1, top_line, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_right_line_45_degrees, 1, bottom_line, 2))
            sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_left_line_45_degrees, 1, bottom_line, 1))
            sketch.addConstraint(Sketcher.Constraint('Angle', top_right_line_45_degrees, 2, top_right_line_x_degrees, 1, math.pi / 2)) 
            sketch.addConstraint(Sketcher.Constraint('Angle', bottom_right_line_45_degrees, 2, bottom_right_line_x_degrees, 1, -math.pi / 2)) 
            sketch.addConstraint(Sketcher.Constraint('Angle', top_left_line_45_degrees, 2, top_left_line_x_degrees, 1, -math.pi / 2)) 
            sketch.addConstraint(Sketcher.Constraint('Angle', bottom_left_line_45_degrees, 2, bottom_left_line_x_degrees, 1, math.pi / 2)) 
            sketch.addConstraint(Sketcher.Constraint('DistanceX', top_right_line_x_degrees, 2, top_left_line_x_degrees, 2, -2 * c))
            sketch.addConstraint(Sketcher.Constraint('DistanceX', bottom_right_line_x_degrees, 2, bottom_left_line_x_degrees, 2, -2 * c))
            sketch.addConstraint(Sketcher.Constraint('Angle', top_right_line_45_degrees, 1, top_line, 2, -3 * math.pi / 4)) 
            sketch.addConstraint(Sketcher.Constraint('Angle', top_left_line_45_degrees, 1, top_line, 1, 3 * math.pi / 4)) 
            sketch.addConstraint(Sketcher.Constraint('Angle', bottom_right_line_45_degrees, 1, bottom_line, 2, 3 * math.pi / 4)) 
            sketch.addConstraint(Sketcher.Constraint('Angle', bottom_left_line_45_degrees, 1, bottom_line, 1, -3 * math.pi / 4)) 
            sketch.addConstraint(Sketcher.Constraint('Vertical', top_right_line_x_degrees, 2, bottom_right_line_x_degrees, 2))
            sketch.addConstraint(Sketcher.Constraint('Horizontal', top_right_line_x_degrees, 2, top_left_line_x_degrees, 2))

    def get_shape_extras(self, data, piece):
        return piece


class Pm(P):

    def get_shape_base(self, data, sketch):
        dimensions = data["dimensions"]
        familySubtype = data["familySubtype"]

        c = dimensions["C"] / 2
        g = dimensions["G"] / 2
        a = dimensions["A"] / 2
        e = dimensions["E"] / 2
        f = dimensions["F"] / 2
        b = dimensions["b"] / 2
        t = dimensions["t"]
        alpha = dimensions["alpha"] / 1000 / 180 * math.pi
        beta = math.asin(g / e)
        xc = f
        z = c - e * math.cos(beta) + e * math.sin(beta)

        internal_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["H"] / 2), False)
        central_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["F"] / 2), False)
        external_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["A"] / 2), False)
        sketch.addConstraint(Sketcher.Constraint('Coincident', central_circle, 3, -1, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', external_circle, 3, -1, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', internal_circle, 3, -1, 1))
        sketch.addConstraint(Sketcher.Constraint('Diameter', central_circle, dimensions["F"]))
        sketch.addConstraint(Sketcher.Constraint('Diameter', external_circle, dimensions["A"]))
        sketch.addConstraint(Sketcher.Constraint('Diameter', internal_circle, dimensions["H"]))

        side_top_right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(e * math.cos(beta), e * math.sin(beta), 0), FreeCAD.Vector(xc, 0, 0)), False)
        side_bottom_right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(e * math.cos(beta), -e * math.sin(beta), 0), FreeCAD.Vector(xc, 0, 0)), False)
        side_top_left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-e * math.cos(beta), e * math.sin(beta), 0), FreeCAD.Vector(-xc, 0, 0)), False)
        side_bottom_left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-e * math.cos(beta), -e * math.sin(beta), 0), FreeCAD.Vector(-xc, 0, 0)), False)

        sketch.addConstraint(Sketcher.Constraint('PointOnObject', side_top_right_line, 1, external_circle))
        sketch.addConstraint(Sketcher.Constraint('PointOnObject', side_bottom_right_line, 1, external_circle))
        sketch.addConstraint(Sketcher.Constraint('PointOnObject', side_top_left_line, 1, external_circle))
        sketch.addConstraint(Sketcher.Constraint('PointOnObject', side_bottom_left_line, 1, external_circle))
        sketch.addConstraint(Sketcher.Constraint('Vertical', side_top_right_line, 1, side_bottom_right_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Vertical', side_top_left_line, 1, side_bottom_left_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', side_top_left_line, 1, side_top_right_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', side_top_left_line, 2, side_top_right_line, 2))
        sketch.addConstraint(Sketcher.Constraint('Angle', side_top_right_line, 2, side_bottom_right_line, 2, -alpha))
        sketch.addConstraint(Sketcher.Constraint('Angle', side_top_left_line, 2, side_bottom_left_line, 2, alpha))
        if familySubtype == '1':
            sketch.addConstraint(Sketcher.Constraint('Horizontal', side_top_left_line, 2, -1, 1))
            sketch.addConstraint(Sketcher.Constraint('PointOnObject', side_top_right_line, 2, central_circle))
            sketch.addConstraint(Sketcher.Constraint('PointOnObject', side_top_left_line, 2, central_circle))
            sketch.addConstraint(Sketcher.Constraint('Coincident', side_top_right_line, 2, side_bottom_right_line, 2))
            sketch.addConstraint(Sketcher.Constraint('Coincident', side_top_left_line, 2, side_bottom_left_line, 2))

            sketch.fillet(side_top_right_line, side_bottom_right_line, FreeCAD.Vector(e * math.cos(beta), e * math.sin(beta), 0), FreeCAD.Vector(e * math.cos(beta), -e * math.sin(beta), 0), a - c, True, False)
            right_fillet = len(sketch.Geometry) - 1

            sketch.addConstraint(Sketcher.Constraint('Vertical', right_fillet, 1, right_fillet, 2))
            sketch.split(right_fillet, FreeCAD.Vector(c, 0, 0))
            right_fillet_bottom = len(sketch.Geometry) - 1
            sketch.addConstraint(Sketcher.Constraint('DistanceX', right_fillet_bottom, 1, -1, 1, -c))

            sketch.fillet(side_top_left_line, side_bottom_left_line, FreeCAD.Vector(-e * math.cos(beta), e * math.sin(beta), 0), FreeCAD.Vector(-e * math.cos(beta), -e * math.sin(beta), 0), a - c, True, False)
            left_fillet = len(sketch.Geometry) - 1
            sketch.addConstraint(Sketcher.Constraint('Vertical', left_fillet, 1, left_fillet, 2))
            sketch.split(left_fillet, FreeCAD.Vector(-c, 0, 0))
            left_fillet_bottom = len(sketch.Geometry) - 1
            sketch.addConstraint(Sketcher.Constraint('DistanceX', left_fillet_bottom, 1, -1, 1, c))
        elif familySubtype == '2':
            side_right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, z, 0), FreeCAD.Vector(c, -z, 0)), False)
            side_left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-c, z, 0), FreeCAD.Vector(-c, -z, 0)), False)
            sketch.addConstraint(Sketcher.Constraint('DistanceX', side_right_line, 1, -1, 1, -c))
            sketch.addConstraint(Sketcher.Constraint('DistanceX', side_left_line, 1, -1, 1, c))
            sketch.addConstraint(Sketcher.Constraint('DistanceY', side_right_line, 1, -1, 1, -z))
            sketch.addConstraint(Sketcher.Constraint('DistanceY', side_right_line, 2, -1, 1, z))

            sketch.addConstraint(Sketcher.Constraint('Vertical', side_right_line, 1, side_right_line, 2))
            sketch.addConstraint(Sketcher.Constraint('Vertical', side_left_line, 1, side_left_line, 2))
            sketch.addConstraint(Sketcher.Constraint('Coincident', side_top_right_line, 2, side_right_line, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', side_bottom_right_line, 2, side_right_line, 2))
            sketch.addConstraint(Sketcher.Constraint('Coincident', side_top_left_line, 2, side_left_line, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', side_bottom_left_line, 2, side_left_line, 2))

        top_dent_left = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-b, a, 0), FreeCAD.Vector(-b, a - t, 0)), False)
        sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-b, a - t, 0), FreeCAD.Vector(b, a - t, 0)), False)
        top_dent_right = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(b, a - t, 0), FreeCAD.Vector(b, a, 0)), False)
        sketch.trim(top_dent_left, FreeCAD.Vector(-b, a, 0))
        sketch.trim(top_dent_right, FreeCAD.Vector(b, a, 0))

        sketch.trim(external_circle, FreeCAD.Vector(-dimensions["A"] / 2, 0, 0))
        sketch.trim(external_circle, FreeCAD.Vector(dimensions["A"] / 2, 0, 0))

        external_circle_bottom = external_circle
        external_circle_top = len(sketch.Geometry) - 1
        sketch.trim(external_circle_top, FreeCAD.Vector(0, a, 0))

        bottom_dent_left = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-b, -a, 0), FreeCAD.Vector(-b, -a + t, 0)), False)
        sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-b, -a + t, 0), FreeCAD.Vector(b, -a + t, 0)), False)
        bottom_dent_right = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(b, -a + t, 0), FreeCAD.Vector(b, -a, 0)), False)
        sketch.trim(bottom_dent_left, FreeCAD.Vector(-b, -a, 0))
        sketch.trim(bottom_dent_right, FreeCAD.Vector(b, -a, 0))
        sketch.trim(external_circle_bottom, FreeCAD.Vector(0, -a, 0))
        sketch.delGeometries([central_circle])

    def get_shape_extras(self, data, piece):
        return piece


class E(IShaper):
    def get_negative_winding_window(self, dimensions):
        document = FreeCAD.ActiveDocument

        winding_window_cube = document.addObject("Part::Box", "winding_window_cube")
        winding_window_cube.Length = dimensions["C"]
        winding_window_cube.Width = dimensions["E"]
        winding_window_cube.Height = dimensions["D"]
        winding_window_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["E"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        central_column_cube = document.addObject("Part::Box", "central_column_cube")
        central_column_cube.Length = dimensions["C"]
        central_column_cube.Width = dimensions["F"]
        central_column_cube.Height = dimensions["D"]
        central_column_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["F"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        negative_winding_window = document.addObject("Part::Cut", "negative_winding_window")
        negative_winding_window.Base = winding_window_cube
        negative_winding_window.Tool = central_column_cube
        document.recompute()

        return negative_winding_window

    def get_shape_base(self, data, sketch):
        dimensions = data["dimensions"]

        c = dimensions["C"] / 2
        a = dimensions["A"] / 2

        top_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-c, a, 0), FreeCAD.Vector(c, a, 0)), False)
        right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, a, 0), FreeCAD.Vector(c, -a, 0)), False)
        bottom_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, -a, 0), FreeCAD.Vector(-c, -a, 0)), False)
        left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-c, -a, 0), FreeCAD.Vector(-c, a, 0)), False)
        sketch.addConstraint(Sketcher.Constraint('Coincident', top_line, 2, right_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', right_line, 2, bottom_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_line, 2, left_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', left_line, 2, top_line, 1))
        sketch.addConstraint(Sketcher.Constraint('DistanceY', bottom_line, 1, -1, 1, a))
        sketch.addConstraint(Sketcher.Constraint('DistanceY', top_line, 1, -1, 1, -a))
        sketch.addConstraint(Sketcher.Constraint('DistanceX', left_line, 1, -1, 1, c))
        sketch.addConstraint(Sketcher.Constraint('DistanceX', right_line, 1, -1, 1, -c))
        sketch.addConstraint(Sketcher.Constraint('Vertical', right_line))
        sketch.addConstraint(Sketcher.Constraint('Vertical', left_line))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', top_line))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', bottom_line))

    def get_shape_extras(self, data, piece):
        return piece


class Er(E):
    def get_negative_winding_window(self, dimensions):
        document = FreeCAD.ActiveDocument
        winding_window = Shapes.addTube(FreeCAD.ActiveDocument, "winding_window")
        winding_window.Height = dimensions["D"]
        winding_window.InnerRadius = dimensions["F"] / 2
        winding_window.OuterRadius = dimensions["E"] / 2
        winding_window.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(90, 0, 0))
        document.recompute()

        if 'G' in dimensions:
            lateral_top_cube = document.addObject("Part::Box", "lateral_top_cube")
            lateral_top_cube.Length = dimensions["C"]
            lateral_top_cube.Width = dimensions["G"] / 2 - dimensions["F"] / 2
            lateral_top_cube.Height = dimensions["D"]
            lateral_top_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, dimensions["F"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            lateral_bottom_cube = document.addObject("Part::Box", "lateral_bottom_cube")
            lateral_bottom_cube.Length = dimensions["C"]
            lateral_bottom_cube.Width = dimensions["G"] / 2 - dimensions["F"] / 2
            lateral_bottom_cube.Height = dimensions["D"]
            lateral_bottom_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["G"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            lateral_right_cube = document.addObject("Part::Box", "lateral_right_cube")
            lateral_right_cube.Length = dimensions["C"] / 2 - dimensions["F"] / 2
            lateral_right_cube.Width = dimensions["G"]
            lateral_right_cube.Height = dimensions["D"]
            lateral_right_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["F"] / 2, -dimensions["G"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            lateral_left_cube = document.addObject("Part::Box", "lateral_left_cube")
            lateral_left_cube.Length = dimensions["C"] / 2 - dimensions["F"] / 2
            lateral_left_cube.Width = dimensions["G"]
            lateral_left_cube.Height = dimensions["D"]
            lateral_left_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["G"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            winding_window_aux = document.addObject("Part::MultiFuse", "Fusion")
            winding_window_aux.Shapes = [winding_window, lateral_top_cube, lateral_bottom_cube, lateral_right_cube, lateral_left_cube]
            document.recompute()
            winding_window = winding_window_aux

        return winding_window

    def get_shape_extras(self, data, piece):
        return piece


class Etd(Er):
    pass


class Lp(Er):

    def get_shape_extras(self, data, piece):
        document = FreeCAD.ActiveDocument
        dimensions = data["dimensions"]

        refined_piece = document.addObject('Part::Refine', 'RefineAux')
        refined_piece.Source = piece

        document.recompute()

        right_side_vertex = self.edges_in_boundbox(part=refined_piece,
                                                   xmin=dimensions["F"] / 2 + (dimensions["C"] - dimensions["F"]) / 4,
                                                   xmax=dimensions["C"],
                                                   ymin=-(dimensions["E"] / 2 + (dimensions["A"] - dimensions["E"]) / 4),
                                                   ymax=dimensions["E"] / 2 + (dimensions["A"] - dimensions["E"]) / 4,
                                                   zmin=(dimensions["B"] - dimensions["D"]) / 2,
                                                   zmax=dimensions["B"] - dimensions["D"])

        vertexes = right_side_vertex
        fillet = document.addObject("Part::Fillet", "Fillet")
        fillet.Base = refined_piece
        fillet_radius = (dimensions["B"] - dimensions["D"]) / 2
        __fillets__ = []
        for i in vertexes:  
            __fillets__.append((i + 1, fillet_radius, fillet_radius))
        fillet.Edges = __fillets__
        document.recompute()
        return fillet

    def get_negative_winding_window(self, dimensions):
        document = FreeCAD.ActiveDocument
        winding_window = Shapes.addTube(FreeCAD.ActiveDocument, "winding_window")
        winding_window.Height = dimensions["D"]
        winding_window.InnerRadius = dimensions["F"] / 2
        winding_window.OuterRadius = dimensions["E"] / 2
        winding_window.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(90, 0, 0))
        document.recompute()

        lateral_top_cube = document.addObject("Part::Box", "lateral_top_cube")
        lateral_top_cube.Length = dimensions["C"] / 2
        lateral_top_cube.Width = dimensions["E"] / 2 - dimensions["F"] / 2
        lateral_top_cube.Height = dimensions["D"]
        lateral_top_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(0, dimensions["F"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        lateral_bottom_cube = document.addObject("Part::Box", "lateral_bottom_cube")
        lateral_bottom_cube.Length = dimensions["C"] / 2
        lateral_bottom_cube.Width = dimensions["E"] / 2 - dimensions["F"] / 2
        lateral_bottom_cube.Height = dimensions["D"]
        lateral_bottom_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(0, -dimensions["E"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        lateral_right_cube = document.addObject("Part::Box", "lateral_right_cube")
        lateral_right_cube.Length = dimensions["C"] / 2 - dimensions["F"] / 2
        lateral_right_cube.Width = dimensions["E"]
        lateral_right_cube.Height = dimensions["D"]
        lateral_right_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["F"] / 2, -dimensions["E"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        lateral_left_cube = document.addObject("Part::Box", "lateral_left_cube")
        lateral_left_cube.Length = dimensions["C"] / 2 - dimensions["F"] / 2
        lateral_left_cube.Width = dimensions["G"]
        lateral_left_cube.Height = dimensions["D"]
        lateral_left_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["G"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        winding_window_aux = document.addObject("Part::MultiFuse", "Fusion")
        winding_window_aux.Shapes = [winding_window, lateral_top_cube, lateral_bottom_cube, lateral_right_cube, lateral_left_cube]
        document.recompute()
        winding_window = winding_window_aux

        return winding_window


class Eq(Er):
    def get_shape_extras(self, data, piece):
        document = FreeCAD.ActiveDocument
        dimensions = data["dimensions"]

        refined_piece = document.addObject('Part::Refine', 'RefineAux')
        refined_piece.Source = piece

        document.recompute()

        right_side_vertex = self.edges_in_boundbox(part=refined_piece,
                                                   xmin=dimensions["C"] / 2 - (dimensions["C"] / 2 - dimensions["E"] / 2 * math.cos(math.asin(dimensions["G"] / dimensions["E"]))) / 2,
                                                   xmax=dimensions["C"] / 2,
                                                   ymin=-(dimensions["E"] / 2 + (dimensions["A"] - dimensions["E"]) / 4),
                                                   ymax=dimensions["E"] / 2 + (dimensions["A"] - dimensions["E"]) / 4,
                                                   zmin=(dimensions["B"] - dimensions["D"]) / 2,
                                                   zmax=dimensions["B"] - dimensions["D"])
        left_side_vertex = self.edges_in_boundbox(part=refined_piece,
                                                  xmin=-dimensions["C"] / 2,
                                                  xmax=-dimensions["C"] / 2 + (dimensions["C"] / 2 - dimensions["E"] / 2 * math.cos(math.asin(dimensions["G"] / dimensions["E"]))) / 2,
                                                  ymin=-(dimensions["E"] / 2 + (dimensions["A"] - dimensions["E"]) / 4),
                                                  ymax=dimensions["E"] / 2 + (dimensions["A"] - dimensions["E"]) / 4,
                                                  zmin=(dimensions["B"] - dimensions["D"]) / 2,
                                                  zmax=dimensions["B"] - dimensions["D"])

        vertexes = right_side_vertex
        vertexes.extend(left_side_vertex)
        fillet = document.addObject("Part::Fillet", "Fillet")
        fillet.Base = refined_piece
        fillet_radius = min(dimensions["C"] / 2 - dimensions["E"] / 2 * math.cos(math.asin(dimensions["G"] / dimensions["E"])), (dimensions["B"] - dimensions["D"]) / 2)
        __fillets__ = []
        for i in vertexes:  
            __fillets__.append((i + 1, fillet_radius, fillet_radius))
        fillet.Edges = __fillets__
        document.recompute()
        return fillet


class Ec(Er):
    def get_shape_base(self, data, sketch):
        dimensions = data["dimensions"]

        c = dimensions["C"] / 2
        a = dimensions["A"] / 2
        t = dimensions["T"] / 2
        s = dimensions["s"] / 2

        top_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-c, a, 0), FreeCAD.Vector(c, a, 0)), False)
        right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, a, 0), FreeCAD.Vector(c, -a, 0)), False)
        bottom_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, -a, 0), FreeCAD.Vector(-c, -a, 0)), False)
        left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-c, -a, 0), FreeCAD.Vector(-c, a, 0)), False)
        sketch.addConstraint(Sketcher.Constraint('Coincident', top_line, 2, right_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', right_line, 2, bottom_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_line, 2, left_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', left_line, 2, top_line, 1))
        sketch.addConstraint(Sketcher.Constraint('DistanceY', bottom_line, 1, -1, 1, a))
        sketch.addConstraint(Sketcher.Constraint('DistanceX', left_line, 1, -1, 1, c))
        sketch.addConstraint(Sketcher.Constraint('DistanceX', right_line, 1, -1, 1, -c))
        sketch.addConstraint(Sketcher.Constraint('Vertical', right_line))
        sketch.addConstraint(Sketcher.Constraint('Vertical', left_line))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', top_line))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', bottom_line))

        sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-s, a, 0), FreeCAD.Vector(-s, t + s, 0)), False)
        sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(s, a, 0), FreeCAD.Vector(s, t + s, 0)), False)
        sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-s, -a, 0), FreeCAD.Vector(-s, -t - s, 0)), False)
        sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(s, -a, 0), FreeCAD.Vector(s, -t - s, 0)), False)
        sketch.addGeometry(Part.ArcOfCircle(Part.Circle(FreeCAD.Vector(0, t + s, 0), FreeCAD.Vector(0, 0, 1), s), math.pi, 0))
        sketch.addGeometry(Part.ArcOfCircle(Part.Circle(FreeCAD.Vector(0, -t - s, 0), FreeCAD.Vector(0, 0, 1), s), 0, math.pi))

        sketch.trim(top_line, FreeCAD.Vector(0, a, 0))
        sketch.trim(bottom_line, FreeCAD.Vector(0, -a, 0))


class Ep(E):
    def get_negative_winding_window(self, dimensions):
        document = FreeCAD.ActiveDocument
        winding_window = Shapes.addTube(FreeCAD.ActiveDocument, "winding_window")
        winding_window.Height = dimensions["D"]
        winding_window.InnerRadius = dimensions["F"] / 2
        winding_window.OuterRadius = dimensions["E"] / 2
        winding_window.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"], 0, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(90, 0, 0))
        document.recompute()

        lateral_top_cube = document.addObject("Part::Box", "lateral_top_cube")
        lateral_top_cube.Length = dimensions["C"] / 2
        lateral_top_cube.Width = dimensions["E"] / 2 - dimensions["F"] / 2
        lateral_top_cube.Height = dimensions["D"]
        lateral_top_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"], dimensions["F"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        lateral_bottom_cube = document.addObject("Part::Box", "lateral_bottom_cube")
        lateral_bottom_cube.Length = dimensions["C"] / 2
        lateral_bottom_cube.Width = dimensions["E"] / 2 - dimensions["F"] / 2
        lateral_bottom_cube.Height = dimensions["D"]
        lateral_bottom_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"], -dimensions["E"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        lateral_right_cube = document.addObject("Part::Box", "lateral_right_cube")
        lateral_right_cube.Length = dimensions["C"] / 2 - dimensions["F"] / 2
        lateral_right_cube.Width = dimensions["E"]
        lateral_right_cube.Height = dimensions["D"]
        lateral_right_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] - dimensions["F"] / 2, -dimensions["E"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        shapes = [winding_window, lateral_top_cube, lateral_bottom_cube, lateral_right_cube]
        if "G" in dimensions:
            lateral_left_cube = document.addObject("Part::Box", "lateral_left_cube")
            lateral_left_cube.Length = dimensions["C"] / 2 - dimensions["F"] / 2
            lateral_left_cube.Width = dimensions["G"]
            lateral_left_cube.Height = dimensions["D"]
            lateral_left_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["G"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
            shapes.append(lateral_left_cube)

        winding_window_aux = document.addObject("Part::MultiFuse", "Fusion")
        winding_window_aux.Shapes = shapes

        document.recompute()
        winding_window = winding_window_aux

        return winding_window


class Epx(E):
    def get_negative_winding_window(self, dimensions):
        document = FreeCAD.ActiveDocument

        cylinder_left = document.addObject("Part::Cylinder", "cylinder_left")
        cylinder_left.Height = dimensions["D"]
        cylinder_left.Radius = dimensions["F"] / 2
        cylinder_left.Angle = 180
        cylinder_left.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"], 0, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(90, 0, 0))
        document.recompute()

        central_column_cube = document.addObject("Part::Box", "central_column_cube")
        central_column_cube.Length = dimensions["K"] - dimensions["F"] / 2
        central_column_cube.Width = dimensions["F"]
        central_column_cube.Height = dimensions["D"]
        central_column_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"], -dimensions["F"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        cylinder_right = document.addObject("Part::Cylinder", "cylinder_right")
        cylinder_right.Height = dimensions["D"]
        cylinder_right.Radius = dimensions["F"] / 2
        cylinder_right.Angle = 180
        cylinder_right.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["F"] / 2, 0, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(-90, 0, 0))
        document.recompute()

        central_column = document.addObject("Part::MultiFuse", "central_column")
        central_column.Shapes = [cylinder_left, central_column_cube, cylinder_right]

        document.recompute()

        winding_window_cylinder_left = document.addObject("Part::Cylinder", "winding_window_cylinder_left")
        winding_window_cylinder_left.Height = dimensions["D"]
        winding_window_cylinder_left.Radius = dimensions["E"] / 2
        winding_window_cylinder_left.Angle = 180
        winding_window_cylinder_left.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"], 0, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(90, 0, 0))

        lateral_top_cube = document.addObject("Part::Box", "lateral_top_cube")
        lateral_top_cube.Length = dimensions["C"] / 2
        lateral_top_cube.Width = dimensions["E"] / 2 - dimensions["F"] / 2
        lateral_top_cube.Height = dimensions["D"]
        lateral_top_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"], dimensions["F"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        lateral_bottom_cube = document.addObject("Part::Box", "lateral_bottom_cube")
        lateral_bottom_cube.Length = dimensions["C"] / 2
        lateral_bottom_cube.Width = dimensions["E"] / 2 - dimensions["F"] / 2
        lateral_bottom_cube.Height = dimensions["D"]
        lateral_bottom_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"], -dimensions["E"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        lateral_right_cube = document.addObject("Part::Box", "lateral_right_cube")
        lateral_right_cube.Length = dimensions["C"] / 2 - dimensions["F"] / 2
        lateral_right_cube.Width = dimensions["E"]
        lateral_right_cube.Height = dimensions["D"]
        lateral_right_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["F"] / 2, -dimensions["E"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        shapes = [winding_window_cylinder_left, lateral_top_cube, lateral_bottom_cube, lateral_right_cube]
        if "G" in dimensions and dimensions["G"] > 0:
            lateral_left_cube = document.addObject("Part::Box", "lateral_left_cube")
            lateral_left_cube.Length = dimensions["C"] / 2 - dimensions["F"] / 2
            lateral_left_cube.Width = dimensions["G"]
            lateral_left_cube.Height = dimensions["D"]
            lateral_left_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["G"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
            shapes.append(lateral_left_cube)

        winding_window_aux = document.addObject("Part::MultiFuse", "Fusion")
        winding_window_aux.Shapes = shapes

        document.recompute()

        winding_window = document.addObject("Part::Cut", "winding_window")
        winding_window.Base = winding_window_aux
        winding_window.Tool = central_column

        document.recompute()

        return winding_window


class Efd(E):
    def get_shape_base(self, data, sketch):
        dimensions = data["dimensions"]

        c = dimensions["C"] / 2
        a = dimensions["A"] / 2
        e = dimensions["E"] / 2
        f1 = dimensions["F1"] / 2
        f2 = dimensions["F2"]
        k = dimensions["K"]
        q = dimensions["q"]

        top_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-c, a, 0), FreeCAD.Vector(c, a, 0)), False)
        right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, a, 0), FreeCAD.Vector(c, -a, 0)), False)
        bottom_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, -a, 0), FreeCAD.Vector(-c, -a, 0)), False)
        left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-c, -a, 0), FreeCAD.Vector(-c, a, 0)), False)
        sketch.addConstraint(Sketcher.Constraint('Coincident', top_line, 2, right_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', right_line, 2, bottom_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_line, 2, left_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', left_line, 2, top_line, 1))
        sketch.addConstraint(Sketcher.Constraint('DistanceY', bottom_line, 1, -1, 1, a))
        sketch.addConstraint(Sketcher.Constraint('DistanceY', top_line, 1, -1, 1, -a))
        sketch.addConstraint(Sketcher.Constraint('DistanceX', left_line, 1, -1, 1, c))
        sketch.addConstraint(Sketcher.Constraint('DistanceX', right_line, 1, -1, 1, -c))
        sketch.addConstraint(Sketcher.Constraint('Vertical', right_line))
        sketch.addConstraint(Sketcher.Constraint('Vertical', left_line))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', top_line))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', bottom_line))
        right_notch_left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector((f2 + k) / 3, f1, 0), FreeCAD.Vector((f2 + k) / 3, -f1, 0)), False)
        right_notch_top_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, f1, 0), FreeCAD.Vector((f2 + k) / 3, f1, 0)), False)
        right_notch_bottom_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, -f1, 0), FreeCAD.Vector((f2 + k) / 3, -f1, 0)), False)
        sketch.addConstraint(Sketcher.Constraint('Vertical', right_notch_left_line))
        sketch.addConstraint(Sketcher.Constraint('PointOnObject', right_notch_top_line, 1, right_line))
        sketch.addConstraint(Sketcher.Constraint('PointOnObject', right_notch_bottom_line, 1, right_line))
        sketch.addConstraint(Sketcher.Constraint('Coincident', right_notch_top_line, 2, right_notch_left_line, 1))
        sketch.addConstraint(Sketcher.Constraint('Coincident', right_notch_bottom_line, 2, right_notch_left_line, 2))
        sketch.addConstraint(Sketcher.Constraint('DistanceY', right_notch_top_line, 1, -1, 1, -(e - f1)))
        sketch.addConstraint(Sketcher.Constraint('DistanceY', right_notch_bottom_line, 1, -1, 1, (e - f1)))
        sketch.addConstraint(Sketcher.Constraint('Angle', right_notch_left_line, 1, right_notch_bottom_line, 2, 75 / 180 * math.pi)) 
        sketch.addConstraint(Sketcher.Constraint('Angle', right_notch_left_line, 2, right_notch_top_line, 2, -75 / 180 * math.pi)) 
        sketch.addConstraint(Sketcher.Constraint('DistanceX', right_notch_left_line, 1, -1, 1, -(f2 + k) / 3))
        sketch.addConstraint(Sketcher.Constraint('DistanceX', right_notch_bottom_line, 1, -1, 1, -c))
        sketch.trim(right_line, FreeCAD.Vector(c, 0, 0))
        sketch.addConstraint(Sketcher.Constraint('DistanceX', bottom_line, 1, -1, 1, -c))

        if dimensions["K"] > 0:
            left_notch_right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector((-c + k), (f1 - q), 0), FreeCAD.Vector((-c + k), -(f1 - q), 0)), False)
            left_notch_top_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, (f1 - q), 0), FreeCAD.Vector((-c + k), (f1 - q), 0)), False)
            left_notch_bottom_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, -(f1 - q), 0), FreeCAD.Vector((-c + k), -(f1 - q), 0)), False)
            sketch.addConstraint(Sketcher.Constraint('Vertical', left_notch_right_line))
            sketch.addConstraint(Sketcher.Constraint('PointOnObject', left_notch_top_line, 1, left_line))
            sketch.addConstraint(Sketcher.Constraint('PointOnObject', left_notch_bottom_line, 1, left_line))
            sketch.addConstraint(Sketcher.Constraint('Coincident', left_notch_top_line, 2, left_notch_right_line, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', left_notch_bottom_line, 2, left_notch_right_line, 2))
            sketch.addConstraint(Sketcher.Constraint('DistanceY', left_notch_top_line, 1, -1, 1, -(e - (f1 - q))))
            sketch.addConstraint(Sketcher.Constraint('DistanceY', left_notch_bottom_line, 1, -1, 1, (e - (f1 - q))))
            sketch.addConstraint(Sketcher.Constraint('Angle', left_notch_right_line, 1, left_notch_bottom_line, 2, -75 / 180 * math.pi)) 
            sketch.addConstraint(Sketcher.Constraint('Angle', left_notch_right_line, 2, left_notch_top_line, 2, 75 / 180 * math.pi)) 
            sketch.addConstraint(Sketcher.Constraint('DistanceX', left_notch_right_line, 1, -1, 1, -(-c + k)))
            sketch.addConstraint(Sketcher.Constraint('DistanceX', left_notch_top_line, 1, -1, 1, c))
            sketch.trim(left_line, FreeCAD.Vector(c, 0, 0))
            sketch.addConstraint(Sketcher.Constraint('DistanceX', top_line, 1, -1, 1, c))

    def get_negative_winding_window(self, dimensions):
        document = FreeCAD.ActiveDocument
        if dimensions["K"] < 0:
            k = dimensions["K"]
        else:
            k = 0

        winding_window_cube = document.addObject("Part::Box", "winding_window_cube")
        winding_window_cube.Width = dimensions["E"]
        winding_window_cube.Height = dimensions["D"]
        winding_window_cube.Length = dimensions["C"] - k
        winding_window_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2 + k, -dimensions["E"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        document.recompute()

        return winding_window_cube

    def get_shape_extras(self, data, piece):
        dimensions = data["dimensions"]
        document = FreeCAD.ActiveDocument
        central_column_cube = document.addObject("Part::Box", "central_column_cube")
        central_column_cube.Length = dimensions["F2"]
        central_column_cube.Width = dimensions["F1"]
        central_column_cube.Height = dimensions["B"]
        central_column_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["F2"] / 2, -dimensions["F1"] / 2, 0), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
        top_right_vertex = self.edges_in_boundbox(part=central_column_cube,
                                                  xmin=0,
                                                  xmax=dimensions["F2"] / 2,
                                                  ymin=0,
                                                  ymax=dimensions["F1"] / 2,
                                                  zmin=0,
                                                  zmax=dimensions["B"])[0]
        top_left_vertex = self.edges_in_boundbox(part=central_column_cube,
                                                 xmin=-dimensions["F2"] / 2,
                                                 xmax=0,
                                                 ymin=0,
                                                 ymax=dimensions["F1"] / 2,
                                                 zmin=0,
                                                 zmax=dimensions["B"])[0]
        bottom_right_vertex = self.edges_in_boundbox(part=central_column_cube,
                                                     xmin=0,
                                                     xmax=dimensions["F2"] / 2,
                                                     ymin=-dimensions["F1"] / 2,
                                                     ymax=0,
                                                     zmin=0,
                                                     zmax=dimensions["B"])[0]
        bottom_left_vertex = self.edges_in_boundbox(part=central_column_cube,
                                                    xmin=-dimensions["F2"] / 2,
                                                    xmax=0,
                                                    ymin=-dimensions["F1"] / 2,
                                                    ymax=0,
                                                    zmin=0,
                                                    zmax=dimensions["B"])[0]
        vertexes = [top_right_vertex, top_left_vertex, bottom_right_vertex, bottom_left_vertex]
        chamfer = document.addObject("Part::Chamfer", "Chamfer")
        chamfer.Base = central_column_cube
        __chamfers__ = []
        for i in vertexes:  
            __chamfers__.append((i + 1, dimensions["q"], dimensions["q"]))
        chamfer.Edges = __chamfers__
        central_column_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2 + dimensions["K"], -dimensions["F1"] / 2, 0), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
        document.recompute()

        piece_with_column = document.addObject("Part::MultiFuse", "Fusion")
        piece_with_column.Shapes = [piece, chamfer]
        document.recompute()
        return piece_with_column


class U(E):
    def get_negative_winding_window(self, dimensions):
        document = FreeCAD.ActiveDocument
        central_hole = document.addObject("Part::Box", "central_hole")
        central_hole.Length = dimensions["C"]
        central_hole.Width = dimensions["E"]
        central_hole.Height = dimensions["D"]
        central_hole.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["E"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
        return central_hole


class Ur(E):

    def get_shape_extras(self, data, piece):
        dimensions = data["dimensions"]
        document = FreeCAD.ActiveDocument
        familySubtype = data["familySubtype"]

        if familySubtype == '1' or familySubtype == '2':
            top_diameter = dimensions["C"]
            bottom_diameter = dimensions["C"]
        elif familySubtype == '3':
            top_diameter = dimensions["F"]
            bottom_diameter = dimensions["C"]
        elif familySubtype == '4':
            top_diameter = dimensions["F"]
            bottom_diameter = dimensions["F"]

        top_column = document.addObject("Part::Cylinder", "top_column")
        top_column.Height = dimensions["D"]
        top_column.Radius = top_diameter / 2
        top_column.Placement = FreeCAD.Placement(FreeCAD.Vector(0, (dimensions["A"] - top_diameter) / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(90, 0, 0))

        if familySubtype == '1' or familySubtype == '3':
            bottom_column = document.addObject("Part::Box", "bottom_column")
            bottom_column.Length = bottom_diameter
            bottom_column.Width = dimensions["H"]
            bottom_column.Height = dimensions["D"]
            bottom_column.Placement = FreeCAD.Placement(FreeCAD.Vector(-bottom_diameter / 2, -dimensions["A"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
        elif familySubtype == '2' or familySubtype == '4':
            bottom_column = document.addObject("Part::Cylinder", "bottom_column")
            bottom_column.Height = dimensions["D"]
            bottom_column.Radius = bottom_diameter / 2
            bottom_column.Placement = FreeCAD.Placement(FreeCAD.Vector(0, -(dimensions["A"] - bottom_diameter) / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(90, 0, 0))

        if familySubtype == '4':
            top_column_hole = document.addObject("Part::Cylinder", "top_column_hole")
            top_column_hole.Height = dimensions["B"]
            top_column_hole.Radius = dimensions["G"] / 2
            top_column_hole.Placement = FreeCAD.Placement(FreeCAD.Vector(0, (dimensions["A"] - top_diameter) / 2, 0), FreeCAD.Rotation(90, 0, 0))

            bottom_column_hole = document.addObject("Part::Cylinder", "bottom_column_hole")
            bottom_column_hole.Height = dimensions["B"]
            bottom_column_hole.Radius = dimensions["G"] / 2
            bottom_column_hole.Placement = FreeCAD.Placement(FreeCAD.Vector(0, -(dimensions["A"] - bottom_diameter) / 2, 0), FreeCAD.Rotation(90, 0, 0))

        columns = document.addObject("Part::MultiFuse", "columns")
        columns.Shapes = [piece, bottom_column, top_column]
        document.recompute()

        if familySubtype == '4':
            top_cut = document.addObject("Part::Cut", "top_cut")
            top_cut.Base = columns
            top_cut.Tool = top_column_hole
            document.recompute()
            columns = top_cut

            bottom_cut = document.addObject("Part::Cut", "bottom_cut")
            bottom_cut.Base = columns
            bottom_cut.Tool = bottom_column_hole
            document.recompute()
            columns = bottom_cut

        return columns

    def get_shape_base(self, data, sketch):
        dimensions = data["dimensions"]
        familySubtype = data["familySubtype"]

        c = dimensions["C"] / 2
        a = dimensions["A"] / 2
        if familySubtype == '1' or familySubtype == '2' or familySubtype == '3':
            f = dimensions["C"] / 2
        else:
            f = dimensions["F"] / 2

        if familySubtype == '1' or familySubtype == '3':
            right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, a - f, 0), FreeCAD.Vector(c, -a, 0)), False)
            left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-c, -a, 0), FreeCAD.Vector(-c, a - f, 0)), False)
        elif familySubtype == '2' or familySubtype == '4':
            right_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, a - f, 0), FreeCAD.Vector(c, -a + f, 0)), False)
            left_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(-c, -a + f, 0), FreeCAD.Vector(-c, a - f, 0)), False)

        sketch.addConstraint(Sketcher.Constraint('DistanceX', left_line, 1, -1, 1, c))
        # sketch.addConstraint(Sketcher.Constraint('DistanceX', right_line, 1, -1, 1, -c))
        sketch.addConstraint(Sketcher.Constraint('Vertical', right_line))

        if familySubtype == '1' or familySubtype == '3':
            bottom_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, -a, 0), FreeCAD.Vector(-c, -a, 0)), False)
            sketch.addConstraint(Sketcher.Constraint('Coincident', right_line, 2, bottom_line, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_line, 2, left_line, 1))
            sketch.addConstraint(Sketcher.Constraint('DistanceY', bottom_line, 1, -1, 1, a))
            sketch.addConstraint(Sketcher.Constraint('Horizontal', bottom_line))
        elif familySubtype == '2' or familySubtype == '4':
            bottom_arc = sketch.addGeometry(Part.ArcOfCircle(Part.Circle(FreeCAD.Vector(0, -(a - f), 0), FreeCAD.Vector(0, 0, 1), f), -math.pi, 0))
            sketch.addConstraint(Sketcher.Constraint('Diameter', bottom_arc, 2 * f))
            sketch.addConstraint(Sketcher.Constraint('DistanceY', bottom_arc, 3, -1, 1, a - f))
            sketch.addConstraint(Sketcher.Constraint('DistanceY', bottom_arc, 2, -1, 1, a - f))
            if familySubtype != '4':
                sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_arc, 2, right_line, 2))
                sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_arc, 1, left_line, 1))
            sketch.addConstraint(Sketcher.Constraint('Horizontal', bottom_arc, 1, bottom_arc, 2))

        top_arc = sketch.addGeometry(Part.ArcOfCircle(Part.Circle(FreeCAD.Vector(0, a - f, 0), FreeCAD.Vector(0, 0, 1), f), 0, -math.pi))
        sketch.addConstraint(Sketcher.Constraint('Diameter', top_arc, 2 * f))
        if familySubtype == '1':
            sketch.addConstraint(Sketcher.Constraint('Vertical', top_arc, 3, -1, 1))
        sketch.addConstraint(Sketcher.Constraint('DistanceY', top_arc, 3, -1, 1, -(a - f)))
        sketch.addConstraint(Sketcher.Constraint('DistanceY', top_arc, 2, -1, 1, -(a - f)))
        if familySubtype != '4':
            sketch.addConstraint(Sketcher.Constraint('Coincident', top_arc, 1, right_line, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', top_arc, 2, left_line, 2))
        sketch.addConstraint(Sketcher.Constraint('Horizontal', top_arc, 1, top_arc, 2))
        if familySubtype == '4':
            bottom_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, -(a - f), 0), FreeCAD.Vector(-c, -(a - f), 0)), False)
            sketch.addConstraint(Sketcher.Constraint('Coincident', right_line, 2, bottom_line, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', bottom_line, 2, left_line, 1))
            sketch.addConstraint(Sketcher.Constraint('DistanceY', bottom_line, 1, -1, 1, (a - f)))
            sketch.addConstraint(Sketcher.Constraint('Horizontal', bottom_line))
            top_line = sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(c, a - f, 0), FreeCAD.Vector(-c, a - f, 0)), False)
            sketch.addConstraint(Sketcher.Constraint('Coincident', right_line, 1, top_line, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', top_line, 2, left_line, 2))
            sketch.addConstraint(Sketcher.Constraint('DistanceY', top_line, 1, -1, 1, -(a - f)))
            sketch.addConstraint(Sketcher.Constraint('Horizontal', top_line))
            sketch.addConstraint(Sketcher.Constraint('Vertical', left_line))
            sketch.addConstraint(Sketcher.Constraint('DistanceX', right_line, 1, -1, 1, -c))
            sketch.addConstraint(Sketcher.Constraint('Vertical', top_arc, 3, -1, 1))
            sketch.addConstraint(Sketcher.Constraint('Vertical', bottom_arc, 3, -1, 1))
            sketch.trim(bottom_line, FreeCAD.Vector(0, -(a - f), 0))
            sketch.trim(top_line, FreeCAD.Vector(0, a - f, 0))

    def get_negative_winding_window(self, dimensions):
        document = FreeCAD.ActiveDocument
        central_hole = document.addObject("Part::Box", "central_hole")
        central_hole.Length = dimensions["C"]
        central_hole.Width = dimensions["A"]
        central_hole.Height = dimensions["D"]
        central_hole.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["A"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
        return central_hole


class T(IShaper):
    def get_negative_winding_window(self, dimensions):
        pass  # TBD

    def get_shape_base(self, data, sketch):
        pass  # TBD

    def get_shape_extras(self, data, piece):
        return piece  # TBD


if __name__ == '__main__':  # pragma: no cover

    with open(f'{os.path.dirname(os.path.abspath(__file__))}/../MAS/data/shapes.ndjson', 'r') as f:
        for ndjson_line in f.readlines():
            data = json.loads(ndjson_line)
            if data["family"] == 'ur':
                core = Builder().factory(data)
                core.get_piece(data)

    # data = {"type": "standard", "family": "ur", "aliases": [], "name": "UR 48/39/17",                          "dimensions": {"A": {"nominal": 0.04800}, "D": {"nominal": 0.02690}, "C": {"nominal": 0.01700}, "E": {"minimum": 0.01740}, "H": {"nominal": 0.01300}, "B": {"nominal": 0.03940}}, "familySubtype": "1"}
    # data = {"type": "standard", "family": "ur", "aliases": [], "name": "UR 42/21/12",                          "dimensions": {"A": {"nominal": 0.04180}, "D": {"nominal": 0.01110}, "C": {"nominal": 0.01190}, "E": {"minimum": 0.01820}, "H": {"nominal": 0.01190}, "B": {"nominal": 0.02060}}, "familySubtype": "2"}
    # data = {"type": "standard", "family": "ur", "aliases": [], "name": "UR 55/38/36",                          "dimensions": {"A": {"nominal": 0.05490}, "D": {"nominal": 0.02550}, "C": {"nominal": 0.03600}, "E": {"minimum": 0.01960}, "H": {"nominal": 0.01200}, "B": {"nominal": 0.03750}, "F": {"nominal": 0.02350}}, "familySubtype": "3"}
    # data = {"type": "standard", "family": "ur", "aliases": [], "name": "UR 64/40/20-D",                        "dimensions": {"A": {"nominal": 0.06400}, "D": {"nominal": 0.02650}, "C": {"nominal": 0.02400}, "E": {"minimum": 0.02320}, "H": {"nominal": 0.02000}, "B": {"nominal": 0.04050}, "G": {"nominal": 0.00510}, "F": {"nominal": 0.02000}}, "familySubtype": "4"}

    # core = Builder().factory(data)

    # core.get_piece(data)
