# Complete Magnetic Tutorial

Build a full ETD49 magnetic component from MAS JSON data, including core,
bobbin, and coil windings.

## Prerequisites

```bash
pip install OpenMagneticsVirtualBuilder
```

Test data files are in `tests/testData/`.

## Step 1: Load MAS Data

MVB uses full MAS (Magnetic Assembly Schema) JSON files that describe the
complete magnetic component:

```python
import json

with open("tests/testData/ETD49_N87_10uH_5T.json") as f:
    mas_data = json.load(f)

# The magnetic data is nested under the "magnetic" key
magnetic_data = mas_data["magnetic"]
```

The MAS magnetic object contains:

- `core` - shape, material, gapping
- `coil` - bobbin, windings, turns

## Step 2: Generate the Complete Magnetic

```python
from OpenMagneticsVirtualBuilder.builder import Builder

builder = Builder("CadQuery")

step_path, stl_path = builder.get_magnetic(
    mas_data,  # Builder handles the "magnetic" key extraction
    "ETD49_N87_10uH",
    output_path="./output/"
)

print(f"STEP: {step_path}")
print(f"STL:  {stl_path}")
```

The `get_magnetic()` method:

1. Generates the core geometry (both halves)
2. Creates the bobbin
3. Builds each winding turn
4. Combines everything into a single assembly

## Step 3: Generate Individual Components

You can also generate components separately:

### Core Only

```python
core_geo = magnetic_data["core"]["geometricalDescription"]

step_path, stl_path = builder.get_core(
    "ETD49_core",
    core_geo,
    output_path="./output/"
)
```

### Bobbin Only

```python
bobbin_data = magnetic_data["coil"]["bobbin"]
winding_window = bobbin_data["processedDescription"]["windingWindows"][0]

step_path, stl_path = builder.get_bobbin(
    bobbin_data,
    winding_window,
    name="ETD49_bobbin",
    output_path="./output/"
)
```

### Winding Only

```python
winding_data = magnetic_data["coil"]

step_path, stl_path = builder.get_winding(
    winding_data,
    {"width": winding_window["width"], "height": winding_window["height"]},
    name="ETD49_winding",
    output_path="./output/"
)
```

## MAS Data Structure

```json
{
    "magnetic": {
        "core": {
            "geometricalDescription": [
                {
                    "type": "half set",
                    "shape": { "family": "etd", "dimensions": {...} },
                    "machining": [...]
                }
            ],
            "processedDescription": {
                "gapping": [...]
            }
        },
        "coil": {
            "bobbin": {
                "processedDescription": {
                    "columnDepth": 0.005,
                    "columnWidth": 0.005,
                    "columnThickness": 0.001,
                    "wallThickness": 0.001,
                    "columnShape": "rectangular",
                    "windingWindows": [{"height": 0.01, "width": 0.003}]
                }
            },
            "functionalDescription": [
                {
                    "name": "Primary",
                    "wire": {
                        "type": "round",
                        "conductingDiameter": {"nominal": 0.001},
                        "outerDiameter": {"nominal": 0.00105}
                    }
                }
            ],
            "turnsDescription": [
                {
                    "coordinates": [0.01, 0.005],
                    "winding": "Primary",
                    "parallel": 0
                }
            ]
        }
    }
}
```

## Next Steps

- [Technical Drawings Tutorial](technical-drawings.md) - generate 2D drawings
- [Toroidal Winding Tutorial](toroidal-winding.md) - toroidal example
- [API Reference](../api/builder.md) - full method documentation
