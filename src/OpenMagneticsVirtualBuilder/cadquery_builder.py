import contextlib
import sys
import math
import os
import json
from abc import ABCMeta, abstractmethod
import copy
import pathlib
import platform
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Union, Dict, Any
sys.path.append(os.path.dirname(__file__))
import utils
import cadquery as cq

file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)


# ==========================================================================
# Enums and Data Classes for Magnetic Building
# ==========================================================================

class WireType(Enum):
    """Wire types supported."""
    round = "round"
    litz = "litz"
    rectangular = "rectangular"
    foil = "foil"
    planar = "planar"


class ColumnShape(Enum):
    """Bobbin column shapes."""
    round = "round"
    rectangular = "rectangular"


def resolve_dimensional_value(value: Any) -> float:
    """Extract numeric value from dimensional data (handles dict with 'nominal' or plain value)."""
    if value is None:
        return 0.0
    if isinstance(value, dict):
        return value.get('nominal', value.get('minimum', value.get('maximum', 0.0)))
    return float(value)


@dataclass
class WireDescription:
    """Description of a wire."""
    wire_type: WireType
    conducting_diameter: Optional[float] = None
    outer_diameter: Optional[float] = None
    conducting_width: Optional[float] = None
    conducting_height: Optional[float] = None
    outer_width: Optional[float] = None
    outer_height: Optional[float] = None
    number_conductors: int = 1
    
    @classmethod
    def from_dict(cls, data: dict) -> 'WireDescription':
        wire_type_str = data.get('type', 'round')
        wire_type = WireType[wire_type_str] if isinstance(wire_type_str, str) else wire_type_str
        
        return cls(
            wire_type=wire_type,
            conducting_diameter=resolve_dimensional_value(data.get('conductingDiameter')),
            outer_diameter=resolve_dimensional_value(data.get('outerDiameter')),
            conducting_width=resolve_dimensional_value(data.get('conductingWidth')),
            conducting_height=resolve_dimensional_value(data.get('conductingHeight')),
            outer_width=resolve_dimensional_value(data.get('outerWidth')),
            outer_height=resolve_dimensional_value(data.get('outerHeight')),
            number_conductors=data.get('numberConductors', 1)
        )


@dataclass
class TurnDescription:
    """Description of a single turn."""
    coordinates: List[float]
    winding: str = ""
    section: str = ""
    layer: str = ""
    parallel: int = 0
    turn_index: int = 0
    dimensions: Optional[List[float]] = None
    rotation: float = 0.0
    additional_coordinates: Optional[List[List[float]]] = None
    cross_sectional_shape: str = "round"
    
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
            additional_coordinates=data.get('additionalCoordinates'),
            cross_sectional_shape=data.get('crossSectionalShape', 'round')
        )


@dataclass
class BobbinProcessedDescription:
    """Processed bobbin description."""
    column_depth: float = 0.0
    column_width: float = 0.0
    column_thickness: float = 0.0
    wall_thickness: float = 0.0
    column_shape: ColumnShape = ColumnShape.rectangular
    winding_window_height: float = 0.0
    winding_window_width: float = 0.0
    winding_window_radial_height: float = 0.0
    winding_window_angle: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BobbinProcessedDescription':
        shape_str = data.get('columnShape', 'rectangular')
        if isinstance(shape_str, str):
            column_shape = ColumnShape[shape_str] if shape_str in ColumnShape.__members__ else ColumnShape.rectangular
        else:
            column_shape = shape_str
            
        # Get winding window info
        ww_height = 0.0
        ww_width = 0.0
        ww_radial_height = 0.0
        ww_angle = None
        
        winding_windows = data.get('windingWindows', [])
        if winding_windows and len(winding_windows) > 0:
            ww = winding_windows[0]
            ww_height = ww.get('height', 0.0)
            ww_width = ww.get('width', 0.0)
            ww_radial_height = ww.get('radialHeight', 0.0)
            ww_angle = ww.get('angle')
        
        return cls(
            column_depth=data.get('columnDepth', 0.0),
            column_width=data.get('columnWidth', 0.0),
            column_thickness=data.get('columnThickness', 0.0),
            wall_thickness=data.get('wallThickness', 0.0),
            column_shape=column_shape,
            winding_window_height=ww_height,
            winding_window_width=ww_width,
            winding_window_radial_height=ww_radial_height,
            winding_window_angle=ww_angle
        )


