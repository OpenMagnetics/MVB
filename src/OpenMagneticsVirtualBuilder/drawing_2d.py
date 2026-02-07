"""2D Drawing Generation Module for OpenMagneticsVirtualBuilder.

Provides multi-format (SVG, DXF, FCMacro) 2D technical drawings with
dimension annotations for magnetic core shapes.
"""

import math
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Tuple, Any


class ViewPlane(Enum):
    XY = "xy"
    XZ = "xz"
    ZY = "zy"


class ViewType(Enum):
    PROJECTION = "projection"
    CROSS_SECTION = "cross_section"


PROJECTION_DIRS = {
    ViewPlane.XY: (0, 0, 1),
    ViewPlane.XZ: (0, 1, 0),
    ViewPlane.ZY: (1, 0, 0),
}


@dataclass
class DimensionAnnotation:
    start: Tuple[float, float]
    end: Tuple[float, float]
    label: str
    dimension_name: str
    dim_type: str  # "DistanceX" or "DistanceY"
    offset: float = 0.0
    label_alignment: float = 0.0


@dataclass
class DrawingView:
    plane: ViewPlane
    view_type: ViewType
    shape: Any  # CadQuery Compound or Shape
    dimensions: List[DimensionAnnotation] = field(default_factory=list)
    title: str = ""
    view_origin_x: float = 0.0
    view_origin_y: float = 0.0


# ======================================================================
# Cross-section slicing
# ======================================================================


def cross_section_at_plane(shape, plane: ViewPlane, offset: float = 0.0):
    """Slice a 3D shape at the given plane and offset.

    Uses OCP BRepAlgoAPI_Section to create a cross-section wire.

    Args:
        shape: CadQuery shape/compound to slice.
        plane: Which principal plane to slice on.
        offset: Offset from origin along the plane normal.

    Returns:
        A CadQuery Compound of the section edges, or None on failure.
    """
    try:
        from OCP.gp import gp_Pln, gp_Pnt, gp_Dir
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
        import cadquery as cq

        # Get the underlying OCC shape
        if hasattr(shape, "wrapped"):
            occ_shape = shape.wrapped
        elif hasattr(shape, "val"):
            occ_shape = shape.val().wrapped
        else:
            occ_shape = shape

        # Define the slicing plane
        if plane == ViewPlane.XY:
            pln = gp_Pln(gp_Pnt(0, 0, offset), gp_Dir(0, 0, 1))
        elif plane == ViewPlane.XZ:
            pln = gp_Pln(gp_Pnt(0, offset, 0), gp_Dir(0, 1, 0))
        elif plane == ViewPlane.ZY:
            pln = gp_Pln(gp_Pnt(offset, 0, 0), gp_Dir(1, 0, 0))
        else:
            return None

        section = BRepAlgoAPI_Section(occ_shape, pln)
        section.Build()
        if not section.IsDone():
            return None

        section_shape = section.Shape()
        return cq.Shape(section_shape)

    except Exception:
        return None


# ======================================================================
# HLR projection (hidden-line removal)
# ======================================================================


def _hlr_project(shape, projection_dir):
    """Project a 3D shape to 2D visible edges using OCC hidden-line removal.

    Uses the same HLRBRep_Algo as CadQuery's getSVG(), producing consistent
    results across SVG/DXF/FCMacro formats.

    Args:
        shape: CadQuery shape/compound to project.
        projection_dir: Tuple (x, y, z) for the projection direction.

    Returns:
        A cq.Compound of visible 2D edges, or None on failure.
    """
    try:
        from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
        from OCP.HLRAlgo import HLRAlgo_Projector
        from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
        from OCP.BRepLib import BRepLib
        from OCP.TopoDS import TopoDS_Compound
        from OCP.BRep import BRep_Builder
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_EDGE
        import cadquery as cq

        if hasattr(shape, "wrapped"):
            occ_shape = shape.wrapped
        elif hasattr(shape, "val"):
            occ_shape = shape.val().wrapped
        else:
            occ_shape = shape

        hlr = HLRBRep_Algo()
        hlr.Add(occ_shape)
        hlr.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(), gp_Dir(*projection_dir))))
        hlr.Update()
        hlr.Hide()

        hlr_shapes = HLRBRep_HLRToShape(hlr)

        builder = BRep_Builder()
        compound = TopoDS_Compound()
        builder.MakeCompound(compound)

        for getter in (hlr_shapes.VCompound, hlr_shapes.Rg1LineVCompound, hlr_shapes.OutLineVCompound):
            try:
                s = getter()
                if s.IsNull():
                    continue
                BRepLib.BuildCurves3d_s(s)
                explorer = TopExp_Explorer(s, TopAbs_EDGE)
                while explorer.More():
                    builder.Add(compound, explorer.Current())
                    explorer.Next()
            except Exception:
                continue

        return cq.Shape(compound)

    except Exception:
        return None


def _shape_to_edge_compound(shape):
    """Normalize a shape to a Compound whose direct children are its edges.

    CadQuery's DxfDocument.add_shape() works best when edges are direct
    children of the compound.

    Args:
        shape: CadQuery Shape or Compound.

    Returns:
        A cq.Compound of edges, or the original shape on failure.
    """
    try:
        import cadquery as cq

        if hasattr(shape, "Edges"):
            edges = shape.Edges()
        elif hasattr(shape, "val") and hasattr(shape.val(), "Edges"):
            edges = shape.val().Edges()
        else:
            return shape

        if not edges:
            return shape

        return cq.Compound.makeCompound(edges)

    except Exception:
        return shape


