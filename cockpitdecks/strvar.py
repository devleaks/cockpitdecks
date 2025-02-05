# A Formula is a Variable that consists of an expression using one or more variables.
# It has ability to report the variable it uses
# and compute/update its value whenever one of its variable changes
#
import logging
import uuid
import re
import traceback

from cockpitdecks.constant import CONFIG_KW
from cockpitdecks.variable import Variable, VariableListener, PATTERN_DOLCB

# from cockpitdecks.button import StateVariableValueProvider
# from cockpitdecks.button.activation import ActivationValueProvider
# from cockpitdecks.simulator import SimulatorVariableValueProvider

from .resources.rpc import RPC
from .resources.color import DEFAULT_COLOR, convert_color
from .resources.iconfonts import ICON_FONTS

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

MESSAGE_NS = uuid.uuid4()
FORMULA_NS = uuid.uuid4()


class StringWithVariable(Variable, VariableListener):
    """A string with variables to be substitued in it.
    text: ${sim/view/weather/pressure_hpa} hPa
    Variables can include internal variables, simulator variables,
    value from button internal state (including activation value), and results for a formula.
    It is the "owner" of the variable's responsibility to provide the value of the above variables.
    Types of variables:
        "data:...": Internal variables,
        "state:...": State variable, currently for button only,
        "...": Assumed to be a simulator variable.
    """

    def __init__(self, owner, message: str, name: str | None = None):
        self._inited = False
        if name is None:
            key = uuid.uuid3(namespace=MESSAGE_NS, name=str(message))
            name = f"{owner.get_id()}|{key}"  # one owner may have several formulas like annunciators that can have up to 4
        Variable.__init__(self, name=name, data_type="string")
        self.owner = owner
        self.message = message if message is not None else ""

        # Used in formula
        self._tokens = {}  # "${path}": path
        self._variables = None
        self._formats = {}  # for later @todo
        self._has_state_vars = False

        self.is_static = True

        self.init()
        if not isinstance(self, Formula):
            print("+++++ CREATED STRING", self.name, self.owner.name, message, self.get_variables())
            if message is None:
                traceback.print_stack()

    def init(self):
        self._variables = self.get_variables()
        if len(self._variables) > 0:
            self.is_static = False
            logger.debug(f"message {self.display_name}: using variables {', '.join(self._tokens.values())}")
            for varname in self._tokens.values():
                v = self.owner.get_variable(varname)
                v.add_listener(self)
        # owner get notified when this string changes
        if isinstance(self.owner, VariableListener):
            self.add_listener(self.owner)
        # else:
        #     logger.debug(f"formula {self.display_name}: constant {self.message}")

    @property
    def display_name(self):
        i = self.name.index("|")  # just the end of the string, for info, to identify
        j = i - 10
        i = i + 7
        if j < 0:
            j = 0
        if i > len(self.name):
            i = len(self.name)
        return self.name[j:i]

    def get_internal_variable_value(self, internal_variable, default=None):
        """Get internal variable value from owner

        Owner should be a InternalVariableValueProvider.

        Returns:
            [type]: [value from internam variable]
        """
        if hasattr(self.owner, "get_internal_variable_value"):
            if Variable.is_state_variable(internal_variable):
                internal_variable = Variable.state_variable_root_name(internal_variable)
            value = self.owner.get_internal_variable_value(internal_variable=internal_variable, default=default)
            logger.debug(f"{internal_variable} = {value}")
            return value
        logger.warning(f"formula {self.display_name}: no get_internal_variable_value for {internal_variable}")
        return None

    def get_simulator_variable_value(self, simulator_variable, default=None):
        """Get simulator variable value from owner

        Owner should be a SimulatorVariableValueProvider.

        Returns:
            [type]: [value from simulator variable]
        """
        if hasattr(self.owner, "get_simulator_variable_value"):
            value = self.owner.get_simulator_variable_value(simulator_variable=simulator_variable, default=default)
            logger.debug(f"{simulator_variable} = {value}")
            return value
        logger.warning(f"formula {self.display_name}: no get_simulator_variable_value for {simulator_variable}")
        return None

    def get_state_variable_value(self, state_variable, default: str = "0.0"):
        """Get button state variable value from owner

        Owner should be a StateVariableValueProvider.

        Returns:
            [type]: [value from state variable]
        """
        if hasattr(self.owner, "get_state_variable_value"):
            varroot = state_variable
            if Variable.is_state_variable(state_variable):
                varroot = Variable.state_variable_root_name(state_variable)
            value = self.owner.get_state_variable_value(varroot)
            logger.debug(f"{state_variable} = {value}")
            return value
        logger.warning(f"formula {self.display_name}: no get_state_variable_value for {state_variable}")
        return default

    def get_activation_value(self, default: str = "0.0"):
        """Get activation value from owner

        Owner should be a ActivationValueProvider.

        Returns:
            [type]: [value from activation]
        """
        if hasattr(self.owner, "get_activation_value"):
            return self.owner.get_activation_value()
        logger.warning(f"formula {self.display_name}: no get_activation_value")
        return default

    def get_formula_result(self, default: str = "0.0"):
        """Get formuala result value from owner

        Owner should be a button.

        Returns:
            str: retult value as string from formula evaluation
        """
        if hasattr(self.owner, "get_formula_result"):
            logger.debug(f"button {self.owner.name}: owner formula result: {self.owner.get_formula_result()}")
            return self.owner.get_formula_result()
        logger.warning(f"formula {self.display_name}: no get_formula_result (owner={type(self.owner)} {self.owner.name})")
        return default

    def variable_changed(self, data: Variable):
        """Called when a constituing variable has changed.

        Recompute its value, and notifies listener of change if any.

        Args:
            data (Variable): [variable that has changed]
        """
        print(">>>>> CHANGED", self.display_name, data.name, data.current_value)
        old_value = self.current_value  # kept for debug
        logger.debug(f"string-with-variable {self.display_name}: {data.name} changed, reevaluating..")
        dummy = self.substitute_values(store=True, cascade=True)
        logger.debug(f"string-with-variable {self.display_name}: ..done (new value: {dummy})")

    def render(self):
        if hasattr(self.owner, "render"):
            return self.owner.render()

    def get_variables(self) -> set:
        """Returns list of variables used by this formula

        [description]

        Returns:
            set: [list of variables used by formula]
        """
        if self._variables is not None:
            return self._variables

        self._variables = set()
        # case 1: formula is single dataref without ${}
        #         formula: data:_internal_var
        if self.message is None or type(self.message) is not str:
            return self._variables

        if "${" not in self.message:  # formula is simple expression, constant or single dataref without ${}
            # Is formula is single internal variable?
            if Variable.is_internal_variable(self.message) or Variable.is_state_variable(self.message):
                if Variable.is_state_variable(self.message):
                    self._has_state_vars = True
                self._variables.add(self.message)
                self._tokens[self.message] = self.message
                return self._variables
            if Variable.may_be_non_internal_variable(self.message):  # probably a dataref path
                self._variables.add(self.message)
                self._tokens[self.message] = self.message
                return self._variables
        # else formula may be a constant like
        #         formula: 2
        #         formula: 3.14

        # case 2: formula contains one or more ${var}
        #         formula: ${sim/pressure} 33.28 *
        tokens = re.findall(PATTERN_DOLCB, self.message)
        for varname in tokens:
            self._variables.add(varname)
            if Variable.is_state_variable(varname):
                self._has_state_vars = True
            found = f"${{{varname}}}"
            self._tokens[found] = varname

        if CONFIG_KW.FORMULA.value in self._variables:
            self._variables.remove(CONFIG_KW.FORMULA.value)

        return self._variables

    def substitute_values(self, text: str | None = None, default: str = "0.0", formatting=None, store: bool = False, cascade: bool = False) -> str:
        """Substitute values for each variable.

        Vamue can come from cockpit, simulator, button internal state or activation.

        Returns:
            str: [Formula string with substitutions]
        """
        if text is None:
            text = self.message

        if hasattr(self, "font"):  # must be a string with font specified so we know where to look for correspondance
            for k, v in ICON_FONTS.items():
                font = getattr(self, "font", "")
                if font.lower().startswith(v[0].lower()):  # should be equal, except extension?
                    s = "\\${%s:([^\\}]+?)}" % (k)
                    icons = re.findall(s, text)
                    for i in icons:
                        if i in v[1].keys():
                            text = text.replace(f"${{{k}:{i}}}", v[1][i])
                            logger.debug(f"button {self.owner.name}: substituing font icon {i}")

        for token in self._tokens:
            value = default
            varname = token[2:-1]  # ${X} -> X

            if token == f"${{{CONFIG_KW.FORMULA.value}}}":  # ${formula} gets replaced by the result of the formula:
                value = self.get_formula_result(default=default)
            elif Variable.is_internal_variable(varname):
                value = self.get_internal_variable_value(varname, default=default)
            elif Variable.is_state_variable(varname):
                value = self.get_state_variable_value(varname, default=default)
            elif Variable.may_be_non_internal_variable(varname):
                value = self.get_simulator_variable_value(varname, default=default)

            if value is None:
                value = default
                logger.warning(f"{token}: value is null, substitued {value}")

            logger.debug(f"{self.owner} ({type(self.owner)}): {varname}: value {value}")
            print("BEFORE", text, token, str(value))
            text = text.replace(token, str(value))
            print("AFTER", text)

        if store:
            self.update_value(new_value=text, cascade=cascade)

        return text


