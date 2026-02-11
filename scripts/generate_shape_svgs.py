#!/usr/bin/env python3
"""Generate representative SVG images for each shape family.

Produces SVG technical drawings for the documentation shape catalog.
Output goes to docs/assets/svg/.

Usage:
    python scripts/generate_shape_svgs.py
"""

import os
import sys
import copy

# Add the source directory so we can import the builder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "OpenMagneticsVirtualBuilder"))

from builder import Builder  # noqa: E402

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "assets", "svg")

# Representative shapes for each family (minimal dimension sets)
REPRESENTATIVE_SHAPES = {
    "e": {
        "name": "E 42/21/20",
        "family": "e",
        "familySubtype": "1",
        "dimensions": {
            "A": {"nominal": 0.042},
            "B": {"nominal": 0.021},
            "C": {"nominal": 0.0157},
            "D": {"nominal": 0.0145},
            "E": {"nominal": 0.0296},
            "F": {"nominal": 0.0142},
        },
    },
    "pq": {
        "name": "PQ 40/40",
        "family": "pq",
        "familySubtype": "1",
        "dimensions": {
            "A": {"nominal": 0.0404},
            "B": {"nominal": 0.0386},
            "C": {"nominal": 0.0287},
            "D": {"nominal": 0.0275},
            "E": {"nominal": 0.0285},
            "F": {"nominal": 0.0135},
        },
    },
    "t": {
        "name": "T 25/15/10",
        "family": "t",
        "familySubtype": "1",
        "dimensions": {
            "A": {"nominal": 0.0254},
            "B": {"nominal": 0.0152},
            "C": {"nominal": 0.0102},
        },
    },
}


def generate_svgs():
    """Generate SVG files for representative shapes."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    builder = Builder("CadQuery")

    for family_name, shape_data in REPRESENTATIVE_SHAPES.items():
        print(f"Generating SVG for {family_name}...")
        try:
            if family_name == "t":
                geo_desc = [
                    {
                        "type": "closed piece",
                        "shape": copy.deepcopy(shape_data),
                        "rotation": [0, 0, 0],
                        "coordinates": [0, 0],
                        "machining": None,
                    }
                ]
            else:
                geo_desc = [
                    {
                        "type": "half set",
                        "shape": copy.deepcopy(shape_data),
                        "rotation": [0, 0, 0],
                        "coordinates": [0, 0],
                        "machining": None,
                    },
                ]

            results = builder.get_svg_drawings(
                f"{family_name}_example",
                geo_desc,
                output_path=OUTPUT_DIR,
            )
            print(f"  OK: {family_name}")
        except Exception as e:
            print(f"  SKIP: {family_name} ({e})")


if __name__ == "__main__":
    generate_svgs()
