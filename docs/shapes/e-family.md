# E Family

The E family is the most common core shape family, with many variants for different applications.

## Shapes

### E - Standard E Core

The basic E-shaped core with rectangular cross-section legs.

| Dimension | Description |
|-----------|-------------|
| A | Overall width |
| B | Overall height (one half) |
| C | Winding window height |
| D | Center leg height below window |
| E | Outer leg spacing |
| F | Center leg width |

```python
e_shape = {
    "family": "e",
    "name": "E 42/21/20",
    "dimensions": {
        "A": {"nominal": 0.042},
        "B": {"nominal": 0.021},
        "C": {"nominal": 0.0157},
        "D": {"nominal": 0.0145},
        "E": {"nominal": 0.0296},
        "F": {"nominal": 0.0142},
    }
}
```

**Class hierarchy:** `E(IPiece)`

---

### ETD - E Core with Round Center Leg

E core variant where the center leg has a round cross-section, reducing winding length.

**Dimensions:** Same as E (A, B, C, D, E, F)

**Class hierarchy:** `Etd(Er(E))`

---

### ER - E Core with Round Center

E core with a round center column. Base class for ETD, LP, EQ, EC.

**Dimensions:** A, B, C, D, E, F

**Class hierarchy:** `Er(E)`

---

### EFD - E Core, Flat Design

Low-profile E core designed for flat transformers. Uses a modified winding window geometry.

**Dimensions:** A, B, C, D, E, F

**Class hierarchy:** `Efd(E)`

---

### EC - E Core, Cylindrical

E core with a cylindrical center leg and modified outer legs.

**Dimensions:** A, B, C, D, E, F

**Class hierarchy:** `Ec(Er)`

---

### EQ - E Core, Square

E core optimized for minimal air gap effects.

**Dimensions:** A, B, C, D, E, F

**Class hierarchy:** `Eq(Er)`

---

### EP - E Core, Pot-Like

E core with a partially enclosed winding area, offering some shielding.

| Dimension | Description |
|-----------|-------------|
| A | Overall width |
| B | Overall height |
| C | Winding window height |
| D | Base height |
| E | Outer dimension |
| F | Center leg dimension |
| G | Opening width |
| H | Additional height dimension |

**Class hierarchy:** `Ep(E)`

---

### EPX - E Core, Pot-Like Extended

Extended variant of EP with additional dimensional parameters.

| Dimension | Description |
|-----------|-------------|
| A-H | Same as EP |

**Class hierarchy:** `Epx(E)`

## Generating an E-Family Core

```python
from OpenMagneticsVirtualBuilder.builder import Builder
import copy

builder = Builder("CadQuery")

shape_data = {
    "family": "etd",
    "name": "ETD 49/25/16",
    "dimensions": {
        "A": {"nominal": 0.0492},
        "B": {"nominal": 0.0250},
        "C": {"nominal": 0.01720},
        "D": {"nominal": 0.01745},
        "E": {"nominal": 0.03780},
        "F": {"nominal": 0.01650},
    }
}

geo_desc = [
    {"type": "half set", "shape": copy.deepcopy(shape_data),
     "rotation": [0, 0, 0], "coordinates": [0, 0], "machining": None},
    {"type": "half set", "shape": copy.deepcopy(shape_data),
     "rotation": [3.14159265359, 0, 0], "coordinates": [0, 0], "machining": None},
]

step_path, stl_path = builder.get_core("ETD49", geo_desc, output_path="./output/")
```
