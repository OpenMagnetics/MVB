# U Family

U-shaped cores for high-power applications, chokes, and inductors.

## Shapes

### U - Standard U Core

Basic U-shaped core. Two U-cores placed together form a rectangular loop.

| Dimension | Description |
|-----------|-------------|
| A | Overall width |
| B | Overall height |
| C | Leg width |
| D | Window width |
| E | Leg depth |

U cores have **1 subtype**.

**Class hierarchy:** `U(IPiece)`

---

### UR - U Core, Round

U core with rounded leg cross-sections.

| Dimension | Description |
|-----------|-------------|
| A | Overall width |
| B | Overall height |
| C | Leg width |
| D | Window width |
| H | Height dimension |
| F, G | Additional dimensions (subtypes 3, 4) |

UR cores have **4 subtypes** with varying dimension sets.

**Class hierarchy:** `Ur(IPiece)`

---

### UT - U Core, T-Shape

U core variant with T-shaped cross-section.

**Class hierarchy:** `Ut(IPiece)`

## U Family Subtypes

```python
U_DIMENSIONS_AND_SUBTYPES = {
    1: ["A", "B", "C", "D", "E"]
}

UR_DIMENSIONS_AND_SUBTYPES = {
    1: ["A", "B", "C", "D", "H"],
    2: ["A", "B", "C", "D", "H"],
    3: ["A", "B", "C", "D", "F", "H"],
    4: ["A", "B", "C", "D", "F", "G", "H"],
}
```

## Generating a U Core

```python
from OpenMagneticsVirtualBuilder.builder import Builder
import copy

builder = Builder("CadQuery")

u_shape = {
    "family": "u",
    "name": "U 25/16/6",
    "familySubtype": "1",
    "dimensions": {
        "A": {"nominal": 0.025},
        "B": {"nominal": 0.016},
        "C": {"nominal": 0.006},
        "D": {"nominal": 0.013},
        "E": {"nominal": 0.006},
    }
}

geo_desc = [
    {"type": "half set", "shape": copy.deepcopy(u_shape),
     "rotation": [0, 0, 0], "coordinates": [0, 0], "machining": None},
    {"type": "half set", "shape": copy.deepcopy(u_shape),
     "rotation": [3.14159265359, 0, 0], "coordinates": [0, 0], "machining": None},
]

step_path, stl_path = builder.get_core("U_25_16_6", geo_desc, output_path="./output/")
```
