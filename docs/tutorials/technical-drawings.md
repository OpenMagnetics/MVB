# Technical Drawings Tutorial

Generate annotated 2D technical drawings in SVG, DXF, and FreeCAD macro formats.

## Overview

MVB supports three 2D output formats:

| Format | Extension | Use Case |
|--------|-----------|----------|
| SVG | `.svg` | Web display, documentation |
| DXF | `.dxf` | CAD import (AutoCAD, LibreCAD) |
| FCMacro | `.FCMacro` | FreeCAD sketch recreation |

## SVG Drawings

### Core Shape Views

Generate top and front SVG views of a core shape:

```python
from OpenMagneticsVirtualBuilder.builder import Builder

builder = Builder("CadQuery")

# E 42/21/20 shape data
e_shape = {
    "name": "E 42/21/20",
    "family": "e",
    "familySubtype": "1",
    "dimensions": {
        "A": {"nominal": 0.042},
        "B": {"nominal": 0.021},
        "C": {"nominal": 0.0157},
        "D": {"nominal": 0.0145},
        "E": {"nominal": 0.0296},
        "F": {"nominal": 0.0142},
    },
}

geometrical_description = [
    {
        "type": "half set",
        "shape": e_shape,
        "rotation": [0, 0, 0],
        "coordinates": [0, 0],
        "machining": None,
    }
]

results = builder.get_svg_drawings(
    "E_42_drawing",
    geometrical_description,
    output_path="./output/"
)
```

### Gapping Technical Drawings

Generate drawings with dimension annotations showing gap details:

```python
import copy

core_data = {
    "geometricalDescription": [
        {
            "type": "half set",
            "shape": copy.deepcopy(e_shape),
            "rotation": [0, 0, 0],
            "coordinates": [0, 0],
            "machining": [{"type": "subtractive", "length": 0.0005, "coordinates": [0, 0, 0]}],
        },
        {
            "type": "half set",
            "shape": copy.deepcopy(e_shape),
            "rotation": [3.14159265359, 0, 0],
            "coordinates": [0, 0],
            "machining": None,
        },
    ],
    "processedDescription": {
        "gapping": [
            {"type": "subtractive", "length": 0.0005, "coordinates": [0, 0, 0]}
        ]
    },
}

svg = builder.get_core_gapping_technical_drawing(
    "E_42_gapped",
    core_data,
    colors={
        "projection_color": "#000000",
        "dimension_color": "#0000FF",
    },
    output_path="./output/"
)
```

## DXF Drawings

DXF output uses cross-section slicing for precise edge geometry:

```python
results = builder.get_dxf_drawings(
    "E_42_dxf",
    geometrical_description,
    output_path="./output/"
)
```

!!! note
    DXF export requires the `ezdxf` package: `pip install ezdxf`

## FreeCAD Macro Sketches

Generate `.FCMacro` files that recreate the 2D sketch in FreeCAD:

```python
results = builder.get_fcstd_sketches(
    "E_42_sketch",
    geometrical_description,
    output_path="./output/"
)
```

## View Planes

Drawings can be generated for three principal view planes:

| Plane | Normal Direction | Typical View |
|-------|-----------------|--------------|
| **XY** | Z axis (top-down) | Top view |
| **XZ** | Y axis (front) | Front view |
| **ZY** | X axis (side) | Side / cross-section view |

## Drawing 2D Module

For advanced customization, use the `drawing_2d` module directly:

```python
from OpenMagneticsVirtualBuilder.drawing_2d import (
    ViewPlane,
    ViewType,
    DimensionAnnotation,
    cross_section_at_plane,
    create_dimension_svg,
)

# Slice a shape at the ZY plane
section = cross_section_at_plane(shape, ViewPlane.ZY, offset=0.0)
```

## Customizing Colors

Both projection lines and dimension annotations support custom colors:

```python
colors = {
    "projection_color": "#333333",   # Dark gray shape outline
    "dimension_color": "#0066CC",    # Blue dimension lines
}
```

## Next Steps

- [Core Generation Tutorial](core-generation.md) - generate 3D geometry first
- [2D Drawing API Reference](../api/drawing-2d.md) - full module documentation
