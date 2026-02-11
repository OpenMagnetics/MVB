# Toroidal Winding Tutorial

Build a toroidal (ring) core magnetic component with windings.

## Overview

Toroidal cores are fundamentally different from concentric cores (E, PQ, etc.):

- The core is a ring that revolves around the Y axis
- Turns are wound **through** the center hole
- MAS coordinates use radial distance and angular position

## Step 1: Load Test Data

```python
import json

with open("tests/testData/T402416_edge40_4uH_8T.json") as f:
    mas_data = json.load(f)
```

## Step 2: Generate the Complete Magnetic

```python
from OpenMagneticsVirtualBuilder.builder import Builder

builder = Builder("CadQuery")

step_path, stl_path = builder.get_magnetic(
    mas_data,
    "T402416_4uH",
    output_path="./output/"
)

print(f"STEP: {step_path}")
print(f"STL:  {stl_path}")
```

## Toroidal Core Geometry

A toroidal core requires only three dimensions:

| Dimension | Description |
|-----------|-------------|
| **A** | Outer diameter |
| **B** | Inner diameter |
| **C** | Height (thickness) |

```python
t_core_shape = {
    "name": "T 40/24/16",
    "family": "t",
    "familySubtype": "1",
    "dimensions": {
        "A": {"nominal": 0.0404},
        "B": {"nominal": 0.0246},
        "C": {"nominal": 0.0163},
    },
}
```

## Toroidal Core Only

```python
import copy

t_geo_desc = [
    {
        "type": "closed piece",
        "shape": copy.deepcopy(t_core_shape),
        "rotation": [0, 0, 0],
        "coordinates": [0, 0],
        "machining": None,
    }
]

step_path, stl_path = builder.get_core(
    "T_40_24_16",
    t_geo_desc,
    output_path="./output/"
)
```

!!! note
    Toroidal cores use `"type": "closed piece"` since they are a single
    piece (unlike E-cores which use `"half set"`).

## Coordinate System

For toroidal cores, the coordinate mapping is:

| Axis | Direction |
|------|-----------|
| **X** | Radial (negative X = inside the hole) |
| **Y** | Core axis (toroid revolves around Y) |
| **Z** | Tangential direction |

MAS turn coordinates for toroidal cores:

- `coordinates[0]` = radial distance from Y axis
- `coordinates[1]` = angular position (rotation around Y axis)

## Winding Styles

Toroidal windings pass through the center hole of the core. The CadQuery
engine creates each turn as a torus swept along the winding path.

```python
# Example turn in MAS format
turn = {
    "coordinates": [0.015, 0.2],  # radial, angular
    "winding": "Primary",
    "parallel": 0,
    "turnIndex": 0
}
```

## Next Steps

- [C-Core Example](c-core-example.md) - another core type
- [Core Generation Tutorial](core-generation.md) - E-core walkthrough
- [Shape Catalog - Toroidal](../shapes/toroidal-family.md) - toroidal details
