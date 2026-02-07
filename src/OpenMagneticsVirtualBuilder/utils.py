import enum
import numpy


class Meta(enum.EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        return True


class ShapeFamily(enum.Enum, metaclass=Meta):
    ETD = enum.auto()
    ER = enum.auto()
    EP = enum.auto()
    EPX = enum.auto()
    PQ = enum.auto()
    E = enum.auto()
    PM = enum.auto()
    P = enum.auto()
    RM = enum.auto()
    PLANAR_ER = enum.auto()
    EFD = enum.auto()
    U = enum.auto()
    EQ = enum.auto()
    PLANAR_E = enum.auto()
    PLANAR_EL = enum.auto()
    EC = enum.auto()
    UR = enum.auto()
    UT = enum.auto()
    LP = enum.auto()
    T = enum.auto()
    C = enum.auto()


def flatten_dimensions(data, scale_factor=1.0):
    import copy

    dimensions = copy.deepcopy(data["dimensions"])
    for k, v in dimensions.items():
        if isinstance(v, dict):
            if "nominal" not in v or v["nominal"] is None:
                if "maximum" not in v or v["maximum"] is None:
                    v["nominal"] = v["minimum"]
                elif "minimum" not in v or v["minimum"] is None:
                    v["nominal"] = v["maximum"]
                else:
                    v["nominal"] = round((v["maximum"] + v["minimum"]) / 2, 6)
        else:
            dimensions[k] = {"nominal": v}
    return {k: v["nominal"] * scale_factor for k, v in dimensions.items() if k != "alpha"}


class BuilderBase:
    """Shared base for FreeCADBuilder and CadQueryBuilder with common factory/families logic."""

    def factory(self, data):
        family = ShapeFamily[data["family"].upper().replace(" ", "_")]
        return self.shapers[family]

    def get_families(self):
        return {shaper.name.lower().replace("_", " "): self.factory({"family": shaper.name}).get_dimensions_and_subtypes() for shaper in self.shapers}


def decimal_ceil(a, precision=0):
    return numpy.true_divide(numpy.ceil(a * 10**precision), 10**precision)


def decimal_floor(a, precision=0):
    return numpy.true_divide(numpy.floor(a * 10**precision), 10**precision)
