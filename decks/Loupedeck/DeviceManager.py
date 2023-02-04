"""
Main Loupedeck and LoupedeckLive classes.
"""
import glob
import logging
import serial
import sys
from .Devices import LoupedeckLive

logger = logging.getLogger("DeviceManager")
VERBOSE = False

class DeviceManager:

    @staticmethod
    def list():
        """ Lists serial port names

            :raises EnvironmentError:
                On unsupported or unknown platforms
            :returns:
                A list of the serial ports available on the system
        """
        if sys.platform.startswith("win"):
            ports = [f"COM{i}" for i in range(1, 256)]
        elif sys.platform.startswith("linux") or sys.platform.startswith("cygwin"):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob("/dev/tty[A-Za-z]*")
        elif sys.platform.startswith("darwin"):
            ports = glob.glob("/dev/tty.*")
        else:
            raise EnvironmentError("Unsupported platform")

        logger.debug(f"list: listing ports..")
        result = []
        for port in ports:
            try:
                logger.debug(f"trying {port}..")
                s = serial.Serial(port)
                s.close()
                result.append(port)
                logger.debug(f"..added {port}")
            except (OSError, serial.SerialException):
                logger.debug(f".. not added {port}", exc_info=VERBOSE)
        logger.debug(f"list: ..listed")
        return result

    def __init__(self):
        pass

    def enumerate(self):
        loupedecks = list()

        paths = DeviceManager.list()
        for path in paths:
            l = LoupedeckLive(path=path)
            if l.is_loupedeck():
                logger.debug(f"enumerate: added Loupedeck device at {path}")
                loupedecks.append(l)

        return loupedecks