# Stolen from another project :-). Without permission. 8-(.
# Good artists copy, great artists steal. Picasso.
#
from decimal import Decimal as D

from XPLMDataAccess import *
from XPLMPlugin import *

MSG_ADD_DATAREF = 0x01000000


class XPCustomDRef(object):

    xplm_types = {
        'int': xplmType_Int,
        'float': xplmType_Float,
        'double': xplmType_Double,
        'int_array': xplmType_IntArray,
    }

    dref = None
    data_type = None
    signature = None
    value = 0
    writeable = False
    refcon = 0

    read_int_cb = None
    read_float_cb = None
    read_double_cb = None
    read_int_array_cb = None

    array_len = 0

    source_value = None

    python_interface = None

    notify_dre = True

    def __init__(
            self, python_interface, signature, data_type, initial_value=None, writeable=False, refcon=0, **kwargs):

        self.python_interface = python_interface

        self.signature = signature
        self.writeable = writeable
        if not refcon:
            self.refcon = signature

        if "[" in data_type:
            self.array_len = int(data_type[data_type.find('[') + 1:data_type.find(']')].split(':')[0])
            data_type = data_type[:data_type.find('[')]

            if data_type == 'int_array':
                self.value = initial_value if initial_value is not None else [int(0)] * self.array_len
                self.read_int_array_cb = self.read_value_int_array_cb
            else:
                print('type not supported')
                return None

        else:

            if data_type == 'int':
                self.value = initial_value if initial_value is not None else int(0)
                self.read_int_cb = self.read_value_cb
            elif data_type == 'float':
                self.value = initial_value if initial_value is not None else float(0)
                self.read_float_cb = self.read_value_cb
            elif data_type == 'double':
                self.value = initial_value if initial_value is not None else float(0)
                self.read_double_cb = self.read_value_cb
            else:
                print('type not supported')
                return None

        self.data_type = data_type

        self.register()

    def register(self):

        self.dref = XPLMRegisterDataAccessor(
            self.signature,  # inDataName
            self.xplm_types[self.data_type],  # inDataType
            1 if self.writeable else 0,  # inIsWritable
            self.read_int_cb,  # inReadInt
            None,  # inWriteInt
            self.read_float_cb,  # inReadFloat
            None,  # inWriteFloat
            self.read_double_cb,  # inReadDouble
            None,  # inWriteDouble
            self.read_int_array_cb,  # inReadIntArray
            None,  # inWriteIntArray
            None,  # inReadFloatArray
            None,  # inWriteFloatArray
            None,  # inReadData
            None,  # inWriteData
            self.refcon,  # inReadRefcon
            0,  # inWriteRefcon
        )

        # logger.debug(('dref_register={}:{}'.format(self.signature, self.dref))

    def unregister(self):
        if self.dref:
            XPLMUnregisterDataAccessor(self.dref)

    def read_value_cb(self, inRefCon):
        print(f"read_value_cb={inRefCon}")
        return self.value

    def read_value_int_array_cb(self, inRefcon, out, offset, maximum):
        if out is None:
            return self.array_len
        out.extend(self.value[offset:offset + maximum])
        return len(out)

    def notify_datarefeditor(self, plugin_id):
        if self.notify_dre:
            XPLMSendMessageToPlugin(plugin_id, MSG_ADD_DATAREF, self.signature)

    def __repr__(self):
        return 'sig:{} - value:{} - dref:{} - data_type:{}'.format(
            self.signature, self.value, self.dref, self.data_type)


