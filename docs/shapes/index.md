# Shape Catalog

MVB supports **21 magnetic core shape families** following the EN 60205 standard naming convention.

## Families at a Glance

| Family | Shapes | Typical Application |
|--------|--------|---------------------|
| [**E Family**](e-family.md) | E, ETD, ER, EFD, EC, EQ, EP, EPX | General purpose, power supplies |
| [**P Family**](p-family.md) | P, PQ, PM, RM | Shielded, low EMI |
| [**Planar**](planar-family.md) | PLANAR_E, PLANAR_ER, PLANAR_EL, LP | Low profile, PCB-mount |
| [**U Family**](u-family.md) | U, UR, UT | High power, chokes |
| [**Toroidal**](toroidal-family.md) | T | EMI filters, current sensors |
| [**C Cores**](c-family.md) | C | High power, adjustable gap |

## Dimension Naming Convention

All shapes use single-letter dimensions from EN 60205:

| Letter | Typical Meaning |
|--------|----------------|
| **A** | Overall width (largest horizontal dimension) |
| **B** | Overall height of one half |
| **C** | Winding window height |
| **D** | Center leg height (below winding window) |
| **E** | Center leg width or outer leg spacing |
| **F** | Center leg depth / diameter |
| **G** | Shape-specific (EP/EPX pot opening, P inner dims) |
| **H** | Shape-specific (EP/EPX height details, P inner dims) |
| **J** | Shape-specific (RM family only) |

!!! note
    Not all dimensions apply to every shape. For example, toroidal cores
    only need A (outer diameter), B (inner diameter), and C (height).

## MAS Dimension Format

Dimensions in MAS data can be specified three ways:

```json
// Plain number
"A": 0.042

// Nominal value
"A": {"nominal": 0.042}

// Min/max range
"A": {"minimum": 0.041, "maximum": 0.043}
```

The `flatten_dimensions()` function resolves all formats to a single value.

## Listing Families Programmatically

```python
from OpenMagneticsVirtualBuilder.builder import Builder

builder = Builder("CadQuery")
families = builder.get_families()

for name, subtypes in families.items():
    print(f"{name}:")
    for subtype, dims in subtypes.items():
        print(f"  Subtype {subtype}: {dims}")
```