# ======================================================================
# SVG Dimension Rendering (ported from FreeCAD engine)
# ======================================================================


def create_dimension_svg(
    starting_coordinates,
    ending_coordinates,
    dimension_type,
    dimension_label,
    view_x,
    view_y,
    colors,
    dimension_font_size=20,
    dimension_line_thickness=1,
    label_offset=0,
    label_alignment=0,
    arrow_size=6,
    arrow_length=15,
):
    """Create SVG markup for a dimension annotation.

    This is a pure-SVG implementation ported from FreeCADBuilder._create_dimension_svg.

    Args:
        starting_coordinates: [x, y] start point in shape coordinates.
        ending_coordinates: [x, y] end point in shape coordinates.
        dimension_type: 'DistanceX' or 'DistanceY'.
        dimension_label: Text label for the dimension.
        view_x: X origin of the view in SVG space.
        view_y: Y origin of the view in SVG space.
        colors: Dict with 'dimension_color' key.
        dimension_font_size: Font size for labels.
        dimension_line_thickness: Stroke width for dimension lines.
        label_offset: Offset for placing the dimension line away from the shape.
        label_alignment: Additional alignment offset for the label text.
        arrow_size: Width of arrowhead.
        arrow_length: Length of arrowhead.

    Returns:
        SVG string for the dimension annotation.
    """
    dimension_svg = ""

    if dimension_type == "DistanceY":
        main_line_start = [starting_coordinates[0] + label_offset, starting_coordinates[1]]
        main_line_end = [ending_coordinates[0] + label_offset, ending_coordinates[1]]
        left_aux_line_start = [starting_coordinates[0], starting_coordinates[1]]
        left_aux_line_end = [starting_coordinates[0] + label_offset, starting_coordinates[1]]
        right_aux_line_start = [ending_coordinates[0], ending_coordinates[1]]
        right_aux_line_end = [ending_coordinates[0] + label_offset, ending_coordinates[1]]

        # Text label (rotated -90 degrees for vertical dimension)
        dimension_svg += (
            f'   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" '
            f'font-family="MS Shell Dlg 2" stroke="{colors["dimension_color"]}" stroke-width="1" '
            f'font-weight="400" transform="matrix(1,0,0,1,'
            f"{view_x + ending_coordinates[0] + label_offset - dimension_font_size / 4},"
            f'{1000 - view_y + label_alignment})" stroke-linecap="square" stroke-linejoin="bevel">\n'
            f'    <text x="0" y="0" text-anchor="middle" fill-opacity="1" font-size="{dimension_font_size}" '
            f'font-style="normal" fill="{colors["dimension_color"]}" font-family="osifont" stroke="none" '
            f'xml:space="preserve" font-weight="400" transform="rotate(-90)">{dimension_label}</text>\n'
            f"   </g>\n"
        )

        # Dimension line and auxiliary lines
        dimension_svg += (
            f'   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" '
            f'font-family="MS Shell Dlg 2" stroke="{colors["dimension_color"]}" '
            f'stroke-width="{dimension_line_thickness}" font-weight="400" '
            f'transform="matrix(1,0,0,1,{view_x},{1000 - view_y})" '
            f'stroke-linecap="round" stroke-linejoin="bevel">\n'
            f'    <path fill-rule="evenodd" vector-effect="none" d="'
            f"M{main_line_start[0]},{main_line_start[1]} L{main_line_end[0]},{main_line_end[1]} "
            f"M{left_aux_line_start[0]},{left_aux_line_start[1]} L{left_aux_line_end[0]},{left_aux_line_end[1]} "
            f'M{right_aux_line_start[0]},{right_aux_line_start[1]} L{right_aux_line_end[0]},{right_aux_line_end[1]}"/>\n'
            f"   </g>\n"
        )

        # Arrowheads
        dimension_svg += (
            f'   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" '
            f'font-family="MS Shell Dlg 2" stroke="{colors["dimension_color"]}" '
            f'stroke-width="{dimension_line_thickness}" font-weight="400" '
            f'transform="matrix(1,0,0,1,{view_x},{1000 - view_y})" '
            f'stroke-linecap="round" stroke-linejoin="bevel">\n'
            # Bottom arrow (pointing down)
            f'    <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" '
            f'fill="{colors["dimension_color"]}" font-family="MS Shell Dlg 2" '
            f'stroke="{colors["dimension_color"]}" stroke-width="1" font-weight="400" '
            f'transform="matrix(1,0,0,1,{ending_coordinates[0] + label_offset},{ending_coordinates[1]})" '
            f'stroke-linecap="round" stroke-linejoin="bevel">\n'
            f'     <path fill-rule="evenodd" vector-effect="none" d="M0,0 L{arrow_size},-{arrow_length} L-{arrow_size},-{arrow_length} L0,0"/>\n'
            f"    </g>\n"
            # Top arrow (pointing up)
            f'    <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" '
            f'fill="{colors["dimension_color"]}" font-family="MS Shell Dlg 2" '
            f'stroke="{colors["dimension_color"]}" stroke-width="1" font-weight="400" '
            f'transform="matrix(1,0,0,1,{starting_coordinates[0] + label_offset},{starting_coordinates[1]})" '
            f'stroke-linecap="round" stroke-linejoin="bevel">\n'
            f'     <path fill-rule="evenodd" vector-effect="none" d="M0,0 L-{arrow_size},{arrow_length} L{arrow_size},{arrow_length} L0,0"/>\n'
            f"    </g>\n"
            f"   </g>\n"
        )

    elif dimension_type == "DistanceX":
        main_line_start = [starting_coordinates[0], starting_coordinates[1] + label_offset]
        main_line_end = [ending_coordinates[0], ending_coordinates[1] + label_offset]
        left_aux_line_start = [starting_coordinates[0], starting_coordinates[1]]
        left_aux_line_end = [starting_coordinates[0], starting_coordinates[1] + label_offset]
        right_aux_line_start = [ending_coordinates[0], ending_coordinates[1]]
        right_aux_line_end = [ending_coordinates[0], ending_coordinates[1] + label_offset]

        # Text label (horizontal)
        dimension_svg += (
            f'   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" '
            f'font-family="MS Shell Dlg 2" stroke="{colors["dimension_color"]}" stroke-width="1" '
            f'font-weight="400" transform="matrix(1,0,0,1,{view_x + label_alignment},{1000 - view_y})" '
            f'stroke-linecap="square" stroke-linejoin="bevel">\n'
            f'    <text x="0" y="{ending_coordinates[1] + label_offset - dimension_font_size / 4}" '
            f'text-anchor="middle" fill-opacity="1" font-size="{dimension_font_size}" '
            f'font-style="normal" fill="{colors["dimension_color"]}" font-family="osifont" stroke="none" '
            f'xml:space="preserve" font-weight="400">{dimension_label}</text>\n'
            f"   </g>\n"
        )

        # Dimension line and auxiliary lines
        dimension_svg += (
            f'   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" '
            f'font-family="MS Shell Dlg 2" stroke="{colors["dimension_color"]}" '
            f'stroke-width="{dimension_line_thickness}" font-weight="400" '
            f'transform="matrix(1,0,0,1,{view_x},{1000 - view_y})" '
            f'stroke-linecap="round" stroke-linejoin="bevel">\n'
            f'    <path fill-rule="evenodd" vector-effect="none" d="'
            f"M{main_line_start[0]},{main_line_start[1]} L{main_line_end[0]},{main_line_end[1]} "
            f"M{left_aux_line_start[0]},{left_aux_line_start[1]} L{left_aux_line_end[0]},{left_aux_line_end[1]} "
            f'M{right_aux_line_start[0]},{right_aux_line_start[1]} L{right_aux_line_end[0]},{right_aux_line_end[1]}"/>\n'
            f"   </g>\n"
        )

        # Arrowheads
        dimension_svg += (
            f'   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" '
            f'font-family="MS Shell Dlg 2" stroke="{colors["dimension_color"]}" '
            f'stroke-width="{dimension_line_thickness}" font-weight="400" '
            f'transform="matrix(1,0,0,1,{view_x},{1000 - view_y})" '
            f'stroke-linecap="round" stroke-linejoin="bevel">\n'
            # Right arrow (pointing right)
            f'    <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" '
            f'fill="{colors["dimension_color"]}" font-family="MS Shell Dlg 2" '
            f'stroke="{colors["dimension_color"]}" stroke-width="1" font-weight="400" '
            f'transform="matrix(1,0,0,1,{ending_coordinates[0]},{ending_coordinates[1] + label_offset})" '
            f'stroke-linecap="round" stroke-linejoin="bevel">\n'
            f'     <path fill-rule="evenodd" vector-effect="none" d="M0,0 L-{arrow_length},-{arrow_size} L-{arrow_length},{arrow_size} L0,0"/>\n'
            f"    </g>\n"
            # Left arrow (pointing left)
            f'    <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" '
            f'fill="{colors["dimension_color"]}" font-family="MS Shell Dlg 2" '
            f'stroke="{colors["dimension_color"]}" stroke-width="1" font-weight="400" '
            f'transform="matrix(1,0,0,1,{starting_coordinates[0]},{starting_coordinates[1] + label_offset})" '
            f'stroke-linecap="round" stroke-linejoin="bevel">\n'
            f'     <path fill-rule="evenodd" vector-effect="none" d="M0,0 L{arrow_length},{arrow_size} L{arrow_length},-{arrow_size} L0,0"/>\n'
            f"    </g>\n"
            f"   </g>\n"
        )

    return dimension_svg