class XPCustomDRefsMgr(object):

    drefs = {}

    python_interface = None

    def __init__(self, python_interface=None):

        self.python_interface = python_interface
        super(XPCustomDRefsMgr, self).__init__()

    def create_dref(self, signature, data_type, writeable=False, refcon=0, dref_class=XPCustomDRef, **kwargs):

        self.drefs[signature] = dref_class(
            self.python_interface, signature, data_type, writeable=writeable, refcon=0, **kwargs)
        return self.drefs[signature]

    def get_value(self, signature):
        return self.drefs[signature].value

    def set_value(self, signature, value):
        self.drefs[signature].value = value

    def exists(self, signature):
        return signature in self.drefs

    def notify_datarefeditor(self, plugin_id):
        for signature in self.drefs:
            self.drefs[signature].notify_datarefeditor(plugin_id)

    def unregister_all(self):
        for signature in self.drefs:
            self.drefs[signature].unregister()

    def destroy_dref(self, signature):
        self.drefs[signature].unregister()
        self.drefs.pop(signature)

    def destroy_all(self):
        self.unregister_all()
        self.drefs = {}


class XPDref:
    '''
    Easy Dataref access

    Copyright (C) 2011  Joan Perez i Cauhe
    '''

    dr_get = None
    dr_set = None
    dr_cast = None
    dref = None

    is_decimal = False
    is_string = False

    last_value = None

    is_array = False
    index = 0
    count = 0
    last = 0

    dref_mapping = {
        'int': {
            'dr_get': XPLMGetDatai,
            'dr_set': XPLMSetDatai,
            'dr_cast': int,
        },
        'float': {
            'dr_get': XPLMGetDataf,
            'dr_set': XPLMSetDataf,
            'dr_cast': float,
        },
        'double': {
            'dr_get': XPLMGetDatad,
            'dr_set': XPLMSetDatad,
            'dr_cast': float,
        },
    }

    dref_mapping_array = {
        'int': {
            'dr_get': XPLMGetDatavi,
            'dr_set': XPLMSetDatavi,
            'dr_cast': int,
        },
        'float': {
            'dr_get': XPLMGetDatavf,
            'dr_set': XPLMSetDatavf,
            'dr_cast': float,
        },
        'byte': {
            'dr_get': XPLMGetDatab,
            'dr_set': XPLMSetDatab,
            'dr_cast': bytearray,
        },
        'string': {
            'dr_get': XPLMGetDatab,
            'dr_set': XPLMSetDatab,
            'dr_cast': bytearray,
        },
    }

    def __init__(self, signature, dref_type="float", is_decimal=False):

        if '[' in dref_type:

            self.is_array = True

            range_array = dref_type[dref_type.find('[') + 1:dref_type.find(']')].split(':')
            if len(range_array) < 2:
                range_array.insert(0, '0')

            dref_type = dref_type[:dref_type.find('[')]
            dref_mapping = self.dref_mapping_array

            self.index = int(range_array[0])
            self.count = int(range_array[1]) - int(range_array[0]) + 1
            self.last = int(range_array[1])

        else:

            dref_mapping = self.dref_mapping

        if dref_type not in dref_mapping:
            print("ERROR: invalid DataRef type", dref_type)
            return

        if dref_type == "string":
            self.is_string = True

        self.dr_get = dref_mapping[dref_type]['dr_get']
        self.dr_set = dref_mapping[dref_type]['dr_set']
        self.dr_cast = dref_mapping[dref_type]['dr_cast']

        self.dref = XPLMFindDataRef(signature)
        if not self.dref:
            print("Can't find DataRef " + signature)
            return

        self.is_decimal = is_decimal

        # force the initial value
        _ = self.value

    def set(self, value):
        if self.is_array:
            self.dr_set(self.dref, value, self.index, len(value))
        else:
            self.dr_set(self.dref, self.dr_cast(value))

    def get(self):
        if self.is_array:
            values = []
            self.dr_get(self.dref, values, self.index, self.count)
            if self.is_string:
                return bytearray([x for x in values if x]).decode('utf-8')
            else:
                return values
        else:
            return self.dr_get(self.dref)

    @property
    def value(self):
        if self.is_decimal:
            return self.decimal_value
        else:
            return self.get()

    @value.setter
    def value(self, value):
        self.__value = value

    @property
    def decimal_value(self):
        return D(self.get()).quantize('0.00')
