# Magnetics Virtual Builder
This project holds all the Python scripts needed to produce FreeCAD and CadQuery related files from any magnetic defined following MAS schemas. These files include 2D and 3D models, meshes, and technical drawings.

<img width="997" height="807" alt="image" src="https://github.com/user-attachments/assets/23fb85e2-7e76-4db1-9af5-768ac213d52f" />

## Features

### Core Generation
Generate 3D models of magnetic cores from shape definitions.

### Complete Magnetic Generation
Generate complete 3D models of magnetic components including:
- Core geometry
- Bobbin
- Coil windings (turns)

## Installation

```bash
pip install OpenMagneticsVirtualBuilder
```

Or install from source:

```bash
git clone https://github.com/OpenMagnetics/MVB.git
cd MVB
pip install -e .
```

## Usage

### Basic Setup

```python
from OpenMagneticsVirtualBuilder.builder import Builder

# Create builder with CadQuery engine (default)
builder = Builder("CadQuery")

# Or use FreeCAD engine (requires FreeCAD installation)
builder = Builder("FreeCAD")
```

### List Available Core Shapes

```python
from OpenMagneticsVirtualBuilder.builder import Builder

builder = Builder()
families = builder.get_families()

# families is a dict with shape family names as keys
for family_name, family_info in families.items():
    print(f"Family: {family_name}")
    print(f"  Info: {family_info}")
```

### Building a Core

```python
from OpenMagneticsVirtualBuilder.builder import Builder

# Core with geometrical description (from MAS schema)
geometrical_description = [...]  # Your core geometry data

builder = Builder()
result = builder.get_core("my_core", geometrical_description)
# Returns tuple: (step_path, stl_path)
```

### Building a Complete Magnetic Component

```python
from OpenMagneticsVirtualBuilder.builder import Builder

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
step_path, stl_path = builder.get_magnetic(magnetic_data, "my_magnetic")
print(f"STEP file: {step_path}")
print(f"STL file: {stl_path}")
```

### Building Just the Bobbin

```python
from OpenMagneticsVirtualBuilder.builder import Builder

bobbin_data = {
    'family': 'standard',
    'material': 'nylon',
    'dimensions': {
        'wallThickness': 0.0005,
        'flangeThickness': 0.001,
        'flangeExtension': 0.002,
        'pinCount': 0
    }
}

winding_window = {
    'width': 0.01,
    'height': 0.02,
    'coordinates': [0.005, 0]
}

builder = Builder()
result = builder.get_bobbin(bobbin_data, winding_window, name="my_bobbin")
```

### Building Just the Winding

```python
from OpenMagneticsVirtualBuilder.builder import Builder

winding_data = {
    'name': 'primary',
    'type': 'round_wire',
    'wireDiameter': 0.0005,
    'insulationThickness': 0.00005,
    'numberOfTurns': 10,
    'numberOfLayers': 2,
    'windingDirection': 'cw'
}

bobbin_dims = {
    'width': 0.008,
    'height': 0.015
}

builder = Builder()
result = builder.get_winding(winding_data, bobbin_dims, name="my_winding")
```

## CAD Engines

The builder supports two CAD engines:
- **CadQuery** (default): Cross-platform, Python-native, no system dependencies
- **FreeCAD**: Full CAD functionality with additional features like SVG/DXF drawings, requires FreeCAD installation

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