# ======================================================================
# Per-shape dimension spec functions
# ======================================================================


def _e_family_dims(dims, original_dims, view_name, family):
    """Dimension annotations for E-family shapes.

    Covers: E, ETD, ER, EL, EFD, EQ, EC, LP, PLANAR_E, PLANAR_ER, PLANAR_EL.
    Ported from freecad_builder.py IPiece.add_dimensions_and_export_view.
    """
    annotations = []
    h_offset = 75
    v_offset = 75
    increment = 75

    if family not in ["p"]:
        shape_semi_height = dims["C"] / 2
    else:
        shape_semi_height = dims["A"] / 2

    correction = 0

    if view_name == "TopView":
        if "L" in dims and dims["L"] > 0:
            annotations.append(
                DimensionAnnotation(
                    start=(dims["J"] / 2, -dims["L"] / 2),
                    end=(dims["J"] / 2, dims["L"] / 2),
                    label=f"L: {round(original_dims.get('L', 0), 2)} mm",
                    dimension_name="L",
                    dim_type="DistanceY",
                    offset=h_offset + dims["A"] / 2 - dims["J"] / 2,
                )
            )
            h_offset += increment

        k = 0
        if "K" in dims and dims["K"] > 0:
            if family == "efd":
                height_of_dimension = dims["C"] / 2
                k = -dims["K"]
            elif family == "ep":
                height_of_dimension = 0
                k = -dims["K"]
            else:
                height_of_dimension = -dims["C"] / 2
                k = dims["K"]

            if dims["K"] < 0:
                correction = dims["K"] / 2
            else:
                correction = 0

            annotations.append(
                DimensionAnnotation(
                    start=(dims["F"] / 2, height_of_dimension + correction),
                    end=(dims["F"] / 2, height_of_dimension + k + correction),
                    label=f"K: {round(original_dims['K'], 2)} mm",
                    dimension_name="K",
                    dim_type="DistanceY",
                    offset=h_offset + (dims["A"] / 2 - dims["F"] / 2),
                    label_alignment=height_of_dimension + k / 2 + correction,
                )
            )
            h_offset += increment

        if "F2" in dims and dims["F2"] > 0:
            if family in ["efd"]:
                annotations.append(
                    DimensionAnnotation(
                        start=(0, dims["C"] / 2 + correction - dims["K"] - dims["F2"]),
                        end=(0, dims["C"] / 2 + correction - dims["K"]),
                        label=f"F2: {round(original_dims['F2'], 2)} mm",
                        dimension_name="F2",
                        dim_type="DistanceY",
                        offset=h_offset + dims["A"] / 2,
                        label_alignment=dims["F2"] / 2 + k / 2 + correction,
                    )
                )
            else:
                annotations.append(
                    DimensionAnnotation(
                        start=(0, -dims["F2"] / 2),
                        end=(0, dims["F2"] / 2),
                        label=f"F2: {round(original_dims['F2'], 2)} mm",
                        dimension_name="F2",
                        dim_type="DistanceY",
                        offset=h_offset + dims["A"] / 2,
                    )
                )
            h_offset += increment

        if "C" in dims and dims["C"] > 0:
            c_correction = correction
            if family == "ep":
                c_correction = dims["C"] / 2 - dims.get("K", 0)

            annotations.append(
                DimensionAnnotation(
                    start=(dims["A"] / 2, -dims["C"] / 2 + c_correction),
                    end=(dims["A"] / 2, dims["C"] / 2 + c_correction),
                    label=f"C: {round(original_dims['C'], 2)} mm",
                    dimension_name="C",
                    dim_type="DistanceY",
                    offset=h_offset,
                )
            )
            h_offset += increment

        if "H" in dims and dims["H"] > 0:
            annotations.append(
                DimensionAnnotation(
                    start=(-dims["H"] / 2, 0),
                    end=(dims["H"] / 2, 0),
                    label=f"H: {round(original_dims['H'], 2)} mm",
                    dimension_name="H",
                    dim_type="DistanceX",
                    offset=v_offset + shape_semi_height,
                )
            )
            v_offset += increment

        if "J" in dims and family == "pq":
            annotations.append(
                DimensionAnnotation(
                    start=(-dims["J"] / 2, dims.get("L", 0) / 2),
                    end=(dims["J"] / 2, dims.get("L", 0) / 2),
                    label=f"J: {round(original_dims.get('J', 0), 2)} mm",
                    dimension_name="J",
                    dim_type="DistanceX",
                    offset=v_offset + shape_semi_height - dims.get("L", 0) / 2,
                )
            )
            v_offset += increment

        if family in ["ep", "epx"]:
            k = dims["C"] / 2 - dims.get("K", 0)
        elif family in ["efd"]:
            if dims.get("K", 0) < 0:
                k = -dims["C"] / 2 - dims.get("K", 0) * 2
        else:
            k = 0

        if family not in ["p"]:
            if "F" in dims and dims["F"] > 0:
                annotations.append(
                    DimensionAnnotation(
                        start=(-dims["F"] / 2, -k),
                        end=(dims["F"] / 2, -k),
                        label=f"F: {round(original_dims['F'], 2)} mm",
                        dimension_name="F",
                        dim_type="DistanceX",
                        offset=v_offset + k + shape_semi_height,
                    )
                )
                v_offset += increment

            if "G" in dims and dims["G"] > 0:
                annotations.append(
                    DimensionAnnotation(
                        start=(-dims["G"] / 2, shape_semi_height),
                        end=(dims["G"] / 2, shape_semi_height),
                        label=f"G: {round(original_dims['G'], 2)} mm",
                        dimension_name="G",
                        dim_type="DistanceX",
                        offset=v_offset,
                    )
                )
                v_offset += increment
        else:
            if "G" in dims and dims["G"] > 0:
                annotations.append(
                    DimensionAnnotation(
                        start=(-dims["G"] / 2, dims["E"] / 2),
                        end=(dims["G"] / 2, dims["E"] / 2),
                        label=f"G: {round(original_dims['G'], 2)} mm",
                        dimension_name="G",
                        dim_type="DistanceX",
                        offset=v_offset + dims["A"] / 2 - dims["E"] / 2,
                    )
                )
                v_offset += increment
            if "F" in dims and dims["F"] > 0:
                annotations.append(
                    DimensionAnnotation(
                        start=(-dims["F"] / 2, -k),
                        end=(dims["F"] / 2, -k),
                        label=f"F: {round(original_dims['F'], 2)} mm",
                        dimension_name="F",
                        dim_type="DistanceX",
                        offset=v_offset + k + shape_semi_height,
                    )
                )
                v_offset += increment

        annotations.append(
            DimensionAnnotation(
                start=(-dims["E"] / 2, -k),
                end=(dims["E"] / 2, -k),
                label=f"E: {round(original_dims['E'], 2)} mm",
                dimension_name="E",
                dim_type="DistanceX",
                offset=v_offset + k + shape_semi_height,
            )
        )
        v_offset += increment

        annotations.append(
            DimensionAnnotation(
                start=(-dims["A"] / 2, 0),
                end=(dims["A"] / 2, 0),
                label=f"A: {round(original_dims['A'], 2)} mm",
                dimension_name="A",
                dim_type="DistanceX",
                offset=v_offset + shape_semi_height,
            )
        )

    else:  # FrontView
        starting_point_for_d = dims["E"] / 2
        annotations.append(
            DimensionAnnotation(
                start=(starting_point_for_d, -dims["B"] / 2),
                end=(starting_point_for_d, -dims["B"] / 2 + dims["D"]),
                label=f"D: {round(original_dims['D'], 2)} mm",
                dimension_name="D",
                dim_type="DistanceY",
                offset=h_offset + (dims["A"] / 2 - starting_point_for_d),
                label_alignment=-dims["B"] / 2 + dims["D"] / 2,
            )
        )
        h_offset += increment

        annotations.append(
            DimensionAnnotation(
                start=(dims["A"] / 2, -dims["B"] / 2),
                end=(dims["A"] / 2, dims["B"] / 2),
                label=f"B: {round(original_dims['B'], 2)} mm",
                dimension_name="B",
                dim_type="DistanceY",
                offset=h_offset,
            )
        )

    return annotations


