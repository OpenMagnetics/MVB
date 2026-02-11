# P Family

Pot cores and their variants. These shapes provide partial or full shielding of
the winding, reducing electromagnetic interference.

## Shapes

### P - Pot Core

Fully enclosed pot core with a cylindrical winding area.

| Dimension | Description |
|-----------|-------------|
| A | Overall diameter |
| B | Overall height (one half) |
| C | Winding window height |
| D | Base height |
| E | Center post diameter |
| F | Winding area outer diameter |
| G | Inner dimension |
| H | Additional dimension |

P cores have **4 subtypes**, each using a slightly different dimension set.

**Class hierarchy:** `P(IPiece)`

---

### PQ - Pot Core, Quasi-Planar

Modified pot core with a more rectangular profile, optimized for PCB mounting
while maintaining some shielding.

**Dimensions:** A, B, C, D, E, F, G, H

**Class hierarchy:** `Pq(P)`

---

### PM - Pot Core, Modified

Modified pot core geometry with non-circular outer profile.

**Dimensions:** A, B, C, D, E, F, G, H

**Class hierarchy:** `Pm(P)`

---

### RM - Pot Core, Rectangular

Rectangular pot core combining the shielding benefits of pot cores with
the mounting convenience of rectangular shapes.

| Dimension | Description |
|-----------|-------------|
| A-H | Standard pot core dimensions |
| J | Additional dimension |

RM cores have **4 subtypes**.

**Class hierarchy:** `Rm(P)`

## Subtypes

P and RM families support multiple subtypes:

```python
# P family subtypes
P_DIMENSIONS_AND_SUBTYPES = {
    1: ["A", "B", "C", "D", "E", "F", "G", "H"],
    2: ["A", "B", "C", "D", "E", "F", "G", "H"],
    3: ["A", "B", "D", "E", "F", "G", "H"],      # No "C"
    4: ["A", "B", "C", "D", "E", "F", "G", "H"],
}

# RM family subtypes
RM_DIMENSIONS_AND_SUBTYPES = {
    1: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
    2: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
    3: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
    4: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
}
```

## Generating a PQ Core

```python
from OpenMagneticsVirtualBuilder.builder import Builder
import copy

builder = Builder("CadQuery")

pq_shape = {
    "family": "pq",
    "name": "PQ 40/40",
    "familySubtype": "1",
    "dimensions": {
        "A": {"nominal": 0.0404},
        "B": {"nominal": 0.0386},
        "C": {"nominal": 0.0287},
        "D": {"nominal": 0.0275},
        "E": {"nominal": 0.0285},
        "F": {"nominal": 0.0135},
    }
}

geo_desc = [
    {"type": "half set", "shape": copy.deepcopy(pq_shape),
     "rotation": [0, 0, 0], "coordinates": [0, 0], "machining": None},
    {"type": "half set", "shape": copy.deepcopy(pq_shape),
     "rotation": [3.14159265359, 0, 0], "coordinates": [0, 0], "machining": None},
]

step_path, stl_path = builder.get_core("PQ4040", geo_desc, output_path="./output/")
```
