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
import shape_configs
import cadquery as cq

file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)


# ==========================================================================
# Global Configuration for Tessellation Quality
# ==========================================================================

# Number of segments per full circle for curved surfaces in STL export
# Lower values = fewer polygons, faster rendering, smaller files
# Higher values = smoother curves, more polygons, larger files
# Default: 20 segments per circle (18° per segment)
TESSELLATION_SEGMENTS_PER_CIRCLE = 20

# Angular tolerance in degrees for STL tessellation
# This is derived from TESSELLATION_SEGMENTS_PER_CIRCLE
def get_angular_tolerance():
    """Get angular tolerance in radians based on segments per circle."""
    return 2 * math.pi / TESSELLATION_SEGMENTS_PER_CIRCLE

# Linear tolerance for STL tessellation (chord deviation)
# Smaller values = more accurate but more polygons
TESSELLATION_LINEAR_TOLERANCE = 0.1  # mm


def set_tessellation_quality(segments_per_circle: int = 20, linear_tolerance: float = 0.1):
    """Configure the tessellation quality for STL export.
    
    Args:
        segments_per_circle: Number of segments per full circle (default: 20).
            - 8-12: Very coarse, good for previews
            - 16-24: Medium quality, good balance
            - 32-48: High quality, smooth curves
            - 64+: Very high quality, large files
        linear_tolerance: Maximum chord deviation in mm (default: 0.1).
            Smaller values = more accurate but more polygons.
    
    Example:
        # Coarse quality for fast previews
        set_tessellation_quality(segments_per_circle=12)
        
        # High quality for final renders
        set_tessellation_quality(segments_per_circle=48, linear_tolerance=0.01)
    """
    global TESSELLATION_SEGMENTS_PER_CIRCLE, TESSELLATION_LINEAR_TOLERANCE
    TESSELLATION_SEGMENTS_PER_CIRCLE = segments_per_circle
    TESSELLATION_LINEAR_TOLERANCE = linear_tolerance


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


def flatten_dimensions(data):
    return utils.flatten_dimensions(data, scale_factor=1.0)


def convert_axis(coordinates):
    if len(coordinates) == 2:
        return [0, coordinates[0], coordinates[1]]
    elif len(coordinates) == 3:
        return [coordinates[0], coordinates[2], coordinates[1]]
    else:
        assert False, "Invalid coordinates length"