def _ur_family_dims(dims, original_dims, view_name):
    """Dimension annotations for UR shapes."""
    annotations = []
    h_offset = 75
    v_offset = 75
    increment = 50
    shape_semi_height = dims["C"] / 2

    if "F" not in dims or dims["F"] == 0:
        dims["F"] = dims["C"]

    if view_name == "TopView":
        if "C" in dims and dims["C"] > 0:
            annotations.append(
                DimensionAnnotation(
                    start=(dims["A"] / 2, -dims["C"] / 2),
                    end=(dims["A"] / 2, dims["C"] / 2),
                    label=f"C: {round(original_dims['C'], 2)} mm",
                    dimension_name="C",
                    dim_type="DistanceY",
                    offset=h_offset,
                )
            )
            h_offset += increment

        if "G" in dims and dims.get("G", 0) > 0:
            annotations.append(
                DimensionAnnotation(
                    start=(-dims["A"] / 2 + dims["F"] / 2 - dims["G"] / 2, 0),
                    end=(-dims["A"] / 2 + dims["F"] / 2 + dims["G"] / 2, 0),
                    label=f"G: {round(original_dims['G'], 2)} mm",
                    dimension_name="G",
                    dim_type="DistanceX",
                    offset=v_offset + shape_semi_height,
                    label_alignment=-dims["A"] / 2 + dims["F"] / 2,
                )
            )
            annotations.append(
                DimensionAnnotation(
                    start=(dims["A"] / 2 - dims["F"] / 2 + dims["G"] / 2, 0),
                    end=(dims["A"] / 2 - dims["F"] / 2 - dims["G"] / 2, 0),
                    label=f"G: {round(original_dims['G'], 2)} mm",
                    dimension_name="G",
                    dim_type="DistanceX",
                    offset=v_offset + shape_semi_height,
                    label_alignment=dims["A"] / 2 - dims["F"] / 2,
                )
            )
            v_offset += increment

        if "F" in dims and dims["F"] > 0:
            annotations.append(
                DimensionAnnotation(
                    start=(-dims["A"] / 2, 0),
                    end=(-dims["A"] / 2 + dims["F"], 0),
                    label=f"F: {round(original_dims['F'], 2)} mm",
                    dimension_name="F",
                    dim_type="DistanceX",
                    offset=v_offset + shape_semi_height,
                    label_alignment=-dims["A"] / 2 + dims["F"] / 2,
                )
            )

        if "H" in dims and dims.get("H", 0) > 0:
            annotations.append(
                DimensionAnnotation(
                    start=(dims["A"] / 2 - dims["H"], 0),
                    end=(dims["A"] / 2, 0),
                    label=f"H: {round(original_dims['H'], 2)} mm",
                    dimension_name="H",
                    dim_type="DistanceX",
                    offset=v_offset + shape_semi_height,
                    label_alignment=dims["A"] / 2 - dims["H"] / 2,
                )
            )

        if "F" in dims:
            left_col = dims["F"]
        else:
            left_col = dims["C"]
        if "H" in dims:
            right_col = dims["H"]
        else:
            right_col = dims["C"]

        if "E" not in original_dims:
            original_dims["E"] = original_dims["A"] - original_dims.get("F", original_dims["C"]) - original_dims.get("H", original_dims["C"])

        if "E" not in dims or dims["E"] == 0:
            dims["E"] = dims["A"] - dims["F"] - dims.get("H", dims["C"])

        annotations.append(
            DimensionAnnotation(
                start=(-dims["A"] / 2 + left_col, 0),
                end=(dims["A"] / 2 - right_col, 0),
                label=f"E: Min {round(original_dims['E'], 2)} mm",
                dimension_name="E",
                dim_type="DistanceX",
                offset=v_offset + shape_semi_height,
                label_alignment=-dims["A"] / 2 + left_col + (dims["A"] - left_col - right_col) / 2,
            )
        )
        v_offset += increment

        annotations.append(
            DimensionAnnotation(
                start=(-dims["A"] / 2, 0),
                end=(dims["A"] / 2, 0),
                label=f"A: {round(original_dims['A'], 2)} mm",
                dimension_name="A",
                dim_type="DistanceX",
                offset=v_offset + shape_semi_height,
            )
        )

    else:  # FrontView
        if "H" in dims:
            starting_point_for_d = dims["H"] / 2
        else:
            starting_point_for_d = dims["E"] / 2

        annotations.append(
            DimensionAnnotation(
                start=(starting_point_for_d, -dims["B"] / 2),
                end=(starting_point_for_d, -dims["B"] / 2 + dims["D"]),
                label=f"D: {round(original_dims['D'], 2)} mm",
                dimension_name="D",
                dim_type="DistanceY",
                offset=h_offset + (dims["A"] / 2 - starting_point_for_d),
                label_alignment=-dims["B"] / 2 + dims["D"] / 2,
            )
        )
        h_offset += increment

        annotations.append(
            DimensionAnnotation(
                start=(dims["A"] / 2, -dims["B"] / 2),
                end=(dims["A"] / 2, dims["B"] / 2),
                label=f"B: {round(original_dims['B'], 2)} mm",
                dimension_name="B",
                dim_type="DistanceY",
                offset=h_offset,
            )
        )

    return annotations


