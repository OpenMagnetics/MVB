# OpenMagnetics Virtual Builder

<div class="grid cards" markdown>

-   **Generate 3D Models**

    ---

    Create parametric STEP, STL, and OBJ files for 21 magnetic core shape families from MAS schema data.

-   **Technical Drawings**

    ---

    Produce annotated SVG, DXF, and FreeCAD macro 2D drawings with dimension lines and gapping details.

-   **Dual CAD Engines**

    ---

    Choose between CadQuery (pure Python, no system dependencies) and FreeCAD (full CAD functionality).

-   **Complete Assemblies**

    ---

    Build full magnetic components including cores, bobbins, coils, and windings.

</div>

[![PyPI](https://img.shields.io/pypi/v/OpenMagneticsVirtualBuilder)](https://pypi.org/project/OpenMagneticsVirtualBuilder/)
[![License](https://img.shields.io/github/license/OpenMagnetics/MVB)](https://github.com/OpenMagnetics/MVB/blob/main/LICENSE)
[![GitHub](https://img.shields.io/github/stars/OpenMagnetics/MVB?style=social)](https://github.com/OpenMagnetics/MVB)

## What is MVB?

**Magnetics Virtual Builder (MVB)** generates FreeCAD and CadQuery based files from any magnetic component defined following the [MAS (Magnetic Assembly Schema)](https://github.com/OpenMagnetics/MAS) standard. Output includes:

- **3D models**: `.step`, `.stl`, `.obj` files
- **2D technical drawings**: `.svg`, `.dxf`, `.FCMacro` files
- **Meshes** for simulation

## Quick Example

```python
from OpenMagneticsVirtualBuilder.builder import Builder

# Create a builder with the CadQuery engine (default)
builder = Builder("CadQuery")

# List all available core shape families
families = builder.get_families()
print(list(families.keys()))
# ['etd', 'er', 'ep', 'epx', 'pq', 'e', 'pm', 'p', 'rm', ...]
```

## Supported Shape Families

| Family | Shapes | Description |
|--------|--------|-------------|
| **E Family** | E, ETD, ER, EFD, EC, EQ, EP, EPX | E-shaped cores and variants |
| **P Family** | P, PQ, PM, RM | Pot cores and variants |
| **Planar** | PLANAR_E, PLANAR_ER, PLANAR_EL, LP | Low-profile planar cores |
| **U Family** | U, UR, UT | U-shaped cores |
| **Toroidal** | T | Ring / toroidal cores |
| **C Cores** | C | C-shaped cut cores |

## Next Steps

- [Installation](getting-started/installation.md) - Get up and running
- [Quick Start](getting-started/quickstart.md) - Generate your first core in 5 minutes
- [Architecture](architecture/overview.md) - Understand how MVB works
- [API Reference](api/builder.md) - Full API documentation
- [Shape Catalog](shapes/index.md) - Browse all supported shapes
