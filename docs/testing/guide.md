# Testing Guide

## Running Tests

### All Tests

```bash
cd /path/to/MVB
python -m unittest tests.test_builder
```

### Single Test

```bash
python -m unittest tests.test_builder.Tests.test_all_shapes_generated
```

### Specific Test Modules

```bash
# 2D drawing tests
python -m unittest tests.test_2d_drawings

# Assembly tests
python -m unittest tests.test_assembly

# Bobbin tests
python -m unittest tests.test_bobbin

# Winding tests
python -m unittest tests.test_winding

# Full pipeline tests
python -m unittest tests.test_full_pipeline

# Complete magnetic tests
python -m unittest tests.test_magnetic
```

## Test Data

Test data files live in `tests/testData/`:

| File | Description |
|------|-------------|
| `ETD49_N87_10uH_5T.json` | ETD49 magnetic with N87 material |
| `T402416_edge40_4uH_8T.json` | Toroidal magnetic |
| `C20_30u_8T_5mm.json` | C-core magnetic |
| `PQ4040_10u_6T_foil.json` | PQ40 with foil winding |
| `concentric_*.json` | Various concentric winding configs |
| `toroidal_*.json` | Various toroidal winding configs |

### MAS Core Shapes

The main shape generation tests require the MAS repository:

```bash
git clone https://github.com/OpenMagnetics/MAS.git ../MAS
```

The `core_shapes.ndjson` file at `../MAS/data/core_shapes.ndjson` contains
all standard core shape definitions.

## Skipped Families

The following shape families are skipped in test_builder:

- `ui` - U + I bar combination
- `pqi` - PQ + I bar combination
- `ut` - UT shape (limited support)

## Test Output

Tests produce output files in the `output/` directory at the project root.
The `setUpClass` method cleans this directory before each test run.

## Test Structure

```
tests/
├── context.py              # Path setup for imports
├── test_builder.py         # Main shape generation tests
├── test_2d_drawings.py     # SVG/DXF/FCMacro drawing tests
├── test_assembly.py        # Assembly generation tests
├── test_bobbin.py          # Bobbin generation tests
├── test_winding.py         # Winding generation tests
├── test_full_pipeline.py   # End-to-end pipeline tests
├── test_magnetic.py        # Complete magnetic tests
└── testData/               # JSON test data files
```

## Writing New Tests

Tests use Python's standard `unittest` framework:

```python
import unittest
import context  # noqa: F401
from builder import Builder

class TestMyFeature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = Builder("CadQuery")

    def test_something(self):
        result = self.builder.get_core("test", geo_desc)
        self.assertIsNotNone(result)
```

The `context.py` module adds the source directory to `sys.path` so that
imports work correctly from the test directory.
