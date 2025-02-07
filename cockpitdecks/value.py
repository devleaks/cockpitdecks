import logging
import re
import math
from typing import Tuple

# from ruamel.yaml.comments import CommentedMap, CommentedSeq

from cockpitdecks import CONFIG_KW
from cockpitdecks.variable import InternalVariable, ValueProvider, INTERNAL_STATE_PREFIX, PATTERN_DOLCB, PATTERN_INTSTATE
from cockpitdecks.simulator import Simulator, SimulatorVariableValueProvider
from cockpitdecks.buttons.activation import ActivationValueProvider

from .strvar import Formula

# from cockpitdecks.button import StateVariableValueProvider

from .resources.iconfonts import ICON_FONTS
from .resources.rpc import RPC

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class Value:
    """A Value is a typed value used by Cockpitdecks entities.

    A Value can be a simple Data (either InternalVariable or SimulatorDate) or a formula that
    combines several Data.
    """

    def __init__(self, name: str, config: dict, provider: ValueProvider):
        self._config = config
        self._provider = provider
        self._button = provider
        self.name = name  # for debeging and information purpose

        self._set_simdata_path = self._config.get(CONFIG_KW.SET_SIM_VARIABLE.value)
        self._set_simdata = None
        if self._set_simdata_path is not None:
            self._set_simdata = self._button.sim.get_variable(self._set_simdata_path)
            self._set_simdata.writable = True

        # Value domain:
        self.value_min = self._config.get(CONFIG_KW.VALUE_MIN.value)
        self.value_max = self._config.get(CONFIG_KW.VALUE_MAX.value)
        self.value_inc = self._config.get(CONFIG_KW.VALUE_INC.value)
        self.value_count = self._config.get(CONFIG_KW.VALUE_COUNT.value)
        if self.value_count is not None:
            self.value_count = int(self.value_count)

        # Used in "value"
        self._simulator_variable: set | None = None
        self._string_simulator_variable: set | None = None
        self._known_extras: Tuple[str] = tuple()
        self._formula: Formula | None = None

        self.init()
        # print("+++++ CREATED VALUE", self.name, provider.name, self.get_variables())

    def init(self):
        self._string_simulator_variable = self.string_datarefs
        if type(self._string_simulator_variable) is str:
            if "," in self._string_simulator_variable:
                self._string_simulator_variable = self._string_simulator_variable.replace(" ", "").split(",")
            else:
                self._string_simulator_variable = [self._string_simulator_variable]

        # there is a special issue if dataref we get value from is also dataref we set
        # in this case there MUST be a formula to evalute the value before we set it
        # if self.dataref is not None and self.set_dataref is not None:
        #     if self.dataref == self.set_dataref:
        #         if self.formula == "":
        #             logger.warning(f"value {self.name}: set and get from same dataref ({self.dataref}) ({'no' if self.formula == '' else 'has'} formula)")
        #         if self.formula is None:
        #             logger.warning(f"value {self.name}: has no formula, get/set are identical")
        #         else:
        #             logger.warning(f"value {self.name}: formula {self.formula} evaluated before set-dataref")

        if self.has_formula:
            formula = self.get_formula()
            self._formula = Formula(owner=self._provider, formula=formula)
            self._formula.add_listener(self._provider)

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
    def string_datarefs(self) -> set:
        # List of string datarefs
        return set(self._config.get(CONFIG_KW.STRING_SIM_DATA.value, set()))

    @property
    def datarefs(self) -> list:
        # List of datarefs
        return self._config.get(CONFIG_KW.SIM_DATA.value, [])

    @property
    def formula(self) -> str:
        # Formula
        return self._config.get(CONFIG_KW.FORMULA.value, "")

    @property
    def has_formula(self) -> bool:
        formula = self.get_formula()
        return formula is not None and formula != ""

    @property
    def has_domain(self) -> bool:
        return self.value_min is not None and self.value_max is not None

    def is_self_modified(self):
        # Determine of the activation of the button directly modifies
        # a dataref used in computation of the value.
        return self._set_simdata_path in self._simulator_variable

    def add_variables(self, datarefs: set, reason: str | None = None):
        # Add datarefs to the value for computation purpose
        # Used by activation and representation to add to button datarefs
        if self._simulator_variable is None:
            self._simulator_variable = set()
        self._simulator_variable = self._simulator_variable | datarefs
        logger.debug(f"value {self.name}: added {len(datarefs)} datarefs ({reason})")

    # ##################################
    # Constituing Variables
    #
    def get_variables(self) -> set:
        """
        Returns all datarefs used by this button from label, texts, computed datarefs, and explicitely
        listed dataref and datarefs attributes.
        This can be applied to the entire button or to a subset (for annunciator parts)
        """
        if self._simulator_variable is not None:
            return self._simulator_variable
        self._simulator_variable = self.scan_variables(self._config)
        logger.debug(f"value {self.name}: found datarefs {self._simulator_variable}")
        return self._simulator_variable

    def get_all_datarefs(self) -> list:
        return self.get_variables() | self._string_simulator_variable

    def scan_variables(self, base: dict | None = None, extra_keys: list = []) -> set:
        """
        scan all datarefs in texts, computed datarefs, or explicitely listed.
        This is applied to the entire button or to a subset (for annunciator parts for example).
        String datarefs are treated separately.
        """
        if base is None:  # local, button-level ones
            base = self._config

        r = set()
        if self.has_formula:
            r = self._formula.get_variables()
            logger.debug(f"value {self.name}: added formula variables {r}")

        # Direct use of datarefs:
        #
        # 1.1 Single datarefs in attributes, yes we monotor the set-dataref as well in case someone is using it.
        for attribute in [CONFIG_KW.SIM_VARIABLE.value, CONFIG_KW.SET_SIM_VARIABLE.value]:
            dataref = base.get(attribute)
            if dataref is not None and InternalVariable.may_be_non_internal_variable(dataref):
                r.add(dataref)
                logger.debug(f"value {self.name}: added single dataref {dataref}")

        # 1.2 Multiple
        datarefs = base.get(CONFIG_KW.SIM_DATA.value)
        if datarefs is not None:
            a = []
            for d in datarefs:
                if InternalVariable.may_be_non_internal_variable(d):
                    r.add(d)
                    a.append(d)
            logger.debug(f"value {self.name}: added multiple datarefs {a}")

        # 2. Command with potential conditions
        for instr_cmd in [CONFIG_KW.COMMAND.value, CONFIG_KW.COMMANDS.value, CONFIG_KW.VIEW.value]:
            commands = base.get(instr_cmd)
            if type(commands) is list:
                for command in commands:
                    if type(command) is dict:  # command "block"
                        datarefs = self.scan_variables(base=command, extra_keys=[CONFIG_KW.CONDITION.value])
                        if len(datarefs) > 0:
                            r = r | datarefs
                            logger.debug(f"value {self.name}: added datarefs found in {command}: {datarefs}")
                    # else command is str, no dref to scan for
            # else: commands is string or None, no dref to scan for

        # 3. In string datarefs (formula, text, etc.)
        allways_extra = [CONFIG_KW.CONDITION.value]  # , CONFIG_KW.VIEW_IF.value
        self._known_extras = set(extra_keys + allways_extra)

        for key in self._known_extras:
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
    # Formula Execution
    #
    def get_formula(self) -> str | None:
        # 1. Formula directly in supplied config
        if self.formula is not None and self.formula != "":
            logger.debug(f"value {self.name}: has formula {self.formula}")
            return self.formula
        # # 2. formula in the provider, if the provider's represntation is not an Annunciator
        # #    DOCUMENT WHY!! @todo
        # if (
        #     hasattr(self._provider, "formula")
        #     and self._provider.formula is not None
        #     and self._provider.formula != ""
        #     and hasattr(self._provider, "_representation")
        #     and type(self._provider._representation).__name__ != "Annunciator"
        # ):
        #     logger.debug(f"value {self.name}: provider has formula {self._provider.formula}")
        #     return self._provider.formula
        return None

    def execute_formula(self, formula, default: float = 0.0) -> float:
        """
        replace datarefs variables with their (numeric) value and execute formula.
        Returns formula result.
        """
        expr = self.substitute_values(text=formula, default=str(default))
        logger.debug(f"value {self.name}: {formula} => {expr}")
        r = RPC(expr)
        value = r.calculate()
        logger.debug(f"execute_formula: value {self.name}: {formula} => {expr} => {value}")
        return value

    # ##################################
    # Formula value substitution
    #
    def get_simulator_variable_value(self, simulator_variable, default=None):
        if isinstance(self._provider, SimulatorVariableValueProvider) or isinstance(self._provider, Simulator):
            return self._provider.get_simulator_variable_value(simulator_variable=simulator_variable, default=default)
        return None

    def get_state_variable_value(self, state):
        if hasattr(self._provider, "get_state_variable_value"):
            # if isinstance(self._provider, StateVariableValueProvider):
            return self._provider.get_state_variable_value(state)
        return None

    def get_activation_value(self):
        if isinstance(self._provider, ActivationValueProvider):
            return self._button.get_activation_value()
        return None

    def substitute_dataref_values(self, message: str | int | float, default: str = "0.0", formatting=None):
        """
        Replaces ${dataref} with value of dataref in labels and execution formula.
        @todo: should take into account dataref value type (Dataref.xp_data_type or Dataref.data_type).
        """
        if not (isinstance(self._provider, SimulatorVariableValueProvider) or isinstance(self._provider, Simulator)):
            return

        if type(message) is int or type(message) is float:  # probably formula is a constant value
            value_str = message
            if formatting is not None:
                if formatting is not None:
                    value_str = formatting.format(message)
                    logger.debug(f"value {self.name}:received int or float, returning as is.")
                else:
                    value_str = str(message)
                    logger.debug(f"value {self.name}:received int or float, returning formatted {formatting}.")
            return value_str

        dataref_names = re.findall(PATTERN_DOLCB, message)

        if len(dataref_names) == 0:
            logger.debug(f"value {self.name}:no dataref to substitute.")
            return message

        if formatting is not None:
            if type(formatting) is list:
                if len(dataref_names) != len(formatting):
                    logger.warning(
                        f"value {self.name}:number of datarefs {len(dataref_names)} not equal to the number of format {len(formatting)}, cannot proceed."
                    )
                    return message
            elif type(formatting) is not str:
                logger.warning(f"value {self.name}:single format is not a string, cannot proceed.")
                return message

        retmsg = message
        cnt = 0
        for dataref_name in dataref_names:
            value = self.get_simulator_variable_value(simulator_variable=dataref_name)
            value_str = ""
            if formatting is not None and value is not None:
                if type(formatting) is list:
                    value_str = formatting[cnt].format(value)
                elif formatting is not None and type(formatting) is str:
                    value_str = formatting.format(value)
            else:
                value_str = str(value) if value is not None else str(default)  # default gets converted in float sometimes!
            retmsg = retmsg.replace(f"${{{dataref_name}}}", value_str)
            logger.debug(f"substitute_dataref_values {dataref_name} = {value_str}{' (default)' if value is not None else ''}")
            cnt = cnt + 1

        more = re.findall(PATTERN_DOLCB, retmsg)  # XXXHERE
        if len(more) > 0:
            logger.warning(f"value {self.name}:unsubstituted dataref values {more}")

        return retmsg

    def substitute_state_values(self, text, default: str = "0.0", formatting=None):
        if not hasattr(self._provider, "get_state_variable_value"):
            return text
        # if not isinstance(self._provider, StateVariableValueProvider):
        #     return text

        txtcpy = text
        more = re.findall(PATTERN_INTSTATE, txtcpy)
        for name in more:
            state_string = f"${{{INTERNAL_STATE_PREFIX}{name}}}"  # @todo: !!possible injection!!
            value = self.get_state_variable_value(name)
            logger.debug(f"value {state_string} = {value}")
            if value is not None:
                txtcpy = txtcpy.replace(state_string, value)
                logger.debug(f"substitute_state_values: {state_string} -> {value}")
            else:
                txtcpy = txtcpy.replace(state_string, default)
                logger.debug(f"substitute_state_values: {state_string} -> {default} (default)")
        more = re.findall(PATTERN_INTSTATE, txtcpy)
        if len(more) > 0:
            logger.warning(f"value {self.name}:unsubstituted status values {more}")
        return txtcpy

    def substitute_values(self, text, default: str = "0.0", formatting=None):
        logger.debug(f"substitute_values: {self._button.name}: value {self.name}: processing '{text}'..")
        if type(text) is not str or "$" not in text:  # no ${..} to stubstitute
            logger.debug(f"substitute_values: {self._button.name}: value {self.name}: {text} has no variable to substitute, returning as it is")
            return text
        step1 = self.substitute_state_values(text, default=default, formatting=formatting)
        if text != step1:
            logger.debug(f"substitute_values: {self._button.name}: value {self.name}: {text} => {step1}")
        else:
            logger.debug(f"substitute_values: {self._button.name}: value {self.name} has no state variable ({text})")
        # step2 = self.substitute_button_values(step1, default=default, formatting=formatting)
        step2 = step1
        step3 = self.substitute_dataref_values(step2, default=default, formatting=formatting)
        if step3 != step2:
            logger.debug(f"substitute_values: {self._button.name}: value {self.name}: {step2} => {step3}")
        else:
            logger.debug(f"substitute_values: {self._button.name}: value {self.name} has no dataref ({step3})")
        logger.debug(f"substitute_values: {self._button.name}: value {self.name}: ..processed '{text}' => {step3}")
        return step3

    # ##################################
    # Text substitution
    #
    def get_text(self, base: dict, root: str = CONFIG_KW.LABEL.value):  # root={label|text}
        """
        Extract label or text from base and perform formula and dataref values substitution if present.
        (I.e. replaces ${formula} and ${dataref} with their values.)
        """
        text = base.get(root)
        if text is None:
            return None

        # HACK 1: Special icon font substitution
        default_font = self._button.get_attribute("label-font")
        if default_font is None:
            logger.warning("no default font")

        text_font = base.get(root + "-font", default_font)

        # Substituing icons in icon fonts
        for k, v in ICON_FONTS.items():
            if text_font.lower().startswith(v[0].lower()):  # should be equal, except extension?
                s = "\\${%s:([^\\}]+?)}" % (k)
                icons = re.findall(s, text)
                for i in icons:
                    if i in v[1].keys():
                        text = text.replace(f"${{{k}:{i}}}", v[1][i])
                        logger.debug(f"button {self._button.name}: substituing font icon {i}")

        # Formula keyword in text
        # If text contains ${formula}, it is replaced by the value of the formula calculation.
        text_format = base.get(f"{root}-format")
        KW_FORMULA_STR = f"${{{CONFIG_KW.FORMULA.value}}}"  # "${formula}"
        if KW_FORMULA_STR in str(text):
            res = ""
            if self.has_formula:
                res = self._formula.value()
                if res is not None and res != "":  # Format output if format present
                    if text_format is not None:
                        res = float(res)
                        logger.debug(f"button {self._button.name}: {root}-format {text_format}: res {res} => {text_format.format(res)}")
                        res = text_format.format(res)
                    else:
                        res = str(res)
            else:
                logger.warning(f"button {self._button.name}: text contains {KW_FORMULA_STR} but no {CONFIG_KW.FORMULA.value} attribute found")

            text = text.replace(KW_FORMULA_STR, res)

        # Rest of text: substitution of ${}
        if root != CONFIG_KW.LABEL.value:
            text = self.substitute_values(text, formatting=text_format, default="---")
        return text

    # ##################################
    # Value computation
    #
    def get_value(self):
        """ """

        def check_domain(val):
            if not self.has_domain:
                return val
            if val < self.value_min:
                logger.debug(f"value {val} out of domain min, set to {self.value_min}")
                return self.value_min
            if val > self.value_max:
                logger.debug(f"value {val} out of domain max, set to {self.value_max}")
                return self.value_max
            return val

        # 1. If there is a formula, value comes from it
        if self.has_formula:
            ret = self._formula.value()
            logger.debug(f"value {self.name}: {ret} (from formula)")
            return ret

        # 2. One dataref
        if self.dataref is not None and (isinstance(self._provider, SimulatorVariableValueProvider) or isinstance(self._provider, Simulator)):
            # if self._simulator_variable[0] in self.page.simulator_variable.keys():  # unnecessary check
            ret = self.get_simulator_variable_value(simulator_variable=self.dataref)
            logger.debug(f"value {self.name}: {ret} (from single dataref {self.dataref})")
            return ret

        # 3. Activation value
        if isinstance(self._provider, ActivationValueProvider) and hasattr(self._provider, "_activation") and self._provider._activation is not None:
            # if self._simulator_variable[0] in self.page.simulator_variable.keys():  # unnecessary check
            ret = self.get_activation_value()
            if ret is not None:
                if type(ret) is bool:
                    ret = 1 if ret else 0
                logger.debug(f"value {self.name}: {ret} (from activation {type(self._button._activation).__name__})")
                return ret

        # From now on, warning issued since returns non scalar value
        #
        # 4. Multiple datarefs
        if len(self._simulator_variable) > 1 and (isinstance(self._provider, SimulatorVariableValueProvider) or isinstance(self._provider, Simulator)):
            r = {}
            for d in self.get_all_datarefs():
                v = self.get_simulator_variable_value(simulator_variable=d)
                r[d] = v
            logger.info(f"value {self.name}: {r} (no formula, no dataref, returning all datarefs)")
            return r

        logger.warning(f"value {self.name}: no formula, no dataref, no activation")

        # 4. State variables?
        if isinstance(self._provider, ActivationValueProvider) and hasattr(self._provider, "_activation") and self._provider._activation is not None:
            r = self._provider._activation.get_state_variables()
            logger.info(f"value {self.name}: {r} (from state variables)")
            return r

        logger.warning(f"value {self.name}: no value")
        return None

    def get_rescaled_value(self, range_min: float, range_max: float, steps: int | None = None):
        value = self.get_value()
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
            new_value = self.get_value()
            if new_value is None:
                logger.warning(f"value {self.name}: value is None, set to 0")
                new_value = 0
            self._set_simdata.update_value(new_value=new_value, cascade=True)
            # print(f"set-dataref>> button {self._button.name}: value {self.name}: set-dataref {self._set_simdata.name} to button value {new_value}")
            self._set_simdata.save()
