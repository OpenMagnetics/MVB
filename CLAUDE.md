# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenMagneticsVirtualBuilder (MVB) generates FreeCAD-related files from magnetic designs following MAS (Magnetic Assembly Schema) standards. It produces 2D/3D models (.step, .obj, .stl), meshes, and technical drawings (.svg) for magnetic core shapes.

## Commands

**Run all tests:**
```bash
cd /home/tinix/claude_wsl/MVB
python -m unittest tests.test_builder
```

**Run a single test:**
```bash
python -m unittest tests.test_builder.Tests.test_all_shapes_generated
```

**Install dependencies:**
```bash
pip install cadquery numpy PyMKF
```

Note: Tests require the MAS repository with `core_shapes.ndjson` at `../MAS/data/core_shapes.ndjson` relative to project root.

## Architecture

### Dual Engine Strategy Pattern

The `Builder` class (`src/OpenMagneticsVirtualBuilder/builder.py`) acts as a facade that delegates to one of two rendering engines:

```python
builder = Builder("FreeCAD")  # Default - uses FreeCAD Python API
builder = Builder("CadQuery")  # Lighter alternative for headless/CI environments
```

### Engine Implementations

- **FreeCADBuilder** (`freecad_builder.py`, ~3800 lines) - Primary engine requiring FreeCAD installation
  - Windows: Searches `LOCALAPPDATA\Programs\FreeCAD 1.0` or `0.21`, then `ProgramFiles`
  - Linux: Searches `/usr/lib/freecad` and `/usr/lib/freecad-daily`

- **CadQueryBuilder** (`cadquery_builder.py`, ~1970 lines) - Pure Python CAD scripting, no system dependencies

### Shape Class Hierarchy

Each engine contains ~18-20 shape classes implementing magnetic core geometries:

- **Base classes:** `IPiece` (interface), `P` (planar/rectangular), `E` (E-shaped), `U` (U-shaped)
- **Concrete shapes:** ETD, ER, EP, EPX, PQ, E, PM, P, RM, PLANAR_ER, PLANAR_E, PLANAR_EL, EFD, EC, EQ, LP, U, UR, UT, T, C

Shapes follow EN 60205 standard naming and dimensions.

### Key Methods

```python
builder.factory(json_data)                    # Create shape-specific builder from MAS JSON
builder.get_families()                        # List available core shape families
builder.get_core(name, geometrical_desc)      # Generate full 3D core geometry
builder.get_core_gapping_technical_drawing()  # Generate technical drawings with gap info
builder.get_spacer(geometrical_data)          # Create spacer geometries
```

### Data Flow

1. Input: JSON data following MAS schema (see `core_shapes.ndjson`)
2. `flatten_dimensions()` converts min/max/nominal dimension values to unified format (meters to mm)
3. Engine generates parametric geometry using either FreeCAD or CadQuery
4. Output: 3D files (.step, .obj, .stl) and 2D technical drawings (.svg)

## Key Files

| File | Purpose |
|------|---------|
| `builder.py` | Main API, engine selection facade |
| `freecad_builder.py` | FreeCAD rendering engine |
| `cadquery_builder.py` | CadQuery rendering engine |
| `utils.py` | `ShapeFamily` enum, math helpers |
| `templates/blank_background.svg` | SVG template for technical drawings |

## Testing Notes

- Tests skip `ui`, `pqi`, and `ut` shape families
- Output directory: `output/` at project root (created during tests)
- `setUpClass` cleans output directory before test run
