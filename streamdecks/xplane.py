import logging

import xp

from .XPDref import XPDref
logger = logging.getLogger("XplaneAPI")


class XPlaneAPI:

    def __init__(self, config: dict = []):
        self.config = config

    def commandOnce(self, command: str):
        logger.debug(f"commandOnce: executing {command}")

    def commandBegin(self, command: str):
        logger.debug(f"commandBegin: executing {command}")

    def commandEnd(self, command: str):
        # cmdref = xp.findCommand(command)
        # xp.XPLMCommandEnd(cmdref)
        logger.debug(f"commandEnd: executing {command}")

    def read(self, dataref: str):
        return XPDref(dataref)
