# Base classes for interface with the simulation software
#
from __future__ import annotations
import threading
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see when simulator_data are updated
# logger.setLevel(logging.DEBUG)


class Instruction(ABC):
    """An Instruction is sent to the Simulator to execute an action."""

    def __init__(self, name: str, performer=None, delay: float = 0.0, condition: str | None = None) -> None:
        super().__init__()
        self.name = name
        self.performer = performer
        self.delay = delay
        self.condition = condition

        self._timer = None

    @abstractmethod
    def _execute(self):
        if self.performer is not None and hasattr(self.performer, "execute"):
            self.performer.execute(instruction=self)
        self.clean_timer()

    @abstractmethod
    def _check_condition(self):
        return True

    def clean_timer(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def execute(self):
        if not self._check_condition():
            logger.debug(f"{self.name} not allowed to run")
            return
        if self._timer is None and self.delay > 0:
            self._timer = threading.Timer(self.delay, self._execute, args=[simulator])
            self._timer.start()
            logger.debug(f"{self.name} will be executed in {self.delay} secs")
            return
        self._execute()


class MacroInstruction(Instruction):
    """A Macro Instruction is a collection of individual Instruction.
    Each instruction comes with its condition for execution and delay since activation.
    (Could have been called Instructions (plural form))
    """

    def __init__(self, name: str, instructions: dict):
        Instruction.__init__(self, name=name)
        self.instructions = instructions
        self._instructions = []
        self.init()

    def __str__(self) -> str:
        return self.name + f" ({', '.join([c.name for c in self._instructions])}"

    def init(self):
        pass

    def _check_condition(self):
        # condition checked in each individual instruction
        return True

    def _execute(self):
        for instruction in self._instructions:
            instruction.execute()
