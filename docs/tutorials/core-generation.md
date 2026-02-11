# Core Generation Tutorial

This tutorial walks through generating 3D core geometry with gapping and
technical drawings.

## Prerequisites

```bash
pip install OpenMagneticsVirtualBuilder
```

## Step 1: Define Core Shape Data

Each core piece is described by its shape family, name, and dimensions
following the MAS schema. Dimensions are in **meters**.

```python
import copy

# E 42/21/20 shape data
e_core_shape = {
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
```

## Step 2: Create Geometrical Description

A typical E-core consists of two half-sets. The second piece is rotated
180 degrees around X to form the bottom half:

```python
geometrical_description = [
    {
        "type": "half set",
        "shape": copy.deepcopy(e_core_shape),
        "rotation": [0, 0, 0],
        "coordinates": [0, 0],
        "machining": None,
    },
    {
        "type": "half set",
        "shape": copy.deepcopy(e_core_shape),
        "rotation": [3.14159265359, 0, 0],  # 180 deg around X
        "coordinates": [0, 0],
        "machining": None,
    },
]
```

## Step 3: Generate 3D Model

```python
from OpenMagneticsVirtualBuilder.builder import Builder

builder = Builder("CadQuery")

step_path, stl_path = builder.get_core(
    "E_42_21_20",
    geometrical_description,
    output_path="./output/"
)

print(f"STEP: {step_path}")
print(f"STL:  {stl_path}")
```

This produces two files:

- `output/E_42_21_20.step` - parametric CAD model
- `output/E_42_21_20.stl` - mesh for visualization

## Step 4: Add Gapping

To add a center-leg gap, include machining data in the geometrical description:

```python
# 0.5 mm center-leg gap on the top half
geometrical_description_gapped = [
    {
        "type": "half set",
        "shape": copy.deepcopy(e_core_shape),
        "rotation": [0, 0, 0],
        "coordinates": [0, 0],
        "machining": [
            {
                "type": "subtractive",
                "length": 0.0005,       # 0.5 mm gap
                "coordinates": [0, 0, 0]  # center leg
            }
        ],
    },
    {
        "type": "half set",
        "shape": copy.deepcopy(e_core_shape),
        "rotation": [3.14159265359, 0, 0],
        "coordinates": [0, 0],
        "machining": None,
    },
]

step_path, stl_path = builder.get_core(
    "E_42_21_20_gapped",
    geometrical_description_gapped,
    output_path="./output/"
)
```

## Step 5: Generate Technical Drawing

```python
core_data = {
    "geometricalDescription": geometrical_description_gapped,
    "processedDescription": {
        "gapping": [
            {
                "type": "subtractive",
                "length": 0.0005,
                "coordinates": [0, 0, 0]
            }
        ]
    }
}

svg = builder.get_core_gapping_technical_drawing(
    "E_42_gapped_drawing",
    core_data,
    colors={"projection_color": "#000000", "dimension_color": "#0000FF"},
    output_path="./output/"
)
```

## Machining Coordinates

The `coordinates` array in machining data controls gap placement:

| `coordinates[0]` | Location |
|-------------------|----------|
| `0` | Center leg |
| `> 0` | Right outer leg |
| `< 0` | Left outer leg |

`coordinates[1]` controls the vertical offset of the gap from the mating surface.

## Next Steps

- [Complete Magnetic Tutorial](complete-magnetic.md) - add bobbin and winding
- [Technical Drawings Tutorial](technical-drawings.md) - SVG/DXF/FCMacro output
- [Shape Catalog](../shapes/index.md) - browse all shape families
