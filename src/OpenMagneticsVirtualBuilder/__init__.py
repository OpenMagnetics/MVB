"""OpenMagneticsVirtualBuilder - 3D magnetic component geometry generation.

Generate FreeCAD and CadQuery based 3D models, meshes, and technical drawings
from magnetic designs following the MAS (Magnetic Assembly Schema) standard.

Supports 21 core shape families (E, ETD, PQ, RM, toroidal, C-core, etc.),
two rendering engines (CadQuery and FreeCAD), and multiple output formats
(STEP, STL, OBJ, SVG, DXF).

Example:
    >>> from OpenMagneticsVirtualBuilder import Builder, ShapeFamily
    >>> builder = Builder("CadQuery")
    >>> families = builder.get_families()
"""

from .builder import Builder
from .utils import ShapeFamily, flatten_dimensions

__version__ = "0.1.0"
__all__ = ["Builder", "ShapeFamily", "flatten_dimensions"]
