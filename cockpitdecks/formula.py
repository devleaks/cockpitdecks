# A Formula is a Variable that consists of an expression using one or more variables.
# It has ability to report the variable it uses
# and compute/update its value whenever one of its variable changes
#
import logging
import uuid
import re

from cockpitdecks.constant import CONFIG_KW
from cockpitdecks.variable import Variable, VariableListener, PATTERN_DOLCB, INTERNAL_DATA_PREFIX, INTERNAL_STATE_PREFIX

from .resources.rpc import RPC

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Formula(Variable, VariableListener):
    """A Formula is a typed value made of one or more Variables.

    A Formula can be a simple Variable (either InternalVariable or SimulatorVariable)
    or an expression that combines several variables.
    """

    def __init__(self, button, data_type: str = "float", default_value=0.0, format_str: str = None):
        name = f"{button.get_id()}|{uuid.uuid4()}"  # one button may have several formulas like annunciators that can have up to 4
        Variable.__init__(self, name=name, data_type=data_type)
        self.default_value = default_value
        self.format_str = format_str
        self.button = button

        # Used in formula
        self._tokens = {}  # "${path}": path
        self._variables = None
        self.init()

    def init(self):
        self._variables = self.get_variables()
        if len(self._variables) > 0:
            logger.debug(f"formula {self.display_name}: using variables {', '.join(self._tokens.values())}")
            for varname in self._tokens.values():
                v = self.button.sim.get_variable(varname)
                v.add_listener(self)
        # else:
        #     logger.debug(f"formula {self.display_name}: constant {self.formula}")

    @property
    def display_name(self):
        i = self.name.index("|") + 5
        return self.name[:i]

    @property
    def formula(self):
        """we remain read-only here"""
        return self.button._config.get(CONFIG_KW.FORMULA.value)

    def compute(self):
        value = self.execute_formula()
        value2 = self.format_value(value)
        self.update_value(new_value=value2, cascade=False)  # False for now

    def variable_changed(self, data: Variable):
        old_value = self.current_value
        logger.debug(f"formula {self.display_name}: {data.name} changed, recomputing..")
        self.compute()
        logger.debug(f"formula {self.display_name}: ..done (new value: {self.current_value})")

    def get_variables(self) -> set:
        if self._variables is not None:
            return self._variables

        self._variables = set()
        # case 1: formula is single dataref without ${}
        #         formula: data:_internal_var
        if self.formula is None or type(self.formula) is not str:
            return self._variables

        if "${" not in self.formula:  # formula is simple expression, constant or single dataref without ${}
            # Is formula is single internal variable?
            if Variable.is_internal_variable(self.formula) or Variable.is_internal_state_variable(self.formula):
                self._variables.add(self.formula)
                self._tokens[self.formula] = self.formula
                return self._variables
            if Variable.may_be_non_internal_variable(self.formula):  # probably a dataref path
                if "/" not in self.formula:
                    logger.warning(f"formula {self.display_name}: value guessed as dataref path without /: {self.formula}")
                self._variables.add(self.formula)
                self._tokens[self.formula] = self.formula
                return self._variables
        # else formula may be a constant like
        #         formula: 2
        #         formula: 3.14

        # case 2: formula contains one or more ${var}
        #         formula: ${sim/pressure} 33.28 *
        tokens = re.findall(PATTERN_DOLCB, self.formula)
        for varname in tokens:
            self._variables.add(varname)
            found = f"${{{varname}}}"
            self._tokens[found] = varname

        return self._variables

    def substitute_values(self) -> str:
        text = self.formula
        for token in self._tokens:
            value = self.default_value
            if token.startswith(INTERNAL_DATA_PREFIX):
                value = self.button.get_variable_value(token)
            elif token.startswith(INTERNAL_STATE_PREFIX):
                value = self.button.get_state_variable_value(token)
            text = text.replace(token, str(value))
        return text

    def execute_formula(self):
        """
        replace datarefs variables with their (numeric) value and execute formula.
        Returns formula result.
        """
        expr = self.substitute_values()
        logger.debug(f"formula {self.display_name}: {self.formula} => {expr}")
        r = RPC(expr)
        value = r.calculate()
        logger.debug(
            f"executeformula: value {self.display_name}: {self.formula} => {expr} => {value}",
        )
        return value

    def format_value(self, value) -> str:
        if self.format_str is not None:
            if type(value) in [int, float]:  # probably formula is a constant value
                value_str = self.format_str.format(value)
                logger.debug(f"formula {self.display_name}: returning formatted {self.format_str}:  {value_str}.")
                return value_str
            else:
                logger.warning(f"formula {self.display_name}: has format string '{self.format_str}' but value is not a number '{value}'")
        value_str = str(value)
        logger.debug(f"formula {self.display_name}: received {value} ({type(value).__name__}), returns as string: '{value_str}'")
        return value_str