def _ut_family_dims(dims, original_dims, view_name):
    """Dimension annotations for UT shapes."""
    annotations = []
    h_offset = 75
    v_offset = 75
    increment = 50
    shape_semi_height = dims["C"] / 2

    if view_name == "TopView":
        if "C" in dims and dims["C"] > 0:
            annotations.append(
                DimensionAnnotation(
                    start=(dims["A"] / 2, -dims["C"] / 2),
                    end=(dims["A"] / 2, dims["C"] / 2),
                    label=f"C: {round(original_dims['C'], 2)} mm",
                    dimension_name="C",
                    dim_type="DistanceY",
                    offset=h_offset,
                )
            )
            h_offset += increment

        if "F" in dims and dims["F"] > 0:
            annotations.append(
                DimensionAnnotation(
                    start=(-dims["A"] / 2, 0),
                    end=(-dims["A"] / 2 + dims["F"], 0),
                    label=f"F: {round(original_dims['F'], 2)} mm",
                    dimension_name="F",
                    dim_type="DistanceX",
                    offset=v_offset + shape_semi_height,
                    label_alignment=-dims["A"] / 2 + dims["F"] / 2,
                )
            )

        left_col = dims.get("F", 0)
        right_col = dims["A"] - dims["E"] - left_col

        annotations.append(
            DimensionAnnotation(
                start=(-dims["A"] / 2 + left_col, 0),
                end=(dims["A"] / 2 - right_col, 0),
                label=f"E: {round(original_dims['E'], 2)} mm",
                dimension_name="E",
                dim_type="DistanceX",
                offset=v_offset + shape_semi_height,
                label_alignment=-dims["A"] / 2 + left_col + (dims["A"] - left_col - right_col) / 2,
            )
        )
        v_offset += increment

        annotations.append(
            DimensionAnnotation(
                start=(-dims["A"] / 2, 0),
                end=(dims["A"] / 2, 0),
                label=f"A: {round(original_dims['A'], 2)} mm",
                dimension_name="A",
                dim_type="DistanceX",
                offset=v_offset + shape_semi_height,
            )
        )

    else:  # FrontView
        if "H" in dims:
            starting_point_for_d = dims["H"] / 2
        else:
            starting_point_for_d = dims["E"] / 2

        annotations.append(
            DimensionAnnotation(
                start=(starting_point_for_d, -dims["D"] / 2),
                end=(starting_point_for_d, dims["D"] / 2),
                label=f"D: {round(original_dims['D'], 2)} mm",
                dimension_name="D",
                dim_type="DistanceY",
                offset=h_offset + (dims["A"] / 2 - starting_point_for_d),
                label_alignment=-dims["B"] / 2 + dims["D"] / 2,
            )
        )
        h_offset += increment

        annotations.append(
            DimensionAnnotation(
                start=(dims["A"] / 2, -dims["B"] / 2),
                end=(dims["A"] / 2, dims["B"] / 2),
                label=f"B: {round(original_dims['B'], 2)} mm",
                dimension_name="B",
                dim_type="DistanceY",
                offset=h_offset,
            )
        )

    return annotations


