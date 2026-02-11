# Toroidal Cores

Ring-shaped (toroidal) cores used in EMI filters, current sensors, and
applications requiring minimal stray flux.

## T - Toroidal Core

The simplest core geometry - a ring with only three dimensions.

| Dimension | Description |
|-----------|-------------|
| **A** | Outer diameter |
| **B** | Inner diameter |
| **C** | Height (ring thickness) |

**Class hierarchy:** `T(IPiece)`

## Key Properties

- **Single piece**: No mating surfaces (uses `"type": "closed piece"`)
- **No winding window cutout**: The center hole is the winding window
- **Minimal stray flux**: Fully enclosed magnetic path
- **Revolution geometry**: Created by revolving a rectangle around the Y axis

## Example

```python
from OpenMagneticsVirtualBuilder.builder import Builder
import copy

builder = Builder("CadQuery")

t_shape = {
    "family": "t",
    "name": "T 25/15/10",
    "familySubtype": "1",
    "dimensions": {
        "A": {"nominal": 0.0254},
        "B": {"nominal": 0.0152},
        "C": {"nominal": 0.0102},
    }
}

geo_desc = [
    {
        "type": "closed piece",
        "shape": copy.deepcopy(t_shape),
        "rotation": [0, 0, 0],
        "coordinates": [0, 0],
        "machining": None,
    }
]

step_path, stl_path = builder.get_core("T_25_15_10", geo_desc, output_path="./output/")
```

## Toroidal Winding

For a complete toroidal magnetic with windings, see the
[Toroidal Winding Tutorial](../tutorials/toroidal-winding.md).

## Coordinate System

Unlike concentric cores, toroidal cores use a cylindrical coordinate mapping:

| MAS Coordinate | CadQuery Axis | Meaning |
|----------------|---------------|---------|
| `coordinates[0]` | Radial from Y | Distance from center |
| `coordinates[1]` | Angle around Y | Angular position |
