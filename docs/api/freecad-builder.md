# FreeCAD Builder

The FreeCAD rendering engine. Requires a system FreeCAD installation.

!!! note "Not available for auto-generation"
    The FreeCAD engine requires a FreeCAD system installation that is not
    available in CI environments. This page documents the API manually.

## FreeCADBuilder

```python
from OpenMagneticsVirtualBuilder.freecad_builder import FreeCADBuilder
```

The `FreeCADBuilder` class mirrors the `CadQueryBuilder` API. It inherits from
`BuilderBase` and registers the same set of shape families.

### Path Discovery

On instantiation, `FreeCADBuilder` searches for a FreeCAD installation:

| Platform | Search Paths |
|----------|-------------|
| **Linux** | `/usr/lib/freecad/lib`, `/usr/lib/freecad-daily/lib` |
| **Windows** | `%LOCALAPPDATA%\Programs\FreeCAD 1.0\bin`, `%LOCALAPPDATA%\Programs\FreeCAD 0.21\bin`, `%ProgramFiles%\FreeCAD 1.0\bin` |

### Public Methods

#### `get_core(project_name, geometrical_description, output_path, save_files, export_files)`

Generate full 3D core geometry. Identical signature to
[`Builder.get_core()`](builder.md).

**Returns:** `(step_path, stl_path)` or list of FreeCAD shapes.

#### `get_core_gapping_technical_drawing(project_name, core_data, colors, output_path, save_files, export_files)`

Generate SVG technical drawing with dimension annotations and gapping details.

**Returns:** SVG string.

#### `get_magnetic_assembly(project_name, assembly_data, output_path, save_files, export_files)`

Generate a full magnetic assembly (core + bobbin + coil).

**Returns:** `(step_path, stl_path)`.

#### `get_bobbin(bobbin_data, winding_window, name, output_path, save_files, export_files)`

Generate bobbin geometry.

**Returns:** `(step_path, stl_path)`.

#### `get_winding(winding_data, bobbin_dims, name, output_path, save_files, export_files)`

Generate winding geometry.

**Returns:** `(step_path, stl_path)`.

#### `get_spacer(geometrical_data)`

Generate spacer geometry for gapped cores.

### Shape Classes

The FreeCAD engine contains the same nested shape classes as the CadQuery
engine (`IPiece`, `E`, `P`, `U`, `T`, `C`, etc.) with identical inheritance
hierarchies. See [Shape Hierarchy](../architecture/shape-hierarchy.md) for
the full class tree.

### Output Formats

In addition to STEP and STL, the FreeCAD engine supports:

- **OBJ** mesh export
- **FCStd** FreeCAD project files (when `save_files=True`)
- **SVG** technical drawings with dimension annotations