class Formula(StringWithVariable):
    """A Formula is a typed value made of one or more Variables.

    A Formula can be a simple Variable or an expression that combines several variables.
    The formula is a StringWithVariables but in addition, the string after substitutions
    can be evaluated as a Reverse Polish Notation expression.
    The result of the expression is the value of the formula.
    The value can be formatted to a string expression.
    """

    def __init__(self, owner, formula: str, data_type: str = "float", default_value=0.0, format_str: str | None = None):
        key = ""
        if formula is None and type(owner).__name__ == "Button":
            formula = owner._config.get(CONFIG_KW.FORMULA.value)
        if formula is None:
            logger.warning(f"{owner.get_id()}: no formula")
            key = uuid.uuid4()
        else:
            key = uuid.uuid3(namespace=FORMULA_NS, name=str(formula))
        name = f"{owner.get_id()}|{key}"  # one owner may have several formulas like annunciators that can have up to 4
        StringWithVariable.__init__(self, owner=owner, message=formula)
        self.default_value = default_value
        self.format_str = format_str
        self.owner = owner

        # Used in formula
        self._tokens = {}  # "${path}": path
        self._variables = None
        self.init()
        print("+++++ CREATED FORMULA", self.name, self.owner.name, formula, self.get_variables())

    @property
    def formula(self):
        """we remain read-only here"""
        # if hasattr(self.owner, "_config"):
        #     return self.owner._config.get(CONFIG_KW.FORMULA.value)
        return self.message

    def value(self):
        if self._has_state_vars:
            return self.execute_formula(store=True, cascade=True)
        return super().value()

    def variable_changed(self, data: Variable):
        """Called when a constituing variable has changed.

        Recompute its value, and notifies listener of change if any.

        Args:
            data (Variable): [variable that has changed]
        """
        print(">>>>> CHANGED", self.display_name, data.name, data.current_value)
        old_value = self.current_value  # kept for debug
        logger.debug(f"formula {self.display_name}: {data.name} changed, recomputing..")
        dummy = self.execute_formula(store=True, cascade=True)
        logger.debug(f"formula {self.display_name}: ..done (new value: {self.current_value})")

    def execute_formula(self, store: bool = False, cascade: bool = False):
        """replace datarefs variables with their value and execute formula.

        Returns:
            [type]: [formula result]
        """
        expr = self.substitute_values()
        logger.debug(f"formula {self.display_name}: {self.formula} => {expr}")
        r = RPC(expr)
        value = r.calculate()
        logger.debug(f"value {self.display_name}: {self.formula} => {expr} => {value}")
        valueout = value
        print(">>>>> NEW VALUE", self.display_name, self.message, " ==> ", valueout)
        if self.is_string:
            valueout = self.format_value(value)
        if store:
            self.update_value(new_value=valueout, cascade=cascade)
        return valueout

    def format_value(self, value: int | float | str) -> str:
        """Format value is format is supplied

        Args:
            value ([any]): [value to format]

        Returns:
            str: [formatted value, or string versionof value if no format supplied]
        """
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


