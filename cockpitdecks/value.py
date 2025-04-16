import logging
import re
import math
from typing import Tuple

# from ruamel.yaml.comments import CommentedMap, CommentedSeq

from cockpitdecks import CONFIG_KW
from cockpitdecks.variable import Variable, InternalVariable, ValueProvider, PATTERN_DOLCB
from .strvar import StringWithVariables, Formula
from cockpitdecks.simulator import Simulator, SimulatorVariableValueProvider
from cockpitdecks.buttons.activation import ActivationValueProvider


# from cockpitdecks.button import StateVariableValueProvider

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class Value(StringWithVariables):
    """A Value is a typed value used by Button and Annunciator parts.

    A Value can be a simple Data (either InternalVariable or SimulatorVariable) or a formula that
    combines several Data.
    """

    def __init__(self, name: str, config: dict, provider: ValueProvider):
        local_name = f"{provider.name}/value/{name}"

        self._config = config
        self._provider = provider

        # Variable to write result to
        self._set_simdata_path = self._config.get(CONFIG_KW.SET_SIM_VARIABLE.value)
        self._set_simdata = None
        if self._set_simdata_path is not None:
            self._set_simdata = self._provider.sim.get_variable(self._set_simdata_path)
            self._set_simdata.add_listener(self)

        # Value range and domain:
        self.value_min = self._config.get(CONFIG_KW.VALUE_MIN.value)
        self.value_max = self._config.get(CONFIG_KW.VALUE_MAX.value)
        self.value_inc = self._config.get(CONFIG_KW.VALUE_INC.value)
        self.value_count = self._config.get(CONFIG_KW.VALUE_COUNT.value)
        if self.value_count is not None:
            self.value_count = int(self.value_count)

        # Used in "value"
        self._variables: set | None = None

        self._formula: Formula | None = None
        self._permanent_keys: Tuple[str] = tuple()
        self._local_warning = True

        StringWithVariables.__init__(self, owner=provider, name=local_name, message="")  # this allows to use get_xxx_variable_value()

        # print("+++++ CREATED VALUE", self.name, provider.name, self.get_variables())

    def init(self):
        if self.formula is not None and self.formula != "":
            logger.debug(f"value {self.name}: has formula {self.formula}")
            self._formula = Formula(owner=self._provider, formula=self.formula)
            self._formula.add_listener(self._provider)

        # there is a special issue if dataref we get value from is also dataref we set
        # in this case there MUST be a formula to evalute the value before we set it
        # if self.dataref is not None and self.set_dataref is not None and self.dataref == self.set_dataref:
        #     if self._formula is None:
        #         logger.warning(f"value {self.name}: get/set dataref are identical, no formula")
        #     else:
        #         logger.info(f"value {self.name}: get/set dataref are identical, formula {self.formula} evaluated before set-dataref")

        if not self.has_domain:
            return

        if self.value_min > self.value_max:
            tmp = self.value_min
            self.value_min = self.value_max
            self.value_max = tmp
        # we have a domain, do we have a snap?
        if self.value_inc is not None:
            cnt = self.value_max - self.value_min
            if self.value_count is None:
                self.value_count = cnt
            elif self.value_count != cnt:
                logger.warning(f"value domain mismatch: value count {self.value_count} != {cnt}")
        elif self.value_count is not None and self.value_count > 0:
            self.value_inc = (self.value_max - self.value_min) / self.value_count

    @property
    def dataref(self) -> str | None:
        # Single datatef
        return self._config.get(CONFIG_KW.SIM_VARIABLE.value)

    @property
    def set_dataref(self) -> str | None:
        # Single datatef
        return self._config.get(CONFIG_KW.SET_SIM_VARIABLE.value)

    @property
    def formula(self) -> str:
        # Formula
        return self._config.get(CONFIG_KW.FORMULA.value, "")

    @property
    def has_formula(self) -> bool:
        return self.formula is not None and self.formula != ""

    @property
    def has_domain(self) -> bool:
        return self.value_min is not None and self.value_max is not None

    # ##################################
    # Constituing Variables
    #
    def get_variables(self) -> set:
        """
        Returns all datarefs used by this button from label, texts, computed datarefs, and explicitely
        listed dataref and datarefs attributes.
        This can be applied to the entire button or to a subset (for annunciator parts)
        """
        if self._variables is not None:
            return self._variables
        self._variables = self.scan_variables()
        logger.debug(f"value {self.name}: found datarefs {self._variables}")
        return self._variables

    def add_variables(self, datarefs: set, reason: str | None = None):
        # Add datarefs to the value for computation purpose
        # Used by activation and representation to add to button datarefs
        if self._variables is None:
            self._variables = set()
        self._variables = self._variables | datarefs
        logger.debug(f"value {self.name}: added {len(datarefs)} datarefs ({reason})")

    def scan_variables(self, base: dict | None = None, extra_keys: list = []) -> set:
        """
        scan all datarefs in texts, computed datarefs, or explicitely listed.
        This is applied to the entire button or to a subset (for annunciator parts for example).
        String datarefs are treated separately.
        """
        if base is None:  # local, button-level ones
            base = self._config

        r = set()

        # Direct use of datarefs:
        #
        # 1. Formula
        formula_str = base.get(CONFIG_KW.FORMULA.value)
        if formula_str is not None and formula_str != "":
            formula = Formula(owner=self._provider, formula=formula_str)
            r = formula.get_variables()
            logger.debug(f"value {self.name}: added formula variables {r}")

        #
        # 2. Single datarefs in attributes, yes we monotor the set-dataref as well in case someone is using it.
        for attribute in [CONFIG_KW.SIM_VARIABLE.value, CONFIG_KW.SET_SIM_VARIABLE.value]:
            dataref = base.get(attribute)
            if dataref is not None and InternalVariable.may_be_non_internal_variable(dataref):
                r.add(dataref)
                logger.debug(f"value {self.name}: added single dataref {dataref}")

        # 3. Command with potential conditions
        #    Note: actions: is list of commands in Observables. (Should be command:? @todo)
        for instr_cmd in [CONFIG_KW.COMMAND.value, CONFIG_KW.COMMANDS.value, CONFIG_KW.VIEW.value, CONFIG_KW.ACTIONS.value]:
            commands = base.get(instr_cmd)
            if type(commands) is list:
                for command in commands:
                    if type(command) is dict:  # command "block"
                        # @hack
                        # actions:
                        #   - command: cockpitdecks-accumulator
                        #     name: test
                        #     save: 60
                        #     variables:  <--------------------------------------+
                        #       - sim/flightmodel/position/latitude              |
                        #       - sim/flightmodel/position/longitude             |
                        #       - sim/flightmodel2/position/pressure_altitude.   |
                        addvars = command.get(CONFIG_KW.VARIABLES.value)  # <----+
                        if addvars is not None:
                            datarefs = set(addvars)
                        else:
                            datarefs = self.scan_variables(base=command, extra_keys=[CONFIG_KW.CONDITION.value])
                        if len(datarefs) > 0:
                            r = r | datarefs
                            logger.debug(f"value {self.name}: added datarefs found in {command}: {datarefs}")
                    # else command is str, no dref to scan for
            # else: commands is string or None, no dref to scan for

        # 3.a Special commands that use datarefs (as arguments)

        # 4. In text, etc.
        allways_extra = [CONFIG_KW.CONDITION.value]  # , CONFIG_KW.VIEW_IF.value
        self._permanent_keys = set(extra_keys + allways_extra)

        for key in self._permanent_keys:
            text = base.get(key)
            if text is None:
                continue
            if type(text) is dict:
                datarefs = self.scan_variables(base=text, extra_keys=extra_keys)
                if len(datarefs) > 0:
                    r = r | datarefs
                continue
            if text is not str:
                text = str(text)
            datarefs = re.findall(PATTERN_DOLCB, text)
            datarefs = set(filter(lambda x: InternalVariable.may_be_non_internal_variable(x), datarefs))
            if len(datarefs) > 0:
                r = r | datarefs
                logger.debug(f"value {self.name}: added datarefs found in {key}: {datarefs}")

        # Clean up
        # label or text may contain like ${{CONFIG_KW.FORMULA.value}}, but CONFIG_KW.FORMULA.value is not a dataref.
        # text: ${formula} replaces text with result of formula
        if CONFIG_KW.FORMULA.value in r:
            r.remove(CONFIG_KW.FORMULA.value)
        if None in r:
            r.remove(None)

        return r

    # ##################################
    # Value computation
    #
    @Variable.value.getter
    def value(self):
        # 1. If there is a formula, value comes from it
        if self.has_formula:
            ret = self._formula.value
            logger.debug(f"value {self.name}: {ret} (from formula)")
            return ret

        # 2a. One dataref, but dataref is actually internal variable
        if self.dataref is not None and Variable.is_internal_variable(self.dataref):
            ret = self.get_internal_variable_value(internal_variable=self.dataref)
            logger.debug(f"value {self.name}: {ret} (from single internal variable {self.dataref})")
            return ret

        # 2b. One dataref, but dataref is actually internal state variable
        if self.dataref is not None and Variable.is_state_variable(self.dataref):
            ret = self.get_state_variable_value(state_variable=self.dataref)
            logger.debug(f"value {self.name}: {ret} (from single state variable {self.dataref})")
            return ret

        # 2c. One dataref
        if self.dataref is not None and isinstance(self._provider, (SimulatorVariableValueProvider, Simulator)):
            ret = self.get_simulator_variable_value(simulator_variable=self.dataref)
            logger.debug(f"value {self.name}: {ret} (from single dataref {self.dataref})")
            return ret

        # 3. Activation value
        if isinstance(self._provider, ActivationValueProvider) and hasattr(self._provider, "_activation") and self._provider._activation is not None:
            ret = self.get_activation_value()
            if ret is not None:
                if type(ret) is bool:
                    ret = 1 if ret else 0
                logger.debug(f"value {self.name}: {ret} (from activation {type(self._provider._activation).__name__})")
                return ret

        # From now on, warning issued since returns non scalar value
        #
        # 4. Multiple datarefs
        if (self._variables is not None and len(self._variables) > 1) and (
            isinstance(self._provider, SimulatorVariableValueProvider) or isinstance(self._provider, Simulator)
        ):
            ret = {d: self.get_simulator_variable_value(simulator_variable=d) for d in self.get_variables()}
            if self._local_warning:
                logger.info(f"value {self.name}: no formula, no dataref, returning all variables: {ret}")
                self._local_warning = False
            return ret

        logger.debug(f"value {self.name}: no formula, no dataref, no activation")

        # 4. *All* state variables?
        if isinstance(self._provider, ActivationValueProvider) and hasattr(self._provider, "_activation") and self._provider._activation is not None:
            ret = self._provider._activation.get_state_variables()
            logger.debug(f"value {self.name}: {ret} (from state variables)")
            return ret
        if self._local_warning:
            logger.info(f"value {self.name}: no local value, returning parent value {self.current_value}")
            self._local_warning = False
        return self.current_value  # super().value

    def get_rescaled_value(self, range_min: float, range_max: float, steps: int | None = None):
        value = self.value
        if value is None:
            return None
        if not self.has_domain:
            logger.warning("no domain for value")
            return value
        if value < self.value_min:
            logger.warning("value too small")
            return value
        if value > self.value_max:
            logger.warning("value too large")
            return value
        pct = (value - self.value_min) / (self.value_max - self.value_min)
        if steps is not None and steps > 0:
            f = 1 / steps
            pct = math.floor(pct / f) * f

        newval = range_min + pct * (range_max - range_min)
        return newval

    def save(self):
        # Writes the computed button value to set-dataref
        if self._set_simdata is not None:
            new_value = self.value
            if new_value is None:
                logger.warning(f"value {self.name}: value is None, set to 0")
                new_value = 0
            self._set_simdata.update_value(new_value=new_value, cascade=True)
            # print(f"set-dataref>> button {self._provider.name}: value {self.name}: set-dataref {self._set_simdata.name} to button value {new_value}")
            self._set_simdata.save()
