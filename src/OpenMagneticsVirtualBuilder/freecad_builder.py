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


class FreeCADBuilder:
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
            utils.ShapeFamily.UT: self.Ut(),
            utils.ShapeFamily.T: self.T()
        }

        if platform.system() == "Windows":
            if os.path.exists(f"{os.getenv('LOCALAPPDATA')}\\Programs\\FreeCAD 1.0"):
                freecad_path = f"{os.getenv('LOCALAPPDATA')}\\Programs\\FreeCAD 1.0"
            elif os.path.exists(f"{os.environ['ProgramFiles']}\\FreeCAD 1.0"):
                freecad_path = f"{os.environ['ProgramFiles']}\\FreeCAD 1.0"
            elif os.path.exists(f"{os.getenv('LOCALAPPDATA')}\\Programs\\FreeCAD 0.21"):
                freecad_path = f"{os.getenv('LOCALAPPDATA')}\\Programs\\FreeCAD 0.21"
            elif os.path.exists(f"{os.environ['ProgramFiles']}\\FreeCAD 0.21"):
                freecad_path = f"{os.environ['ProgramFiles']}\\FreeCAD 0.21"

            sys.path.insert(0, f"{freecad_path}\\bin\\Lib\\site-packages")
            sys.path.append(f"{freecad_path}\\bin")
            sys.path.append(f"{freecad_path}\\Ext")
            sys.path.append(f"{freecad_path}\\Mod")
            sys.path.append(f"{freecad_path}\\Mod\\Draft")
            sys.path.append(f"{freecad_path}\\Mod\\Part")
            sys.path.append(f"{freecad_path}\\Mod\\PartDesign")
            sys.path.append(f"{freecad_path}\\Mod\\Sketcher")
            sys.path.append(f"{freecad_path}\\Mod\\Arch")
        else:
            freecad_name = None
            if os.path.exists("/usr/lib/freecad-daily"):
                freecad_name = "freecad-daily"
            elif os.path.exists("/usr/lib/freecad"):
                freecad_name = "freecad"
            
            sys.path.insert(0, "/usr/lib/python3/dist-packages")

            if freecad_name is not None:
                sys.path.append(f"/usr/lib/{freecad_name}/lib")
                sys.path.append(f"/usr/share/{freecad_name}/Ext")
                sys.path.append(f"/usr/share/{freecad_name}/Mod")
                sys.path.append(f"/usr/share/{freecad_name}/Mod/Part")
                sys.path.append(f"/usr/share/{freecad_name}/Mod/Draft")
                sys.path.append(f"/usr/share/{freecad_name}/Mod/Draft/draftobjects")
                # Comment line 31 from /usr/share/freecad-daily/Mod/Draft/draftutils/params.py if it crashes at import
            else:
                sys.path.append("/usr/local/lib")
                sys.path.append("/usr/local/Ext")
                sys.path.append("/usr/local/Mod")
                sys.path.append("/usr/local/Mod/Part")
                sys.path.append("/usr/local/Mod/Draft")
                sys.path.append("/usr/local/Mod/Draft/draftobjects")

                # Comment line 31 from /usr/local/Mod/Draft/draftutils/params.py if it crashes at import
                # import Arch_rc

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
        import FreeCAD
        document = FreeCAD.ActiveDocument
        document.recompute()

        spacer = document.addObject("Part::Box", "Spacer")
        spacer.Length = geometrical_data["dimensions"][2] * 1000
        spacer.Width = geometrical_data["dimensions"][0] * 1000
        spacer.Height = geometrical_data["dimensions"][1] * 1000
        spacer.Placement = FreeCAD.Placement(FreeCAD.Vector((geometrical_data["coordinates"][2] - geometrical_data["dimensions"][2] / 2) * 1000,
                                                            (geometrical_data["coordinates"][0] - geometrical_data["dimensions"][0] / 2) * 1000,
                                                            (geometrical_data["coordinates"][1] - geometrical_data["dimensions"][1] / 2) * 1000),
                                             FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        document.recompute()
        m = spacer.Placement.Matrix
        m.rotateX(geometrical_data['rotation'][2])
        m.rotateY(geometrical_data['rotation'][0])
        m.rotateZ(geometrical_data['rotation'][1])
        spacer.Placement.Matrix = m
        document.recompute()
        return spacer

    def get_core(self, project_name, geometrical_description, output_path=f'{os.path.dirname(os.path.abspath(__file__))}/../../output/', save_files=True, export_files=True):
        import FreeCAD
        try:
            pieces_to_export = []
            project_name = f"{project_name}_core".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")

            os.makedirs(output_path, exist_ok=True)

            close_file_after_finishing = False
            if FreeCAD.ActiveDocument is None:
                close_file_after_finishing = True
                FreeCAD.newDocument(project_name)

            document = FreeCAD.ActiveDocument

            for index, geometrical_part in enumerate(geometrical_description):
                if geometrical_part['type'] == 'spacer':
                    spacer = self.get_spacer(geometrical_part)
                    pieces_to_export.append(spacer)
                elif geometrical_part['type'] in ['half set', 'toroidal']:
                    shape_data = geometrical_part['shape']
                    part_builder = FreeCADBuilder().factory(shape_data)

                    piece = part_builder.get_piece(data=copy.deepcopy(shape_data),
                                                   name=f"Piece_{index}",
                                                   save_files=False,
                                                   export_files=False)

                    m = piece.Placement.Matrix
                    m.rotateX(geometrical_part['rotation'][2])
                    m.rotateY(geometrical_part['rotation'][0])
                    m.rotateZ(geometrical_part['rotation'][1])
                    piece.Placement.Matrix = m
                    document.recompute()

                    if 'machining' in geometrical_part and geometrical_part['machining'] is not None:
                        for machining in geometrical_part['machining']:
                            piece = part_builder.apply_machining(piece=piece,
                                                                 machining=machining,
                                                                 dimensions=flatten_dimensions(shape_data))
                        document.recompute()

                    piece.Placement.move(FreeCAD.Vector(geometrical_part['coordinates'][2] * 1000,
                                                        geometrical_part['coordinates'][0] * 1000,
                                                        geometrical_part['coordinates'][1] * 1000))

                    # if the piece is half a set, we add a residual gap between the pieces
                    if geometrical_part['type'] in ['half set']:
                        residual_gap = 5e-6
                        if geometrical_part['rotation'][0] > 0:
                            piece.Placement.move(FreeCAD.Vector(0, 0, residual_gap / 2 * 1000))
                        else:
                            piece.Placement.move(FreeCAD.Vector(0, 0, -residual_gap / 2 * 1000))

                    document.recompute()

                    pieces_to_export.append(piece)

            if export_files:
                for index, piece in enumerate(pieces_to_export):
                    piece.Label = f"core_part_{index}"

                import Import
                import Mesh
                Import.export(pieces_to_export, f"{output_path}{os.path.sep}{project_name}.step")
                Mesh.export(pieces_to_export, f"{output_path}{os.path.sep}{project_name}.obj")

            if save_files:
                document.saveAs(f"{output_path}{os.path.sep}{project_name}.FCStd")

            if close_file_after_finishing:
                FreeCAD.closeDocument(project_name)

            if export_files:
                return f"{output_path}{os.path.sep}{project_name}.step", f"{output_path}{os.path.sep}{project_name}.obj"
            else:
                return pieces_to_export

        except:  # noqa: E722
            with contextlib.suppress(NameError):
                document = FreeCAD.ActiveDocument
                document.saveAs(f"{output_path}/error.FCStd")
                FreeCAD.closeDocument(project_name)
            return None, None

    def get_core_gapping_technical_drawing(self, project_name, core_data, colors=None, output_path=f'{os.path.dirname(os.path.abspath(__file__))}/../../output/', save_files=True, export_files=True):
        import FreeCAD

        def calculate_total_dimensions(margin):
            base_width = 0
            base_height = 0
            for piece in geometrical_description:
                if piece['type'] == "half set":
                    dimensions = flatten_dimensions(piece['shape'])
                    base_height += dimensions['B']
                elif piece['type'] == "toroidal":
                    dimensions = flatten_dimensions(piece['shape'])
                    base_height += dimensions['A']
                elif piece['type'] == "spacer":
                    base_height += piece['dimensions'][1] * 1000

                if piece['type'] in ['half set', 'toroidal']:
                    base_width = max(base_width, dimensions['A'])

            return base_width, base_height

        try:
            project_name = f"{project_name}_core_gaps_FrontView".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
            geometrical_description = core_data['geometricalDescription']

            close_file_after_finishing = False
            if FreeCAD.ActiveDocument is None:
                close_file_after_finishing = True
                FreeCAD.newDocument(project_name)

            document = FreeCAD.ActiveDocument

            pieces = self.get_core(project_name, geometrical_description, output_path, save_files=False, export_files=False)

            margin = 35

            base_width, base_height = calculate_total_dimensions(margin)
            scale = 1000 / (1.25 * base_width)

            projection_rotation = 180
            for piece in geometrical_description:
                if piece['type'] in ['half set', 'toroidal']: 
                    dimensions = flatten_dimensions(piece['shape'])

                    if piece['shape']['family'] in ['efd']:
                        projection_depth = -dimensions['C'] / 2 + dimensions['K'] + dimensions['F2'] / 2
                    elif piece['shape']['family'] in ['epx', 'ep']:
                        projection_depth = dimensions['C'] / 2 - dimensions['K']
                    else:
                        projection_depth = 0

                    if piece['shape']['family'] in ['u', 'ur']:
                        projection_rotation = 0

            projection_depth *= scale

            front_view = self.get_front_projection(pieces, margin, scale, base_height, base_width, projection_depth, projection_rotation)
            if save_files:
                document.saveAs(f"{output_path}/{project_name}.FCStd")

            if colors is None:
                colors = {
                    "projection_color": "#000000",
                    "dimension_color": "#000000"
                }

            core = FreeCAD.ActiveDocument.addObject("Part::MultiFuse", "Core")
            core.Shapes = pieces
            FreeCAD.ActiveDocument.recompute()

            core = self.cut_piece_in_half(core)

            front_view_file = self.add_dimensions_and_export_view(core_data, scale, base_height, base_width, front_view, project_name, margin, colors, save_files, core)
            if save_files:
                document.saveAs(f"{output_path}/{project_name}.FCStd")
                with open(f"{output_path}/{project_name}.svg", "w", encoding="utf-8") as svgFile:
                    svgFile.write(front_view_file)
            if close_file_after_finishing:
                FreeCAD.closeDocument(project_name)

            return {"front_view": front_view_file}
        except Exception as e:  # noqa: E722
            print(e)
            FreeCAD.closeDocument(project_name)
            return {"top_view": None, "front_view": None}

    def cut_piece_in_half(self, piece):
        import FreeCAD
        document = FreeCAD.ActiveDocument

        half_volume = document.addObject("Part::Box", "half_volume")
        document.recompute()
        size = 100000
        half_volume.Length = size
        half_volume.Width = size
        half_volume.Height = size
        half_volume.Placement = FreeCAD.Placement(FreeCAD.Vector(-size, -size / 2, -size / 2), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

        piece_cut = document.addObject("Part::Cut", "Core")
        piece_cut.Base = piece
        piece_cut.Tool = half_volume
        document.recompute()

        return piece_cut

    def add_dimensions_and_export_view(self, core_data, scale, base_height, base_width, view, project_name, margin, colors, save_files, core):
        import FreeCAD
        import Draft
        import TechDraw

        def create_dimension(starting_coordinates, ending_coordinates, dimension_type, dimension_label, label_offset=0, label_alignment=0):
            dimension_svg = ""

            if dimension_type == "DistanceY":
                main_line_start = [starting_coordinates[0] + label_offset, starting_coordinates[1]]
                main_line_end = [ending_coordinates[0] + label_offset, ending_coordinates[1]]
                left_aux_line_start = [starting_coordinates[0], starting_coordinates[1]]
                left_aux_line_end = [starting_coordinates[0] + label_offset, starting_coordinates[1]]
                right_aux_line_start = [ending_coordinates[0], ending_coordinates[1]]
                right_aux_line_end = [ending_coordinates[0] + label_offset, ending_coordinates[1]]

                dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value + ending_coordinates[0] + label_offset - dimension_font_size / 4},{1000 - view.Y.Value + label_alignment})" stroke-linecap="square" stroke-linejoin="bevel">
                                         <text x="0" y="0" text-anchor="middle" fill-opacity="1" font-size="{dimension_font_size}" font-style="normal" fill="{colors['dimension_color']}" font-family="osifont" stroke="none" xml:space="preserve" font-weight="400" transform="rotate(-90)">{dimension_label}</text>
                                        </g>\n""".replace("                                    ", "")
                dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                          <path fill-rule="evenodd" vector-effect="none" d="M{main_line_start[0]},{main_line_start[1]} L{main_line_end[0]},{main_line_end[1]} M{left_aux_line_start[0]},{left_aux_line_start[1]} L{left_aux_line_end[0]},{left_aux_line_end[1]} M{right_aux_line_start[0]},{right_aux_line_start[1]} L{right_aux_line_end[0]},{right_aux_line_end[1]}"/>
                                        </g>\n""".replace("                                     ", "")
                dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                         <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{ending_coordinates[0] + label_offset},{ending_coordinates[1]})" stroke-linecap="round" stroke-linejoin="bevel">
                                          <path fill-rule="evenodd" vector-effect="none" d="M0,0 L3,-10 L-3,-10 L0,0"/>
                                         </g>
                                         <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{starting_coordinates[0] + label_offset},{starting_coordinates[1]})" stroke-linecap="round" stroke-linejoin="bevel">
                                          <path fill-rule="evenodd" vector-effect="none" d="M0,0 L-3,10 L3,10 L0,0"/>
                                         </g>
                                        </g>\n""".replace("                                     ", "")
            elif dimension_type == "DistanceX":
                main_line_start = [starting_coordinates[0], starting_coordinates[1] + label_offset]
                main_line_end = [ending_coordinates[0], ending_coordinates[1] + label_offset]
                left_aux_line_start = [starting_coordinates[0], starting_coordinates[1]]
                left_aux_line_end = [starting_coordinates[0], starting_coordinates[1] + label_offset]
                right_aux_line_start = [ending_coordinates[0], ending_coordinates[1]]
                right_aux_line_end = [ending_coordinates[0], ending_coordinates[1] + label_offset]

                dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="square" stroke-linejoin="bevel">
                                         <text x="0" y="{ending_coordinates[1] + label_offset - dimension_font_size / 4}" text-anchor="middle" fill-opacity="1" font-size="{dimension_font_size}" font-style="normal" fill="{colors['dimension_color']}" font-family="osifont" stroke="none" xml:space="preserve" font-weight="400">{dimension_label}</text>
                                        </g>\n""".replace("                                    ", "")
                dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                          <path fill-rule="evenodd" vector-effect="none" d="M{main_line_start[0]},{main_line_start[1]} L{main_line_end[0]},{main_line_end[1]} M{left_aux_line_start[0]},{left_aux_line_start[1]} L{left_aux_line_end[0]},{left_aux_line_end[1]} M{right_aux_line_start[0]},{right_aux_line_start[1]} L{right_aux_line_end[0]},{right_aux_line_end[1]}"/>
                                        </g>\n""".replace("                                     ", "")
                dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                         <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{ending_coordinates[0]},{ending_coordinates[1] + label_offset})" stroke-linecap="round" stroke-linejoin="bevel">
                                          <path fill-rule="evenodd" vector-effect="none" d="M0,0 L-10,-3 L-10,3 L0,0"/>
                                         </g>
                                         <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{starting_coordinates[0]},{starting_coordinates[1] + label_offset})" stroke-linecap="round" stroke-linejoin="bevel">
                                          <path fill-rule="evenodd" vector-effect="none" d="M0,0 L10,3 L10,-3 L0,0"/>
                                         </g>
                                        </g>\n""".replace("                                     ", "")
            return dimension_svg

        projection_line_thickness = 4
        dimension_line_thickness = 1
        dimension_font_size = 20
        horizontal_offset = 30
        horizontal_offset_gaps = 60

        base_width = 1000
        base_height *= scale
        base_height += margin
        head = f"""<svg xmlns:dc="http://purl.org/dc/elements/1.1/" baseProfile="tiny" xmlns:svg="http://www.w3.org/2000/svg" version="1.2" width="100%" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {base_width} {base_height}" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" height="100%" xmlns:freecad="http://www.freecadweb.org/wiki/index.php?title=Svg_Namespace" xmlns:cc="http://creativecommons.org/ns#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
                     <title>Open Magnetic SVG Export</title>
                     <desc>Drawing exported from https://openmagnetics.com</desc>
                     <defs/>
                     <g id="{view.Name}" inkscape:label="TechDraw" inkscape:groupmode="layer">
                      <g id="DrawingContent" fill="none" stroke="black" stroke-width="1" fill-rule="evenodd" stroke-linecap="square" stroke-linejoin="bevel">""".replace("                    ", "")
        projetion_head = f"""    <g fill-opacity="1" font-size="29.1042" font-style="normal" fill="#ffffff" font-family="MS Shell Dlg 2" stroke="none" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})">\n"""
        projetion_tail = """   </g>\n"""
        tail = """</g>
                 </g>
                </svg>
                """.replace("                ", "")
        svgFile_data = ""
        svgFile_data += head
        svgFile_data += projetion_head

        piece = Draft.scale(core, FreeCAD.Vector(scale, scale, scale))

        m = piece.Placement.Matrix
        if core_data['functionalDescription']['shape']['family'] in ['u', 'ur']:
            m.rotateZ(math.radians(90))
        else:
            m.rotateZ(math.radians(-90))
        piece.Placement.Matrix = m
        m = piece.Placement.Matrix
        m.rotateY(math.radians(90))
        piece.Placement.Matrix = m

        svgFile_data += TechDraw.projectToSVG(piece.Shape, FreeCAD.Vector(0., 1., 0.)).replace("><", ">\n<").replace("<", "    <").replace("stroke-width=\"0.7\"", f"stroke-width=\"{projection_line_thickness}\"").replace("#000000", colors['projection_color']).replace("rgb(0, 0, 0)", colors['projection_color'])

        svgFile_data += projetion_tail
        geometrical_description = core_data['geometricalDescription']

        center_offset = 0
        if (len(core_data['processedDescription']['columns']) == 2 and core_data['processedDescription']['columns'][1]['coordinates'][2] == 0):
            for piece in geometrical_description:
                if piece['type'] == "half set" and piece['shape']['family'] not in ['u', 'ur']:
                    dimensions = flatten_dimensions(piece['shape'])
                    if 'F' in dimensions and dimensions['F'] > 0:
                        center_offset = -dimensions['A'] / 2 + dimensions['F'] / 2
                    elif 'E' in dimensions and dimensions['E'] > 0:
                        center_offset = -dimensions['A'] / 2 + (dimensions['A'] - dimensions['E']) / 4
                    else:
                        center_offset = -dimensions['A'] / 2 + dimensions['C'] / 2
                    break

                elif piece['type'] == "toroidal":
                    dimensions = flatten_dimensions(piece['shape'])
                    center_offset = 0
                    break

        grouped_gaps_per_column = {}

        for gap in core_data['functionalDescription']['gapping']:
            if gap['coordinates'] is None:
                continue
            if (
                gap['coordinates'][0],
                gap['coordinates'][2],
            ) not in grouped_gaps_per_column:
                grouped_gaps_per_column[gap['coordinates'][0], gap['coordinates'][2]] = []
            grouped_gaps_per_column[
                gap['coordinates'][0], gap['coordinates'][2]
            ].append(gap)

        ordered_gaps_per_column = {}
        for key, value in grouped_gaps_per_column.items():
            ordered_list = value
            ordered_list.sort(key=lambda a: a['coordinates'][1])
            ordered_gaps_per_column[key] = ordered_list

        column_semi_height = core_data['processedDescription']['columns'][0]['height'] / 2
        for key, gaps_per_column in ordered_gaps_per_column.items():
            for gap_index, gap in enumerate(gaps_per_column):
                if gap['type'] == "additive" and (gap['coordinates'][0] > 0 or gap['coordinates'][2] != 0):
                    if gap['length'] < 0.0001:
                        dimension_label = f"{round(gap['length'] * 1000000, 2)} μm"
                    else:
                        dimension_label = f"{round(gap['length'] * 1000, 2)} mm"
                    svgFile_data += create_dimension(starting_coordinates=[(gap['coordinates'][0] * 1000 + center_offset) * scale, -gap['length'] * scale * 1000 / 2],
                                                     ending_coordinates=[(gap['coordinates'][0] * 1000 + center_offset) * scale, gap['length'] * scale * 1000 / 2],
                                                     dimension_type="DistanceY",
                                                     dimension_label=dimension_label,
                                                     label_offset=min(base_width / 2, gap['sectionDimensions'][0] / 2 * scale * 1000 + horizontal_offset_gaps))

                if gap['sectionDimensions'] is None:
                    continue

                if gap['type'] in ["subtractive", "residual"]:
                    if gap['length'] < 0.0001:
                        dimension_label = f"{round(gap['length'] * 1000000, 2)} μm"
                    else:
                        dimension_label = f"{round(gap['length'] * 1000, 2)} mm"
                    svgFile_data += create_dimension(starting_coordinates=[(gap['coordinates'][0] * 1000 + center_offset) * scale, (-gap['length'] / 2 - gap['coordinates'][1]) * scale * 1000],
                                                     ending_coordinates=[(gap['coordinates'][0] * 1000 + center_offset) * scale, (gap['length'] / 2 - gap['coordinates'][1]) * scale * 1000],
                                                     dimension_type="DistanceY",
                                                     dimension_label=dimension_label,
                                                     label_offset=min(base_width / 2, gap['sectionDimensions'][0] / 2 * scale * 1000 + horizontal_offset_gaps),
                                                     label_alignment=-gap['coordinates'][1] * scale * 1000)
                    if len(gaps_per_column) > 1 and gap_index < len(gaps_per_column) - 1:
                        next_gap = gaps_per_column[gap_index + 1]
                        chunk_size = (-gap['length'] / 2 - gap['coordinates'][1]) - (next_gap['length'] / 2 - next_gap['coordinates'][1])
                        dimension_label = f"{round(chunk_size * 1000, 2)}"
                        if chunk_size * 1000 * scale > 70:
                            dimension_label += " mm"
                        svgFile_data += create_dimension(ending_coordinates=[((gap['coordinates'][0] + gap['sectionDimensions'][0] / 2) * 1000 + center_offset) * scale, (-gap['length'] / 2 - gap['coordinates'][1]) * scale * 1000],
                                                         starting_coordinates=[((gap['coordinates'][0] + gap['sectionDimensions'][0] / 2) * 1000 + center_offset) * scale, (next_gap['length'] / 2 - next_gap['coordinates'][1]) * scale * 1000],
                                                         dimension_type="DistanceY",
                                                         dimension_label=dimension_label,
                                                         label_offset=min(base_width / 2, horizontal_offset),
                                                         label_alignment=(-gap['coordinates'][1] - gap['length'] / 2 - chunk_size / 2) * scale * 1000)

                    if len(gaps_per_column) > 1 and gap_index < len(gaps_per_column) - 1:
                        next_gap = gaps_per_column[gap_index + 1]
                        chunk_size = (-gap['length'] / 2 - gap['coordinates'][1]) - (next_gap['length'] / 2 - next_gap['coordinates'][1])
                        dimension_label = f"{round(chunk_size * 1000, 2)}"
                        if chunk_size * 1000 * scale > 70:
                            dimension_label += " mm"
                        svgFile_data += create_dimension(ending_coordinates=[((gap['coordinates'][0] + gap['sectionDimensions'][0] / 2) * 1000 + center_offset) * scale, (-gap['length'] / 2 - gap['coordinates'][1]) * scale * 1000],
                                                         starting_coordinates=[((gap['coordinates'][0] + gap['sectionDimensions'][0] / 2) * 1000 + center_offset) * scale, (next_gap['length'] / 2 - next_gap['coordinates'][1]) * scale * 1000],
                                                         dimension_type="DistanceY",
                                                         dimension_label=dimension_label,
                                                         label_offset=min(base_width / 2, horizontal_offset),
                                                         label_alignment=(-gap['coordinates'][1] - gap['length'] / 2 - chunk_size / 2) * scale * 1000)

                    if len(gaps_per_column) > 1 and gap_index == 0:
                        chunk_size = column_semi_height - (gap['length'] / 2 - gap['coordinates'][1])
                        dimension_label = f"{round(chunk_size * 1000, 2)}"
                        if chunk_size * 1000 * scale > 70:
                            dimension_label += " mm"
                        svgFile_data += create_dimension(starting_coordinates=[((gap['coordinates'][0] + gap['sectionDimensions'][0] / 2) * 1000 + center_offset) * scale, (gap['length'] / 2 - gap['coordinates'][1]) * scale * 1000],
                                                         ending_coordinates=[((gap['coordinates'][0] + gap['sectionDimensions'][0] / 2) * 1000 + center_offset) * scale, column_semi_height * scale * 1000],
                                                         dimension_type="DistanceY",
                                                         dimension_label=dimension_label,
                                                         label_offset=min(base_width / 2, horizontal_offset),
                                                         label_alignment=(column_semi_height - chunk_size / 2) * scale * 1000)

                    if len(gaps_per_column) > 1 and gap_index == len(gaps_per_column) - 1:
                        chunk_size = (-gap['length'] / 2 - gap['coordinates'][1]) + column_semi_height
                        dimension_label = f"{round(chunk_size * 1000, 2)}"
                        if chunk_size * 1000 * scale > 70:
                            dimension_label += " mm"
                        svgFile_data += create_dimension(ending_coordinates=[((gap['coordinates'][0] + gap['sectionDimensions'][0] / 2) * 1000 + center_offset) * scale, (-gap['length'] / 2 - gap['coordinates'][1]) * scale * 1000],
                                                         starting_coordinates=[((gap['coordinates'][0] + gap['sectionDimensions'][0] / 2) * 1000 + center_offset) * scale, -column_semi_height * scale * 1000],
                                                         dimension_type="DistanceY",
                                                         dimension_label=dimension_label,
                                                         label_offset=min(base_width / 2, horizontal_offset),
                                                         label_alignment=(-column_semi_height + chunk_size / 2) * scale * 1000)

        svgFile_data += tail

        return svgFile_data

    def get_front_projection(self, pieces, margin, scale, base_height, base_width, projection_depth, projection_rotation):
        import FreeCAD
        import Draft

        document = FreeCAD.ActiveDocument
        page = document.addObject('TechDraw::DrawPage', 'Top Page')
        template = document.addObject('TechDraw::DrawSVGTemplate', 'Template')
        page.Template = template
        document.recompute()

        # cloned_piece = Draft.make_clone(pieces, forcedraft=True)

        if len(pieces) > 1:
            aux = document.addObject("Part::MultiFuse", "Fusion")
            aux.Shapes = pieces
            document.recompute()
        else:
            aux = pieces[0]

        cloned_piece = Draft.scale(aux, FreeCAD.Vector(scale, scale, scale))
        # cloned_piece.Scale = FreeCAD.Vector(scale, scale, scale)
        FreeCAD.ActiveDocument.recompute()

        top_view = document.addObject('TechDraw::DrawViewPart', 'TopView')
        page.addView(top_view)
        top_view.Source = [cloned_piece]
        top_view.Rotation = 180
        top_view.Direction = FreeCAD.Vector(0.00, 0.00, 1.00)
        top_view.XDirection = FreeCAD.Vector(0.00, -1.00, 0.00)

        document = FreeCAD.ActiveDocument
        page = document.addObject('TechDraw::DrawPage', 'Front Page')
        template = document.addObject('TechDraw::DrawSVGTemplate', 'Template')
        page.Template = template
        document.recompute()

        section_front_view = document.addObject('TechDraw::DrawViewSection', 'FrontView')
        page.addView(section_front_view)
        section_front_view.BaseView = document.getObject('TopView')
        section_front_view.Source = document.getObject('TopView').Source
        section_front_view.ScaleType = 0
        section_front_view.SectionDirection = 'Down'
        if projection_rotation == 0:
            section_front_view.SectionNormal = FreeCAD.Vector(1.000, 0.000, 0.000)
        else:
            section_front_view.SectionNormal = FreeCAD.Vector(-1.000, 0.000, 0.000)
        section_front_view.SectionOrigin = FreeCAD.Vector(projection_depth, 0.000, 0)
        section_front_view.SectionSymbol = ''
        section_front_view.Label = 'Section  - '
        section_front_view.Scale = 1.000000
        section_front_view.ScaleType = 0
        section_front_view.Rotation = projection_rotation
        if projection_rotation == 0:
            section_front_view.Direction = FreeCAD.Vector(1.00, 0.00, 0.00)
        else:
            section_front_view.Direction = FreeCAD.Vector(-1.00, 0.00, 0.00)
        section_front_view.XDirection = FreeCAD.Vector(0.00, 1.00, 0.00)
        section_front_view.X = margin + base_width * scale / 2
        section_front_view.Y = 1000 - base_height * scale / 2 - margin
        document.recompute()
        return section_front_view

    class IPiece(metaclass=ABCMeta):
        def __init__(self):
            self.output_path = f'{os.path.dirname(os.path.abspath(__file__))}/../../output/'

        def set_output_path(self, output_path):
            self.output_path = output_path

        @staticmethod
        def edges_in_boundbox(part, xmin, ymin, zmin, xmax, ymax, zmax):
            import FreeCAD
            bb = FreeCAD.BoundBox(xmin, ymin, zmin, xmax, ymax, zmax)

            return [
                i
                for i, edge in enumerate(part.Shape.Edges)
                if bb.isInside(edge.BoundBox)
            ]

        @staticmethod
        def create_sketch():
            import FreeCAD
            document = FreeCAD.ActiveDocument

            document.addObject('PartDesign::Body', 'Body')
            document.recompute()

            sketch = document.getObject('Body').newObject('Sketcher::SketchObject', 'Sketch')
            # sketch.Support = (document.getObject('XY_Plane'), [''])
            sketch.MapMode = 'FlatFace'
            document.recompute()
            return sketch

        @staticmethod
        def extrude_sketch(sketch, part_name, height):
            import FreeCAD
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

        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F"]}

        def get_top_projection(self, data, piece, margin):
            import FreeCAD

            dimensions = data["dimensions"]

            document = FreeCAD.ActiveDocument
            page = document.addObject('TechDraw::DrawPage', 'Top Page')
            template = document.addObject('TechDraw::DrawSVGTemplate', 'Template')
            page.Template = template
            document.recompute()

            top_view = document.addObject('TechDraw::DrawViewPart', 'TopView')
            page.addView(top_view)
            top_view.Source = [piece]
            top_view.Direction = FreeCAD.Vector(0.00, 0.00, 1.00)
            top_view.XDirection = FreeCAD.Vector(0.00, -1.00, 0.00)
            top_view.X = margin + dimensions['A'] / 2

            if data['family'] in ['p', 'rm']:
                base_height = data['dimensions']['A'] + margin
            elif data['family'] in ['pm']:
                base_height = data['dimensions']['E'] + margin
            else:
                base_height = data['dimensions']['C'] + margin

            top_view.Y = 1000 - base_height / 2

            top_view.Scale = 1
            document.recompute()
            return top_view

        def get_front_projection(self, data, piece, margin):
            import FreeCAD

            dimensions = data["dimensions"]

            document = FreeCAD.ActiveDocument
            page = document.addObject('TechDraw::DrawPage', 'Top Page')
            template = document.addObject('TechDraw::DrawSVGTemplate', 'Template')
            page.Template = template
            document.recompute()

            if data['family'] in ['efd']:
                semi_depth = -dimensions['C'] / 2 + dimensions['K'] + dimensions['F2'] / 2
            elif data['family'] in ['epx']:
                semi_depth = dimensions['C'] / 2 - dimensions['K']
            else:
                semi_depth = 0

            section_front_view = document.addObject('TechDraw::DrawViewSection', 'FrontView')
            page.addView(section_front_view)
            section_front_view.BaseView = document.getObject('TopView')
            section_front_view.Source = document.getObject('TopView').Source
            section_front_view.ScaleType = 0
            section_front_view.SectionDirection = 'Down'
            section_front_view.SectionNormal = FreeCAD.Vector(-1.000, 0.000, 0.000)
            section_front_view.SectionOrigin = FreeCAD.Vector(semi_depth, 0.000, 0)
            section_front_view.SectionSymbol = ''
            section_front_view.Label = 'Section  - '
            section_front_view.Scale = 1.000000
            section_front_view.ScaleType = 0
            section_front_view.Rotation = 0
            section_front_view.Direction = FreeCAD.Vector(-1.00, 0.00, 0.00)
            section_front_view.XDirection = FreeCAD.Vector(0.00, -1.00, 0.00)
            section_front_view.X = margin + dimensions['A'] / 2
            section_front_view.Y = 1000 - margin - dimensions['B'] / 2
            document.recompute()

            return section_front_view

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

                sketch = self.create_sketch()
                self.get_shape_base(data, sketch)

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
                    import Import
                    import Mesh
                    Import.export([plate], f"{self.output_path}/{project_name}.step")
                    Mesh.export([plate], f"{self.output_path}/{project_name}.obj")

                if save_files:
                    document.saveAs(f"{self.output_path}/{project_name}.FCStd")

                if not close_file_after_finishing:
                    return plate

                FreeCAD.closeDocument(project_name)
                return f"{self.output_path}/{project_name}.step", f"{self.output_path}/{project_name}.obj"
            except:  # noqa: E722
                FreeCAD.closeDocument(project_name)
                return None, None

        def get_piece(self, data, name="Piece", save_files=False, export_files=True):
            import FreeCAD
            close_file_after_finishing = FreeCAD.ActiveDocument is None
            try:
                project_name = f"{data['name']}_piece".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")

                data["dimensions"] = flatten_dimensions(data)

                if FreeCAD.ActiveDocument is None:
                    FreeCAD.newDocument(project_name)
                document = FreeCAD.ActiveDocument

                sketch = self.create_sketch()
                self.get_shape_base(data, sketch)

                document = FreeCAD.ActiveDocument
                document.recompute()

                part_name = "piece"

                base = self.extrude_sketch(
                    sketch=sketch,
                    part_name=part_name,
                    height=data["dimensions"]["B"] if data["family"] != 't' else data["dimensions"]["C"]
                )

                document.recompute()

                negative_winding_window = self.get_negative_winding_window(data["dimensions"])

                if negative_winding_window is None:
                    piece_cut = base
                else:
                    piece_cut = document.addObject("Part::Cut", "Cut")
                    piece_cut.Base = base
                    piece_cut.Tool = negative_winding_window
                    document.recompute()

                piece_with_extra = self.get_shape_extras(data, piece_cut)

                piece = document.addObject('Part::Refine', name)
                piece.Source = piece_with_extra

                document.recompute()

                if data["family"] != 't':
                    piece.Placement.move(FreeCAD.Vector(0, 0, -data["dimensions"]["B"]))
                else:
                    piece.Placement.move(FreeCAD.Vector(0, 0, -data["dimensions"]["C"] / 2))
                    m = piece.Placement.Matrix
                    m.rotateX(math.radians(90))
                    piece.Placement.Matrix = m
                document.recompute()

                pathlib.Path(self.output_path).mkdir(parents=True, exist_ok=True)

                if export_files:
                    import Import
                    import Mesh
                    Import.export([piece], f"{self.output_path}/{project_name}.step")
                    Mesh.export([piece], f"{self.output_path}/{project_name}.obj")

                if save_files:
                    document.saveAs(f"{self.output_path}/{project_name}.FCStd")

                if not close_file_after_finishing:
                    return piece
                FreeCAD.closeDocument(project_name)
                return f"{self.output_path}/{project_name}.step", f"{self.output_path}/{project_name}.obj"
            except:  # noqa: E722
                with contextlib.suppress(NameError):
                    FreeCAD.closeDocument(project_name)
                return (None, None) if close_file_after_finishing else None

        def get_piece_technical_drawing(self, data, colors=None, save_files=False):
            import FreeCAD
            try:
                return self.try_get_piece_technical_drawing(
                    data, colors, save_files
                )
            except Exception as e:  # noqa: E722
                print(e)
                project_name = f"{data['name']}_piece_scaled".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
                FreeCAD.closeDocument(project_name)
                return {"top_view": None, "front_view": None}

        def try_get_piece_technical_drawing(self, data, colors, save_files):
            import FreeCAD
            project_name = f"{data['name']}_piece_scaled".replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "__")
            if colors is None:
                colors = {
                    "projection_color": "#000000",
                    "dimension_color": "#000000"
                }

            original_dimensions = flatten_dimensions(data)
            scale = 1000 / (1.25 * original_dimensions['A'])
            data["dimensions"] = {}
            for k, v in original_dimensions.items():
                data["dimensions"][k] = v * scale

            if FreeCAD.ActiveDocument is None:
                FreeCAD.newDocument(project_name)
            document = FreeCAD.getDocument(project_name)

            sketch = self.create_sketch()
            self.get_shape_base(data, sketch)

            document = FreeCAD.ActiveDocument
            document.recompute()

            part_name = "piece"

            base = self.extrude_sketch(
                sketch=sketch,
                part_name=part_name,
                height=data["dimensions"]["B"] if data["family"] != 't' else data["dimensions"]["C"]
            )

            document.recompute()

            negative_winding_window = self.get_negative_winding_window(data["dimensions"])

            if negative_winding_window is None:
                piece_cut = base
            else:
                piece_cut = document.addObject("Part::Cut", "Cut")
                piece_cut.Base = base
                piece_cut.Tool = negative_winding_window
                document.recompute()

            piece_with_extra = self.get_shape_extras(data, piece_cut)

            piece = document.addObject('Part::Refine', 'Refine')
            piece.Source = piece_with_extra

            document.recompute()

            error_in_piece = False
            for obj in FreeCAD.ActiveDocument.Objects:
                if not obj.isValid():
                    error_in_piece = True
                    print(f"Error in part: {obj.Name}")
                    break

            pathlib.Path(self.output_path).mkdir(parents=True, exist_ok=True)

            margin = 35

            if not error_in_piece:
                top_view = self.get_top_projection(data, piece, margin)
                front_view = self.get_front_projection(data, piece, margin)
            if save_files:
                document.saveAs(f"{self.output_path}/{project_name}.FCStd")
            if not error_in_piece:
                top_view_file = self.add_dimensions_and_export_view(data, original_dimensions, top_view, project_name, margin, colors, save_files, piece)
                front_view_file = self.add_dimensions_and_export_view(data, original_dimensions, front_view, project_name, margin, colors, save_files, piece)

            FreeCAD.closeDocument(project_name)

            return (
                {"top_view": None, "front_view": None}
                if error_in_piece
                else {"top_view": top_view_file, "front_view": front_view_file}
            )

        def add_dimensions_and_export_view(self, data, original_dimensions, view, project_name, margin, colors, save_files, piece):
            import FreeCAD
            import TechDraw

            def calculate_total_dimensions():
                base_width = data['dimensions']['A'] + margin
                base_width += horizontal_offset
                top_base_width = base_width
                if 'C' in dimensions:
                    top_base_width += increment
                if 'L' in dimensions:
                    top_base_width += increment
                if 'K' in dimensions:
                    top_base_width += increment
                front_base_width = base_width
                if 'B' in dimensions:
                    front_base_width += increment
                if 'D' in dimensions:
                    front_base_width += increment

                base_width = max(top_base_width, front_base_width)

                if view.Name == "TopView":
                    # base_width = data['dimensions']['A'] + margin
                    # base_width += horizontal_offset
                    # if 'C' in dimensions:
                    #     base_width += increment
                    # if 'L' in dimensions:
                    #     base_width += increment
                    # if 'K' in dimensions:
                    #     base_width += increment

                    if data['family'] == 'p':
                        base_height = data['dimensions']['A'] + margin
                    elif data['family'] in ['rm', 'pm']:
                        base_height = data['dimensions']['E'] + margin
                    else:
                        base_height = data['dimensions']['C'] + margin

                    if 'A' in dimensions:
                        base_height += increment
                    if 'E' in dimensions:
                        base_height += increment
                    if 'F' in dimensions:
                        base_height += increment
                    if 'G' in dimensions and dimensions['G'] > 0:
                        base_height += increment
                    if 'H' in dimensions and dimensions['H'] > 0:
                        base_height += increment
                    if 'J' in dimensions:
                        base_height += increment

                if view.Name == "FrontView":
                    # base_width = data['dimensions']['A'] + margin
                    # base_width += horizontal_offset
                    # if 'B' in dimensions:
                    #     base_width += increment
                    # if 'D' in dimensions:
                    #     base_width += increment

                    base_height = data['dimensions']['B'] + margin * 2

                return base_width, base_height

            def create_dimension(starting_coordinates, ending_coordinates, dimension_type, dimension_label, label_offset=0, label_alignment=0):

                dimension_svg = ""

                if dimension_type == "DistanceY":
                    main_line_start = [starting_coordinates[0] + label_offset, starting_coordinates[1]]
                    main_line_end = [ending_coordinates[0] + label_offset, ending_coordinates[1]]
                    left_aux_line_start = [starting_coordinates[0], starting_coordinates[1]]
                    left_aux_line_end = [starting_coordinates[0] + label_offset, starting_coordinates[1]]
                    right_aux_line_start = [ending_coordinates[0], ending_coordinates[1]]
                    right_aux_line_end = [ending_coordinates[0] + label_offset, ending_coordinates[1]]

                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value + ending_coordinates[0] + label_offset - dimension_font_size / 4},{1000 - view.Y.Value + label_alignment})" stroke-linecap="square" stroke-linejoin="bevel">
                                             <text x="0" y="0" text-anchor="middle" fill-opacity="1" font-size="{dimension_font_size}" font-style="normal" fill="{colors['dimension_color']}" font-family="osifont" stroke="none" xml:space="preserve" font-weight="400" transform="rotate(-90)">{dimension_label}</text>
                                            </g>\n""".replace("                                    ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M{main_line_start[0]},{main_line_start[1]} L{main_line_end[0]},{main_line_end[1]} M{left_aux_line_start[0]},{left_aux_line_start[1]} L{left_aux_line_end[0]},{left_aux_line_end[1]} M{right_aux_line_start[0]},{right_aux_line_start[1]} L{right_aux_line_end[0]},{right_aux_line_end[1]}"/>
                                            </g>\n""".replace("                                     ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{ending_coordinates[0] + label_offset},{ending_coordinates[1]})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L6,-15 L-6,-15 L0,0"/>
                                             </g>
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{starting_coordinates[0] + label_offset},{starting_coordinates[1]})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L-6,15 L6,15 L0,0"/>
                                             </g>
                                            </g>\n""".replace("                                     ", "")
                elif dimension_type == "DistanceX":
                    main_line_start = [starting_coordinates[0], starting_coordinates[1] + label_offset]
                    main_line_end = [ending_coordinates[0], ending_coordinates[1] + label_offset]
                    left_aux_line_start = [starting_coordinates[0], starting_coordinates[1]]
                    left_aux_line_end = [starting_coordinates[0], starting_coordinates[1] + label_offset]
                    right_aux_line_start = [ending_coordinates[0], ending_coordinates[1]]
                    right_aux_line_end = [ending_coordinates[0], ending_coordinates[1] + label_offset]

                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="square" stroke-linejoin="bevel">
                                             <text x="0" y="{ending_coordinates[1] + label_offset - dimension_font_size / 4}" text-anchor="middle" fill-opacity="1" font-size="{dimension_font_size}" font-style="normal" fill="{colors['dimension_color']}" font-family="osifont" stroke="none" xml:space="preserve" font-weight="400">{dimension_label}</text>
                                            </g>\n""".replace("                                    ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M{main_line_start[0]},{main_line_start[1]} L{main_line_end[0]},{main_line_end[1]} M{left_aux_line_start[0]},{left_aux_line_start[1]} L{left_aux_line_end[0]},{left_aux_line_end[1]} M{right_aux_line_start[0]},{right_aux_line_start[1]} L{right_aux_line_end[0]},{right_aux_line_end[1]}"/>
                                            </g>\n""".replace("                                     ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{ending_coordinates[0]},{ending_coordinates[1] + label_offset})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L-15,-6 L-15,6 L0,0"/>
                                             </g>
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{starting_coordinates[0]},{starting_coordinates[1] + label_offset})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L15,6 L15,-6 L0,0"/>
                                             </g>
                                            </g>\n""".replace("                                     ", "")
                return dimension_svg

            projection_line_thickness = 4
            dimension_line_thickness = 1
            dimension_font_size = 50
            horizontal_offset = 75
            vertical_offset = 75
            correction = 0
            increment = 75
            dimensions = data["dimensions"]
            if data['family'] not in ['p']:
                shape_semi_height = dimensions['C'] / 2
            else:
                shape_semi_height = dimensions['A'] / 2
            scale = 1000 / (1.25 * original_dimensions['A'])
            base_width, base_height = calculate_total_dimensions()
            head = f"""<svg xmlns:dc="http://purl.org/dc/elements/1.1/" baseProfile="tiny" xmlns:svg="http://www.w3.org/2000/svg" version="1.2" width="100%" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {base_width} {base_height}" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" height="100%" xmlns:freecad="http://www.freecadweb.org/wiki/index.php?title=Svg_Namespace" xmlns:cc="http://creativecommons.org/ns#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
                         <title>Open Magnetic SVG Export</title>
                         <desc>Drawing exported from https://openmagnetics.com</desc>
                         <defs/>
                         <g id="{view.Name}" inkscape:label="TechDraw" inkscape:groupmode="layer">
                          <g id="DrawingContent" fill="none" stroke="black" stroke-width="1" fill-rule="evenodd" stroke-linecap="square" stroke-linejoin="bevel">""".replace("                    ", "")
            projetion_head = f"""    <g fill-opacity="1" font-size="29.1042" font-style="normal" fill="#ffffff" font-family="MS Shell Dlg 2" stroke="none" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})">\n"""
            projetion_tail = """   </g>\n"""
            tail = """</g>
                     </g>
                    </svg>
                    """.replace("                ", "")
            svgFile_data = ""
            svgFile_data += head
            svgFile_data += projetion_head

            if view.Name == "TopView":
                m = piece.Placement.Matrix
                m.rotateZ(math.radians(90))
                piece.Placement.Matrix = m
                svgFile_data += TechDraw.projectToSVG(piece.Shape, FreeCAD.Vector(0., 0., 1.)).replace("><", ">\n<").replace("<", "    <").replace("stroke-width=\"0.7\"", f"stroke-width=\"{projection_line_thickness}\"").replace("#000000", colors['projection_color']).replace("rgb(0, 0, 0)", colors['projection_color'])
            else:
                m = piece.Placement.Matrix
                m.rotateY(math.radians(90))
                piece.Placement.Matrix = m
                piece.Placement.move(FreeCAD.Vector(-dimensions["B"] / 2, 0, 0))
                svgFile_data += TechDraw.projectToSVG(piece.Shape, FreeCAD.Vector(0., 1., 0.)).replace("><", ">\n<").replace("<", "    <").replace("stroke-width=\"0.7\"", f"stroke-width=\"{projection_line_thickness}\"").replace("#000000", colors['projection_color']).replace("rgb(0, 0, 0)", colors['projection_color'])

            svgFile_data += projetion_tail
            if view.Name == "TopView":
                if "L" in dimensions and dimensions["L"] > 0:
                    svgFile_data += create_dimension(starting_coordinates=[dimensions['J'] / 2, -dimensions['L'] / 2],
                                                     ending_coordinates=[dimensions['J'] / 2, dimensions['L'] / 2],
                                                     dimension_type="DistanceY",
                                                     dimension_label=f"L: {round(dimensions['L'] / scale, 2)} mm",
                                                     label_offset=horizontal_offset + dimensions['A'] / 2 - dimensions['J'] / 2)
                    horizontal_offset += increment
                k = 0
                if "K" in dimensions and dimensions["K"] > 0:
                    if data['family'] == 'efd':
                        height_of_dimension = dimensions['C'] / 2
                        k = -dimensions['K']
                    else:
                        height_of_dimension = -dimensions['C'] / 2
                        k = dimensions['K']
                    if dimensions['K'] < 0:
                        correction = dimensions['K'] / 2
                    else:
                        correction = 0
                    svgFile_data += create_dimension(starting_coordinates=[dimensions['F'] / 2, height_of_dimension + correction],
                                                     ending_coordinates=[dimensions['F'] / 2, height_of_dimension + k + correction],
                                                     dimension_type="DistanceY",
                                                     dimension_label=f"K: {round(original_dimensions['K'], 2)} mm",
                                                     label_offset=horizontal_offset + (dimensions['A'] / 2 - dimensions['F'] / 2),
                                                     label_alignment=height_of_dimension + k / 2 + correction)
                    horizontal_offset += increment
                if "F2" in dimensions and dimensions["F2"] > 0:
                    if data['family'] in ['efd']:
                        svgFile_data += create_dimension(starting_coordinates=[0, dimensions['C'] / 2 + correction - dimensions['K'] - dimensions['F2']],
                                                         ending_coordinates=[0, dimensions['C'] / 2 + correction - dimensions['K']],
                                                         dimension_type="DistanceY",
                                                         dimension_label=f"F2: {round(original_dimensions['F2'], 2)} mm",
                                                         label_offset=horizontal_offset + dimensions['A'] / 2,
                                                         label_alignment=dimensions['F2'] / 2 + k / 2 + correction)
                    else:
                        svgFile_data += create_dimension(starting_coordinates=[0, -dimensions['F2'] / 2],
                                                         ending_coordinates=[0, dimensions['F2'] / 2],
                                                         dimension_type="DistanceY",
                                                         dimension_label=f"F2: {round(original_dimensions['F2'], 2)} mm",
                                                         label_offset=horizontal_offset + dimensions['A'] / 2)
                    horizontal_offset += increment
                if "C" in dimensions and dimensions['C'] > 0:
                    svgFile_data += create_dimension(starting_coordinates=[dimensions['A'] / 2, -dimensions['C'] / 2 + correction],
                                                     ending_coordinates=[dimensions['A'] / 2, dimensions['C'] / 2 + correction],
                                                     dimension_type="DistanceY",
                                                     dimension_label=f"C: {round(original_dimensions['C'], 2)} mm",
                                                     label_offset=horizontal_offset)
                    horizontal_offset += increment
                if "H" in dimensions and dimensions['H'] > 0:
                    svgFile_data += create_dimension(starting_coordinates=[-dimensions['H'] / 2, 0],
                                                     ending_coordinates=[dimensions['H'] / 2, 0],
                                                     dimension_type="DistanceX",
                                                     dimension_label=f"H: {round(original_dimensions['H'], 2)} mm",
                                                     label_offset=vertical_offset + shape_semi_height)
                    vertical_offset += increment
                if "J" in dimensions and data['family'] == 'pq':
                    svgFile_data += create_dimension(starting_coordinates=[-dimensions['J'] / 2, dimensions['L'] / 2],
                                                     ending_coordinates=[dimensions['J'] / 2, dimensions['L'] / 2],
                                                     dimension_type="DistanceX",
                                                     dimension_label=f"J: {round(dimensions['J'] / scale, 2)} mm",
                                                     label_offset=vertical_offset + shape_semi_height - dimensions['L'] / 2)
                    vertical_offset += increment
                if data['family'] in ['ep', 'epx']:
                    k = dimensions['C'] / 2 - dimensions['K']
                elif data['family'] in ['efd']:
                    if dimensions['K'] < 0:
                        k = - dimensions['C'] / 2 - dimensions['K'] * 2
                else:
                    k = 0

                if data['family'] not in ['p']:
                    if "F" in dimensions and dimensions["F"] > 0:
                        svgFile_data += create_dimension(starting_coordinates=[-dimensions['F'] / 2, -k],
                                                         ending_coordinates=[dimensions['F'] / 2, -k],
                                                         dimension_type="DistanceX",
                                                         dimension_label=f"F: {round(original_dimensions['F'], 2)} mm",
                                                         label_offset=vertical_offset + k + shape_semi_height)
                        vertical_offset += increment
                    if "G" in dimensions and dimensions['G'] > 0:
                        svgFile_data += create_dimension(starting_coordinates=[-dimensions['G'] / 2, shape_semi_height],
                                                         ending_coordinates=[dimensions['G'] / 2, shape_semi_height],
                                                         dimension_type="DistanceX",
                                                         dimension_label=f"G: {round(original_dimensions['G'], 2)} mm",
                                                         label_offset=vertical_offset)
                        vertical_offset += increment
                else:   
                    if "G" in dimensions and dimensions['G'] > 0:
                        svgFile_data += create_dimension(starting_coordinates=[-dimensions['G'] / 2, dimensions['E'] / 2],
                                                         ending_coordinates=[dimensions['G'] / 2, dimensions['E'] / 2],
                                                         dimension_type="DistanceX",
                                                         dimension_label=f"G: {round(original_dimensions['G'], 2)} mm",
                                                         label_offset=vertical_offset + dimensions['A'] / 2 - dimensions['E'] / 2)
                        vertical_offset += increment
                    if "F" in dimensions and dimensions["F"] > 0:
                        svgFile_data += create_dimension(starting_coordinates=[-dimensions['F'] / 2, -k],
                                                         ending_coordinates=[dimensions['F'] / 2, -k],
                                                         dimension_type="DistanceX",
                                                         dimension_label=f"F: {round(original_dimensions['F'], 2)} mm",
                                                         label_offset=vertical_offset + k + shape_semi_height)
                        vertical_offset += increment

                svgFile_data += create_dimension(starting_coordinates=[-dimensions['E'] / 2, -k],
                                                 ending_coordinates=[dimensions['E'] / 2, -k],
                                                 dimension_type="DistanceX",
                                                 dimension_label=f"E: {round(original_dimensions['E'], 2)} mm",
                                                 label_offset=vertical_offset + k + shape_semi_height)
                vertical_offset += increment
                svgFile_data += create_dimension(starting_coordinates=[-dimensions['A'] / 2, 0],
                                                 ending_coordinates=[dimensions['A'] / 2, 0],
                                                 dimension_type="DistanceX",
                                                 dimension_label=f"A: {round(original_dimensions['A'], 2)} mm",
                                                 label_offset=vertical_offset + shape_semi_height)
                vertical_offset += increment
            else:
                starting_point_for_d = dimensions['E'] / 2
                svgFile_data += create_dimension(starting_coordinates=[starting_point_for_d, -dimensions['B'] / 2],
                                                 ending_coordinates=[starting_point_for_d, -dimensions['B'] / 2 + dimensions['D']],
                                                 dimension_type="DistanceY",
                                                 dimension_label=f"D: {round(original_dimensions['D'], 2)} mm",
                                                 label_offset=horizontal_offset + (dimensions['A'] / 2 - starting_point_for_d),
                                                 label_alignment=-dimensions['B'] / 2 + dimensions['D'] / 2)
                horizontal_offset += increment
                svgFile_data += create_dimension(starting_coordinates=[dimensions['A'] / 2, -dimensions['B'] / 2],
                                                 ending_coordinates=[dimensions['A'] / 2, dimensions['B'] / 2],
                                                 dimension_type="DistanceY",
                                                 dimension_label=f"B: {round(original_dimensions['B'], 2)} mm",
                                                 label_offset=horizontal_offset)

            svgFile_data += tail

            if save_files:
                svgFile = open(f"{self.output_path}/{project_name}_{view.Name}.svg", "w")
                svgFile.write(svgFile_data) 
                svgFile.close() 
            return svgFile_data

        @abstractmethod
        def get_shape_base(self, data, sketch):
            raise NotImplementedError

        @abstractmethod
        def get_negative_winding_window(self, dimensions):
            raise NotImplementedError

        def apply_machining(self, piece, machining, dimensions):
            import FreeCAD
            document = FreeCAD.ActiveDocument

            original_tool = document.addObject("Part::Box", "tool")
            original_tool.Length = dimensions["A"]
            x_coordinate = -dimensions["A"] / 2
            if machining['coordinates'][0] == 0:
                original_tool.Width = dimensions["F"]
                original_tool.Length = dimensions["F"]
                y_coordinate = -dimensions["F"] / 2
                x_coordinate = -dimensions["F"] / 2
            else:
                original_tool.Width = dimensions["A"] / 2
                if machining['coordinates'][0] < 0:
                    y_coordinate = 0
                if machining['coordinates'][0] > 0:
                    y_coordinate = -dimensions["A"] / 2

            original_tool.Height = machining['length'] * 1000
            original_tool.Placement = FreeCAD.Placement(FreeCAD.Vector(x_coordinate, y_coordinate, (machining['coordinates'][1] - machining['length'] / 2) * 1000), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            if machining['coordinates'][0] == 0:
                tool = original_tool
            else:
                central_column_tool = document.addObject("Part::Box", "central_column_tool")
                central_column_width = dimensions["F"] * 1.001
                central_column_tool.Length = central_column_width
                central_column_tool.Width = central_column_width
                central_column_tool.Height = machining['length'] * 1000
                central_column_tool.Placement = FreeCAD.Placement(FreeCAD.Vector(-central_column_width / 2, -central_column_width / 2, (machining['coordinates'][1] - machining['length'] / 2) * 1000), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

                tool = document.addObject("Part::Cut", "machined_piece")
                tool.Base = original_tool
                tool.Tool = central_column_tool
                document.recompute()

            machined_piece = document.addObject("Part::Cut", "machined_piece")
            machined_piece.Base = piece
            machined_piece.Tool = tool
            document.recompute()

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
            import FreeCAD
            # rotation in order to avoid cut in projection
            m = piece.Base.Placement.Matrix
            m.rotateZ(math.radians(180))
            piece.Base.Placement.Matrix = m

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
                    if "C" in dimensions and dimensions['C'] > 0:
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

                internal_vertexes = []
                internal_top_right_vertex = self.edges_in_boundbox(part=piece,
                                                                   xmin=internal_xmin,
                                                                   xmax=dimensions["E"] / 2,
                                                                   ymin=dimensions["G"] / 4,
                                                                   ymax=3 * dimensions["G"] / 4,
                                                                   zmin=dimensions["B"] - dimensions["D"],
                                                                   zmax=dimensions["B"])
                if len(internal_top_right_vertex) > 0:
                    internal_vertexes.append(internal_top_right_vertex[0])
                internal_bottom_right_vertex = self.edges_in_boundbox(part=piece,
                                                                      xmin=internal_xmin,
                                                                      xmax=dimensions["E"] / 2,
                                                                      ymax=-dimensions["G"] / 4,
                                                                      ymin=-3 * dimensions["G"] / 4,
                                                                      zmin=dimensions["B"] - dimensions["D"],
                                                                      zmax=dimensions["B"])
                if len(internal_bottom_right_vertex) > 0:
                    internal_vertexes.append(internal_bottom_right_vertex[0])
                internal_top_left_vertex = self.edges_in_boundbox(part=piece,
                                                                  xmin=-dimensions["E"] / 2,
                                                                  xmax=-internal_xmin,
                                                                  ymin=dimensions["G"] / 4,
                                                                  ymax=3 * dimensions["G"] / 4,
                                                                  zmin=dimensions["B"] - dimensions["D"],
                                                                  zmax=dimensions["B"])
                if len(internal_top_left_vertex) > 0:
                    internal_vertexes.append(internal_top_left_vertex[0])
                internal_bottom_left_vertex = self.edges_in_boundbox(part=piece,
                                                                     xmin=-dimensions["E"] / 2,
                                                                     xmax=-internal_xmin,
                                                                     ymax=-dimensions["G"] / 4,
                                                                     ymin=-3 * dimensions["G"] / 4,
                                                                     zmin=dimensions["B"] - dimensions["D"],
                                                                     zmax=dimensions["B"])
                if len(internal_bottom_left_vertex) > 0:
                    internal_vertexes.append(internal_bottom_left_vertex[0])

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

                fillet_external_radius = 0.95 * utils.decimal_floor((dimensions['A'] - dimensions["E"]) / 4, 2)
                fillet_internal_radius = 0.95 * min(utils.decimal_floor((dimensions['A'] - dimensions["E"]) / 4, 2), (dimensions["E"] - dimensions["E"] * math.cos(math.asin(dimensions["G"] / dimensions["E"]))))
                fillet_base_radius = 0.95 * min(0.1 * dimensions["G"], (dimensions["E"] - dimensions["E"] * math.cos(math.asin(dimensions["G"] / dimensions["E"]))) / 4)
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
            import FreeCAD
            import Part
            import Sketcher
            dimensions = data["dimensions"]
            familySubtype = data["familySubtype"]

            external_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["A"] / 2), False)
            sketch.addConstraint(Sketcher.Constraint('Coincident', external_circle, 3, -1, 1))
            sketch.addConstraint(Sketcher.Constraint('Diameter', external_circle, dimensions["A"]))
            if "H" in dimensions and dimensions["H"] > 0:
                internal_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["H"] / 2), False)
                sketch.addConstraint(Sketcher.Constraint('Coincident', internal_circle, 3, -1, 1))
                sketch.addConstraint(Sketcher.Constraint('Diameter', internal_circle, dimensions["H"]))

            if familySubtype == '1':
                pass    
            elif familySubtype == '2': 
                a = dimensions["A"] / 2
                if "C" in dimensions and dimensions["C"] > 0:
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
                f = dimensions["F"] / 2 * 1.01  # to avoid bug in three.js
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
            import FreeCAD
            from BasicShapes import Shapes
            document = FreeCAD.ActiveDocument
            tube = Shapes.addTube(FreeCAD.ActiveDocument, "winding_window")
            tube.Height = dimensions["D"]
            tube.InnerRadius = dimensions["F"] / 2
            tube.OuterRadius = dimensions["E"] / 2
            tube.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(90, 0, 0))
            document.recompute()

            return tube

    class Pq(P):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "G"]} 

        def get_shape_base(self, data, sketch):
            import FreeCAD
            import Part
            import Sketcher
            dimensions = data["dimensions"]

            if "L" not in dimensions:
                dimensions["L"] = dimensions["F"] + (dimensions["C"] - dimensions["F"]) / 3

            if "J" not in dimensions:
                dimensions["J"] = dimensions["F"] / 2

            if "G" in dimensions:
                g_angle = math.asin(dimensions["G"] / dimensions["E"])
            else:
                g_angle = math.asin((dimensions["E"] - ((dimensions["E"] - dimensions["F"]) / 2)) / dimensions["E"])

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
        def get_dimensions_and_subtypes(self):
            return {
                1: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
                2: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
                3: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
                4: ["A", "B", "C", "D", "E", "F", "G", "H", "J"]
            }

        def get_shape_base(self, data, sketch):
            import FreeCAD
            import Part
            import Sketcher
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
            # rotation in order to avoid cut in projection
            m = piece.Base.Placement.Matrix
            m.rotateZ(math.radians(180))
            piece.Base.Placement.Matrix = m
            return piece

    class Pm(P):
        def get_dimensions_and_subtypes(self):
            return {
                1: ["A", "B", "C", "D", "E", "F", "G", "H", "b", "t"],
                2: ["A", "B", "C", "D", "E", "F", "G", "H", "b", "t"]
            }

        def get_shape_base(self, data, sketch):
            import FreeCAD
            import Part
            import Sketcher
            dimensions = data["dimensions"]
            familySubtype = data["familySubtype"]

            c = dimensions["C"] / 2
            g = dimensions["G"] / 2
            a = dimensions["A"] / 2
            e = dimensions["E"] / 2
            f = dimensions["F"] / 2
            b = dimensions["b"] / 2
            t = dimensions["t"]

            if 'alpha' not in dimensions:
                if familySubtype == '1':
                    dimensions["alpha"] = 120
                else:
                    dimensions["alpha"] = 90

            alpha = dimensions["alpha"] / 180 * math.pi

            beta = math.asin(g / e)
            xc = f
            z = c - e * math.cos(beta) + e * math.sin(beta)

            internal_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["H"] / 2), False)
            central_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["F"] / 2), False)
            external_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["A"] / 2), False)
            winding_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["E"] / 2), False)
            sketch.addConstraint(Sketcher.Constraint('Coincident', central_circle, 3, -1, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', external_circle, 3, -1, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', internal_circle, 3, -1, 1))
            sketch.addConstraint(Sketcher.Constraint('Coincident', winding_circle, 3, -1, 1))
            sketch.addConstraint(Sketcher.Constraint('Diameter', central_circle, dimensions["F"]))
            sketch.addConstraint(Sketcher.Constraint('Diameter', external_circle, dimensions["A"]))
            sketch.addConstraint(Sketcher.Constraint('Diameter', internal_circle, dimensions["H"]))
            sketch.addConstraint(Sketcher.Constraint('Diameter', winding_circle, dimensions["E"]))

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
                # sketch.addConstraint(Sketcher.Constraint('Symmetric', side_right_line, 1, side_right_line, 2, -1, 1)) 

                # sketch.addConstraint(Sketcher.Constraint('DistanceY', side_right_line, 1, -1, 1, -z))
                # sketch.addConstraint(Sketcher.Constraint('DistanceY', side_right_line, 2, -1, 1, z))

                sketch.addConstraint(Sketcher.Constraint('Vertical', side_right_line, 1, side_right_line, 2))
                sketch.addConstraint(Sketcher.Constraint('Vertical', side_left_line, 1, side_left_line, 2))
                sketch.addConstraint(Sketcher.Constraint('Coincident', side_top_right_line, 2, side_right_line, 1))
                sketch.addConstraint(Sketcher.Constraint('Coincident', side_bottom_right_line, 2, side_right_line, 2))
                sketch.addConstraint(Sketcher.Constraint('Coincident', side_top_left_line, 2, side_left_line, 1))
                sketch.addConstraint(Sketcher.Constraint('Coincident', side_bottom_left_line, 2, side_left_line, 2))

            sketch.trim(winding_circle, FreeCAD.Vector(e, 0, 0))
            sketch.addConstraint(Sketcher.Constraint('DistanceY', winding_circle, 1, -1, 1, -g))
            sketch.addConstraint(Sketcher.Constraint('DistanceY', winding_circle, 2, -1, 1, g))

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
            sketch.delGeometries([winding_circle])
            sketch.delGeometries([central_circle])

        def get_shape_extras(self, data, piece):
            # rotation in order to avoid cut in projection
            m = piece.Base.Placement.Matrix
            m.rotateZ(math.radians(180))
            piece.Base.Placement.Matrix = m
            return piece

    class E(IPiece):
        def get_negative_winding_window(self, dimensions):
            import FreeCAD
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
            import FreeCAD
            import Part
            import Sketcher
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

        def apply_machining(self, piece, machining, dimensions):
            import FreeCAD
            document = FreeCAD.ActiveDocument

            original_tool = document.addObject("Part::Box", "tool")
            original_tool.Length = dimensions["A"]
            x_coordinate = -dimensions["A"] / 2
            if machining['coordinates'][0] == 0:
                original_tool.Width = dimensions["F"]
                original_tool.Length = dimensions["C"]
                y_coordinate = -dimensions["F"] / 2
                x_coordinate = -dimensions["C"] / 2
                if 'K' in dimensions:
                    original_tool.Length = dimensions["C"] - dimensions['K']
                    x_coordinate += dimensions['K']
            else:
                original_tool.Width = dimensions["A"] / 2
                if machining['coordinates'][0] < 0:
                    y_coordinate = 0
                if machining['coordinates'][0] > 0:
                    y_coordinate = -dimensions["A"] / 2

            original_tool.Height = machining['length'] * 1000
            original_tool.Placement = FreeCAD.Placement(FreeCAD.Vector(x_coordinate, y_coordinate, (machining['coordinates'][1] - machining['length'] / 2) * 1000), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            if machining['coordinates'][0] == 0:
                tool = original_tool
            else:
                central_column_tool = document.addObject("Part::Box", "central_column_tool")
                central_column_width = dimensions["F"] * 1.001
                central_column_length = dimensions["C"] * 1.001
                if 'K' in dimensions:
                    central_column_length = (dimensions["C"] - dimensions['K'] * 2) * 1.001
                central_column_tool.Length = central_column_length
                central_column_tool.Width = central_column_width
                central_column_tool.Height = machining['length'] * 1000
                central_column_tool.Placement = FreeCAD.Placement(FreeCAD.Vector(-central_column_length / 2, -central_column_width / 2, (machining['coordinates'][1] - machining['length'] / 2) * 1000), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

                tool = document.addObject("Part::Cut", "machined_piece")
                tool.Base = original_tool
                tool.Tool = central_column_tool
                document.recompute()

            machined_piece = document.addObject("Part::Cut", "machined_piece")
            machined_piece.Base = piece
            machined_piece.Tool = tool
            document.recompute()

            return machined_piece

    class Er(E):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "G"]}

        def get_negative_winding_window(self, dimensions):
            import FreeCAD
            from BasicShapes import Shapes
            document = FreeCAD.ActiveDocument
            winding_window = Shapes.addTube(FreeCAD.ActiveDocument, "winding_window")
            winding_window.Height = dimensions["D"]
            winding_window.InnerRadius = dimensions["F"] / 2
            winding_window.OuterRadius = dimensions["E"] / 2
            winding_window.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(90, 0, 0))
            document.recompute()

            if 'G' in dimensions and dimensions["G"] > dimensions["F"]:
                if dimensions["C"] > dimensions["F"]:
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
                else:
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
                    winding_window_aux = document.addObject("Part::MultiFuse", "Fusion")
                    winding_window_aux.Shapes = [winding_window, lateral_top_cube, lateral_bottom_cube]

                document.recompute()
                winding_window = winding_window_aux

            return winding_window

        def get_shape_extras(self, data, piece):
            return piece

    class El(E):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "F2"]}

        def get_negative_winding_window(self, dimensions):
            import FreeCAD
            document = FreeCAD.ActiveDocument

            winding_window_cube = document.addObject("Part::Box", "winding_window_cube")
            winding_window_cube.Length = dimensions["C"]
            winding_window_cube.Width = dimensions["E"]
            winding_window_cube.Height = dimensions["D"]
            winding_window_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["E"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            central_column_cube = document.addObject("Part::Box", "central_column_cube")
            central_column_cube.Length = dimensions["F2"] - dimensions["F"]
            central_column_cube.Width = dimensions["F"]
            central_column_cube.Height = dimensions["D"]
            central_column_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-(dimensions["F2"] - dimensions["F"]) / 2, -dimensions["F"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            cylinder_left = document.addObject("Part::Cylinder", "cylinder_left")
            cylinder_left.Height = dimensions["D"]
            cylinder_left.Radius = dimensions["F"] / 2
            cylinder_left.Angle = 180
            cylinder_left.Placement = FreeCAD.Placement(FreeCAD.Vector(-(dimensions["F2"] - dimensions["F"]) / 2, 0, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(90, 0, 0))
            document.recompute()

            cylinder_right = document.addObject("Part::Cylinder", "cylinder_right")
            cylinder_right.Height = dimensions["D"]
            cylinder_right.Radius = dimensions["F"] / 2
            cylinder_right.Angle = 180
            cylinder_right.Placement = FreeCAD.Placement(FreeCAD.Vector((dimensions["F2"] - dimensions["F"]) / 2, 0, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(-90, 0, 0))
            document.recompute()

            central_column = document.addObject("Part::MultiFuse", "central_column")
            central_column.Shapes = [cylinder_left, central_column_cube, cylinder_right]

            document.recompute()

            negative_winding_window = document.addObject("Part::Cut", "negative_winding_window")
            negative_winding_window.Base = winding_window_cube
            negative_winding_window.Tool = central_column
            document.recompute()

            return negative_winding_window

        def get_shape_extras(self, data, piece):
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
            import FreeCAD
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
            import FreeCAD
            from BasicShapes import Shapes
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
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "G"]}

        def get_shape_extras(self, data, piece):
            import FreeCAD
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
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "T", "s"]}

        def get_shape_base(self, data, sketch):
            import FreeCAD
            import Part
            import Sketcher
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
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "G", "K"]}

        def get_negative_winding_window(self, dimensions):
            import FreeCAD
            from BasicShapes import Shapes
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
            if "G" in dimensions and dimensions['G'] > 0:
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

        def apply_machining(self, piece, machining, dimensions):
            import FreeCAD
            document = FreeCAD.ActiveDocument

            original_tool = document.addObject("Part::Box", "tool")
            original_tool.Length = dimensions["C"]
            x_coordinate = -dimensions["C"] + dimensions["K"] 

            if machining['coordinates'][0] == 0 and machining['coordinates'][2] == 0:
                original_tool.Width = dimensions["F"]
                original_tool.Length = dimensions["F"]
                x_coordinate = -dimensions["F"] / 2
                y_coordinate = -dimensions["F"] / 2
            elif machining['coordinates'][0] != 0 and machining['coordinates'][2] == 0:
                original_tool.Width = dimensions["A"] / 2
                if machining['coordinates'][0] < 0:
                    y_coordinate = 0
                if machining['coordinates'][0] > 0:
                    y_coordinate = -dimensions["A"] / 2
            else:
                original_tool.Width = dimensions["A"]
                y_coordinate = -dimensions["A"] / 2

            original_tool.Height = machining['length'] * 1000
            original_tool.Placement = FreeCAD.Placement(FreeCAD.Vector(x_coordinate, y_coordinate, (machining['coordinates'][1] - machining['length'] / 2) * 1000), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            if machining['coordinates'][0] == 0 and machining['coordinates'][2] == 0:
                tool = original_tool
            else:
                central_column_tool = document.addObject("Part::Cylinder", "central_column_tool")
                central_column_width = dimensions["F"] * 1.001
                central_column_tool.Radius = central_column_width / 2
                central_column_tool.Height = machining['length'] * 1000
                central_column_tool.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, (machining['coordinates'][1] - machining['length'] / 2) * 1000), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

                tool = document.addObject("Part::Cut", "machined_piece_with_central_column")
                tool.Base = original_tool
                tool.Tool = central_column_tool
                document.recompute()

            machined_piece = document.addObject("Part::Cut", "machined_piece_with_lateral_gap")
            machined_piece.Base = piece
            machined_piece.Tool = tool
            document.recompute()

            return machined_piece

        def get_shape_extras(self, data, piece):
            import FreeCAD
            # movement to center column
            dimensions = data["dimensions"]

            piece.Placement.move(FreeCAD.Vector(-dimensions["C"] / 2 + dimensions["K"],
                                                0,
                                                0))
            return piece

    class Epx(E):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E", "F", "G", "K"]}

        def get_negative_winding_window(self, dimensions):
            import FreeCAD
            document = FreeCAD.ActiveDocument

            if dimensions["K"] >= dimensions["F"] / 2:
                cylinder_left = document.addObject("Part::Cylinder", "cylinder_left")
                cylinder_left.Height = dimensions["D"]
                cylinder_left.Radius = dimensions["F"] / 2
                cylinder_left.Angle = 180
                cylinder_left.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"], 0, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(90, 0, 0))
                document.recompute()

                if dimensions["K"] != dimensions["F"] / 2:
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
            else:
                cylinder_left = document.addObject("Part::Cylinder", "cylinder_left")
                cylinder_left.Height = dimensions["D"]
                cylinder_left.Radius = dimensions["K"]
                cylinder_left.Angle = 180
                cylinder_left.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"], -(dimensions["F"] / 2 - dimensions["K"]), dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(180, 0, 0))
                document.recompute()

                central_column_cube = document.addObject("Part::Box", "central_column_cube")
                central_column_cube.Length = dimensions["K"] * 2
                central_column_cube.Width = dimensions["F"] - dimensions["K"] * 2
                central_column_cube.Height = dimensions["D"]
                central_column_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"] * 2, -(dimensions["F"] / 2 - dimensions["K"]), dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
                document.recompute()

                cylinder_right = document.addObject("Part::Cylinder", "cylinder_right")
                cylinder_right.Height = dimensions["D"]
                cylinder_right.Radius = dimensions["K"]
                cylinder_right.Angle = 180 
                cylinder_right.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"], (dimensions["F"] / 2 - dimensions["K"]), dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(0, 0, 0))
                document.recompute()

            central_column = document.addObject("Part::MultiFuse", "central_column")
            if dimensions["K"] != dimensions["F"] / 2:
                central_column.Shapes = [cylinder_left, central_column_cube, cylinder_right]
            else:
                central_column.Shapes = [cylinder_left, cylinder_right]

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
            if dimensions["K"] >= dimensions["F"] / 2:
                lateral_right_cube.Length = dimensions["C"] / 2
            else:
                lateral_right_cube.Length = dimensions["K"]
            lateral_right_cube.Width = dimensions["E"]
            lateral_right_cube.Height = dimensions["D"]
            lateral_right_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(dimensions["C"] / 2 - dimensions["K"], -dimensions["E"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

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

        def apply_machining(self, piece, machining, dimensions):
            import FreeCAD
            document = FreeCAD.ActiveDocument

            original_tool = document.addObject("Part::Box", "tool")
            original_tool.Length = dimensions["A"]
            x_coordinate = -dimensions["A"] / 2
            if machining['coordinates'][0] == 0 and machining['coordinates'][2] == 0:
                original_tool.Width = dimensions["F"]
                original_tool.Length = dimensions["F"] / 2 + dimensions["K"]
                x_coordinate = (dimensions["C"] / 2 - (dimensions["F"] / 2 + dimensions["K"]))
                y_coordinate = -dimensions["F"] / 2
            elif machining['coordinates'][0] != 0 and machining['coordinates'][2] == 0:
                original_tool.Width = dimensions["A"] / 2
                if machining['coordinates'][0] < 0:
                    y_coordinate = 0
                if machining['coordinates'][0] > 0:
                    y_coordinate = -dimensions["A"] / 2
            else:
                original_tool.Width = dimensions["A"]
                y_coordinate = -dimensions["A"] / 2

            original_tool.Height = machining['length'] * 1000
            original_tool.Placement = FreeCAD.Placement(FreeCAD.Vector(x_coordinate, y_coordinate, (machining['coordinates'][1] - machining['length'] / 2) * 1000), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            if machining['coordinates'][0] == 0 and machining['coordinates'][2] == 0:
                tool = original_tool
            else:
                central_column_tool = document.addObject("Part::Box", "central_column_tool")
                central_column_length = (dimensions["F"] / 2 + dimensions["K"]) * 1.01
                central_column_width = dimensions["F"] * 1.01
                central_column_tool.Length = central_column_length
                central_column_tool.Width = central_column_width
                central_column_tool.Height = machining['length'] * 1000
                central_column_tool.Placement = FreeCAD.Placement(FreeCAD.Vector((dimensions["C"] / 2 * 1.01 - central_column_length), -central_column_width / 2, (machining['coordinates'][1] - machining['length'] / 2) * 1000), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

                tool = document.addObject("Part::Cut", "machined_piece")
                tool.Base = original_tool
                tool.Tool = central_column_tool
                document.recompute()

            machined_piece = document.addObject("Part::Cut", "machined_piece")
            machined_piece.Base = piece
            machined_piece.Tool = tool
            document.recompute()

            return machined_piece

    class Efd(E):
        def get_dimensions_and_subtypes(self):
            return {
                1: ["A", "B", "C", "D", "E", "F", "F2", "K", "q"],
                2: ["A", "B", "C", "D", "E", "F", "F2", "K", "q"]
            }

        def get_shape_base(self, data, sketch):
            import FreeCAD
            import Part
            import Sketcher
            dimensions = data["dimensions"]

            c = dimensions["C"] / 2
            a = dimensions["A"] / 2
            e = dimensions["E"] / 2
            f1 = dimensions["F"] / 2
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
            import FreeCAD
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
            import FreeCAD
            dimensions = data["dimensions"]
            document = FreeCAD.ActiveDocument
            central_column_cube = document.addObject("Part::Box", "central_column_cube")
            central_column_cube.Length = dimensions["F2"]
            central_column_cube.Width = dimensions["F"]
            central_column_cube.Height = dimensions["B"]
            central_column_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["F2"] / 2, -dimensions["F"] / 2, 0), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
            top_right_vertex = self.edges_in_boundbox(part=central_column_cube,
                                                      xmin=0,
                                                      xmax=dimensions["F2"] / 2,
                                                      ymin=0,
                                                      ymax=dimensions["F"] / 2,
                                                      zmin=0,
                                                      zmax=dimensions["B"])[0]
            top_left_vertex = self.edges_in_boundbox(part=central_column_cube,
                                                     xmin=-dimensions["F2"] / 2,
                                                     xmax=0,
                                                     ymin=0,
                                                     ymax=dimensions["F"] / 2,
                                                     zmin=0,
                                                     zmax=dimensions["B"])[0]
            bottom_right_vertex = self.edges_in_boundbox(part=central_column_cube,
                                                         xmin=0,
                                                         xmax=dimensions["F2"] / 2,
                                                         ymin=-dimensions["F"] / 2,
                                                         ymax=0,
                                                         zmin=0,
                                                         zmax=dimensions["B"])[0]
            bottom_left_vertex = self.edges_in_boundbox(part=central_column_cube,
                                                        xmin=-dimensions["F2"] / 2,
                                                        xmax=0,
                                                        ymin=-dimensions["F"] / 2,
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
            central_column_cube.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2 + dimensions["K"], -dimensions["F"] / 2, 0), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
            document.recompute()

            piece_with_column = document.addObject("Part::MultiFuse", "Fusion")
            piece_with_column.Shapes = [piece, chamfer]
            document.recompute()
            return piece_with_column

    class U(E):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C", "D", "E"]}

        def get_negative_winding_window(self, dimensions):
            import FreeCAD
            document = FreeCAD.ActiveDocument
            central_hole = document.addObject("Part::Box", "central_hole")
            central_hole.Length = dimensions["C"]
            central_hole.Width = dimensions["E"]
            central_hole.Height = dimensions["D"]
            central_hole.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["E"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
            return central_hole

        def apply_machining(self, piece, machining, dimensions):
            import FreeCAD
            document = FreeCAD.ActiveDocument

            tool = document.addObject("Part::Box", "tool")
            winding_column_width = (dimensions["A"] - dimensions["E"]) / 2
            tool.Length = dimensions["A"]
            tool.Width = winding_column_width
            x_coordinate = -dimensions["A"] / 2
            if machining['coordinates'][0] == 0:
                y_coordinate = -winding_column_width / 2
            else:
                y_coordinate = winding_column_width / 2 + dimensions["E"]

            tool.Height = machining['length'] * 1000
            tool.Placement = FreeCAD.Placement(FreeCAD.Vector(x_coordinate, y_coordinate, (machining['coordinates'][1] - machining['length'] / 2) * 1000), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            machined_piece = document.addObject("Part::Cut", "machined_piece")
            machined_piece.Base = piece
            machined_piece.Tool = tool
            document.recompute()

            return machined_piece

        def get_shape_extras(self, data, piece):
            import FreeCAD
            dimensions = data["dimensions"]
            piece.Placement.move(FreeCAD.Vector(0,
                                                -(dimensions['E'] / 2 + (dimensions['A'] - dimensions['E']) / 4),
                                                0))
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
            import FreeCAD
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

            columns.Placement.move(FreeCAD.Vector(0,
                                   -dimensions['A'] / 2 + top_diameter / 2,
                                   0))
            return columns

        def get_shape_base(self, data, sketch):
            import FreeCAD
            import Part
            import Sketcher
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
            import FreeCAD
            document = FreeCAD.ActiveDocument
            central_hole = document.addObject("Part::Box", "central_hole")
            central_hole.Length = dimensions["C"]
            central_hole.Width = dimensions["A"]
            central_hole.Height = dimensions["D"]
            central_hole.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["A"] / 2, dimensions["B"] - dimensions["D"]), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
            return central_hole

        def add_dimensions_and_export_view(self, data, original_dimensions, view, project_name, margin, colors, save_files, piece):
            import FreeCAD
            import TechDraw

            def calculate_total_dimensions():
                if view.Name == "TopView":
                    base_width = data['dimensions']['A'] + margin
                    base_width += horizontal_offset
                    if 'C' in dimensions:
                        base_width += increment

                    base_height = data['dimensions']['C'] + margin

                    base_height += vertical_offset
                    if 'A' in dimensions:
                        base_height += increment
                    if 'E' in dimensions:
                        base_height += increment
                    if 'F' in dimensions:
                        base_height += increment
                    if 'G' in dimensions and dimensions['G'] > 0:
                        base_height += increment
                    if 'H' in dimensions and dimensions['H'] > 0:
                        base_height += increment

                if view.Name == "FrontView":
                    base_width = data['dimensions']['A'] + margin
                    base_width += horizontal_offset
                    if 'B' in dimensions:
                        base_width += increment
                    if 'D' in dimensions:
                        base_width += increment

                    base_height = data['dimensions']['B'] + margin * 2

                return base_width, base_height

            def create_dimension(starting_coordinates, ending_coordinates, dimension_type, dimension_label, label_offset=0, label_alignment=0):
                dimension_svg = ""

                if dimension_type == "DistanceY":
                    main_line_start = [starting_coordinates[0] + label_offset, starting_coordinates[1]]
                    main_line_end = [ending_coordinates[0] + label_offset, ending_coordinates[1]]
                    left_aux_line_start = [starting_coordinates[0], starting_coordinates[1]]
                    left_aux_line_end = [starting_coordinates[0] + label_offset, starting_coordinates[1]]
                    right_aux_line_start = [ending_coordinates[0], ending_coordinates[1]]
                    right_aux_line_end = [ending_coordinates[0] + label_offset, ending_coordinates[1]]

                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value + ending_coordinates[0] + label_offset - dimension_font_size / 4},{1000 - view.Y.Value + label_alignment})" stroke-linecap="square" stroke-linejoin="bevel">
                                             <text x="0" y="0" text-anchor="middle" fill-opacity="1" font-size="{dimension_font_size}" font-style="normal" fill="{colors['dimension_color']}" font-family="osifont" stroke="none" xml:space="preserve" font-weight="400" transform="rotate(-90)">{dimension_label}</text>
                                            </g>\n""".replace("                                    ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M{main_line_start[0]},{main_line_start[1]} L{main_line_end[0]},{main_line_end[1]} M{left_aux_line_start[0]},{left_aux_line_start[1]} L{left_aux_line_end[0]},{left_aux_line_end[1]} M{right_aux_line_start[0]},{right_aux_line_start[1]} L{right_aux_line_end[0]},{right_aux_line_end[1]}"/>
                                            </g>\n""".replace("                                     ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{ending_coordinates[0] + label_offset},{ending_coordinates[1]})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L6,-15 L-6,-15 L0,0"/>
                                             </g>
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{starting_coordinates[0] + label_offset},{starting_coordinates[1]})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L-6,15 L6,15 L0,0"/>
                                             </g>
                                            </g>\n""".replace("                                     ", "")
                elif dimension_type == "DistanceX":
                    main_line_start = [starting_coordinates[0], starting_coordinates[1] + label_offset]
                    main_line_end = [ending_coordinates[0], ending_coordinates[1] + label_offset]
                    left_aux_line_start = [starting_coordinates[0], starting_coordinates[1]]
                    left_aux_line_end = [starting_coordinates[0], starting_coordinates[1] + label_offset]
                    right_aux_line_start = [ending_coordinates[0], ending_coordinates[1]]
                    right_aux_line_end = [ending_coordinates[0], ending_coordinates[1] + label_offset]

                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value + label_alignment},{1000 - view.Y.Value})" stroke-linecap="square" stroke-linejoin="bevel">
                                             <text x="0" y="{ending_coordinates[1] + label_offset - dimension_font_size / 4}" text-anchor="middle" fill-opacity="1" font-size="{dimension_font_size}" font-style="normal" fill="{colors['dimension_color']}" font-family="osifont" stroke="none" xml:space="preserve" font-weight="400">{dimension_label}</text>
                                            </g>\n""".replace("                                    ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M{main_line_start[0]},{main_line_start[1]} L{main_line_end[0]},{main_line_end[1]} M{left_aux_line_start[0]},{left_aux_line_start[1]} L{left_aux_line_end[0]},{left_aux_line_end[1]} M{right_aux_line_start[0]},{right_aux_line_start[1]} L{right_aux_line_end[0]},{right_aux_line_end[1]}"/>
                                            </g>\n""".replace("                                     ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{ending_coordinates[0]},{ending_coordinates[1] + label_offset})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L-15,-6 L-15,6 L0,0"/>
                                             </g>
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{starting_coordinates[0]},{starting_coordinates[1] + label_offset})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L15,6 L15,-6 L0,0"/>
                                             </g>
                                            </g>\n""".replace("                                     ", "")
                return dimension_svg

            projection_line_thickness = 4
            dimension_line_thickness = 1
            dimension_font_size = 30
            horizontal_offset = 75
            vertical_offset = 75
            increment = 50
            dimensions = data["dimensions"]
            shape_semi_height = dimensions['C'] / 2
            base_width, base_height = calculate_total_dimensions()
            head = f"""<svg xmlns:dc="http://purl.org/dc/elements/1.1/" baseProfile="tiny" xmlns:svg="http://www.w3.org/2000/svg" version="1.2" width="100%" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {base_width} {base_height}" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" height="100%" xmlns:freecad="http://www.freecadweb.org/wiki/index.php?title=Svg_Namespace" xmlns:cc="http://creativecommons.org/ns#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
                         <title>FreeCAD SVG Export</title>
                         <desc>Drawing page: {view.Name} exported from FreeCAD document: {project_name}</desc>
                         <defs/>
                         <g id="{view.Name}" inkscape:label="TechDraw" inkscape:groupmode="layer">
                          <g id="DrawingContent" fill="none" stroke="black" stroke-width="1" fill-rule="evenodd" stroke-linecap="square" stroke-linejoin="bevel">""".replace("                    ", "")
            projetion_head = f"""    <g fill-opacity="1" font-size="29.1042" font-style="normal" fill="#ffffff" font-family="MS Shell Dlg 2" stroke="none" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})">\n"""
            projetion_tail = """   </g>\n"""
            tail = """</g>
                     </g>
                    </svg>
                    """.replace("                ", "")
            svgFile_data = ""
            svgFile_data += head
            svgFile_data += projetion_head
            if 'F' not in dimensions:
                dimensions['F'] = dimensions['C']

            if view.Name == "TopView":
                m = piece.Placement.Matrix
                m.rotateZ(math.radians(90))
                piece.Placement.Matrix = m
                piece.Placement.move(FreeCAD.Vector(-dimensions["A"] / 2 + dimensions["F"] / 2, 0, 0))
                svgFile_data += TechDraw.projectToSVG(piece.Shape, FreeCAD.Vector(0., 0., 1.)).replace("><", ">\n<").replace("<", "    <").replace("stroke-width=\"0.7\"", f"stroke-width=\"{projection_line_thickness}\"").replace("#000000", colors['projection_color']).replace("rgb(0, 0, 0)", colors['projection_color'])
            else:
                m = piece.Placement.Matrix
                m.rotateY(math.radians(90))
                piece.Placement.Matrix = m
                piece.Placement.move(FreeCAD.Vector(-dimensions["B"] / 2, 0, 0))
                svgFile_data += TechDraw.projectToSVG(piece.Shape, FreeCAD.Vector(0., 1., 0.)).replace("><", ">\n<").replace("<", "    <").replace("stroke-width=\"0.7\"", f"stroke-width=\"{projection_line_thickness}\"").replace("#000000", colors['projection_color']).replace("rgb(0, 0, 0)", colors['projection_color'])

            svgFile_data += projetion_tail
            if 'F' not in original_dimensions:
                original_dimensions['F'] = original_dimensions['C']

            if 'E' not in original_dimensions:
                original_dimensions['E'] = original_dimensions['A'] - original_dimensions['F'] - original_dimensions['H']

            if 'E' not in dimensions:
                dimensions['E'] = dimensions['A'] - dimensions['F'] - dimensions['H']

            if view.Name == "TopView":
                if "C" in dimensions and dimensions["C"] > 0:
                    svgFile_data += create_dimension(starting_coordinates=[dimensions['A'] / 2, -dimensions['C'] / 2],
                                                     ending_coordinates=[dimensions['A'] / 2, dimensions['C'] / 2],
                                                     dimension_type="DistanceY",
                                                     dimension_label=f"C: {round(original_dimensions['C'], 2)} mm",
                                                     label_offset=horizontal_offset)
                    horizontal_offset += increment

                if "G" in dimensions and dimensions['G'] > 0:
                    svgFile_data += create_dimension(starting_coordinates=[-dimensions['A'] / 2 + dimensions['F'] / 2 - dimensions['G'] / 2, 0],
                                                     ending_coordinates=[-dimensions['A'] / 2 + dimensions['F'] / 2 + dimensions['G'] / 2, 0],
                                                     dimension_type="DistanceX",
                                                     dimension_label=f"G: {round(original_dimensions['G'], 2)} mm",
                                                     label_offset=vertical_offset + shape_semi_height,
                                                     label_alignment=-dimensions['A'] / 2 + dimensions['F'] / 2)
                    svgFile_data += create_dimension(starting_coordinates=[dimensions['A'] / 2 - dimensions['F'] / 2 + dimensions['G'] / 2, 0],
                                                     ending_coordinates=[dimensions['A'] / 2 - dimensions['F'] / 2 - dimensions['G'] / 2, 0],
                                                     dimension_type="DistanceX",
                                                     dimension_label=f"G: {round(original_dimensions['G'], 2)} mm",
                                                     label_offset=vertical_offset + shape_semi_height,
                                                     label_alignment=dimensions['A'] / 2 - dimensions['F'] / 2)
                vertical_offset += increment
                if "F" in dimensions and dimensions["F"] > 0:
                    svgFile_data += create_dimension(starting_coordinates=[-dimensions['A'] / 2, 0],
                                                     ending_coordinates=[-dimensions['A'] / 2 + dimensions['F'], 0],
                                                     dimension_type="DistanceX",
                                                     dimension_label=f"F: {round(original_dimensions['F'], 2)} mm",
                                                     label_offset=vertical_offset + shape_semi_height,
                                                     label_alignment=-dimensions['A'] / 2 + dimensions['F'] / 2)
                if "H" in dimensions and dimensions["H"] > 0:
                    svgFile_data += create_dimension(starting_coordinates=[dimensions['A'] / 2 - dimensions['H'], 0],
                                                     ending_coordinates=[dimensions['A'] / 2, 0],
                                                     dimension_type="DistanceX",
                                                     dimension_label=f"H: {round(original_dimensions['H'], 2)} mm",
                                                     label_offset=vertical_offset + shape_semi_height,
                                                     label_alignment=dimensions['A'] / 2 - dimensions['H'] / 2)

                if 'F' in dimensions:
                    left_column_diameter = dimensions['F']
                else:
                    left_column_diameter = dimensions['C']

                if 'H' in dimensions:
                    right_column_diameter = dimensions['H']
                else:
                    right_column_diameter = dimensions['C']

                if 'E' not in original_dimensions:
                    original_dimensions['E'] = original_dimensions['A'] - original_dimensions['F'] - original_dimensions['']

                svgFile_data += create_dimension(starting_coordinates=[-dimensions['A'] / 2 + left_column_diameter, 0],
                                                 ending_coordinates=[dimensions['A'] / 2 - right_column_diameter, 0],
                                                 dimension_type="DistanceX",
                                                 dimension_label=f"E: Min {round(original_dimensions['E'], 2)} mm",
                                                 label_offset=vertical_offset + shape_semi_height,
                                                 label_alignment=-dimensions['A'] / 2 + left_column_diameter + (dimensions['A'] - left_column_diameter - right_column_diameter) / 2)
                vertical_offset += increment
                svgFile_data += create_dimension(starting_coordinates=[-dimensions['A'] / 2, 0],
                                                 ending_coordinates=[dimensions['A'] / 2, 0],
                                                 dimension_type="DistanceX",
                                                 dimension_label=f"A: {round(original_dimensions['A'], 2)} mm",
                                                 label_offset=vertical_offset + shape_semi_height)
                vertical_offset += increment
            else:
                if 'H' in dimensions:
                    starting_point_for_d = dimensions['H'] / 2
                else:
                    starting_point_for_d = dimensions['E'] / 2
                svgFile_data += create_dimension(starting_coordinates=[starting_point_for_d, -dimensions['B'] / 2],
                                                 ending_coordinates=[starting_point_for_d, -dimensions['B'] / 2 + dimensions['D']],
                                                 dimension_type="DistanceY",
                                                 dimension_label=f"D: {round(original_dimensions['D'], 2)} mm",
                                                 label_offset=horizontal_offset + (dimensions['A'] / 2 - starting_point_for_d),
                                                 label_alignment=-dimensions['B'] / 2 + dimensions['D'] / 2)
                horizontal_offset += increment
                svgFile_data += create_dimension(starting_coordinates=[dimensions['A'] / 2, -dimensions['B'] / 2],
                                                 ending_coordinates=[dimensions['A'] / 2, dimensions['B'] / 2],
                                                 dimension_type="DistanceY",
                                                 dimension_label=f"B: {round(original_dimensions['B'], 2)} mm",
                                                 label_offset=horizontal_offset)

            svgFile_data += tail
            
            if save_files:
                svgFile = open(f"{self.output_path}/{project_name}_{view.Name}.svg", "w")
                svgFile.write(svgFile_data)
                svgFile.close() 
            return svgFile_data

        def apply_machining(self, piece, machining, dimensions):
            document = FreeCAD.ActiveDocument

            tool = document.addObject("Part::Box", "tool")
            if 'F' in dimensions and dimensions['F'] > 0:
                winding_column_width = dimensions["F"]
            else:
                winding_column_width = dimensions["C"]
            tool.Length = dimensions["A"]
            tool.Width = winding_column_width
            x_coordinate = -dimensions["A"] / 2
            if machining['coordinates'][0] == 0:
                tool.Width = winding_column_width
                y_coordinate = -winding_column_width / 2
            else:
                tool.Width = dimensions["A"]
                y_coordinate = winding_column_width / 2

            tool.Height = machining['length'] * 1000
            tool.Placement = FreeCAD.Placement(FreeCAD.Vector(x_coordinate, y_coordinate, (machining['coordinates'][1] - machining['length'] / 2) * 1000), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            machined_piece = document.addObject("Part::Cut", "machined_piece")
            machined_piece.Base = piece
            machined_piece.Tool = tool
            document.recompute()

            return machined_piece

    class Ut(IPiece):
        def get_dimensions_and_subtypes(self):
            return {
                1: ["A", "B", "C", "D", "E", "F"],
            }

        def get_shape_extras(self, data, piece):
            import FreeCAD
            dimensions = data["dimensions"]
            document = FreeCAD.ActiveDocument

            top_column = document.addObject("Part::Box", "top_column")
            top_column.Length = dimensions["C"]
            top_column.Width = dimensions["F"]
            top_column.Height = dimensions["D"]
            top_column.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["A"] / 2, (dimensions["B"] - dimensions["D"]) / 2), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
        
            bottom_column_width = dimensions["A"] - dimensions["E"] - dimensions["F"]
            bottom_column = document.addObject("Part::Box", "bottom_column")
            bottom_column.Length = dimensions["C"]
            bottom_column.Width = bottom_column_width
            bottom_column.Height = dimensions["D"]
            bottom_column.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, dimensions["A"] / 2 - bottom_column_width, (dimensions["B"] - dimensions["D"]) / 2), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            columns = document.addObject("Part::MultiFuse", "columns")
            columns.Shapes = [piece, bottom_column, top_column]
            document.recompute()

            columns.Placement.move(FreeCAD.Vector(0, 0, dimensions["B"] / 2))

            return columns

        def get_shape_base(self, data, sketch):
            import FreeCAD
            import Part
            import Sketcher
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

        def get_negative_winding_window(self, dimensions):
            import FreeCAD
            document = FreeCAD.ActiveDocument
            central_hole = document.addObject("Part::Box", "central_hole")
            central_hole.Length = dimensions["C"]
            central_hole.Width = dimensions["A"]
            central_hole.Height = dimensions["D"]
            central_hole.Placement = FreeCAD.Placement(FreeCAD.Vector(-dimensions["C"] / 2, -dimensions["A"] / 2, (dimensions["B"] - dimensions["D"]) / 2), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))
            return central_hole

        def get_top_projection(self, data, piece, margin):
            import FreeCAD

            dimensions = data["dimensions"]

            document = FreeCAD.ActiveDocument
            page = document.addObject('TechDraw::DrawPage', 'Top Page')
            template = document.addObject('TechDraw::DrawSVGTemplate', 'Template')
            page.Template = template
            document.recompute()

            aux_view = document.addObject('TechDraw::DrawViewPart', 'AuxView')
            page.addView(aux_view)
            aux_view.Source = [piece]
            aux_view.Direction = FreeCAD.Vector(1.00, 0.00, 0.00)
            aux_view.XDirection = FreeCAD.Vector(0.00, 1.00, 0.00)
            aux_view.X = margin + dimensions['A'] / 2

            semi_height = dimensions['B'] / 2

            top_view = document.addObject('TechDraw::DrawViewSection', 'TopView')
            page.addView(top_view)
            top_view.BaseView = document.getObject('AuxView')
            top_view.Source = document.getObject('AuxView').Source
            top_view.ScaleType = 0
            top_view.SectionDirection = 'Down'
            top_view.SectionNormal = FreeCAD.Vector(0.000, 0.000, 1.000)
            top_view.SectionOrigin = FreeCAD.Vector(0, 0.000, semi_height)
            top_view.SectionSymbol = ''
            top_view.Label = 'Section  - '
            top_view.Scale = 1.000000
            top_view.ScaleType = 0
            top_view.Rotation = 0
            top_view.Direction = FreeCAD.Vector(0.00, 0.00, 1.00)
            top_view.XDirection = FreeCAD.Vector(0.00, 1.00, 0.00)
            top_view.X = margin + dimensions['A'] / 2

            base_height = data['dimensions']['C'] + margin

            top_view.Y = 1000 - base_height / 2

            top_view.Scale = 1
            document.recompute()
            return top_view

        def get_front_projection(self, data, piece, margin):
            import FreeCAD

            dimensions = data["dimensions"]

            document = FreeCAD.ActiveDocument
            page = document.addObject('TechDraw::DrawPage', 'Top Page')
            template = document.addObject('TechDraw::DrawSVGTemplate', 'Template')
            page.Template = template
            document.recompute()

            front_view = document.addObject('TechDraw::DrawViewPart', 'FrontView')
            page.addView(front_view)
            front_view.Source = [piece]
            front_view.Direction = FreeCAD.Vector(1.00, 0.00, 0.00)
            front_view.XDirection = FreeCAD.Vector(0.00, 1.00, 0.00)
            front_view.X = margin + dimensions['A'] / 2
            front_view.Y = 1000 - margin - dimensions['B'] / 2

            document.recompute()

            return front_view

        def add_dimensions_and_export_view(self, data, original_dimensions, view, project_name, margin, colors, save_files, piece):
            import FreeCAD
            import TechDraw

            def calculate_total_dimensions():
                if view.Name == "TopView":
                    base_width = data['dimensions']['A'] + margin
                    base_width += horizontal_offset
                    if 'C' in dimensions:
                        base_width += increment

                    base_height = data['dimensions']['C'] + margin

                    base_height += vertical_offset
                    if 'A' in dimensions:
                        base_height += increment
                    if 'E' in dimensions:
                        base_height += increment
                    if 'F' in dimensions:
                        base_height += increment

                if view.Name == "FrontView":
                    base_width = data['dimensions']['A'] + margin
                    base_width += horizontal_offset
                    if 'B' in dimensions:
                        base_width += increment
                    if 'D' in dimensions:
                        base_width += increment

                    base_height = data['dimensions']['B'] + margin * 2

                return base_width, base_height

            def create_dimension(starting_coordinates, ending_coordinates, dimension_type, dimension_label, label_offset=0, label_alignment=0):
                dimension_svg = ""

                if dimension_type == "DistanceY":
                    main_line_start = [starting_coordinates[0] + label_offset, starting_coordinates[1]]
                    main_line_end = [ending_coordinates[0] + label_offset, ending_coordinates[1]]
                    left_aux_line_start = [starting_coordinates[0], starting_coordinates[1]]
                    left_aux_line_end = [starting_coordinates[0] + label_offset, starting_coordinates[1]]
                    right_aux_line_start = [ending_coordinates[0], ending_coordinates[1]]
                    right_aux_line_end = [ending_coordinates[0] + label_offset, ending_coordinates[1]]

                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value + ending_coordinates[0] + label_offset - dimension_font_size / 4},{1000 - view.Y.Value + label_alignment})" stroke-linecap="square" stroke-linejoin="bevel">
                                             <text x="0" y="0" text-anchor="middle" fill-opacity="1" font-size="{dimension_font_size}" font-style="normal" fill="{colors['dimension_color']}" font-family="osifont" stroke="none" xml:space="preserve" font-weight="400" transform="rotate(-90)">{dimension_label}</text>
                                            </g>\n""".replace("                                    ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M{main_line_start[0]},{main_line_start[1]} L{main_line_end[0]},{main_line_end[1]} M{left_aux_line_start[0]},{left_aux_line_start[1]} L{left_aux_line_end[0]},{left_aux_line_end[1]} M{right_aux_line_start[0]},{right_aux_line_start[1]} L{right_aux_line_end[0]},{right_aux_line_end[1]}"/>
                                            </g>\n""".replace("                                     ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{ending_coordinates[0] + label_offset},{ending_coordinates[1]})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L6,-15 L-6,-15 L0,0"/>
                                             </g>
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{starting_coordinates[0] + label_offset},{starting_coordinates[1]})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L-6,15 L6,15 L0,0"/>
                                             </g>
                                            </g>\n""".replace("                                     ", "")
                elif dimension_type == "DistanceX":
                    main_line_start = [starting_coordinates[0], starting_coordinates[1] + label_offset]
                    main_line_end = [ending_coordinates[0], ending_coordinates[1] + label_offset]
                    left_aux_line_start = [starting_coordinates[0], starting_coordinates[1]]
                    left_aux_line_end = [starting_coordinates[0], starting_coordinates[1] + label_offset]
                    right_aux_line_start = [ending_coordinates[0], ending_coordinates[1]]
                    right_aux_line_end = [ending_coordinates[0], ending_coordinates[1] + label_offset]

                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value + label_alignment},{1000 - view.Y.Value})" stroke-linecap="square" stroke-linejoin="bevel">
                                             <text x="0" y="{ending_coordinates[1] + label_offset - dimension_font_size / 4}" text-anchor="middle" fill-opacity="1" font-size="{dimension_font_size}" font-style="normal" fill="{colors['dimension_color']}" font-family="osifont" stroke="none" xml:space="preserve" font-weight="400">{dimension_label}</text>
                                            </g>\n""".replace("                                    ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M{main_line_start[0]},{main_line_start[1]} L{main_line_end[0]},{main_line_end[1]} M{left_aux_line_start[0]},{left_aux_line_start[1]} L{left_aux_line_end[0]},{left_aux_line_end[1]} M{right_aux_line_start[0]},{right_aux_line_start[1]} L{right_aux_line_end[0]},{right_aux_line_end[1]}"/>
                                            </g>\n""".replace("                                     ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{ending_coordinates[0]},{ending_coordinates[1] + label_offset})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L-15,-6 L-15,6 L0,0"/>
                                             </g>
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{starting_coordinates[0]},{starting_coordinates[1] + label_offset})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L15,6 L15,-6 L0,0"/>
                                             </g>
                                            </g>\n""".replace("                                     ", "")
                return dimension_svg

            projection_line_thickness = 4
            dimension_line_thickness = 1
            dimension_font_size = 30
            horizontal_offset = 75
            vertical_offset = 75
            increment = 50
            dimensions = data["dimensions"]
            shape_semi_height = dimensions['C'] / 2
            base_width, base_height = calculate_total_dimensions()
            head = f"""<svg xmlns:dc="http://purl.org/dc/elements/1.1/" baseProfile="tiny" xmlns:svg="http://www.w3.org/2000/svg" version="1.2" width="100%" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {base_width} {base_height}" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" height="100%" xmlns:freecad="http://www.freecadweb.org/wiki/index.php?title=Svg_Namespace" xmlns:cc="http://creativecommons.org/ns#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
                         <title>FreeCAD SVG Export</title>
                         <desc>Drawing page: {view.Name} exported from FreeCAD document: {project_name}</desc>
                         <defs/>
                         <g id="{view.Name}" inkscape:label="TechDraw" inkscape:groupmode="layer">
                          <g id="DrawingContent" fill="none" stroke="black" stroke-width="1" fill-rule="evenodd" stroke-linecap="square" stroke-linejoin="bevel">""".replace("                    ", "")
            projetion_head = f"""    <g fill-opacity="1" font-size="29.1042" font-style="normal" fill="#ffffff" font-family="MS Shell Dlg 2" stroke="none" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})">\n"""
            projetion_tail = """   </g>\n"""
            tail = """</g>
                     </g>
                    </svg>
                    """.replace("                ", "")
            svgFile_data = ""
            svgFile_data += head
            svgFile_data += projetion_head

            if view.Name == "TopView":
                m = piece.Placement.Matrix
                m.rotateZ(math.radians(90))
                piece.Placement.Matrix = m
                svgFile_data += TechDraw.projectToSVG(piece.Shape, FreeCAD.Vector(0., 0., 1.)).replace("><", ">\n<").replace("<", "    <").replace("stroke-width=\"0.7\"", f"stroke-width=\"{projection_line_thickness}\"").replace("#000000", colors['projection_color']).replace("rgb(0, 0, 0)", colors['projection_color'])
            else:
                m = piece.Placement.Matrix
                m.rotateY(math.radians(90))
                piece.Placement.Matrix = m
                piece.Placement.move(FreeCAD.Vector(-dimensions["B"], 0, 0))
                svgFile_data += TechDraw.projectToSVG(piece.Shape, FreeCAD.Vector(0., 1., 0.)).replace("><", ">\n<").replace("<", "    <").replace("stroke-width=\"0.7\"", f"stroke-width=\"{projection_line_thickness}\"").replace("#000000", colors['projection_color']).replace("rgb(0, 0, 0)", colors['projection_color'])
            svgFile_data += projetion_tail
            if view.Name == "TopView":
                if "C" in dimensions and dimensions["C"] > 0:
                    svgFile_data += create_dimension(starting_coordinates=[dimensions['A'] / 2, -dimensions['C'] / 2],
                                                     ending_coordinates=[dimensions['A'] / 2, dimensions['C'] / 2],
                                                     dimension_type="DistanceY",
                                                     dimension_label=f"C: {round(original_dimensions['C'], 2)} mm",
                                                     label_offset=horizontal_offset)
                    horizontal_offset += increment

                if "F" in dimensions and dimensions["F"] > 0:
                    svgFile_data += create_dimension(starting_coordinates=[-dimensions['A'] / 2, 0],
                                                     ending_coordinates=[-dimensions['A'] / 2 + dimensions['F'], 0],
                                                     dimension_type="DistanceX",
                                                     dimension_label=f"F: {round(original_dimensions['F'], 2)} mm",
                                                     label_offset=vertical_offset + shape_semi_height,
                                                     label_alignment=-dimensions['A'] / 2 + dimensions['F'] / 2)

                left_column_diameter = dimensions['F']
                right_column_diameter = dimensions['A'] - dimensions['E'] - dimensions['F']

                svgFile_data += create_dimension(starting_coordinates=[-dimensions['A'] / 2 + left_column_diameter, 0],
                                                 ending_coordinates=[dimensions['A'] / 2 - right_column_diameter, 0],
                                                 dimension_type="DistanceX",
                                                 dimension_label=f"E: {round(original_dimensions['E'], 2)} mm",
                                                 label_offset=vertical_offset + shape_semi_height,
                                                 label_alignment=-dimensions['A'] / 2 + left_column_diameter + (dimensions['A'] - left_column_diameter - right_column_diameter) / 2)
                vertical_offset += increment
                svgFile_data += create_dimension(starting_coordinates=[-dimensions['A'] / 2, 0],
                                                 ending_coordinates=[dimensions['A'] / 2, 0],
                                                 dimension_type="DistanceX",
                                                 dimension_label=f"A: {round(original_dimensions['A'], 2)} mm",
                                                 label_offset=vertical_offset + shape_semi_height)
                vertical_offset += increment
            else:
                if 'H' in dimensions:
                    starting_point_for_d = dimensions['H'] / 2
                else:
                    starting_point_for_d = dimensions['E'] / 2
                svgFile_data += create_dimension(starting_coordinates=[starting_point_for_d, -dimensions['D'] / 2],
                                                 ending_coordinates=[starting_point_for_d, dimensions['D'] / 2],
                                                 dimension_type="DistanceY",
                                                 dimension_label=f"D: {round(original_dimensions['D'], 2)} mm",
                                                 label_offset=horizontal_offset + (dimensions['A'] / 2 - starting_point_for_d),
                                                 label_alignment=-dimensions['B'] / 2 + dimensions['D'] / 2)
                horizontal_offset += increment
                svgFile_data += create_dimension(starting_coordinates=[dimensions['A'] / 2, -dimensions['B'] / 2],
                                                 ending_coordinates=[dimensions['A'] / 2, dimensions['B'] / 2],
                                                 dimension_type="DistanceY",
                                                 dimension_label=f"B: {round(original_dimensions['B'], 2)} mm",
                                                 label_offset=horizontal_offset)

            svgFile_data += tail
            
            if save_files:
                svgFile = open(f"{self.output_path}/{project_name}_{view.Name}.svg", "w")
                svgFile.write(svgFile_data)
                svgFile.close() 
            return svgFile_data

        def apply_machining(self, piece, machining, dimensions):
            import FreeCAD
            document = FreeCAD.ActiveDocument

            tool = document.addObject("Part::Box", "tool")
            tool.Length = dimensions["A"]
            tool.Width = dimensions["A"] / 2
            x_coordinate = -dimensions["A"] / 2
            if machining['coordinates'][0] == 0:
                y_coordinate = -dimensions["A"] / 2
            else:
                y_coordinate = 0

            tool.Height = machining['length'] * 1000
            tool.Placement = FreeCAD.Placement(FreeCAD.Vector(x_coordinate, y_coordinate, (machining['coordinates'][1] - machining['length'] / 2) * 1000), FreeCAD.Rotation(FreeCAD.Vector(0.00, 0.00, 1.00), 0.00))

            machined_piece = document.addObject("Part::Cut", "machined_piece")
            machined_piece.Base = piece
            machined_piece.Tool = tool
            document.recompute()

            return machined_piece

    class T(IPiece):
        def get_dimensions_and_subtypes(self):
            return {1: ["A", "B", "C"]}

        def get_negative_winding_window(self, dimensions):
            return None

        def get_shape_base(self, data, sketch):
            import FreeCAD
            import Part
            import Sketcher
            dimensions = data["dimensions"]

            inner_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["B"] / 2), False)
            sketch.addConstraint(Sketcher.Constraint('Coincident', inner_circle, 3, -1, 1))
            sketch.addConstraint(Sketcher.Constraint('Diameter', inner_circle, dimensions["B"]))
            outer_circle = sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), dimensions["A"] / 2), False)
            sketch.addConstraint(Sketcher.Constraint('Coincident', outer_circle, 3, -1, 1))
            sketch.addConstraint(Sketcher.Constraint('Diameter', outer_circle, dimensions["A"]))

        def get_shape_extras(self, data, piece):
            # rotation in order to avoid cut in projection
            m = piece.Base.Placement.Matrix
            m.rotateZ(math.radians(180))
            piece.Base.Placement.Matrix = m
            return piece

        def get_top_projection(self, data, piece, margin):
            import FreeCAD
            dimensions = data["dimensions"]

            document = FreeCAD.ActiveDocument
            page = document.addObject('TechDraw::DrawPage', 'Top Page')
            template = document.addObject('TechDraw::DrawSVGTemplate', 'Template')
            page.Template = template
            document.recompute()

            top_view = document.addObject('TechDraw::DrawViewPart', 'TopView')
            page.addView(top_view)
            top_view.Source = [piece]
            top_view.Direction = FreeCAD.Vector(0.00, 0.00, 1.00)
            top_view.XDirection = FreeCAD.Vector(0.00, -1.00, 0.00)
            top_view.X = margin + dimensions['A'] / 2
            top_view.Y = 1000 - data['dimensions']['A'] / 2 - margin / 2

            top_view.Scale = 1
            document.recompute()
            return top_view

        def get_front_projection(self, data, piece, margin):
            import FreeCAD
            dimensions = data["dimensions"]

            document = FreeCAD.ActiveDocument
            page = document.addObject('TechDraw::DrawPage', 'Top Page')
            template = document.addObject('TechDraw::DrawSVGTemplate', 'Template')
            page.Template = template
            document.recompute()

            semi_depth = 0

            section_front_view = document.addObject('TechDraw::DrawViewSection', 'FrontView')
            page.addView(section_front_view)
            section_front_view.BaseView = document.getObject('TopView')
            section_front_view.Source = document.getObject('TopView').Source
            section_front_view.ScaleType = 0
            section_front_view.SectionDirection = 'Down'
            section_front_view.SectionNormal = FreeCAD.Vector(-1.000, 0.000, 0.000)
            section_front_view.SectionOrigin = FreeCAD.Vector(semi_depth, 0.000, 0)
            section_front_view.SectionSymbol = ''
            section_front_view.Label = 'Section  - '
            section_front_view.Scale = 1.000000
            section_front_view.ScaleType = 0
            section_front_view.Rotation = 0
            section_front_view.Direction = FreeCAD.Vector(-1.00, 0.00, 0.00)
            section_front_view.XDirection = FreeCAD.Vector(0.00, -1.00, 0.00)
            section_front_view.X = margin + dimensions['A'] / 2
            section_front_view.Y = 1000 - margin - dimensions['C'] / 2
            document.recompute()

            return section_front_view

        def add_dimensions_and_export_view(self, data, original_dimensions, view, project_name, margin, colors, save_files, piece):
            import FreeCAD
            import TechDraw

            def calculate_total_dimensions():
                if view.Name == "TopView":
                    base_width = data['dimensions']['A'] + margin
                    base_width += horizontal_offset

                    base_height = data['dimensions']['A'] + margin
                    base_height += vertical_offset
                    base_height += increment

                if view.Name == "FrontView":
                    base_width = data['dimensions']['A'] + margin
                    base_width += horizontal_offset

                    base_height = data['dimensions']['C'] + margin
                    base_height += vertical_offset

                return base_width, base_height

            def create_dimension(starting_coordinates, ending_coordinates, dimension_type, dimension_label, label_offset=0, label_alignment=0):
                dimension_svg = ""

                if dimension_type == "DistanceY":
                    main_line_start = [starting_coordinates[0] + label_offset, starting_coordinates[1]]
                    main_line_end = [ending_coordinates[0] + label_offset, ending_coordinates[1]]
                    left_aux_line_start = [starting_coordinates[0], starting_coordinates[1]]
                    left_aux_line_end = [starting_coordinates[0] + label_offset, starting_coordinates[1]]
                    right_aux_line_start = [ending_coordinates[0], ending_coordinates[1]]
                    right_aux_line_end = [ending_coordinates[0] + label_offset, ending_coordinates[1]]

                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value + ending_coordinates[0] + label_offset - dimension_font_size / 4},{1000 - view.Y.Value + label_alignment})" stroke-linecap="square" stroke-linejoin="bevel">
                                             <text x="0" y="0" text-anchor="middle" fill-opacity="1" font-size="{dimension_font_size}" font-style="normal" fill="{colors['dimension_color']}" font-family="osifont" stroke="none" xml:space="preserve" font-weight="400" transform="rotate(-90)">{dimension_label}</text>
                                            </g>\n""".replace("                                    ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M{main_line_start[0]},{main_line_start[1]} L{main_line_end[0]},{main_line_end[1]} M{left_aux_line_start[0]},{left_aux_line_start[1]} L{left_aux_line_end[0]},{left_aux_line_end[1]} M{right_aux_line_start[0]},{right_aux_line_start[1]} L{right_aux_line_end[0]},{right_aux_line_end[1]}"/>
                                            </g>\n""".replace("                                     ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{ending_coordinates[0] + label_offset},{ending_coordinates[1]})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L6,-15 L-6,-15 L0,0"/>
                                             </g>
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{starting_coordinates[0] + label_offset},{starting_coordinates[1]})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L-6,15 L6,15 L0,0"/>
                                             </g>
                                            </g>\n""".replace("                                     ", "")
                elif dimension_type == "DistanceX":
                    main_line_start = [starting_coordinates[0], starting_coordinates[1] + label_offset]
                    main_line_end = [ending_coordinates[0], ending_coordinates[1] + label_offset]
                    left_aux_line_start = [starting_coordinates[0], starting_coordinates[1]]
                    left_aux_line_end = [starting_coordinates[0], starting_coordinates[1] + label_offset]
                    right_aux_line_start = [ending_coordinates[0], ending_coordinates[1]]
                    right_aux_line_end = [ending_coordinates[0], ending_coordinates[1] + label_offset]

                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value + label_alignment},{1000 - view.Y.Value})" stroke-linecap="square" stroke-linejoin="bevel">
                                             <text x="0" y="{ending_coordinates[1] + label_offset - dimension_font_size / 4}" text-anchor="middle" fill-opacity="1" font-size="{dimension_font_size}" font-style="normal" fill="{colors['dimension_color']}" font-family="osifont" stroke="none" xml:space="preserve" font-weight="400">{dimension_label}</text>
                                            </g>\n""".replace("                                    ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M{main_line_start[0]},{main_line_start[1]} L{main_line_end[0]},{main_line_end[1]} M{left_aux_line_start[0]},{left_aux_line_start[1]} L{left_aux_line_end[0]},{left_aux_line_end[1]} M{right_aux_line_start[0]},{right_aux_line_start[1]} L{right_aux_line_end[0]},{right_aux_line_end[1]}"/>
                                            </g>\n""".replace("                                     ", "")
                    dimension_svg += f"""   <g font-size="29.1042" font-style="normal" stroke-opacity="1" fill="none" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="{dimension_line_thickness}" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})" stroke-linecap="round" stroke-linejoin="bevel">
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{ending_coordinates[0]},{ending_coordinates[1] + label_offset})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L-15,-6 L-15,6 L0,0"/>
                                             </g>
                                             <g fill-opacity="1" font-size="29.1042" font-style="normal" stroke-opacity="1" fill="{colors['dimension_color']}" font-family="MS Shell Dlg 2" stroke="{colors['dimension_color']}" stroke-width="1" font-weight="400" transform="matrix(1,0,0,1,{starting_coordinates[0]},{starting_coordinates[1] + label_offset})" stroke-linecap="round" stroke-linejoin="bevel">
                                              <path fill-rule="evenodd" vector-effect="none" d="M0,0 L15,6 L15,-6 L0,0"/>
                                             </g>
                                            </g>\n""".replace("                                     ", "")
                return dimension_svg

            projection_line_thickness = 4
            dimension_line_thickness = 1
            dimension_font_size = 30
            horizontal_offset = 75
            vertical_offset = 75
            increment = 50
            dimensions = data["dimensions"]
            shape_semi_height = dimensions['A'] / 2
            base_width, base_height = calculate_total_dimensions()
            head = f"""<svg xmlns:dc="http://purl.org/dc/elements/1.1/" baseProfile="tiny" xmlns:svg="http://www.w3.org/2000/svg" version="1.2" width="100%" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {base_width} {base_height}" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" height="100%" xmlns:freecad="http://www.freecadweb.org/wiki/index.php?title=Svg_Namespace" xmlns:cc="http://creativecommons.org/ns#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
                         <title>FreeCAD SVG Export</title>
                         <desc>Drawing page: {view.Name} exported from FreeCAD document: {project_name}</desc>
                         <defs/>
                         <g id="{view.Name}" inkscape:label="TechDraw" inkscape:groupmode="layer">
                          <g id="DrawingContent" fill="none" stroke="black" stroke-width="1" fill-rule="evenodd" stroke-linecap="square" stroke-linejoin="bevel">""".replace("                    ", "")
            projetion_head = f"""    <g fill-opacity="1" font-size="29.1042" font-style="normal" fill="#ffffff" font-family="MS Shell Dlg 2" stroke="none" font-weight="400" transform="matrix(1,0,0,1,{view.X.Value},{1000 - view.Y.Value})">\n"""
            projetion_tail = """   </g>\n"""
            tail = """</g>
                     </g>
                    </svg>
                    """.replace("                ", "")
            svgFile_data = ""
            svgFile_data += head
            svgFile_data += projetion_head

            if view.Name == "TopView":
                m = piece.Placement.Matrix
                m.rotateZ(math.radians(90))
                piece.Placement.Matrix = m
                svgFile_data += TechDraw.projectToSVG(piece.Shape, FreeCAD.Vector(0., 0., 1.)).replace("><", ">\n<").replace("<", "    <").replace("stroke-width=\"0.7\"", f"stroke-width=\"{projection_line_thickness}\"").replace("#000000", colors['projection_color']).replace("rgb(0, 0, 0)", colors['projection_color'])
            else:
                m = piece.Placement.Matrix
                m.rotateY(math.radians(90))
                piece.Placement.Matrix = m
                piece.Placement.move(FreeCAD.Vector(-dimensions["B"] / 2, 0, 0))
                svgFile_data += TechDraw.projectToSVG(piece.Shape, FreeCAD.Vector(0., 1., 0.)).replace("><", ">\n<").replace("<", "    <").replace("stroke-width=\"0.7\"", f"stroke-width=\"{projection_line_thickness}\"").replace("#000000", colors['projection_color']).replace("rgb(0, 0, 0)", colors['projection_color'])
            svgFile_data += projetion_tail
            if view.Name == "TopView":
                svgFile_data += create_dimension(starting_coordinates=[-dimensions['B'] / 2, 0],
                                                 ending_coordinates=[dimensions['B'] / 2, 0],
                                                 dimension_type="DistanceX",
                                                 dimension_label=f"B: {round(original_dimensions['B'], 2)} mm",
                                                 label_offset=vertical_offset + shape_semi_height)
                vertical_offset += increment
                svgFile_data += create_dimension(starting_coordinates=[-dimensions['A'] / 2, 0],
                                                 ending_coordinates=[dimensions['A'] / 2, 0],
                                                 dimension_type="DistanceX",
                                                 dimension_label=f"A: {round(original_dimensions['A'], 2)} mm",
                                                 label_offset=vertical_offset + shape_semi_height)
                vertical_offset += increment
            else:
                svgFile_data += create_dimension(starting_coordinates=[0, -dimensions['C'] / 2],
                                                 ending_coordinates=[0, dimensions['C'] / 2],
                                                 dimension_type="DistanceY",
                                                 dimension_label=f"C: {round(original_dimensions['C'], 2)} mm",
                                                 label_offset=horizontal_offset)

            svgFile_data += tail
            
            if save_files:
                svgFile = open(f"{self.output_path}/{project_name}_{view.Name}.svg", "w")
                svgFile.write(svgFile_data)
                svgFile.close() 
            return svgFile_data


if __name__ == '__main__':  # pragma: no cover

    with open(f'{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson', 'r') as f:
        for ndjson_line in f.readlines():
            data = json.loads(ndjson_line)
            if data["name"] == "PQ 40/40":
                # if data["family"] in ['pm']:
                # if data["family"] not in ['ui']:
                core = FreeCADBuilder().factory(data)
                core.get_core(data, None)
                # break
