# C-Core Example

Generate a C-shaped cut core with gapping and windings.

## Overview

C-cores are cut from a continuous toroidal or rectangular core. They inherit
from the U-shape family and use the same dimension set.

## Step 1: Load Test Data

```python
import json

with open("tests/testData/C20_30u_8T_5mm.json") as f:
    mas_data = json.load(f)
```

## Step 2: Generate the Complete Magnetic

```python
from OpenMagneticsVirtualBuilder.builder import Builder

builder = Builder("CadQuery")

step_path, stl_path = builder.get_magnetic(
    mas_data,
    "C20_30u",
    output_path="./output/"
)

print(f"STEP: {step_path}")
print(f"STL:  {stl_path}")
```

## C-Core Geometry

The C-core class inherits from U-core and uses U-family dimensions:

| Dimension | Description |
|-----------|-------------|
| **A** | Overall width |
| **B** | Overall height |
| **C** | Leg width |
| **D** | Window width |
| **E** | Leg depth |

## C-Core Only

```python
import copy

c_shape = {
    "name": "C 20",
    "family": "c",
    "familySubtype": "1",
    "dimensions": {
        "A": {"nominal": 0.020},
        "B": {"nominal": 0.020},
        "C": {"nominal": 0.005},
        "D": {"nominal": 0.010},
        "E": {"nominal": 0.010},
    },
}

c_geo_desc = [
    {
        "type": "half set",
        "shape": copy.deepcopy(c_shape),
        "rotation": [0, 0, 0],
        "coordinates": [0, 0],
        "machining": None,
    },
    {
        "type": "half set",
        "shape": copy.deepcopy(c_shape),
        "rotation": [0, 3.14159265359, 0],
        "coordinates": [0, 0],
        "machining": None,
    },
]

step_path, stl_path = builder.get_core(
    "C_20",
    c_geo_desc,
    output_path="./output/"
)
```

## C-Core vs U-Core

| Feature | C-Core | U-Core |
|---------|--------|--------|
| Shape | C-shaped (two halves) | U-shaped |
| Pieces | 2 (mirror pair) | 1 or 2 |
| Gap location | At joint faces | Optional machining |
| Class hierarchy | `C(U)` | `U(IPiece)` |

## Next Steps

- [Core Generation Tutorial](core-generation.md) - E-core walkthrough
- [Toroidal Winding Tutorial](toroidal-winding.md) - toroidal example
- [Shape Catalog - C Cores](../shapes/c-family.md) - full C-core details
