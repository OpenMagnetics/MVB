# Quick Start

Generate your first magnetic core in 5 minutes.

## 1. Create a Builder

```python
from OpenMagneticsVirtualBuilder.builder import Builder

builder = Builder("CadQuery")  # default engine, no system deps
```

## 2. List Available Families

```python
families = builder.get_families()
for name, info in families.items():
    print(f"{name}: {info}")
```

Output:

```
etd: {1: ['A', 'B', 'C', 'D', 'E', 'F']}
er: {1: ['A', 'B', 'C', 'D', 'E', 'F']}
ep: {1: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']}
...
```

## 3. Generate a Core

Core generation uses MAS geometrical descriptions. Each piece of the core is described by its shape family, dimensions, and optional machining (gapping):

```python
import json

# E 42/21/20 core - two halves with a center-leg gap
geometrical_description = [
    {
        "type": "half set",
        "shape": {
            "family": "etd",
            "name": "ETD 42/21/20",
            "dimensions": {
                "A": {"nominal": 0.0422},
                "B": {"nominal": 0.0214},
                "C": {"nominal": 0.01720},
                "D": {"nominal": 0.01490},
                "E": {"nominal": 0.03020},
                "F": {"nominal": 0.01370}
            }
        },
        "machining": []
    },
    {
        "type": "half set",
        "shape": {
            "family": "etd",
            "name": "ETD 42/21/20",
            "dimensions": {
                "A": {"nominal": 0.0422},
                "B": {"nominal": 0.0214},
                "C": {"nominal": 0.01720},
                "D": {"nominal": 0.01490},
                "E": {"nominal": 0.03020},
                "F": {"nominal": 0.01370}
            }
        },
        "rotation": [3.14159, 0, 0],
        "machining": []
    }
]

step_path, stl_path = builder.get_core(
    "my_etd42",
    geometrical_description,
    output_path="./output/"
)
print(f"STEP: {step_path}")
print(f"STL:  {stl_path}")
```

## 4. Generate a Technical Drawing

```python
core_data = {
    "geometricalDescription": geometrical_description,
    "processedDescription": {
        "gapping": [
            {
                "type": "subtractive",
                "length": 0.0005,
                "coordinates": [0, 0, 0]
            }
        ]
    }
}

svg = builder.get_core_gapping_technical_drawing(
    "my_etd42_drawing",
    core_data,
    output_path="./output/"
)
```

## 5. Generate a Complete Magnetic

For a full magnetic component (core + bobbin + coil), load MAS JSON data:

```python
import json

with open("tests/testData/ETD49_N87_10uH_5T.json") as f:
    magnetic_data = json.load(f)

step_path, stl_path = builder.get_magnetic(
    magnetic_data,
    "ETD49_magnetic",
    output_path="./output/"
)
```

## Next Steps

- [Core Generation Tutorial](../tutorials/core-generation.md) - detailed walkthrough
- [Complete Magnetic Tutorial](../tutorials/complete-magnetic.md) - full assembly example
- [Shape Catalog](../shapes/index.md) - browse all 21 shape families
- [API Reference](../api/builder.md) - full method documentation