# #############################
# In a block like this:
#
# text: ${formula}
# text-format: "{:4.0f}"
# text-size: 60
# text-font: Seven Segment.ttf
# formula: ${sim/cockpit2/gauges/actuators/barometer_setting_in_hg_pilot} 33.86389 * round
#
# handles variable and formula result substitutions, replacement, handling, etc.
# Above, prefix is "text"
#
class TextWithVariables(StringWithVariable):
    """A StringWithVariables that can be used in representation."""

    def __init__(self, owner, config: dict, prefix: str = CONFIG_KW.LABEL.value):
        self._config = config
        self.prefix = prefix

        # Text attributes
        self.format = None

        self.font = None
        self.size = None
        self.color = None
        self.position = None

        self.framed = None

        self.bg_color = None
        self.bg_texture = None

        # local formula?
        self._formula = None
        formula = config.get(CONFIG_KW.FORMULA.value)
        if formula is not None:
            self._formula = Formula(owner=owner, formula=formula)
            print(">>>>> has a local formula")

        message = config.get(prefix)
        StringWithVariable.__init__(self, owner=owner, message=message)
        self.init()

    def get_variables(self) -> set:
        ret = super().get_variables()
        if self._formula is not None:
            ret = ret | self._formula.get_variables()
        if CONFIG_KW.FORMULA.value in ret:
            ret.remove(CONFIG_KW.FORMULA.value)
        return ret

    # ##################################
    # Text substitution
    #
    def init(self):
        DEFAULT_VALID_TEXT_POSITION = "cm"
        self.format = self._config.get(f"{self.prefix}-format")

        dflt_system_font = self.owner.get_attribute("system-font")
        if dflt_system_font is None:
            logger.error(f"button {self.owner.name}: no system font")

        dflt_text_font = self.owner.get_attribute(f"{self.prefix}-font")
        if dflt_text_font is None:
            dflt_text_font = self.owner.get_attribute("label-font")
            if dflt_text_font is None:
                logger.warning(f"button {self.owner.name}: no default label font, using system font")
                dflt_text_font = dflt_system_font

        self.font = self._config.get(f"{self.prefix}-font", dflt_text_font)

        dflt_text_size = self.owner.get_attribute(f"{self.prefix}-size")
        if dflt_text_size is None:
            dflt_text_size = self.owner.get_attribute("label-size")
            if dflt_text_size is None:
                dflt_text_size = 16
                logger.warning(f"button {self.owner.name}: no default label size, using {dflt_text_size}px")
        self.size = self._config.get(f"{self.prefix}-size", dflt_text_size)

        dflt_text_color = self.owner.get_attribute(f"{self.prefix}-color")
        if dflt_text_color is None:
            dflt_text_color = self.owner.get_attribute("label-color")
            if dflt_text_color is None:
                dflt_text_color = DEFAULT_COLOR
                logger.warning(f"button {self.owner.name}: no default label color, using {dflt_text_color}")
        self.color = self._config.get(f"{self.prefix}-color", dflt_text_color)
        self.color = convert_color(self.color)

        dflt_text_position = self.owner.get_attribute(f"{self.prefix}-position")
        if dflt_text_position is None:
            dflt_text_position = self.owner.get_attribute("label-position")
            if dflt_text_position is None:
                dflt_text_position = DEFAULT_VALID_TEXT_POSITION  # middle of icon
                logger.warning(f"button {self.owner.name}: no default label position, using {dflt_text_position}")
        self.position = self._config.get(f"{self.prefix}-position", dflt_text_position)
        if self.position[0] not in "lcr":
            invalid = self.position[0]
            self.position = DEFAULT_VALID_TEXT_POSITION[0] + self.position[1:]
            logger.warning(f"button {self.owner.name}: {type(self).__name__}: invalid horizontal label position code {invalid}, using default")
        if self.position[1] not in "tmb":
            invalid = self.position[1]
            self.position = self.position[0] + DEFAULT_VALID_TEXT_POSITION[1] + (self.position[2:] if len(self.position) > 2 else "")
            logger.warning(f"button {self.owner.name}: {type(self).__name__}: invalid vertical label position code {invalid}, using default")

        # print(f">>>> {self.owner.get_id()}:{self.prefix}", dflt_text_font, dflt_text_size, dflt_text_color, dflt_text_position)

        if self.message is not None and not isinstance(self.message, str):
            logger.warning(f"button {self.owner.name}: converting text {self.message} to string (type {type(self.message)})")
            self.message = str(self.message)

    def get_formula_result(self, default: str = "0.0"):
        """In this case, we do not get the result from the formula from the parent host,
        we get the result of the "local" formula
        """
        if self._formula is not None:
            logger.debug(f"button {self.owner.name}: local formula result: {self._formula.current_value}")
            return self._formula.current_value
        if default is None:
            return super().get_formula_result()
        return default

    def get_text(self):
        # 1. Static icon font like ${fa:airplane}, font=fontawesome.otf
        text = self.message

        # 2. Formula in text
        # If text contains ${formula}, it is replaced by the value of the formula calculation.
        KW_FORMULA_STR = f"${{{CONFIG_KW.FORMULA.value}}}"  # "${formula}"
        if KW_FORMULA_STR in str(text):
            res = ""
            if self._formula is not None:
                res = self._formula.execute_formula()
                if res is not None and res != "":  # Format output if format present
                    if self.format is not None:
                        res = float(res)
                        logger.debug(f"button {self.owner.name}: {self.prefix}-format {self.format}: res {res} => {self.format.format(res)}")
                        res = self.format.format(res)
                    else:
                        res = str(res)
            else:
                logger.warning(f"button {self.owner.name}: text contains {KW_FORMULA_STR} but no {CONFIG_KW.FORMULA.value} attribute found")

            text = text.replace(KW_FORMULA_STR, res)

        # 3. Rest of text: substitution of ${}
        if self.prefix != CONFIG_KW.LABEL.value:
            text = self.substitute_values(text=text, formatting=self.format, default="---")
        return text