def _t_family_dims(dims, original_dims, view_name):
    """Dimension annotations for T (toroidal) shapes."""
    annotations = []
    h_offset = 75
    v_offset = 75
    increment = 50
    shape_semi_height = dims["A"] / 2

    if view_name == "TopView":
        annotations.append(
            DimensionAnnotation(
                start=(-dims["B"] / 2, 0),
                end=(dims["B"] / 2, 0),
                label=f"B: {round(original_dims['B'], 2)} mm",
                dimension_name="B",
                dim_type="DistanceX",
                offset=v_offset + shape_semi_height,
            )
        )
        v_offset += increment

        annotations.append(
            DimensionAnnotation(
                start=(-dims["A"] / 2, 0),
                end=(dims["A"] / 2, 0),
                label=f"A: {round(original_dims['A'], 2)} mm",
                dimension_name="A",
                dim_type="DistanceX",
                offset=v_offset + shape_semi_height,
            )
        )

    else:  # FrontView
        annotations.append(
            DimensionAnnotation(
                start=(0, -dims["C"] / 2),
                end=(0, dims["C"] / 2),
                label=f"C: {round(original_dims['C'], 2)} mm",
                dimension_name="C",
                dim_type="DistanceY",
                offset=h_offset,
            )
        )

    return annotations