class CadQueryBuilder(utils.BuilderBase):
    """Builder for 3D magnetic component geometry using CadQuery.

    This class creates 3D geometry for magnetic components including:
    - Core shapes (E, ETD, PQ, RM, toroidal, etc.)
    - Coil turns (concentric and toroidal winding styles)
    - Bobbins

    Coordinate System (MAS to CadQuery mapping):
    - For concentric cores (E, PQ, RM, etc.):
        - X axis: Core depth direction (perpendicular to winding window)
        - Y axis: Core width direction (radial, distance from central column)
        - Z axis: Core height direction (along core axis, vertical)
        - MAS coordinates[0] (radial) -> Y position
        - MAS coordinates[1] (height) -> Z position

    - For toroidal cores:
        - Y axis: Core axis (toroid revolves around Y)
        - X axis: Radial direction (negative X = inside the donut hole)
        - Z axis: Tangential direction (along circumference at Y=0)
        - MAS coordinates[0] (radial) -> distance from Y axis
        - MAS coordinates[1] (angular) -> rotation angle around Y axis

    Units:
    - All MAS input values are in meters
    - Internal geometry is built in millimeters for precision
    - Output is scaled back to meters before export
    """

    # Scale factor: build geometry in mm, scale back to meters for output
    SCALE = 1000.0

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
            utils.ShapeFamily.UT: self.Ut(),
            utils.ShapeFamily.C: self.C()
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
                # Use configurable tessellation parameters for STL
                exporters.export(
                    scaled_pieces_to_export, 
                    f"{output_path}/{project_name}.stl", 
                    "STL",
                    tolerance=TESSELLATION_LINEAR_TOLERANCE,
                    angularTolerance=get_angular_tolerance()
                )
                return f"{output_path}/{project_name}.step", f"{output_path}/{project_name}.stl",
            else:
                return scaled_pieces_to_export

        except:  # noqa: E722
            return None, None

    def get_magnetic_assembly(self, project_name, assembly_data, output_path=None, save_files=True, export_files=True):
        """Build a magnetic assembly from core, bobbin, and winding data.

        Parameters
        ----------
        project_name : str
            Name for the output files.
        assembly_data : dict
            Dictionary with optional keys: 'core', 'bobbin', 'windings', 'coil'.
        output_path : str
            Directory for output files.
        save_files : bool
            Whether to save intermediate files.
        export_files : bool
            Whether to export STEP/STL files.
        """
        try:
            from cadquery import exporters

            if output_path is None:
                output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../output/'

            os.makedirs(output_path, exist_ok=True)
            project_name = f"{project_name}".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")

            pieces = []

            # Build core
            if "core" in assembly_data and assembly_data["core"].get("geometricalDescription"):
                geometrical_description = assembly_data["core"]["geometricalDescription"]
                for index, geometrical_part in enumerate(geometrical_description):
                    if geometrical_part['type'] == 'spacer':
                        spacer = self.get_spacer(geometrical_part)
                        pieces.append(spacer)
                    elif geometrical_part['type'] in ['half set', 'toroidal']:
                        shape_data = geometrical_part['shape']
                        part_builder = CadQueryBuilder().factory(shape_data)

                        piece = part_builder.get_piece(data=copy.deepcopy(shape_data),
                                                       name=f"Piece_{index}",
                                                       save_files=False,
                                                       export_files=False)
                        if piece is None:
                            continue

                        piece = piece.rotate((1, 0, 0), (-1, 0, 0), geometrical_part['rotation'][0] / math.pi * 180)
                        piece = piece.rotate((0, 1, 0), (0, -1, 0), geometrical_part['rotation'][2] / math.pi * 180)
                        piece = piece.rotate((0, 0, 1), (0, 0, -1), geometrical_part['rotation'][1] / math.pi * 180)

                        if 'machining' in geometrical_part and geometrical_part['machining'] is not None:
                            for machining in geometrical_part['machining']:
                                piece = part_builder.apply_machining(piece=piece,
                                                                     machining=machining,
                                                                     dimensions=flatten_dimensions(shape_data))

                        piece = piece.translate(convert_axis(geometrical_part['coordinates']))

                        if geometrical_part['type'] in ['half set']:
                            residual_gap = 5e-6
                            if geometrical_part['rotation'][0] > 0:
                                piece = piece.translate((0, 0, residual_gap / 2))
                            else:
                                piece = piece.translate((0, 0, -residual_gap / 2))

                        pieces.append(piece)

            if not pieces:
                return None, None

            if export_files:
                scaled_pieces = []
                for piece in pieces:
                    for o in piece.objects:
                        scaled_pieces.append(o.scale(1000))

                compound = cq.Compound.makeCompound(scaled_pieces)

                exporters.export(compound, f"{output_path}/{project_name}_assembly.step", "STEP")
                exporters.export(
                    compound,
                    f"{output_path}/{project_name}_assembly.stl",
                    "STL",
                    tolerance=TESSELLATION_LINEAR_TOLERANCE,
                    angularTolerance=get_angular_tolerance()
                )
                return f"{output_path}/{project_name}_assembly.step", f"{output_path}/{project_name}_assembly.stl"
            else:
                return pieces

        except:  # noqa: E722
            return None, None

    def get_bobbin(self, bobbin_data, winding_window, name="Bobbin", output_path=None, save_files=False, export_files=True):
        if output_path is None:
            output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../output/'

        bobbin_builder = self.StandardBobbin()
        bobbin_builder.set_output_path(output_path)
        return bobbin_builder.get_bobbin(bobbin_data, winding_window, name, save_files, export_files)

    def get_winding(self, winding_data, bobbin_dims, name="Winding", output_path=None, save_files=False, export_files=True):
        if output_path is None:
            output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../output/'

        winding_builder = self.RoundWireWinding()
        winding_builder.set_output_path(output_path)
        return winding_builder.get_winding(winding_data, bobbin_dims, name, save_files, export_files)

    def get_core_gapping_technical_drawing(self, project_name, core_data, colors=None, output_path=f'{os.path.dirname(os.path.abspath(__file__))}/../../output/', save_files=True, export_files=True):
        try:
            from cadquery import exporters
            from cadquery.occ_impl.exporters.svg import getSVG

            svg_project_name = f"{project_name}_core_gaps_FrontView".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
            geometrical_description = core_data['geometricalDescription']

            os.makedirs(output_path, exist_ok=True)

            if colors is None:
                colors = {
                    "projection_color": "#000000",
                    "dimension_color": "#000000"
                }

            pieces_to_export = []
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
                    if piece is None:
                        continue

                    piece = piece.rotate((1, 0, 0), (-1, 0, 0), geometrical_part['rotation'][0] / math.pi * 180)
                    piece = piece.rotate((0, 1, 0), (0, -1, 0), geometrical_part['rotation'][2] / math.pi * 180)
                    piece = piece.rotate((0, 0, 1), (0, 0, -1), geometrical_part['rotation'][1] / math.pi * 180)

                    if 'machining' in geometrical_part and geometrical_part['machining'] is not None:
                        for machining in geometrical_part['machining']:
                            piece = part_builder.apply_machining(piece=piece,
                                                                 machining=machining,
                                                                 dimensions=flatten_dimensions(shape_data))

                    piece = piece.translate(convert_axis(geometrical_part['coordinates']))
                    pieces_to_export.append(piece)

            if not pieces_to_export:
                return None

            scaled_pieces = []
            for piece in pieces_to_export:
                for o in piece.objects:
                    scaled_pieces.append(o.scale(1000))

            compound = cq.Compound.makeCompound(scaled_pieces)

            stroke_color = self.IPiece._hex_to_rgb(colors.get("projection_color", "#000000"))
            svg_opts = {
                "width": 800,
                "height": 600,
                "strokeWidth": 0.5,
                "strokeColor": stroke_color,
                "showHidden": False,
                "projectionDir": (0, 1, 0),
            }

            front_svg = getSVG(compound, svg_opts)
            svg_path = f"{output_path}/{svg_project_name}.svg"
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(front_svg)

            return front_svg

        except Exception:
            return None

    def get_turn(
        self,
        turn_description: TurnDescription,
        wire_description: WireDescription,
        bobbin_description: BobbinProcessedDescription,
        is_toroidal: bool = False,
    ) -> cq.Workplane:
        """Create a single turn geometry.
        
        Args:
            turn_description: Turn parameters (coordinates, winding, etc.)
            wire_description: Wire parameters (type, diameter, etc.)
            bobbin_description: Bobbin parameters
            is_toroidal: If True, create toroidal turn; otherwise concentric turn
            
        Returns:
            CadQuery Workplane with the turn geometry
        """
        if is_toroidal or bobbin_description.winding_window_angle is not None:
            return self._create_toroidal_turn(turn_description, wire_description, bobbin_description)
        else:
            return self._create_concentric_turn(turn_description, wire_description, bobbin_description)

    def _create_concentric_turn(
        self,
        turn_description: TurnDescription,
        wire_description: WireDescription,
        bobbin_description: BobbinProcessedDescription,
    ) -> cq.Workplane:
        """Create a concentric turn (for E-cores, PQ, RM, etc.).
        
        Following Ansyas approach with CadQuery coordinate system:
        - X axis: depth direction (along column depth, perpendicular to winding window)
        - Y axis: width direction (radial, distance from center column)
        - Z axis: height direction (along core axis, vertical)
        
        MAS coordinates for turns:
        - coordinates[0] = radial position (distance from center) -> maps to Y
        - coordinates[1] = height position (along core axis) -> maps to Z
        
        The turn is built as 4 straight tubes + 4 corner quarter-tori.
        """
        from OCP.gp import gp_Pnt, gp_Dir, gp_Ax1, gp_Ax2
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus, BRepPrimAPI_MakeRevol
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
        from OCP.GC import GC_MakeCircle
        from OCP.BRep import BRep_Builder
        from OCP.TopoDS import TopoDS_Compound
        import cadquery as cq
        
        SCALE = self.SCALE
        
        # Get wire dimensions
        is_rectangular_wire = wire_description.wire_type == WireType.rectangular
        if is_rectangular_wire:
            # Try turn dimensions first, then fall back to wire description
            if turn_description.dimensions and len(turn_description.dimensions) >= 2:
                wire_width = turn_description.dimensions[0] * SCALE
                wire_height = turn_description.dimensions[1] * SCALE
            else:
                wire_width = (wire_description.outer_width or wire_description.conducting_width or 0.001) * SCALE
                wire_height = (wire_description.outer_height or wire_description.conducting_height or 0.001) * SCALE
            wire_radius = min(wire_width, wire_height) / 2.0  # used for corner sizing
        else:  # round, litz
            wire_diameter = (wire_description.outer_diameter or wire_description.conducting_diameter or 0.001) * SCALE
            wire_radius = wire_diameter / 2.0
            wire_width = wire_diameter  # for consistent API
            wire_height = wire_diameter
        
        # Get bobbin/column dimensions
        # In MAS, bobbin columnWidth and columnDepth are HALF dimensions (distance from center to edge)
        half_col_depth = bobbin_description.column_depth * SCALE  # half column depth
        half_col_width = bobbin_description.column_width * SCALE  # half column width
        
        # Get turn position from coordinates
        coords = turn_description.coordinates
        radial_pos = coords[0] * SCALE if len(coords) > 0 else (half_col_width + wire_radius)
        height_pos = coords[1] * SCALE if len(coords) > 1 else 0
        
        # Corner radius: distance from column edge to wire center
        # Ansyas: turn_turn_radius = turn.coordinates[0] - columnWidth
        turn_turn_radius = radial_pos - half_col_width
        if turn_turn_radius < wire_radius:
            turn_turn_radius = wire_radius
        
        if bobbin_description.column_shape == ColumnShape.round:
            # Round column: circular turn path
            turn_radius = radial_pos  # Distance from center to wire center
            
            if is_rectangular_wire:
                # For rectangular wire: sweep a rectangular cross-section around the circular path
                # Create rectangular cross-section at the wire center position, then sweep
                from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
                from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
                from OCP.GC import GC_MakeCircle
                
                # Create the circular spine (path around the column)
                spine_center = gp_Pnt(0, 0, height_pos)
                spine_axis = gp_Ax2(spine_center, gp_Dir(0, 0, 1), gp_Dir(1, 0, 0))
                spine_circle = GC_MakeCircle(spine_axis, turn_radius).Value()
                spine_edge = BRepBuilderAPI_MakeEdge(spine_circle).Edge()
                spine_wire = BRepBuilderAPI_MakeWire(spine_edge).Wire()
                
                # Create rectangular cross-section profile at the start of the path
                # Profile is in the YZ plane (perpendicular to X, the initial tangent direction)
                # Centered at (turn_radius, 0, height_pos)
                profile = (
                    cq.Workplane("YZ")
                    .center(turn_radius, height_pos)
                    .rect(wire_width, wire_height)
                    .wires().val()
                )
                profile_face = BRepBuilderAPI_MakeFace(profile.wrapped).Face()
                
                # Sweep the rectangle along the spine
                pipe = BRepOffsetAPI_MakePipe(spine_wire, profile_face).Shape()
                turn = cq.Workplane("XY").add(cq.Shape(pipe))
            else:
                # For round wire: use torus
                torus_center = gp_Pnt(0, 0, height_pos)
                torus_axis = gp_Ax2(torus_center, gp_Dir(0, 0, 1), gp_Dir(1, 0, 0))
                torus = BRepPrimAPI_MakeTorus(torus_axis, turn_radius, wire_radius).Shape()
                turn = cq.Workplane("XY").add(cq.Shape(torus))
            
        else:
            # Rectangular column: build using tubes and torus arcs
            # 
            # The turn is a rounded rectangle around the column:
            # - 4 straight tubes (one per side of the column)
            # - 4 corner quarter-tori connecting the tubes
            #
            # Tube positions (wire center):
            # - +Y side: runs along X from -half_col_depth to +half_col_depth, at Y = radial_pos
            # - -Y side: runs along X from -half_col_depth to +half_col_depth, at Y = -radial_pos  
            # - +X side: runs along Y from -half_col_width to +half_col_width, at X = half_col_depth + turn_turn_radius
            # - -X side: runs along Y from -half_col_width to +half_col_width, at X = -(half_col_depth + turn_turn_radius)
            
            builder = BRep_Builder()
            compound = TopoDS_Compound()
            builder.MakeCompound(compound)
            
            # Calculate positions
            # Wire center on +Y and -Y sides is at radial_pos from center
            # Wire center on +X and -X sides is at half_col_depth + turn_turn_radius from center
            wire_y_pos = radial_pos  # = half_col_width + turn_turn_radius
            wire_x_pos = half_col_depth + turn_turn_radius
            
            # Tube lengths
            tube_x_length = 2 * half_col_depth  # tubes along X span full column depth
            tube_y_length = 2 * half_col_width  # tubes along Y span full column width
            
            # +Y side tube (along X, at Y = wire_y_pos)
            tube_py = (
                cq.Workplane("YZ")
                .center(wire_y_pos, height_pos)
                .circle(wire_radius)
                .extrude(tube_x_length)
                .translate((-half_col_depth, 0, 0))
            )
            builder.Add(compound, tube_py.val().wrapped)
            
            # -Y side tube (along X, at Y = -wire_y_pos)
            tube_ny = (
                cq.Workplane("YZ")
                .center(-wire_y_pos, height_pos)
                .circle(wire_radius)
                .extrude(tube_x_length)
                .translate((-half_col_depth, 0, 0))
            )
            builder.Add(compound, tube_ny.val().wrapped)
            
            # +X side tube (along Y, at X = wire_x_pos)
            # XZ plane extrudes in -Y by default, so use positive to go -Y then translate up
            tube_px = (
                cq.Workplane("XZ")
                .center(wire_x_pos, height_pos)
                .circle(wire_radius)
                .extrude(tube_y_length)  # Goes from Y=0 to Y=-tube_y_length
                .translate((0, half_col_width, 0))  # Shift up to center at Y=0
            )
            builder.Add(compound, tube_px.val().wrapped)
            
            # -X side tube (along Y, at X = -wire_x_pos)
            tube_nx = (
                cq.Workplane("XZ")
                .center(-wire_x_pos, height_pos)
                .circle(wire_radius)
                .extrude(tube_y_length)  # Goes from Y=0 to Y=-tube_y_length
                .translate((0, half_col_width, 0))  # Shift up to center at Y=0
            )
            builder.Add(compound, tube_nx.val().wrapped)
            
            # Four corner arcs (quarter tori created by revolving a circle 90°)
            # Corners are at (±half_col_depth, ±half_col_width, height_pos)
            # Each corner has a quarter-torus connecting two adjacent tubes
            #
            # For each corner:
            # 1. Create a circle (wire cross-section) at turn_turn_radius from corner
            # 2. Revolve 90° around Z axis at corner center
            
            def create_quarter_torus(corner_x, corner_y, corner_z, start_angle_deg):
                """Create a quarter torus at the given corner.
                
                start_angle_deg: angle from +X axis where the circle starts
                The circle will revolve 90° counterclockwise (when viewed from +Z)
                """
                # Circle center position (turn_turn_radius from corner, at start angle)
                angle_rad = math.radians(start_angle_deg)
                circle_x = corner_x + turn_turn_radius * math.cos(angle_rad)
                circle_y = corner_y + turn_turn_radius * math.sin(angle_rad)
                
                # Circle normal points tangent to the arc (perpendicular to radial direction)
                # For counterclockwise rotation, tangent is 90° ahead
                tangent_angle = angle_rad + math.pi / 2
                circle_normal = gp_Dir(math.cos(tangent_angle), math.sin(tangent_angle), 0)
                
                circle_center = gp_Pnt(circle_x, circle_y, corner_z)
                circle_axis = gp_Ax2(circle_center, circle_normal)
                
                circle = GC_MakeCircle(circle_axis, wire_radius).Value()
                circle_edge = BRepBuilderAPI_MakeEdge(circle).Edge()
                circle_wire = BRepBuilderAPI_MakeWire(circle_edge).Wire()
                circle_face = BRepBuilderAPI_MakeFace(circle_wire).Face()
                
                # Revolve around Z axis at corner
                revolve_axis = gp_Ax1(gp_Pnt(corner_x, corner_y, corner_z), gp_Dir(0, 0, 1))
                quarter = BRepPrimAPI_MakeRevol(circle_face, revolve_axis, math.pi / 2).Shape()
                
                return quarter
            
            # +X +Y corner: circle starts at +X direction (0°), sweeps to +Y
            corner_shape = create_quarter_torus(+half_col_depth, +half_col_width, height_pos, 0)
            builder.Add(compound, corner_shape)
            
            # -X +Y corner: circle starts at +Y direction (90°), sweeps to -X
            corner_shape = create_quarter_torus(-half_col_depth, +half_col_width, height_pos, 90)
            builder.Add(compound, corner_shape)
            
            # -X -Y corner: circle starts at -X direction (180°), sweeps to -Y
            corner_shape = create_quarter_torus(-half_col_depth, -half_col_width, height_pos, 180)
            builder.Add(compound, corner_shape)
            
            # +X -Y corner: circle starts at -Y direction (270°), sweeps to +X
            corner_shape = create_quarter_torus(+half_col_depth, -half_col_width, height_pos, 270)
            builder.Add(compound, corner_shape)
            
            turn = cq.Workplane("XY").add(cq.Shape(compound))
        
        # Scale back to meters
        final_shape = turn.val()
        scaled_shape = final_shape.scale(1 / SCALE)
        
        return cq.Workplane("XY").add(scaled_shape)

    def _build_bobbin_geometry(
        self,
        bobbin_description: BobbinProcessedDescription,
    ) -> Optional[cq.Workplane]:
        """Create bobbin geometry for concentric (E-core, PQ, etc.) magnetics.

        Internal method used by get_magnetic for MAS-based bobbin creation.

        Args:
            bobbin_description: Processed bobbin parameters

        Returns:
            CadQuery Workplane with bobbin geometry, or None if bobbin has zero thickness
        """
        # Check if bobbin has actual thickness
        if (round(bobbin_description.wall_thickness, 12) == 0 or 
            round(bobbin_description.column_thickness, 12) == 0):
            return None
        
        SCALE = self.SCALE
        
        # Scale to mm for construction
        col_depth = bobbin_description.column_depth * SCALE
        col_width = bobbin_description.column_width * SCALE
        col_thickness = bobbin_description.column_thickness * SCALE
        wall_thickness = bobbin_description.wall_thickness * SCALE
        ww_height = bobbin_description.winding_window_height * SCALE
        ww_width = bobbin_description.winding_window_width * SCALE
        
        # Total bobbin dimensions
        total_height = ww_height + wall_thickness * 2
        total_width = ww_width + col_width
        total_depth = ww_width + col_depth
        
        if bobbin_description.column_shape == ColumnShape.round:
            # Round column bobbin (cylindrical)
            bobbin = (
                cq.Workplane("XY")
                .cylinder(total_height, total_width)
            )
            
            # Negative winding window (hollow ring)
            neg_ww = (
                cq.Workplane("XY")
                .cylinder(ww_height, total_width)
            )
            
            # Central column solid (will be subtracted from negative_ww)
            central_col = (
                cq.Workplane("XY")
                .cylinder(ww_height, col_width)
            )
            
            # Central hole (through entire height)
            central_hole = (
                cq.Workplane("XY")
                .cylinder(total_height, col_width - col_thickness)
            )
            
            # Subtract operations
            neg_ww_cut = neg_ww.cut(central_col)
            bobbin = bobbin.cut(neg_ww_cut)
            bobbin = bobbin.cut(central_hole)
            
        else:
            # Rectangular column bobbin (box-shaped)
            # Create outer shell centered at origin
            bobbin = (
                cq.Workplane("XY")
                .box(total_depth * 2, total_width * 2, total_height)
            )
            
            # Negative winding window (hollow region where turns go)
            neg_ww = (
                cq.Workplane("XY")
                .box(total_depth * 2, total_width * 2, ww_height)
            )
            
            # Central column solid (keeps material around column)
            central_col = (
                cq.Workplane("XY")
                .box(col_depth * 2, col_width * 2, ww_height)
            )
            
            # Central hole (through entire height for the core column)
            inner_depth = col_depth - col_thickness
            inner_width = col_width - col_thickness
            central_hole = (
                cq.Workplane("XY")
                .box(inner_depth * 2, inner_width * 2, total_height)
            )
            
            # Subtract operations (same as Ansyas logic)
            neg_ww_cut = neg_ww.cut(central_col)
            bobbin = bobbin.cut(neg_ww_cut)
            bobbin = bobbin.cut(central_hole)
        
        # Scale back to meters
        final_shape = bobbin.val()
        scaled_shape = final_shape.scale(1 / SCALE)
        
        return cq.Workplane("XY").add(scaled_shape)

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
        
        For multilayer turns, the outer wire may be at a different angular position
        than the inner wire. The radial segment will be angled to connect them.
        
        Wire coordinates are in XZ plane (at Y=0):
        - coordinates[0] = X position (radial, negative = inside hole)
        - coordinates[1] = Z position (tangential)
        """
        from OCP.gp import gp_Pnt, gp_Dir, gp_Ax2, gp_Circ
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus
        from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
        from OCP.GC import GC_MakeCircle, GC_MakeArcOfCircle
        import cadquery as cq
        
        SCALE = self.SCALE
        
        # Determine wire type and dimensions
        is_rectangular_wire = wire_description.wire_type == WireType.rectangular
        if is_rectangular_wire:
            # Try turn dimensions first, then fall back to wire description
            if turn_description.dimensions and len(turn_description.dimensions) >= 2:
                wire_width = turn_description.dimensions[0] * SCALE
                wire_height = turn_description.dimensions[1] * SCALE
            else:
                wire_width = (wire_description.outer_width or wire_description.conducting_width or 0.001) * SCALE
                wire_height = (wire_description.outer_height or wire_description.conducting_height or 0.001) * SCALE
            wire_radius = min(wire_width, wire_height) / 2.0  # for corner sizing
        else:
            wire_diameter = (wire_description.outer_diameter or wire_description.conducting_diameter or 0.001) * SCALE
            wire_radius = wire_diameter / 2.0
            wire_width = wire_diameter
            wire_height = wire_diameter
        
        # Get bobbin dimensions
        # column_depth is the half-depth of the core (distance from Y=0 to top/bottom)
        half_depth = bobbin_description.column_depth * SCALE
        
        # Bend radius for corners
        # For rectangular wire, use half of the larger dimension so corners properly connect
        if is_rectangular_wire:
            bend_radius = max(wire_width, wire_height) / 2.0
        else:
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
            # Calculate angular position of inner wire
            inner_angle_deg = 180.0 / math.pi * math.atan2(coords[1], coords[0])
        else:
            inner_radial = 5.0  # Default fallback
            inner_angle_deg = turn_angle_deg
        
        # Get outer wire position from additionalCoordinates
        add_coords = turn_description.additional_coordinates
        if add_coords and len(add_coords) > 0:
            ac = add_coords[0]
            if len(ac) >= 2:
                # Calculate radial distance using Pythagorean theorem
                outer_radial = math.sqrt(ac[0]**2 + ac[1]**2) * SCALE
                # Calculate angular position of outer wire
                outer_angle_deg = 180.0 / math.pi * math.atan2(ac[1], ac[0])
            else:
                outer_radial = inner_radial + (bobbin_description.winding_window_radial_height or 0.003) * SCALE
                outer_angle_deg = inner_angle_deg
        else:
            # Fallback: outer is at inner + winding window height, same angle
            outer_radial = inner_radial + (bobbin_description.winding_window_radial_height or 0.003) * SCALE
            outer_angle_deg = inner_angle_deg
        
        # Calculate the angle difference between inner and outer wires (for multilayer)
        # This is the "tilt" of the radial segment around the Y axis
        angle_diff_deg = outer_angle_deg - inner_angle_deg
        angle_diff_rad = math.radians(angle_diff_deg)
        
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
        
        # Clearance between wire and core surface
        # For multilayer: inner layers need more clearance so outer layers can pass underneath
        # The radial segment height is based on the radial distance being spanned
        # This ensures turns with larger spans (inner layers) have higher radial segments
        base_clearance = wire_radius
        
        # Add extra height based on radial_distance - inner layers span more distance
        # so their top/bottom segments need to be higher to clear outer layer segments
        core_internal_radius = bobbin_description.winding_window_radial_height * SCALE
        layer_clearance = core_internal_radius - inner_radial

        # The radial segment (top/bottom) should be at half_depth + total clearance
        radial_height = half_depth + base_clearance + layer_clearance
        
        # Tube lengths (along Y, going through the core)
        # Tubes go from Y=0 to Y=(radial_height - bend_radius) to leave room for corner
        tube_length = radial_height - bend_radius
        
        # For the radial segment, we need to account for the angle difference
        # The segment goes from inner corner end to outer corner start
        # With angle difference, outer parts are rotated around Y axis
        
        # Radial segment length (straight line distance between corners)
        # Inner corner end: (-bend_radius, half_depth, 0) 
        # Outer corner start needs to connect to outer tube which is at angle_diff offset
        radial_length = radial_distance - 2 * bend_radius
        
        # === Build top half of turn (Y > 0) ===
        # Using workplane at Y=0 facing +Y direction
        
        # Helper function to create a tube (extruded cross-section)
        def create_tube(length, plane="XY", swap_dims=False):
            """Create a tube with circular or rectangular cross-section.
            
            For rectangular wire, dimensions are:
            - wire_width: tangential dimension (along toroid circumference)
            - wire_height: radial dimension (toward/away from core axis Y)
            
            After rotation:
            - Inner/outer tubes: point in +Y, cross-section in XZ plane
              -> width in X (tangential), height in Z (radial, but Z is up)
            - Radial tubes: point in -X, cross-section in YZ plane
              -> need to swap: width in Z (tangential), height in Y (radial)
            """
            wp = cq.Workplane(plane)
            if is_rectangular_wire:
                if swap_dims:
                    # For radial tube: height goes in Y (radial), width in Z (tangential)
                    return wp.rect(wire_height, wire_width).extrude(length)
                else:
                    return wp.rect(wire_width, wire_height).extrude(length)
            else:
                return wp.circle(wire_radius).extrude(length)
        
        # Helper function to create a corner (swept cross-section around arc)
        def create_corner(center_pt, axis_dir, x_ref_dir, angle_rad=math.pi/2):
            """Create a corner with circular or rectangular cross-section.
            
            For round wire: use torus
            For rectangular wire: sweep rectangle along arc path
            """
            if is_rectangular_wire:
                # Create arc path for the corner
                # The arc is centered at center_pt, in the plane normal to axis_dir
                arc_center = center_pt
                
                # Calculate start and end points of the arc
                # Start point is at x_ref_dir * bend_radius from center
                start_x = arc_center.X() + x_ref_dir.X() * bend_radius
                start_y = arc_center.Y() + x_ref_dir.Y() * bend_radius
                start_z = arc_center.Z() + x_ref_dir.Z() * bend_radius
                start_pt = gp_Pnt(start_x, start_y, start_z)
                
                # End point is x_ref rotated by angle_rad around axis
                cos_a = math.cos(angle_rad)
                sin_a = math.sin(angle_rad)
                ax = axis_dir.X()
                ay = axis_dir.Y()
                az = axis_dir.Z()
                rx = x_ref_dir.X()
                ry = x_ref_dir.Y()
                rz = x_ref_dir.Z()
                
                # Rodrigues rotation formula
                dot = ax*rx + ay*ry + az*rz
                cross_x = ay*rz - az*ry
                cross_y = az*rx - ax*rz
                cross_z = ax*ry - ay*rx
                
                end_ref_x = rx*cos_a + cross_x*sin_a + ax*dot*(1-cos_a)
                end_ref_y = ry*cos_a + cross_y*sin_a + ay*dot*(1-cos_a)
                end_ref_z = rz*cos_a + cross_z*sin_a + az*dot*(1-cos_a)
                
                end_x = arc_center.X() + end_ref_x * bend_radius
                end_y = arc_center.Y() + end_ref_y * bend_radius
                end_z = arc_center.Z() + end_ref_z * bend_radius
                end_pt = gp_Pnt(end_x, end_y, end_z)
                
                # Create the arc using gp_Circ
                arc_axis = gp_Ax2(arc_center, axis_dir, x_ref_dir)
                arc_circle = gp_Circ(arc_axis, bend_radius)
                arc = GC_MakeArcOfCircle(arc_circle, 0, angle_rad, True).Value()
                arc_edge = BRepBuilderAPI_MakeEdge(arc).Edge()
                arc_wire = BRepBuilderAPI_MakeWire(arc_edge).Wire()
                
                # Create rectangular profile at start point
                # Profile plane is perpendicular to the arc tangent at start
                # Tangent at start is perpendicular to x_ref in the arc plane (cross product of axis and x_ref)
                tangent_x = ay*rz - az*ry  # axis × x_ref
                tangent_y = az*rx - ax*rz
                tangent_z = ax*ry - ay*rx
                tangent_dir = gp_Dir(tangent_x, tangent_y, tangent_z)
                
                profile_axis = gp_Ax2(start_pt, tangent_dir)
                
                # Create rectangle centered at start_pt
                # Use OCP to create the rectangle
                from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
                hw = wire_width / 2
                hh = wire_height / 2
                
                # Rectangle vertices in local coordinates (perpendicular to tangent)
                # Local X = axis_dir, Local Y = x_ref_dir (approximately, for the profile orientation)
                # Actually we need vectors perpendicular to tangent
                # Use axis_dir and (tangent × axis) for the profile plane
                profile_x = gp_Dir(ax, ay, az)  # Use axis direction
                profile_y_x = tangent_y*az - tangent_z*ay
                profile_y_y = tangent_z*ax - tangent_x*az
                profile_y_z = tangent_x*ay - tangent_y*ax
                profile_y_len = math.sqrt(profile_y_x**2 + profile_y_y**2 + profile_y_z**2)
                if profile_y_len > 1e-10:
                    profile_y_x /= profile_y_len
                    profile_y_y /= profile_y_len
                    profile_y_z /= profile_y_len
                else:
                    profile_y_x, profile_y_y, profile_y_z = rx, ry, rz
                
                # Four corners of rectangle
                def offset_point(base, dx_local, dy_local):
                    return gp_Pnt(
                        base.X() + dx_local * profile_x.X() + dy_local * profile_y_x,
                        base.Y() + dx_local * profile_x.Y() + dy_local * profile_y_y,
                        base.Z() + dx_local * profile_x.Z() + dy_local * profile_y_z
                    )
                
                p1 = offset_point(start_pt, -hh, -hw)
                p2 = offset_point(start_pt, -hh, +hw)
                p3 = offset_point(start_pt, +hh, +hw)
                p4 = offset_point(start_pt, +hh, -hw)
                
                poly = BRepBuilderAPI_MakePolygon(p1, p2, p3, p4, True)
                rect_wire = poly.Wire()
                rect_face = BRepBuilderAPI_MakeFace(rect_wire).Face()
                
                # Sweep rectangle along arc
                pipe = BRepOffsetAPI_MakePipe(arc_wire, rect_face).Shape()
                return cq.Workplane("XY").add(cq.Shape(pipe))
            else:
                # Round wire: use torus
                corner_axis = gp_Ax2(center_pt, axis_dir, x_ref_dir)
                torus = BRepPrimAPI_MakeTorus(corner_axis, bend_radius, wire_radius, angle_rad).Shape()
                return cq.Workplane("XY").add(cq.Shape(torus))
        
        # 1. Inner tube: at X=0, Z=0, from Y=0 to Y=tube_length (going up through the hole)
        #    Create on XY plane (normal = +Z), rotate to point in +Y
        inner_tube = create_tube(tube_length)
        inner_tube = inner_tube.rotate((0,0,0), (1,0,0), -90)  # Rotate to point in +Y
        
        # 2. Inner corner: connects inner tube (at Y=tube_length) to radial segment
        #    The corner curves from +Y direction to -X direction
        #    Center is at (-bend_radius, tube_length, 0) - offset from the corner in the -X direction
        #    Arc goes from +X (relative to center, connects to tube) to +Y (connects to radial)
        #    With axis +Z and Xref +X, rotating +X by 90° around +Z gives +Y ✓
        inner_corner_center = gp_Pnt(-bend_radius, tube_length, 0)
        inner_corner = create_corner(inner_corner_center, gp_Dir(0, 0, 1), gp_Dir(1, 0, 0))
        
        # 3. Radial segment: at Y=radial_height, from inner corner to outer corner
        #    For multilayer, this needs to be tilted to connect to the outer wire at angle_diff
        #    The radial segment goes from (-bend_radius, radial_height, 0) toward outer position
        #    swap_dims=True because after rotating -90° around Y, the cross-section is in YZ plane
        radial_tube = create_tube(radial_length, swap_dims=True)
        radial_tube = radial_tube.rotate((0,0,0), (0,1,0), -90)  # Rotate to point in -X
        
        # Apply tilt for angle difference - rotate around Y at the inner corner position
        if abs(angle_diff_deg) > 0.001:
            # The radial tube needs to be tilted by angle_diff around Y axis
            # But the rotation point should be at the inner end of the radial
            radial_tube = radial_tube.rotate((0, 0, 0), (0, 1, 0), angle_diff_deg)
        
        radial_tube = radial_tube.translate((-bend_radius, radial_height, 0))
        
        # 4. Outer corner: connects radial segment to outer tube
        #    The corner curves from +Y direction (relative to center) to -X direction
        #    Center is at (-radial_distance + bend_radius, tube_length, 0)
        #    For multilayer, this corner and outer tube are rotated by angle_diff around Y
        outer_corner_center = gp_Pnt(-radial_distance + bend_radius, tube_length, 0)
        outer_corner = create_corner(outer_corner_center, gp_Dir(0, 0, 1), gp_Dir(0, 1, 0))
        
        # 5. Outer tube: at X=-radial_distance, Z=0, from Y=0 to Y=tube_length
        outer_tube = create_tube(tube_length)
        outer_tube = outer_tube.rotate((0,0,0), (1,0,0), -90)  # Rotate to point in +Y
        outer_tube = outer_tube.translate((-radial_distance, 0, 0))
        
        # Apply angle offset to outer parts for multilayer
        if abs(angle_diff_deg) > 0.001:
            # Rotate outer corner and outer tube around Y axis at origin
            outer_corner = outer_corner.rotate((0, 0, 0), (0, 1, 0), angle_diff_deg)
            outer_tube = outer_tube.rotate((0, 0, 0), (0, 1, 0), angle_diff_deg)
        
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
        
        # Detect if this is a toroidal core
        is_toroidal = False
        
        # Build core
        core_data = magnetic_data.get('core', {})
        geometrical_description = core_data.get('geometricalDescription', [])
        if geometrical_description:
            for index, geometrical_part in enumerate(geometrical_description):
                if geometrical_part['type'] == 'toroidal':
                    is_toroidal = True
                if geometrical_part['type'] in ['half set', 'toroidal']:
                    shape_data = geometrical_part['shape']
                    # Check if shape family is 't' (toroidal)
                    if shape_data.get('family', '').lower() == 't':
                        is_toroidal = True
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
        
        # Build bobbin geometry if not toroidal and bobbin has thickness
        if not is_toroidal:
            bobbin_geom = self._build_bobbin_geometry(bobbin_processed)
            if bobbin_geom is not None:
                all_pieces.append(bobbin_geom)
        
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
            
            turn_geom = self.get_turn(turn_desc, wire_desc, bobbin_processed, is_toroidal=is_toroidal)
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
            # Use configurable tessellation parameters for STL
            exporters.export(
                compound, 
                stl_path, 
                "STL",
                tolerance=TESSELLATION_LINEAR_TOLERANCE,
                angularTolerance=get_angular_tolerance()
            )
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

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            piece = piece.translate((0, 0, -dimensions["B"]))
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

        @staticmethod
        def _hex_to_rgb(hex_color):
            """Convert hex color string like '#d4d4d4' to RGB tuple (212, 212, 212)."""
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        def get_piece_technical_drawing(self, data, colors=None, save_files=False):
            try:
                from cadquery.occ_impl.exporters.svg import getSVG

                if colors is None:
                    colors = {
                        "projection_color": "#000000",
                        "dimension_color": "#000000"
                    }

                project_name = f"{data['name']}_piece_scaled".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")

                piece = self.get_piece(data=copy.deepcopy(data), save_files=False, export_files=False)
                if piece is None:
                    return {"top_view": None, "front_view": None}

                scaled_piece = piece.newObject([o.scale(1000) for o in piece.objects])

                pathlib.Path(self.output_path).mkdir(parents=True, exist_ok=True)

                stroke_color = self._hex_to_rgb(colors.get("projection_color", "#000000"))
                svg_opts = {
                    "width": 800,
                    "height": 600,
                    "strokeWidth": 0.5,
                    "strokeColor": stroke_color,
                    "showHidden": False,
                }

                top_svg = getSVG(scaled_piece.val(), {**svg_opts, "projectionDir": (0, 0, 1)})
                top_path = f"{self.output_path}/{project_name}_TopView.svg"
                with open(top_path, "w", encoding="utf-8") as f:
                    f.write(top_svg)

                front_svg = getSVG(scaled_piece.val(), {**svg_opts, "projectionDir": (0, 1, 0)})
                front_path = f"{self.output_path}/{project_name}_FrontView.svg"
                with open(front_path, "w", encoding="utf-8") as f:
                    f.write(front_svg)

                return {"top_view": top_svg, "front_view": front_svg}
            except Exception:
                return {"top_view": None, "front_view": None}

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
            return shape_configs.P_DIMENSIONS_AND_SUBTYPES

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

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]
            piece = piece.translate((0, 0, -dimensions["B"]))
            return piece

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

    class Rm(P):
        def get_dimensions_and_subtypes(self):
            return shape_configs.RM_DIMENSIONS_AND_SUBTYPES

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

    class Etd(Er):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F"]}

    class Lp(Er):
        def get_dimensions_and_subtypes(self):
            return {
                1: ["A", "B", "C", "D", "E", "F", "G"],
            }

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
            return shape_configs.U_DIMENSIONS_AND_SUBTYPES

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

    class Ur(IPiece):
        def get_dimensions_and_subtypes(self):
            return shape_configs.UR_DIMENSIONS_AND_SUBTYPES

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

                # Extend rectangular hole slightly past column surface to avoid
                # tangent-surface boolean failures in OCC kernel
                eps = 1e-5
                translate = (winding_column_width / 2 - dimensions["S"] / 4 + eps / 2, 0, dimensions["B"] / 2)
                lateral_hole_rectangular_right = (
                    cq.Workplane()
                    .box(dimensions["S"] / 2 + eps, dimensions["S"], dimensions["B"])
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

    class Ut(IPiece):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F"]}

        def get_shape_base(self, data):
            dimensions = data["dimensions"]
            a = dimensions["A"] / 2
            c = dimensions["C"] / 2

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

        def get_negative_winding_window(self, dimensions):
            negative_winding_window = (
                cq.Workplane()
                .box(dimensions["A"] * 2, dimensions["C"] * 2, dimensions["D"])
                .tag("negative_winding_window")
                .translate((0, 0, dimensions["B"] / 2))
            )
            return negative_winding_window

        def get_shape_extras(self, data, piece):
            dimensions = data["dimensions"]

            top_column = (
                cq.Workplane()
                .box(dimensions["F"], dimensions["C"], dimensions["D"])
                .tag("top_column")
                .translate((-dimensions["A"] / 2 + dimensions["F"] / 2, 0, dimensions["B"] / 2))
            )

            bottom_column_width = dimensions["A"] - dimensions["E"] - dimensions["F"]
            bottom_column = (
                cq.Workplane()
                .box(bottom_column_width, dimensions["C"], dimensions["D"])
                .tag("bottom_column")
                .translate((dimensions["A"] / 2 - bottom_column_width / 2, 0, dimensions["B"] / 2))
            )

            piece = piece + top_column + bottom_column
            piece = piece.translate((0, 0, -dimensions["B"]))
            return piece

    class C(U):
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
                    flange_extension = dims.get("flangeExtension", 0.002)
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
            dims = data.get("dimensions", {})
            processed = data.get("processedDescription", {})

            if processed:
                wall_thickness = processed.get("wallThickness", dims.get("wallThickness", 0.0005))
                column_shape = processed.get("columnShape", "rectangular")
                column_width = processed.get("columnWidth", 0)
                column_thickness = processed.get("columnThickness", wall_thickness)
                bobbin_ww = processed.get("windingWindows", [{}])[0] if processed.get("windingWindows") else {}
                ww_width = bobbin_ww.get("width", winding_window.get("width", 0))
                ww_height = bobbin_ww.get("height", winding_window.get("height", 0))
            else:
                wall_thickness = dims.get("wallThickness", 0.0005)
                ww_width = winding_window.get("width", 0)
                ww_height = winding_window.get("height", 0)
                column_shape = winding_window.get("columnShape", "rectangular")
                column_width = winding_window.get("columnWidth", 0)
                column_thickness = wall_thickness

            tube_height = ww_height

            if column_shape == "round":
                if column_width > 0:
                    outer_radius = column_width
                    hole_radius = column_width - column_thickness
                    if hole_radius <= 0:
                        hole_radius = outer_radius - wall_thickness
                else:
                    ww_coords = winding_window.get("coordinates", [0, 0])
                    outer_radius = abs(ww_coords[0]) if ww_coords[0] != 0 else ww_width * 0.5
                    hole_radius = outer_radius - wall_thickness

                outer_cyl = cq.Workplane("XY").cylinder(tube_height, outer_radius)
                inner_cyl = cq.Workplane("XY").cylinder(tube_height * 1.1, hole_radius)
                body = outer_cyl - inner_cyl
            else:
                depth = winding_window.get("radialHeight", ww_width) if winding_window.get("radialHeight") else ww_width
                outer_width = ww_width + wall_thickness * 2
                outer_depth = depth + wall_thickness * 2

                outer_box = cq.Workplane("XY").box(outer_width, outer_depth, tube_height)
                inner_box = cq.Workplane("XY").box(ww_width, depth, tube_height * 1.1)

                central_hole_width = depth * 0.8
                central_hole_depth = depth * 0.8
                central_hole = cq.Workplane("XY").box(central_hole_width, central_hole_depth, tube_height * 1.2)

                body = outer_box - inner_box - central_hole

            return body

        def get_bobbin_flanges(self, data, winding_window):
            dims = data.get("dimensions", {})
            flange_thickness = dims.get("flangeThickness", 0.001)
            flange_extension = dims.get("flangeExtension", 0.002)
            processed = data.get("processedDescription", {})

            if processed:
                wall_thickness = processed.get("wallThickness", dims.get("wallThickness", 0.0005))
                column_shape = processed.get("columnShape", "rectangular")
                column_width = processed.get("columnWidth", 0)
                column_depth = processed.get("columnDepth", column_width)
                column_thickness = processed.get("columnThickness", wall_thickness)
                bobbin_ww = processed.get("windingWindows", [{}])[0] if processed.get("windingWindows") else {}
                ww_width = bobbin_ww.get("width", winding_window.get("width", 0))
                ww_height = bobbin_ww.get("height", winding_window.get("height", 0))
            else:
                wall_thickness = dims.get("wallThickness", 0.0005)
                ww_width = winding_window.get("width", 0)
                ww_height = winding_window.get("height", 0)
                column_shape = winding_window.get("columnShape", "rectangular")
                column_width = winding_window.get("columnWidth", 0)
                column_depth = winding_window.get("columnDepth", column_width)
                column_thickness = wall_thickness

            if column_shape == "round":
                if column_width > 0:
                    outer_radius = column_width
                    hole_radius = column_width - column_thickness
                    if hole_radius <= 0:
                        hole_radius = outer_radius - wall_thickness
                else:
                    ww_coords = winding_window.get("coordinates", [0, 0])
                    outer_radius = abs(ww_coords[0]) if ww_coords[0] != 0 else ww_width * 0.5
                    hole_radius = outer_radius - wall_thickness

                flange_outer_x = outer_radius + ww_width + flange_extension
                flange_half_y = column_depth / 2 if column_depth > 0 else outer_radius

                top_flange_solid = (
                    cq.Workplane("XY")
                    .box(flange_outer_x * 2, flange_half_y * 2, flange_thickness)
                    .translate((0, 0, ww_height / 2 + flange_thickness / 2))
                )
                top_hole = (
                    cq.Workplane("XY")
                    .cylinder(flange_thickness * 1.1, hole_radius)
                    .translate((0, 0, ww_height / 2 + flange_thickness / 2))
                )
                top_flange = top_flange_solid - top_hole

                bottom_flange_solid = (
                    cq.Workplane("XY")
                    .box(flange_outer_x * 2, flange_half_y * 2, flange_thickness)
                    .translate((0, 0, -(ww_height / 2 + flange_thickness / 2)))
                )
                bottom_hole = (
                    cq.Workplane("XY")
                    .cylinder(flange_thickness * 1.1, hole_radius)
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

            return flanges

        def get_mounting_pins(self, data, outer_radius):
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

                turns_description = data.get("turnsDescription", [])
                winding_name = data.get("windingName", name)

                if turns_description:
                    wire_diameter = data.get("wireDiameter")
                    winding = self.get_winding_from_mas(turns_description, winding_name, wire_diameter)
                    if winding is None:
                        turns_description = []

                if not turns_description:
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
            wire_diameter = data.get("wireDiameter", 0.0005)
            insulation = data.get("insulationThickness", 0.00005)
            num_layers = data.get("numberOfLayers", 1)
            total_wire_diameter = wire_diameter + 2 * insulation

            ww_height = bobbin_dims.get("height", 0.01)
            ww_width = bobbin_dims.get("width", 0.005)

            layer_thickness = total_wire_diameter * num_layers
            winding_length = ww_height * 0.9

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
            wire_diameter = data.get("wireDiameter", 0.0005)

            radius = position.get("radius", 0.005)
            y_pos = position.get("y", 0)
            layer_offset = position.get("layer_offset", 0)

            turn_radius = radius + layer_offset

            path = (
                cq.Workplane("XY")
                .center(0, 0)
                .circle(turn_radius)
            )

            wire_profile = (
                cq.Workplane("XZ")
                .center(turn_radius, 0)
                .circle(wire_diameter / 2)
            )

            turn = wire_profile.sweep(path, isFrenet=True)
            turn = turn.translate((0, 0, y_pos))

            return turn

        def create_turn_from_description(self, turn_desc, wire_diameter=None):
            radial_pos = turn_desc.coordinates[0]
            z_pos = turn_desc.coordinates[1]

            if wire_diameter is None:
                if turn_desc.dimensions:
                    wire_diameter = turn_desc.dimensions[0]
                else:
                    wire_diameter = 0.0005

            path = (
                cq.Workplane("XY")
                .center(0, 0)
                .circle(radial_pos)
            )

            wire_profile = (
                cq.Workplane("XZ")
                .center(radial_pos, 0)
                .circle(wire_diameter / 2)
            )

            turn = wire_profile.sweep(path, isFrenet=True)
            turn = turn.translate((0, 0, z_pos))

            return turn

        def get_winding_from_mas(self, turns_description, winding_name, wire_diameter=None):
            all_turns = [TurnDescription.from_dict(t) for t in turns_description]
            winding_turns = [t for t in all_turns if t.winding == winding_name]

            if not winding_turns:
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

            if column_shape == "round" and column_width > 0:
                wall_thickness = 0.0005
                base_radius = column_width / 2 + wall_thickness + total_wire_diameter / 2
            else:
                base_radius = ww_width / 2 + total_wire_diameter / 2

            for turn_idx in range(turns_per_layer):
                z_pos = -ww_height / 2 + total_wire_diameter / 2 + turn_idx * total_wire_diameter

                if z_pos > ww_height / 2 - total_wire_diameter / 2:
                    break

                position = {
                    "radius": base_radius,
                    "y": z_pos,
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

            return winding


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
