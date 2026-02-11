# C Cores

C-shaped cut cores for high-power applications with adjustable air gaps.

## C - Cut C-Core

C-cores are manufactured by cutting a toroidal or wound core in half.
Two C-cores are assembled face-to-face with an optional air gap.

| Dimension | Description |
|-----------|-------------|
| **A** | Overall width |
| **B** | Overall height |
| **C** | Leg width |
| **D** | Window width |
| **E** | Leg depth |

**Class hierarchy:** `C(U)` - inherits from U-core

## C-Core vs U-Core

The C-core class inherits directly from U since the geometry is identical.
The distinction is in assembly: C-cores always come in pairs (two halves
facing each other), while U-cores may be paired with an I-bar.

## Example

```python
from OpenMagneticsVirtualBuilder.builder import Builder
import copy

builder = Builder("CadQuery")

c_shape = {
    "family": "c",
    "name": "C 20",
    "familySubtype": "1",
    "dimensions": {
        "A": {"nominal": 0.020},
        "B": {"nominal": 0.020},
        "C": {"nominal": 0.005},
        "D": {"nominal": 0.010},
        "E": {"nominal": 0.010},
    }
}

# Two C-halves mirrored to form a complete core
geo_desc = [
    {"type": "half set", "shape": copy.deepcopy(c_shape),
     "rotation": [0, 0, 0], "coordinates": [0, 0], "machining": None},
    {"type": "half set", "shape": copy.deepcopy(c_shape),
     "rotation": [0, 3.14159265359, 0], "coordinates": [0, 0], "machining": None},
]

step_path, stl_path = builder.get_core("C_20", geo_desc, output_path="./output/")
```

## Gapping

C-cores naturally have a gap at the joint faces. Additional machining can
be applied to increase the gap:

```python
geo_desc_gapped = [
    {"type": "half set", "shape": copy.deepcopy(c_shape),
     "rotation": [0, 0, 0], "coordinates": [0, 0],
     "machining": [{"type": "subtractive", "length": 0.001, "coordinates": [0, 0, 0]}]},
    {"type": "half set", "shape": copy.deepcopy(c_shape),
     "rotation": [0, 3.14159265359, 0], "coordinates": [0, 0],
     "machining": None},
]
```

## Full C-Core Magnetic

For a complete example with windings, see the
[C-Core Tutorial](../tutorials/c-core-example.md).
