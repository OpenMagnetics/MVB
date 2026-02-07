"""Shared shape dimension and subtype configurations for both FreeCAD and CadQuery engines."""

P_DIMENSIONS_AND_SUBTYPES = {
    1: ["A", "B", "C", "D", "E", "F", "G", "H"],
    2: ["A", "B", "C", "D", "E", "F", "G", "H"],
    3: ["A", "B", "D", "E", "F", "G", "H"],
    4: ["A", "B", "C", "D", "E", "F", "G", "H"],
}

RM_DIMENSIONS_AND_SUBTYPES = {
    1: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
    2: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
    3: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
    4: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
}

UR_DIMENSIONS_AND_SUBTYPES = {1: ["A", "B", "C", "D", "H"], 2: ["A", "B", "C", "D", "H"], 3: ["A", "B", "C", "D", "F", "H"], 4: ["A", "B", "C", "D", "F", "G", "H"]}

U_DIMENSIONS_AND_SUBTYPES = {1: ["A", "B", "C", "D", "E"]}

# Default cross-section offsets per shape family and plane.
# 0.0 works for most shapes since geometry is centered at origin.
# Values are in the same unit as the shape dimensions (mm after scaling).
CROSS_SECTION_OFFSETS = {
    "e": {"zy": 0.0},
    "etd": {"zy": 0.0},
    "er": {"zy": 0.0},
    "ep": {"zy": 0.0},
    "epx": {"zy": 0.0},
    "efd": {"zy": 0.0},
    "eq": {"zy": 0.0},
    "ec": {"zy": 0.0},
    "lp": {"zy": 0.0},
    "planar_e": {"zy": 0.0},
    "planar_er": {"zy": 0.0},
    "planar_el": {"zy": 0.0},
    "pq": {"zy": 0.0},
    "rm": {"zy": 0.0},
    "pm": {"zy": 0.0},
    "p": {"zy": 0.0},
    "u": {"zy": 0.0},
    "ur": {"zy": 0.0},
    "ut": {"zy": 0.0},
    "c": {"zy": 0.0},
    "t": {"zy": 0.0},
}
