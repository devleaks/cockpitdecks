"""
Main Loupedeck and LoupedeckLive classes.
"""
import logging
import mido
from typing import List, Tuple

from .Devices import XTouchMini

logger = logging.getLogger("DeviceManager")


class DeviceManager:

    @staticmethod
    def list() -> Tuple[str, str]:
        """ Lists serial port names

            :raises EnvironmentError:
                On unsupported or unknown platforms
            :returns:
                A list of the serial ports available on the system
        """
        names: List[str] = list()

        for name in mido.get_input_names():
            names.append(("in",name))
        for name in mido.get_output_names():
            names.append(("out",name))
        return names


    def __init__(self):
        pass

    def enumerate(self):
        devices = list()

        names = DeviceManager.list()
        has_one = False
        # @todo: List loupedeck live devices only
        for n in names:
            name = list(n)
            if name[1].startswith("X-TOUCH MINI") and not has_one:
                has_one = True
                l = XTouchMini(input_device_name=name[1], output_device_name=name[1])
                devices.append(l)

        return devices