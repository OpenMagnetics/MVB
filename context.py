"""
Test context setup module.

This module sets up the environment for testing.
"""

import os
import sys

# Add the OpenMagneticsVirtualBuilder package to the path for direct imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src/OpenMagneticsVirtualBuilder')))

# Also add the tests directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'tests')))