def convert_axis_toroidal(coordinates):
    """Convert coordinates for toroidal cores (axis along Y)."""
    if len(coordinates) == 2:
        # [radial, angle] or [x, z] -> [x, 0, z]
        return [coordinates[0], 0, coordinates[1]]
    elif len(coordinates) == 3:
        return [coordinates[0], coordinates[1], coordinates[2]]
    else:
        return [0, 0, 0]


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
                return scaled_pieces_to_export

        except:  # noqa: E722
            return None, None
    
    def get_core_gapping_technical_drawing(self, project_name, core_data, colors=None, output_path=f'{os.path.dirname(os.path.abspath(__file__))}/../../output/', save_files=True, export_files=True):
        raise NotImplementedError

    def get_turn(
        self,
        turn_description: TurnDescription,
        wire_description: WireDescription,
        bobbin_description: BobbinProcessedDescription,
    ) -> cq.Workplane:
        """Create a single turn geometry for a toroidal core."""
        return self._create_toroidal_turn(turn_description, wire_description, bobbin_description)

    def _create_toroidal_turn(
        self,
        turn_description: TurnDescription,
        wire_description: WireDescription,
        bobbin_description: BobbinProcessedDescription,
    ) -> cq.Workplane:
        """Create a toroidal turn using tubes and torus arcs.
        
        Coordinate system for toroidal cores:
        - Y axis: Core axis (torus revolves around Y)
        - X axis: Radial direction (negative X is inside the donut hole)
        - Z axis: Tangential direction (along the circumference at Y=0)
        
        The turn consists of:
        - Inner tube: At inner radius, going through the core hole (along Y)
        - Top radial segment: Connecting inner to outer on top of the core
        - Outer tube: At outer radius, going through the outside (along Y) 
        - Bottom radial segment: Connecting outer to inner below the core
        
        Wire coordinates are in XZ plane (at Y=0):
        - coordinates[0] = X position (radial, negative = inside hole)
        - coordinates[1] = Z position (tangential)
        """
        from OCP.gp import gp_Pnt, gp_Dir, gp_Ax2
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus
        import cadquery as cq
        
        # Scale factor to avoid OpenCascade precision issues
        SCALE = 1000.0  # Build in mm, scale back to meters at end
        
        # Get wire diameter
        wire_diameter = wire_description.outer_diameter or wire_description.conducting_diameter or 0.001
        wire_radius = wire_diameter * SCALE / 2.0
        
        # Get bobbin dimensions
        # column_depth is the half-depth of the core (distance from Y=0 to top/bottom)
        half_depth = bobbin_description.column_depth * SCALE
        
        # Bend radius for corners
        bend_radius = wire_radius
        
        # Get the turn's angular position around the toroid (rotation field in degrees)
        # This tells us where on the toroid's circumference this turn is located
        turn_angle_deg = turn_description.rotation  # e.g., 0, 90, 180, 270
        
        # Get inner wire position from coordinates
        # Coordinates are in Cartesian [x, z] format in the XZ plane
        # The radial distance from center is sqrt(x² + z²)
        coords = turn_description.coordinates
        if len(coords) >= 2:
            # Calculate radial distance using Pythagorean theorem
            inner_radial = math.sqrt(coords[0]**2 + coords[1]**2) * SCALE
        else:
            inner_radial = 5.0  # Default fallback
        
        # Get outer wire position from additionalCoordinates
        add_coords = turn_description.additional_coordinates
        if add_coords and len(add_coords) > 0:
            ac = add_coords[0]
            if len(ac) >= 2:
                # Calculate radial distance using Pythagorean theorem
                outer_radial = math.sqrt(ac[0]**2 + ac[1]**2) * SCALE
            else:
                outer_radial = inner_radial + (bobbin_description.winding_window_radial_height or 0.003) * SCALE
        else:
            # Fallback: outer is at inner + winding window height
            outer_radial = inner_radial + (bobbin_description.winding_window_radial_height or 0.003) * SCALE
        
        # The turn is built at the -X position (rotation=180°) then rotated to final position
        # Inner wire at -inner_radial on X axis, outer wire at -outer_radial on X axis
        inner_x = -inner_radial
        outer_x = -outer_radial
        
        # Calculate how much to rotate from the default position (180°) to the target position
        turn_rotation_deg = turn_angle_deg - 180.0
        
        # Radial distance between inner and outer wires
        radial_distance = outer_radial - inner_radial
        
        # Build geometry at origin first, then translate to actual position
        # Reference: inner wire at (0, 0, 0), outer wire at (-radial_distance, 0, 0)
        
        # Tube lengths (along Y, going through the core)
        tube_length = half_depth - bend_radius  # Shortened to make room for corner
        
        # Radial segment length (along X, on top/bottom of core)
        radial_length = radial_distance - 2 * bend_radius
        
        # === Build top half of turn (Y > 0) ===
        # Using workplane at Y=0 facing +Y direction
        
        # 1. Inner tube: at X=0, Z=0, from Y=0 to Y=tube_length (going up through the hole)
        #    Create on XY plane (normal = +Z), rotate to point in +Y
        inner_tube = cq.Workplane("XY").circle(wire_radius).extrude(tube_length)
        inner_tube = inner_tube.rotate((0,0,0), (1,0,0), -90)  # Rotate to point in +Y
        
        # 2. Inner corner: connects inner tube (at Y=tube_length) to radial segment
        #    The corner curves from +Y direction to -X direction
        #    Center is at (-bend_radius, tube_length, 0) - offset from the corner in the -X direction
        #    Arc goes from +X (relative to center, connects to tube) to +Y (connects to radial)
        #    With axis +Z and Xref +X, rotating +X by 90° around +Z gives +Y ✓
        inner_corner_center = gp_Pnt(-bend_radius, tube_length, 0)
        inner_corner_axis = gp_Ax2(inner_corner_center, gp_Dir(0, 0, 1), gp_Dir(1, 0, 0))
        inner_corner_torus = BRepPrimAPI_MakeTorus(inner_corner_axis, bend_radius, wire_radius, math.pi / 2).Shape()
        inner_corner = cq.Workplane("XY").add(cq.Shape(inner_corner_torus))
        
        # 3. Radial segment: at Y=half_depth, going from X=-bend_radius to X=-(bend_radius + radial_length)
        #    This is on top of the core, going radially outward (-X direction)
        #    Rotate -90 around Y to point in -X direction (positive rotation goes +Z to +X, so -90 goes +Z to -X)
        radial_tube = cq.Workplane("XY").circle(wire_radius).extrude(radial_length)
        radial_tube = radial_tube.rotate((0,0,0), (0,1,0), -90)  # Rotate to point in -X
        radial_tube = radial_tube.translate((-bend_radius, half_depth, 0))
        
        # 4. Outer corner: connects radial segment to outer tube
        #    The corner curves from +Y direction (relative to center) to -X direction
        #    Center is at (-radial_distance + bend_radius, tube_length, 0)
        #    With axis +Z and Xref +Y, rotating +Y by 90° around +Z gives -X ✓
        outer_corner_center = gp_Pnt(-radial_distance + bend_radius, tube_length, 0)
        outer_corner_axis = gp_Ax2(outer_corner_center, gp_Dir(0, 0, 1), gp_Dir(0, 1, 0))
        outer_corner_torus = BRepPrimAPI_MakeTorus(outer_corner_axis, bend_radius, wire_radius, math.pi / 2).Shape()
        outer_corner = cq.Workplane("XY").add(cq.Shape(outer_corner_torus))
        
        # 5. Outer tube: at X=-radial_distance, Z=0, from Y=0 to Y=tube_length
        outer_tube = cq.Workplane("XY").circle(wire_radius).extrude(tube_length)
        outer_tube = outer_tube.rotate((0,0,0), (1,0,0), -90)  # Rotate to point in +Y
        outer_tube = outer_tube.translate((-radial_distance, 0, 0))
        
        # Combine all parts of top half using compound (more reliable than unions)
        from OCP.BRep import BRep_Builder
        from OCP.TopoDS import TopoDS_Compound
        
        def combine_shapes(shapes):
            """Combine multiple shapes into a compound."""
            builder = BRep_Builder()
            compound = TopoDS_Compound()
            builder.MakeCompound(compound)
            for shape in shapes:
                builder.Add(compound, shape.val().wrapped)
            return cq.Workplane("XY").add(cq.Shape(compound))
        
        # Translate individual pieces to actual position BEFORE combining
        # The inner wire should be at inner_x on the X axis (inner_x is negative)
        # No Z translation needed - rotation will handle angular positioning
        inner_tube = inner_tube.translate((inner_x, 0, 0))
        inner_corner = inner_corner.translate((inner_x, 0, 0))
        radial_tube = radial_tube.translate((inner_x, 0, 0))
        outer_corner = outer_corner.translate((inner_x, 0, 0))
        outer_tube = outer_tube.translate((inner_x, 0, 0))
        
        # Combine all pieces into top half
        top_half = combine_shapes([inner_tube, inner_corner, radial_tube, outer_corner, outer_tube])
        
        # Mirror to create bottom half (mirror across XZ plane at Y=0)
        bottom_half = top_half.mirror("XZ")
        
        # Combine top and bottom halves
        full_turn = combine_shapes([top_half, bottom_half])
        
        # Rotate around Y axis if inner and outer wires are at different angles
        if abs(turn_rotation_deg) > 0.001:
            full_turn = full_turn.rotate((0, 0, 0), (0, 1, 0), turn_rotation_deg)
        
        # Scale back to meters
        final_shape = full_turn.val()
        scaled_shape = final_shape.scale(1 / SCALE)
        
        return cq.Workplane("XY").add(scaled_shape)

    def get_magnetic(
        self,
        magnetic_data: dict,
        project_name: str = "Magnetic",
        output_path: str = None,
        export_files: bool = True,
    ):
        """Build complete magnetic assembly (core + coil).
        
        Args:
            magnetic_data: MAS format magnetic data with 'core' and 'coil' keys
            project_name: Name for the output files
            output_path: Directory for output files
            export_files: Whether to export STEP/STL files
            
        Returns:
            Tuple of (step_path, stl_path) or compound if export_files is False
        """
        if output_path is None:
            output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../output/'
        
        os.makedirs(output_path, exist_ok=True)
        project_name = project_name.replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
        
        all_pieces = []
        
        # Build core
        core_data = magnetic_data.get('core', {})
        geometrical_description = core_data.get('geometricalDescription', [])
        if geometrical_description:
            for index, geometrical_part in enumerate(geometrical_description):
                if geometrical_part['type'] in ['half set', 'toroidal']:
                    shape_data = geometrical_part['shape']
                    part_builder = CadQueryBuilder().factory(shape_data)
                    
                    piece = part_builder.get_piece(
                        data=copy.deepcopy(shape_data),
                        name=f"Core_{index}",
                        save_files=False,
                        export_files=False
                    )
                    
                    # Apply rotations
                    piece = piece.rotate((1, 0, 0), (-1, 0, 0), geometrical_part['rotation'][0] / math.pi * 180)
                    piece = piece.rotate((0, 1, 0), (0, -1, 0), geometrical_part['rotation'][2] / math.pi * 180)
                    piece = piece.rotate((0, 0, 1), (0, 0, -1), geometrical_part['rotation'][1] / math.pi * 180)
                    
                    # Apply translation
                    piece = piece.translate(convert_axis(geometrical_part['coordinates']))
                    
                    all_pieces.append(piece)
        
        # Build coil turns
        coil_data = magnetic_data.get('coil', {})
        bobbin_data = coil_data.get('bobbin', {})
        if isinstance(bobbin_data, str):
            # Bobbin is a reference string, no processed description available
            bobbin_processed = BobbinProcessedDescription()
        else:
            bobbin_processed_data = bobbin_data.get('processedDescription', {})
            bobbin_processed = BobbinProcessedDescription.from_dict(bobbin_processed_data)
        
        # Get wire info from functionalDescription
        wire_desc = WireDescription(WireType.round)  # default
        functional_desc = coil_data.get('functionalDescription', [])
        if functional_desc:
            wire_data = functional_desc[0].get('wire', {})
            if wire_data:
                wire_desc = WireDescription.from_dict(wire_data)
        
        # In MAS format, turnsDescription is at coil level, not inside sections/layers
        turns_data = coil_data.get('turnsDescription', [])
        for turn_data in turns_data:
            turn_desc = TurnDescription.from_dict(turn_data)
            
            # Get wire dimensions from turn data if available
            if turn_data.get('dimensions'):
                dims = turn_data['dimensions']
                # dimensions is [width, height] or [diameter, diameter] for round wire
                if len(dims) >= 2:
                    wire_desc = WireDescription(
                        wire_type=WireType.round if turn_data.get('crossSectionalShape', 'round') == 'round' else WireType.rectangular,
                        outer_diameter=dims[0],
                        conducting_diameter=dims[0]
                    )
            
            turn_geom = self.get_turn(turn_desc, wire_desc, bobbin_processed)
            all_pieces.append(turn_geom)
        
        # Export
        if export_files and all_pieces:
            from cadquery import exporters
            scaled_pieces = []
            for piece in all_pieces:
                for o in piece.objects:
                    scaled_pieces.append(o.scale(1000))
            
            compound = cq.Compound.makeCompound(scaled_pieces)
            
            step_path = f"{output_path}/{project_name}.step"
            stl_path = f"{output_path}/{project_name}.stl"
            exporters.export(compound, step_path, "STEP")
            exporters.export(compound, stl_path, "STL")
            return step_path, stl_path
        elif all_pieces:
            return all_pieces
        else:
            return None, None

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

            if "S" in dimensions:
                if "F" in dimensions:
                    winding_column_width = dimensions["F"]
                else:
                    winding_column_width = dimensions["C"]

                if "H" in dimensions:
                    lateral_column_width = dimensions["H"]
                else:
                    lateral_column_width = dimensions["F"]

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
