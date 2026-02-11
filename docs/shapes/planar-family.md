# Planar Family

Low-profile cores designed for planar transformers and PCB-integrated magnetics.

## Shapes

### PLANAR_E - Planar E Core

Low-profile version of the standard E core for planar transformer designs.

**Dimensions:** A, B, C, D, E, F

**Class hierarchy:** In CadQuery engine, uses `E` base with planar modifications.

---

### PLANAR_ER - Planar ER Core

Low-profile version of the ER core with a round center leg.

**Dimensions:** A, B, C, D, E, F

**Class hierarchy:** In CadQuery engine, uses `Er` base with planar modifications.

---

### PLANAR_EL - Planar EL Core

Extended low-profile E core variant.

**Dimensions:** A, B, C, D, E, F

**Class hierarchy:** In CadQuery engine, uses `El` base.

---

### LP - Low Profile

Dedicated low-profile core shape, inheriting from the ER class.

**Dimensions:** A, B, C, D, E, F

**Class hierarchy:** `Lp(Er(E))`

## Planar vs Standard Cores

| Feature | Standard | Planar |
|---------|----------|--------|
| Height | Taller | Very low profile |
| Winding | Wire wound | PCB traces |
| Power density | Moderate | High |
| Typical use | Discrete transformers | Embedded power |

## Generating a Planar Core

```python
from OpenMagneticsVirtualBuilder.builder import Builder
import copy

builder = Builder("CadQuery")

planar_shape = {
    "family": "planar_e",
    "name": "PLANAR E 32",
    "familySubtype": "1",
    "dimensions": {
        "A": {"nominal": 0.032},
        "B": {"nominal": 0.006},
        "C": {"nominal": 0.0037},
        "D": {"nominal": 0.0048},
        "E": {"nominal": 0.0229},
        "F": {"nominal": 0.0110},
    }
}

geo_desc = [
    {"type": "half set", "shape": copy.deepcopy(planar_shape),
     "rotation": [0, 0, 0], "coordinates": [0, 0], "machining": None},
    {"type": "half set", "shape": copy.deepcopy(planar_shape),
     "rotation": [3.14159265359, 0, 0], "coordinates": [0, 0], "machining": None},
]

step_path, stl_path = builder.get_core("PLANAR_E32", geo_desc, output_path="./output/")
```
