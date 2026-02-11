# Magnetic Builder

Backward-compatibility module that re-exports magnetic building functionality
from `cadquery_builder.py`.

::: OpenMagneticsVirtualBuilder.magnetic_builder
    options:
      show_source: true
      members: false
      heading_level: 2

## Aliases

The following aliases are provided for backward compatibility:

| Alias | Target |
|-------|--------|
| `CadQueryBobbinBuilder` | `CadQueryBuilder` |
| `CadQueryCoilBuilder` | `CadQueryBuilder` |
| `CadQueryMagneticBuilder` | `CadQueryBuilder` |

All bobbin, coil, and magnetic building functionality is now integrated
into the main `CadQueryBuilder` class. See
[CadQuery Builder](cadquery-builder.md) for the full API.
