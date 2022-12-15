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


def decimal_ceil(a, precision=0):
    return numpy.true_divide(numpy.ceil(a * 10**precision), 10**precision)


def decimal_floor(a, precision=0):
    return numpy.true_divide(numpy.floor(a * 10**precision), 10**precision)
