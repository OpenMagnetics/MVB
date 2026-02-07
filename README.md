# Magnetics Virtual Builder
This project holds all the Python scripts needed to produce FreeCAD and CadQuery related files from any magnetic defined following MAS schemas. These files include 2D and 3D models, meshes, and technical drawings.

## Features

### Core Generation
Generate 3D models of magnetic cores from shape definitions.

### Complete Magnetic Generation
Generate complete 3D models of magnetic components including:
- Core geometry
- Bobbin
- Coil windings (turns)

## Usage

### Building a Core
```python
from builder import Builder
import json

# Load shape data
with open('core_shapes.ndjson', 'r') as f:
    shape_data = json.loads(f.readline())

# Create core
builder = Builder()  # Uses CadQuery by default
result = builder.get_core("my_core", geometrical_description)
```

### Building a Complete Magnetic Component
```python
from builder import Builder
import json

# Load MAS data with core, coil, and bobbin information
magnetic_data = {
    'core': {
        'geometricalDescription': [...]  # Core geometry
    },
    'coil': {
        'bobbin': {
            'processedDescription': {
                'columnDepth': 0.005,
                'columnWidth': 0.005,
                'columnThickness': 0.001,
                'wallThickness': 0.001,
                'columnShape': 'rectangular',
                'windingWindows': [{'height': 0.01, 'width': 0.003}]
            }
        },
        'functionalDescription': [
            {
                'name': 'Primary',
                'wire': {
                    'type': 'round',
                    'conductingDiameter': {'nominal': 0.001},
                    'outerDiameter': {'nominal': 0.00105}
                }
            }
        ],
        'turnsDescription': [
            {
                'name': 'Turn 1',
                'coordinates': [0.01, 0.005],
                'length': 0.044,
                'winding': 'Primary',
                'parallel': 0
            }
        ]
    }
}

builder = Builder()
result = builder.get_magnetic(magnetic_data, "my_magnetic")
print(f"Files created: {result['files']}")
```

### Building Just the Bobbin
```python
from builder import Builder

bobbin_data = {
    'processedDescription': {
        'columnDepth': 0.005,
        'columnWidth': 0.005,
        'columnThickness': 0.001,
        'wallThickness': 0.001,
        'columnShape': 'rectangular',  # or 'round'
        'windingWindows': [{'height': 0.01, 'width': 0.003}]
    }
}

builder = Builder()
result = builder.get_bobbin(bobbin_data, "my_bobbin")
```

### Building Just the Coil (Turns)
```python
from builder import Builder

coil_data = {
    'bobbin': {...},  # Bobbin processed description
    'functionalDescription': [...],  # Winding descriptions with wire info
    'turnsDescription': [...]  # Turn coordinates and properties
}

builder = Builder()
result = builder.get_coil(coil_data, project_name="my_coil")
```

## Engines

The builder supports two CAD engines:
- **CadQuery** (default): Cross-platform, Python-native
- **FreeCAD**: Full CAD functionality, requires FreeCAD installation

```python
# Use CadQuery (default)
builder = Builder("CadQuery")

# Use FreeCAD
builder = Builder("FreeCAD")
```

## Output Formats

- **STEP**: Standard CAD exchange format
- **STL**: Mesh format for 3D printing and visualization
- **OBJ**: Mesh format (FreeCAD engine)
- **SVG**: Technical drawings (FreeCAD engine)

## MAS Data Format

The Magnetic Analysis Specification (MAS) format is used by OpenMagnetics to describe magnetic components. Key structures include:

- **Core**: Shape, material, gapping, dimensions
- **Coil**: Bobbin, windings, turns
- **Bobbin**: Column dimensions, wall thickness, winding windows
