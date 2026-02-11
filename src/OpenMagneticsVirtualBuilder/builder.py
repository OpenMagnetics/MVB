"""Main facade for the OpenMagnetics Virtual Builder.

Provides a unified API for generating 3D geometry and 2D technical drawings
of magnetic components. Delegates to either the CadQuery or FreeCAD engine
via the Strategy pattern.
"""

import sys
import os
import json

sys.path.append(os.path.dirname(__file__))

file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)


class Builder:
    """Facade that delegates to a CadQuery or FreeCAD rendering engine.

    The Builder class is the main entry point for generating magnetic component
    geometry. It selects and wraps one of two CAD engines and exposes a
    uniform API for core generation, assembly, bobbin/winding creation,
    and technical drawing export.

    Args:
        engine: Engine name, either ``"CadQuery"`` (default) or ``"FreeCAD"``.

    Example:
        >>> builder = Builder("CadQuery")
        >>> families = builder.get_families()
    """

    def __init__(self, engine="CadQuery"):
        if engine == "FreeCAD":
            import freecad_builder

            self.engine = freecad_builder.FreeCADBuilder()
        else:
            import cadquery_builder

            self.engine = cadquery_builder.CadQueryBuilder()

    def factory(self, data):
        """Create a shape-specific builder from MAS JSON data.

        Args:
            data: Dictionary with at least a ``"family"`` key matching a
                :class:`~OpenMagneticsVirtualBuilder.utils.ShapeFamily` member.

        Returns:
            A shape builder instance (e.g. ``E``, ``Pq``, ``T``) for the
            requested family.
        """
        return self.engine.factory(data)

    def get_families(self):
        """List all available core shape families with their dimensions.

        Returns:
            Dict mapping family name (lowercase) to a dict of subtype numbers
            and their dimension letters.
        """
        return {shaper.name.lower().replace("_", " "): self.factory({"family": shaper.name}).get_dimensions_and_subtypes() for shaper in self.engine.shapers}

    def get_spacer(self, geometrical_data):
        """Generate spacer geometry for gapped cores.

        Args:
            geometrical_data: MAS geometrical description list.

        Returns:
            CadQuery/FreeCAD geometry for the spacer.
        """
        return self.engine.get_spacer(geometrical_data)

    def get_core(self, project_name, geometrical_description, output_path=None, save_files=True, export_files=True):
        """Generate full 3D core geometry from a MAS geometrical description.

        Handles multi-piece cores (top/bottom halves) and applies gapping
        (machining) when specified.

        Args:
            project_name: Base name for output files.
            geometrical_description: List of MAS piece descriptions, each
                containing shape data, dimensions, and optional machining.
            output_path: Directory for output files. Defaults to ``output/``.
            save_files: Whether to save FreeCAD project files.
            export_files: Whether to export STEP/STL files.

        Returns:
            Tuple ``(step_path, stl_path)`` when ``export_files`` is True,
            or a list of CadQuery/FreeCAD pieces otherwise.
        """
        if output_path is None:
            output_path = f"{os.path.dirname(os.path.abspath(__file__))}/../../output/"
        return self.engine.get_core(project_name, geometrical_description, output_path, save_files, export_files)

    def get_core_gapping_technical_drawing(self, project_name, core_data, colors=None, output_path=None, save_files=True, export_files=True):
        """Generate a technical drawing showing core gapping details.

        Produces an SVG drawing with dimension annotations for the core
        cross-section, highlighting gap positions and lengths.

        Args:
            project_name: Base name for output files.
            core_data: MAS core data dictionary with ``geometricalDescription``
                and ``processedDescription`` (including ``gapping``).
            colors: Optional dict with ``"projection_color"`` and
                ``"dimension_color"`` hex values.
            output_path: Directory for output files.
            save_files: Whether to save intermediate files.
            export_files: Whether to export final SVG.

        Returns:
            SVG string of the technical drawing.
        """
        if output_path is None:
            output_path = f"{os.path.dirname(os.path.abspath(__file__))}/../../output/"
        return self.engine.get_core_gapping_technical_drawing(project_name, core_data, colors, output_path, save_files, export_files)

    def get_magnetic_assembly(self, project_name, assembly_data, output_path=None, save_files=True, export_files=True):
        """Generate a full magnetic assembly (core + bobbin + coil).

        Args:
            project_name: Base name for output files.
            assembly_data: MAS assembly data containing core, coil, and
                bobbin descriptions.
            output_path: Directory for output files.
            save_files: Whether to save intermediate files.
            export_files: Whether to export STEP/STL.

        Returns:
            Tuple ``(step_path, stl_path)`` when ``export_files`` is True.
        """
        if output_path is None:
            output_path = f"{os.path.dirname(os.path.abspath(__file__))}/../../output/"
        return self.engine.get_magnetic_assembly(project_name, assembly_data, output_path, save_files, export_files)

    def get_bobbin(self, bobbin_data, winding_window, name="Bobbin", output_path=None, save_files=False, export_files=True):
        """Generate a bobbin (coil former) geometry.

        Args:
            bobbin_data: MAS bobbin description with ``processedDescription``.
            winding_window: Dict with ``height`` and ``width`` keys (meters).
            name: Part name for the output files.
            output_path: Directory for output files.
            save_files: Whether to save intermediate files.
            export_files: Whether to export STEP/STL.

        Returns:
            Tuple ``(step_path, stl_path)`` when ``export_files`` is True.
        """
        if output_path is None:
            output_path = f"{os.path.dirname(os.path.abspath(__file__))}/../../output/"
        return self.engine.get_bobbin(bobbin_data, winding_window, name, output_path, save_files, export_files)

    def get_winding(self, winding_data, bobbin_dims, name="Winding", output_path=None, save_files=False, export_files=True):
        """Generate winding (coil) geometry.

        Args:
            winding_data: MAS winding description with wire type, turns, etc.
            bobbin_dims: Dict with ``width`` and ``height`` keys.
            name: Part name for output files.
            output_path: Directory for output files.
            save_files: Whether to save intermediate files.
            export_files: Whether to export STEP/STL.

        Returns:
            Tuple ``(step_path, stl_path)`` when ``export_files`` is True.
        """
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
