# Installation

## From PyPI

```bash
pip install OpenMagneticsVirtualBuilder
```

## From Source

```bash
git clone https://github.com/OpenMagnetics/MVB.git
cd MVB
pip install -e .
```

### Dependencies

The CadQuery engine (default) requires:

```bash
pip install cadquery numpy
```

For 2D drawing export (DXF format):

```bash
pip install ezdxf
```

## FreeCAD Engine Setup

The FreeCAD engine requires a system FreeCAD installation.

=== "Linux"

    ```bash
    sudo apt install freecad
    ```

    The builder searches for FreeCAD in:

    - `/usr/lib/freecad`
    - `/usr/lib/freecad-daily`

=== "Windows"

    Install FreeCAD from [freecad.org](https://www.freecad.org/downloads.php).

    The builder searches in:

    - `%LOCALAPPDATA%\Programs\FreeCAD 1.0`
    - `%LOCALAPPDATA%\Programs\FreeCAD 0.21`
    - `%ProgramFiles%\FreeCAD 1.0`

## MAS Data

Tests and some examples require the MAS repository with core shape definitions:

```bash
git clone https://github.com/OpenMagnetics/MAS.git ../MAS
```

The `core_shapes.ndjson` file should be at `../MAS/data/core_shapes.ndjson` relative to the MVB project root.

## Verify Installation

```python
from OpenMagneticsVirtualBuilder.builder import Builder

builder = Builder("CadQuery")
families = builder.get_families()
print(f"Available families: {len(families)}")
# Available families: 21
```
