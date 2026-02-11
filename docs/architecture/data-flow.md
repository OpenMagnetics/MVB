# Data Flow

## Core Generation Pipeline

```mermaid
flowchart TD
    A[MAS JSON Input] --> B[flatten_dimensions]
    B --> C{Shape Family}
    C --> D[get_shape_base - 2D Sketch]
    D --> E[extrude_sketch - 3D Solid]
    E --> F[get_negative_winding_window]
    F --> G[Boolean Subtract]
    G --> H[get_shape_extras - Position]
    H --> I{Has Machining?}
    I -->|Yes| J[apply_machining - Cut Gaps]
    I -->|No| K[Scale to Meters]
    J --> K
    K --> L[Export STEP / STL]
```

## Dimension Flattening

MAS dimensions can be specified in three ways:

```json
// Plain number
"A": 0.042

// Nominal value
"A": {"nominal": 0.042}

// Min/max range (nominal is computed as average)
"A": {"minimum": 0.041, "maximum": 0.043}
```

The `flatten_dimensions()` function resolves all formats to a single numeric value:

```python
from OpenMagneticsVirtualBuilder.utils import flatten_dimensions

data = {
    "dimensions": {
        "A": {"minimum": 0.041, "maximum": 0.043},
        "B": {"nominal": 0.021},
        "C": 0.017
    }
}

flat = flatten_dimensions(data, scale_factor=1000)
# {"A": 42.0, "B": 21.0, "C": 17.0}  (converted to mm)
```

## Gapping / Machining

Core gaps are specified as machining operations in the geometrical description:

```json
{
    "machining": [
        {
            "type": "subtractive",
            "length": 0.0005,
            "coordinates": [0, 0, 0]
        }
    ]
}
```

The `apply_machining()` method creates a tool solid and performs a boolean subtraction from the core piece.

- **coordinates[0] == 0**: Center-leg gap (uses column width `F`)
- **coordinates[0] != 0**: Lateral-leg gap (uses half of `A`)

## Technical Drawing Pipeline

```mermaid
flowchart TD
    A[3D Core Shape] --> B{Format}
    B -->|SVG| C[HLR Projection]
    B -->|DXF| D[Cross-Section Slice]
    B -->|FCMacro| E[Cross-Section Slice]
    C --> F[Add Dimension Annotations]
    D --> G[DXF Edge Export]
    E --> H[FCMacro Script Generation]
    F --> I[SVG Output]
    G --> J[DXF Output]
    H --> K[FCMacro Output]
```

### SVG Generation

1. Shape is projected using OCC hidden-line removal (HLR)
2. Visible and hidden edges are separated
3. Dimension annotations are computed from shape bounding box
4. SVG markup is assembled with projection lines and labels

### DXF Generation

1. Shape is sliced at the principal plane (XY, XZ, or ZY)
2. Cross-section edges are extracted
3. Edges are written to DXF format via `ezdxf`

## Complete Magnetic Pipeline

```mermaid
flowchart TD
    A[MAS Magnetic Data] --> B[Core Generation]
    A --> C[Bobbin Generation]
    A --> D[Coil Generation]
    B --> E[Assembly]
    C --> E
    D --> E
    E --> F[Export STEP / STL]

    D --> D1[Parse Turns Description]
    D1 --> D2[Build Individual Turns]
    D2 --> D3{Wire Type}
    D3 -->|Round| D4[Torus Sweep]
    D3 -->|Rectangular| D5[Rectangular Sweep]
    D3 -->|Foil| D6[Foil Sweep]
    D4 --> D7[Combine Turns]
    D5 --> D7
    D6 --> D7
```

### Turn Hierarchy

1. **Turn**: Single wire loop around the core column
2. **Layer**: Multiple turns stacked vertically
3. **Section**: Multiple layers stacked radially
4. **Winding**: Complete winding (primary, secondary, etc.)
5. **Coil**: All windings combined
6. **Magnetic**: Core + bobbin + coil assembly
