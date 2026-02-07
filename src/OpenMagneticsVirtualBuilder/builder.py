import sys
import os
import json

sys.path.append(os.path.dirname(__file__))

file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)


class Builder:
    """
    Class for building 3D models of magnetic components.
    """

    def __init__(self, engine="CadQuery"):
        if engine == "FreeCAD":
            import freecad_builder

            self.engine = freecad_builder.FreeCADBuilder()
        else:
            import cadquery_builder

            self.engine = cadquery_builder.CadQueryBuilder()

    def factory(self, data):
        return self.engine.factory(data)

    def get_families(self):
        return {shaper.name.lower().replace("_", " "): self.factory({"family": shaper.name}).get_dimensions_and_subtypes() for shaper in self.engine.shapers}

    def get_spacer(self, geometrical_data):
        return self.engine.get_spacer(geometrical_data)

    def get_core(self, project_name, geometrical_description, output_path=None, save_files=True, export_files=True):
        if output_path is None:
            output_path = f"{os.path.dirname(os.path.abspath(__file__))}/../../output/"
        return self.engine.get_core(project_name, geometrical_description, output_path, save_files, export_files)

    def get_core_gapping_technical_drawing(self, project_name, core_data, colors=None, output_path=None, save_files=True, export_files=True):
        if output_path is None:
            output_path = f"{os.path.dirname(os.path.abspath(__file__))}/../../output/"
        return self.engine.get_core_gapping_technical_drawing(project_name, core_data, colors, output_path, save_files, export_files)

    def get_magnetic_assembly(self, project_name, assembly_data, output_path=None, save_files=True, export_files=True):
        if output_path is None:
            output_path = f"{os.path.dirname(os.path.abspath(__file__))}/../../output/"
        return self.engine.get_magnetic_assembly(project_name, assembly_data, output_path, save_files, export_files)

    def get_bobbin(self, bobbin_data, winding_window, name="Bobbin", output_path=None, save_files=False, export_files=True):
        if output_path is None:
            output_path = f"{os.path.dirname(os.path.abspath(__file__))}/../../output/"
        return self.engine.get_bobbin(bobbin_data, winding_window, name, output_path, save_files, export_files)

    def get_winding(self, winding_data, bobbin_dims, name="Winding", output_path=None, save_files=False, export_files=True):
        if output_path is None:
            output_path = f"{os.path.dirname(os.path.abspath(__file__))}/../../output/"
        return self.engine.get_winding(winding_data, bobbin_dims, name, output_path, save_files, export_files)

    def get_magnetic(self, magnetic_data, project_name="Magnetic", output_path=None, export_files=True):
        """Create a complete 3D magnetic component from MAS data.

        Parameters
        ----------
        magnetic_data : dict
            MAS magnetic description dictionary containing core, coil, etc.
            Can be either a complete MAS file (with 'magnetic' key) or just the magnetic data.
        project_name : str
            Name for the output files.
        output_path : str
            Path to save output files.
        export_files : bool
            If True, export STEP and STL files.

        Returns
        -------
        Tuple of (step_path, stl_path) or list of pieces if export_files is False.
        """
        if output_path is None:
            output_path = f"{os.path.dirname(os.path.abspath(__file__))}/../../output/"
        # Handle both full MAS format and just magnetic data
        if "magnetic" in magnetic_data:
            magnetic_data = magnetic_data["magnetic"]
        return self.engine.get_magnetic(magnetic_data, project_name, output_path, export_files)

    def get_svg_drawings(self, project_name, geometrical_description, **kwargs):
        """Generate annotated SVG drawings for a core shape."""
        return self.engine.get_svg_drawings(project_name, geometrical_description, **kwargs)

    def get_dxf_drawings(self, project_name, geometrical_description, **kwargs):
        """Generate DXF drawings for a core shape."""
        return self.engine.get_dxf_drawings(project_name, geometrical_description, **kwargs)

    def get_fcstd_sketches(self, project_name, geometrical_description, **kwargs):
        """Generate FreeCAD macro files for a core shape."""
        return self.engine.get_fcstd_sketches(project_name, geometrical_description, **kwargs)

    def get_assembly_svg_drawings(self, project_name, magnetic_data, **kwargs):
        """Generate annotated SVG drawings for assembly or individual components."""
        return self.engine.get_assembly_svg_drawings(project_name, magnetic_data, **kwargs)

    def get_assembly_dxf_drawings(self, project_name, magnetic_data, **kwargs):
        """Generate DXF drawings for assembly or individual components."""
        return self.engine.get_assembly_dxf_drawings(project_name, magnetic_data, **kwargs)

    def get_assembly_fcstd_sketches(self, project_name, magnetic_data, **kwargs):
        """Generate FreeCAD macro files for assembly or individual components."""
        return self.engine.get_assembly_fcstd_sketches(project_name, magnetic_data, **kwargs)


if __name__ == "__main__":  # pragma: no cover
    with open(f"{os.path.dirname(os.path.abspath(__file__))}/../../MAS/data/core_shapes.ndjson", "r") as f:
        for ndjson_line in f.readlines():
            data = json.loads(ndjson_line)
            if data["name"] == "PQ 40/40":
                core = Builder().factory(data)
                core.get_core(data, None)