def _u_family_dims(dims, original_dims, view_name, family):
    """Dimension annotations for U and C shapes.

    Uses same logic as E-family base but adapted for U/C specifics.
    """
    return _e_family_dims(dims, original_dims, view_name, family)


def get_dimensions_for_family(family, dims, original_dims, view_name):
    """Get dimension annotations for a shape family.

    Args:
        family: Shape family name (lowercase string).
        dims: Processed dimensions dict (in mm, scaled).
        original_dims: Original dimensions dict for labels.
        view_name: 'TopView' or 'FrontView'.

    Returns:
        List of DimensionAnnotation objects.
    """
    family_lower = family.lower().replace(" ", "_")

    if family_lower in ("ur",):
        return _ur_family_dims(dims, original_dims, view_name)
    elif family_lower in ("ut",):
        return _ut_family_dims(dims, original_dims, view_name)
    elif family_lower in ("t",):
        return _t_family_dims(dims, original_dims, view_name)
    else:
        # E-family covers: e, etd, er, ep, epx, efd, eq, ec, lp, planar_e, planar_er, planar_el
        # Also u, c, p, pq, pm, rm
        return _e_family_dims(dims, original_dims, view_name, family_lower)


# ======================================================================
# SVG Composer
# ======================================================================


def compose_annotated_svg(
    base_svg,
    view_origin_x,
    view_origin_y,
    annotations,
    colors,
    dimension_font_size=50,
    dimension_line_thickness=1,
):
    """Inject dimension annotations into an existing SVG string.

    Args:
        base_svg: The base SVG string (from CadQuery getSVG).
        view_origin_x: X origin in SVG coordinate space.
        view_origin_y: Y origin in SVG coordinate space.
        annotations: List of DimensionAnnotation objects.
        colors: Dict with 'dimension_color' key.
        dimension_font_size: Font size for dimension labels.
        dimension_line_thickness: Stroke width for dimension lines.

    Returns:
        Annotated SVG string.
    """
    dim_svg = ""
    for ann in annotations:
        dim_svg += create_dimension_svg(
            starting_coordinates=list(ann.start),
            ending_coordinates=list(ann.end),
            dimension_type=ann.dim_type,
            dimension_label=ann.label,
            view_x=view_origin_x,
            view_y=view_origin_y,
            colors=colors,
            dimension_font_size=dimension_font_size,
            dimension_line_thickness=dimension_line_thickness,
            label_offset=ann.offset,
            label_alignment=ann.label_alignment,
        )

    # Inject before closing </svg>
    if "</svg>" in base_svg:
        return base_svg.replace("</svg>", dim_svg + "</svg>")
    return base_svg + dim_svg


def build_annotated_svg(
    compound,
    projection_dir,
    dims,
    original_dims,
    family,
    view_name,
    colors,
    projection_line_thickness=4,
    dimension_font_size=50,
    dimension_line_thickness=1,
):
    """Build a complete annotated SVG for a shape view.

    Args:
        compound: CadQuery compound (scaled to mm).
        projection_dir: Tuple (x, y, z) for projection direction.
        dims: Processed dimensions dict.
        original_dims: Original dimensions dict for labels.
        family: Shape family name.
        view_name: 'TopView' or 'FrontView'.
        colors: Dict with 'projection_color' and 'dimension_color'.

    Returns:
        Annotated SVG string, or None on failure.
    """
    try:
        from cadquery.occ_impl.exporters.svg import getSVG

        # Calculate view dimensions for proper sizing
        margin = 100
        h_offset = 75
        v_offset = 75
        increment = 75

        base_width = dims["A"] + margin + h_offset + increment * 3
        if family not in ["t"]:
            base_height = max(dims.get("C", dims["A"]), dims.get("B", dims["A"])) + margin + v_offset + increment * 5
        else:
            base_height = dims["A"] + margin + v_offset + increment * 3

        view_x = base_width / 2
        view_y = base_height / 2

        # Get projection color
        if isinstance(colors.get("projection_color", "#000000"), str):
            hex_color = colors["projection_color"].lstrip("#")
            stroke_color = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        else:
            stroke_color = colors["projection_color"]

        svg_opts = {
            "width": 800,
            "height": 600,
            "strokeWidth": 0.5,
            "strokeColor": stroke_color,
            "showHidden": False,
            "projectionDir": projection_dir,
        }

        # Get base SVG
        if hasattr(compound, "val"):
            base_svg = getSVG(compound.val(), svg_opts)
        else:
            base_svg = getSVG(compound, svg_opts)

        # Get dimension annotations
        annotations = get_dimensions_for_family(family, dims, original_dims, view_name)

        # Parse SVG to find the actual view origin
        # CadQuery's getSVG centers the view, so we need to extract the transform
        import re

        transform_match = re.search(r'transform="translate\(([^,]+),([^)]+)\)"', base_svg)
        if transform_match:
            view_x = float(transform_match.group(1))
            view_y = float(transform_match.group(2))

        # Compose final SVG with dimensions
        return compose_annotated_svg(
            base_svg,
            view_x,
            view_y,
            annotations,
            colors,
            dimension_font_size=dimension_font_size,
            dimension_line_thickness=dimension_line_thickness,
        )

    except Exception:
        return None


