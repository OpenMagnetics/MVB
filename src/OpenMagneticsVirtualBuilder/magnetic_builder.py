"""
Magnetic Builder Module for OpenMagnetics Virtual Builder (MVB)

This module provides backward compatibility by re-exporting the magnetic building
functionality from cadquery_builder.py.

All bobbin, coil, and magnetic building functionality is now integrated into
the main CadQueryBuilder class for a unified API.

The hierarchical structure is:
- Turn: single wire loop around core (get_turn)
- Layer: multiple turns stacked vertically (get_layer)
- Section: multiple layers stacked radially (get_section)
- Winding: complete winding - primary, secondary, etc. (get_winding)
- Coil: all windings combined (get_coil)
- Magnetic: complete assembly - core + bobbin + coil (get_magnetic)
"""

# Re-export everything from cadquery_builder for backward compatibility
from cadquery_builder import (
    # Main builder class
    CadQueryBuilder,
)

# Aliases for backward compatibility with old class names
CadQueryBobbinBuilder = CadQueryBuilder
CadQueryCoilBuilder = CadQueryBuilder
CadQueryMagneticBuilder = CadQueryBuilder


if __name__ == "__main__":
    # Example usage
    winding_window = {"height": 0.01, "width": 0.003}
    bobbin_data = {
        "processedDescription": {
            "columnDepth": 0.005,
            "columnWidth": 0.005,
            "columnThickness": 0.001,
            "wallThickness": 0.001,
            "columnShape": "rectangular",
            "windingWindows": [winding_window],
        }
    }

    builder = CadQueryBuilder()
    step_file, stl_file = builder.get_bobbin(bobbin_data, winding_window, "test_bobbin", export_files=True)

    if step_file or stl_file:
        print("Bobbin exported to:")
        if step_file:
            print(f"  STEP: {step_file}")
        if stl_file:
            print(f"  STL: {stl_file}")
    else:
        print("No bobbin generated (zero thickness)")
