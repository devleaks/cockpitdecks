# Stolen from another project :-). Without permission. 8-(.
# Good artists copy, great artists steal. Picasso.
# Adapted for X-Plane 11 and XPPython3.
#
import logging
import xp

from decimal import Decimal as D
from .xplane import Dataref

logger = logging.getLogger("XPDref")


class XPDref(Dataref):
    """
    Extends dataref to read (and write disabled) dataref through X-Plane SDK API.
    """

    def __init__(self, path: str, is_decimal:bool = False, is_string:bool = False, length:int = None):
        Dataref.__init__(self, path=path, is_decimal=is_decimal, is_string=is_string, length=length)

        self.ref = None
        self.inited = False

        self.xp_datatype = None
        self.xp_datatype_str = None
        self.xp_value = None
        self.dr_get = None
        self.dr_set = None
        self.dr_cast = None

        self.init()

    def init(self):
        if self.inited:
            return

        self.ref = xp.findDataRef(self.dataref)
        if self.ref is None:
            logger.warning(f"exists: dataref {self.dataref} not found")
            return

        self.xp_datatype = xp.getDataRefTypes(self.ref)

        # logger.debug(f"__init__: dataref {self.dataref} of type {self.xp_datatype} ({self.xp_datatype :b})")

        if self.is_array:
            if self.xp_datatype & xp.Type_IntArray:
                self.dr_get = xp.getDatavi
                self.dr_set = xp.setDatavi
                self.dr_cast = int
                self.xp_datatype_str = "IntArray"
            elif self.xp_datatype & xp.Type_FloatArray:
                self.dr_get = xp.getDatavf
                self.dr_set = xp.setDatavf
                self.dr_cast = float
                self.xp_datatype_str = "FloatArray"
            elif self.xp_datatype & xp.Type_Data:
                self.dr_get = xp.getDatab
                self.dr_set = xp.setDatab
                self.dr_cast = bytearray
                self.xp_datatype_str = "ByteArray"

            if self.dr_get:
                self.xp_length = self.dr_get(self.ref, None)
                # logger.debug(f"__init__: dataref {self.path}: array length {self.xp_length}")

        else:
            if self.xp_datatype & xp.Type_Int:
                self.dr_get = xp.getDatai
                self.dr_set = xp.setDatai
                self.dr_cast = int
                self.xp_datatype_str = "Int"
            elif self.xp_datatype & xp.Type_Float:
                self.dr_get = xp.getDataf
                self.dr_set = xp.setDataf
                self.dr_cast = float
                self.xp_datatype_str = "Float"
            elif self.xp_datatype & xp.Type_Double:
                self.dr_get = xp.getDatad
                self.dr_set = xp.setDatad
                self.dr_cast = bytearray
                self.xp_datatype_str = "Byte"

        if self.dr_get is None:  # this is the only one we use so far
            logger.error(f"__init__: dataref {self.path}: no data handler found for type {self.xp_datatype} ({self.xp_datatype})")

        self.inited = True
        logger.debug(f"__init__: dataref {self.path} ({self.get_datatype()}) ready")

        # force the initial value
        self.xp_value = self.value
        logger.debug(f"__init__: dataref {self.path}: initial value {self.xp_value}")

    def get_datatype(self, long:bool = False):
        s = self.xp_datatype_str
        if s.endswith("Array"):
            s = s + f"[{self.xp_length}]"
        if self.is_decimal:
            s = s + ", decimal"
        if self.is_string:
            s = s + ", string"
        if long:
            s = s + f" ({self.xp_datatype} ({self.xp_datatype :b}))"
        return s

    def exists(self) -> bool:
        if not self.inited:
            self.ref = xp.findDataRef(self.dataref)
            if self.ref is not None:
                self.init()
            else:
                logger.warning(f"exists: dataref {self.dataref} not found")
        return self.inited
    # def set(self, value):
    #     if self.is_array:
    #         self.dr_set(self.ref, value, self.index, len(value))
    #     else:
    #         self.dr_set(self.ref, self.dr_cast(value))

    def get(self):
        if self.exists():
            if self.dr_cast is None:
                logger.error(f"get: dataref {self.path}: no data handler found for type {self.xp_datatype} ({self.xp_datatype})")
                return None
            if self.is_array:
                values = []
                self.dr_get(self.ref, values=values, offset=self.index, count=1)
                if self.is_string:
                    return bytearray([x for x in values if x]).decode('utf-8')
                else:
                    # logger.debug(f"get: dataref {self.path}: got array {values}")
                    return values[0] if len(values) > 0 else None
            else:
                return self.dr_get(self.ref)
        else:
            logger.error(f"get: dataref {self.dataref}: cannot find")

    @property
    def value(self):
        if self.is_decimal:
            return self.decimal_value
        else:
            return self.get()

    # @value.setter
    # def value(self, value):
    #     self.__value = value

    @property
    def decimal_value(self):
        return D(self.get()).quantize('0.00')