# ======================================================================
# DXF Export
# ======================================================================


def export_dxf_from_shape(shape, view_plane, output_path, filename, view_type=ViewType.PROJECTION, colors=None):
    """Export a shape's 2D projection or cross-section to DXF.

    Uses HLR projection for PROJECTION views and direct edges for
    CROSS_SECTION views, then writes via CadQuery's DxfDocument.

    Args:
        shape: CadQuery shape to project.
        view_plane: ViewPlane enum value.
        output_path: Directory for output file.
        filename: Output filename (without extension).
        view_type: ViewType.PROJECTION or ViewType.CROSS_SECTION.
        colors: Optional color config dict.

    Returns:
        File path of the exported DXF, or None on failure.
    """
    try:
        from cadquery.occ_impl.exporters.dxf import DxfDocument

        if view_type == ViewType.PROJECTION:
            proj_dir = PROJECTION_DIRS[view_plane]
            projected = _hlr_project(shape, proj_dir)
            if projected is None:
                return None
            edge_compound = _shape_to_edge_compound(projected)
        else:
            edge_compound = _shape_to_edge_compound(shape)

        dxf_doc = DxfDocument()
        dxf_doc.add_shape(edge_compound)

        filepath = f"{output_path}/{filename}.dxf"
        dxf_doc.document.saveas(filepath)
        return filepath

    except Exception:
        return None


# ======================================================================
# FreeCAD Macro Export
# ======================================================================


def export_fcstd_macro_from_shape(shape, view_plane, output_path, filename, view_type=ViewType.PROJECTION):
    """Export a shape's 2D projection to a FreeCAD macro (.FCMacro).

    Uses HLR projection for PROJECTION views. Filters out degenerate
    zero-length edges that crash FreeCAD with "Both points are equal".

    Args:
        shape: CadQuery shape to project.
        view_plane: ViewPlane enum value.
        output_path: Directory for output file.
        filename: Output filename (without extension).
        view_type: ViewType.PROJECTION or ViewType.CROSS_SECTION.

    Returns:
        File path of the exported FCMacro, or None on failure.
    """
    try:
        import cadquery as cq

        if view_type == ViewType.PROJECTION:
            proj_dir = PROJECTION_DIRS[view_plane]
            projected = _hlr_project(shape, proj_dir)
            if projected is None:
                return None
            source_shape = projected
        else:
            source_shape = shape

        # Get CadQuery edges
        if hasattr(source_shape, "Edges"):
            edges = source_shape.Edges()
        elif hasattr(source_shape, "val") and hasattr(source_shape.val(), "Edges"):
            edges = source_shape.val().Edges()
        else:
            edges = cq.Shape(source_shape.wrapped if hasattr(source_shape, "wrapped") else source_shape).Edges()

        lines = [
            "# FreeCAD macro generated by OpenMagneticsVirtualBuilder",
            "import FreeCAD",
            "import Part",
            "import Sketcher",
            "",
            "doc = FreeCAD.newDocument('Drawing2D')",
            "sketch = doc.addObject('Sketcher::SketchObject', 'Sketch')",
            "",
            "# Geometry",
        ]

        for edge in edges:
            sp = edge.startPoint()
            ep = edge.endPoint()

            # Skip degenerate zero-length edges (fixes "Both points are equal")
            if sp.sub(ep).Length < 1e-6:
                continue

            geom_type = edge.geomType()

            if geom_type == "LINE":
                lines.append(f"sketch.addGeometry(Part.LineSegment(FreeCAD.Vector({sp.x}, {sp.y}, 0), FreeCAD.Vector({ep.x}, {ep.y}, 0)))")
            elif geom_type == "CIRCLE":
                center = edge.Center()
                radius = edge.radius()
                lines.append(f"sketch.addGeometry(Part.Circle(FreeCAD.Vector({center.x}, {center.y}, 0), FreeCAD.Vector(0, 0, 1), {radius}))")
            elif geom_type in ("ARC_OF_CIRCLE", "ARCOFCIRCLE"):
                center = edge.Center()
                radius = edge.radius()
                lines.append(
                    f"sketch.addGeometry(Part.ArcOfCircle("
                    f"Part.Circle(FreeCAD.Vector({center.x}, {center.y}, 0), "
                    f"FreeCAD.Vector(0, 0, 1), {radius}), "
                    f"{math.atan2(sp.y - center.y, sp.x - center.x)}, "
                    f"{math.atan2(ep.y - center.y, ep.x - center.x)}))"
                )
            else:
                # Fallback: approximate as line segment
                lines.append(f"sketch.addGeometry(Part.LineSegment(FreeCAD.Vector({sp.x}, {sp.y}, 0), FreeCAD.Vector({ep.x}, {ep.y}, 0)))")

        lines.append("")
        lines.append("doc.recompute()")
        lines.append("")

        filepath = f"{output_path}/{filename}.FCMacro"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return filepath

    except Exception:
        return None
