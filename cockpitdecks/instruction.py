# Base classes for interface with the simulation software
#
from __future__ import annotations
import threading
import logging
from abc import ABC, abstractmethod

from cockpitdecks import CONFIG_KW
from .strvar import Formula

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see when simulator_variable are updated
# logger.setLevel(logging.DEBUG)


class InstructionFactory:
    """An InstructionFactory is an entity capable of generating instructions
    Often, the entity generates instruction it will perform.
    """

    def instruction_factory(self, name: str, instruction_block: dict) -> Instruction:
        raise NotImplementedError("Please implement InstructionFactory.instruction_factory method")


class InstructionPerformer:
    """An InstructionFactory is an entity capable of generating instructions
    Often, the entity generates instruction it will perform.
    """

    def execute(self, instruction) -> bool:
        raise NotImplementedError("Please implement InstructionFactory.instruction_factory method")


class Instruction(ABC):
    """An Instruction to execute an action by a Performer.
    Often, the Performer is an InstructionFactory and generates the Instruction it will later execute.
    """

    INSTRUCTION_NAME = "undefined"

    def __init__(
        self, name: str, performer: InstructionPerformer, factory: InstructionFactory | None = None, delay: float = 0.0, condition: str | None = None
    ) -> None:
        self.name = name
        self.performer = performer
        self.factory = factory
        self.delay = delay
        self.condition = condition
        self._condition = None

        self._timer: threading.Timer | None = None

        if self.delay is None:
            self.delay = 0

        if self.condition is not None:
            if "${" in self.condition:
                self._condition = Formula(owner=self.performer, formula=self.condition)
            else:  # we assume the confition is a single dataref, we enclose it in ${} to make it a formula
                self._condition = Formula(owner=self.performer, formula=f"${{{self.condition}}}")

    @classmethod
    def int_name(cls) -> str:
        return cls.INSTRUCTION_NAME

    def __str__(self) -> str:
        return f"{self.INSTRUCTION_NAME} {self.name}"

    @staticmethod
    def all_subclasses(cls) -> list:
        """Returns the list of all subclasses.

        Recurses through all sub-sub classes

        Returns:
            [list]: list of all subclasses

        Raises:
            ValueError: If invalid class found in recursion (types, etc.)
        """
        if cls is type:
            raise ValueError("Invalid class - 'type' is not a class")
        subclasses = set()
        stack = []
        try:
            stack.extend(cls.__subclasses__())
        except (TypeError, AttributeError) as ex:
            raise ValueError("Invalid class" + repr(cls)) from ex
        while stack:
            sub = stack.pop()
            subclasses.add(sub)
            try:
                stack.extend(s for s in sub.__subclasses__() if s not in subclasses)
            except (TypeError, AttributeError):
                continue
        return list(subclasses)

    @abstractmethod
    def _execute(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def _check_condition(self) -> bool:
        raise NotImplementedError

    def clean_timer(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def execute(self) -> bool:
        self.clean_timer()
        if not self._check_condition():
            logger.debug(f"{self.name} not allowed to run")
            return False
        if self._timer is None and self.delay > 0:
            self._timer = threading.Timer(self.delay, self._execute)
            self._timer.start()
            logger.debug(f"{self.name} will be executed in {self.delay} secs")
            return True
        return self._execute()


class MacroInstruction(Instruction):
    """A Macro Instruction is a collection of individual Instruction.
    Each instruction comes with its condition for execution and delay since activation.
    (Could have been called Instructions (plural form))
    """

    INSTRUCTION_NAME = "macro"

    def __init__(
        self, name: str, performer: InstructionPerformer, factory: InstructionFactory, instructions: dict, delay: float = 0.0, condition: str | None = None
    ) -> None:
        Instruction.__init__(self, name=name, performer=performer, factory=factory, delay=delay, condition=condition)
        self.instructions = instructions
        self._instructions = []
        self.init()

    def __str__(self) -> str:
        return f"{self.name} ({', '.join([c.name for c in self._instructions])})"

    def init(self):
        total_delay = 0
        count = 0
        if self.performer is not None:
            for c in self.instructions:
                total_delay = total_delay + c.get(CONFIG_KW.DELAY.value, 0)
                if total_delay > 0:
                    c[CONFIG_KW.DELAY.value] = total_delay
                ci = self.factory.instruction_factory(name=f"{self.name}-{count}", instruction_block=c)
                if ci is not None:
                    self._instructions.append(ci)
                count = count + 1
        else:
            logger.warning(f"{self.name} has no performer")

    def _check_condition(self) -> bool:
        # condition checked in each individual instruction
        if self.condition is None:
            return True
        return self._condition.value != 0


    def _execute(self):
        for instruction in self._instructions:
            instruction.execute()


class NoOperation(Instruction):

    INSTRUCTION_NAME = "no-op"

    def __init__(self, name: str, delay: float = 0.0, condition: str | None = None):
        Instruction.__init__(self, name=name, performer=None)

    def _check_condition(self):
        # condition checked in each individual instruction
        return True

    def _execute(self):
        logger.debug(f"{self.name} born to do nothing")
