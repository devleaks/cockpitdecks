# A Formula is a Variable that consists of an expression using one or more variables.
# It has ability to report the variable it uses
# and compute/update its value whenever one of its variable changes
#
import logging
import uuid
import re

from cockpitdecks.constant import CONFIG_KW
from cockpitdecks.variable import Variable, VariableListener, PATTERN_DOLCB, INTERNAL_DATA_PREFIX, INTERNAL_STATE_PREFIX

# from cockpitdecks.button import StateVariableValueProvider
# from cockpitdecks.button.activation import ActivationValueProvider
# from cockpitdecks.simulator import SimulatorVariableValueProvider

from .resources.rpc import RPC

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

    def __init__(self, owner, message: str):
        self._inited = False
        key = uuid.uuid3(namespace=MESSAGE_NS, name=str(message))
        name = f"{owner.get_id()}|{key}"  # one owner may have several formulas like annunciators that can have up to 4
        Variable.__init__(self, name=name, data_type="string")
        self.owner = owner

        # Used in formula
        self._tokens = {}  # "${path}": path
        self._variables = None
        self._formats = {}  # for later @todo
        self.init()

    def init(self):
        self._variables = self.get_variables()
        if len(self._variables) > 0:
            logger.debug(f"message {self.display_name}: using variables {', '.join(self._tokens.values())}")
            for varname in self._tokens.values():
                v = self.owner.sim.get_variable(varname)
                v.add_listener(self)
        # else:
        #     logger.debug(f"formula {self.display_name}: constant {self.formula}")

    @property
    def display_name(self):
        i = self.name.index("|") + 5  # just the end of the string, for info, to identify
        return self.name[:i]

    def get_internal_variable_value(self, internal_variable, default=None):
        """Get internal variable value from owner

        Owner should be a InternalVariableValueProvider.

        Returns:
            [type]: [value from internam variable]
        """
        if hasattr(self.owner, "get_internal_variable_value"):
            return self.owner.get_internal_variable_value(simulator_variable=internal_variable, default=default)
        logger.warning(f"formula {self.display_name}: no get_internal_variable_value for {internal_variable}")
        return None

    def get_simulator_variable_value(self, simulator_variable, default=None):
        """Get simulator variable value from owner

        Owner should be a SimulatorVariableValueProvider.

        Returns:
            [type]: [value from simulator variable]
        """
        if hasattr(self.owner, "get_simulator_variable_value"):
            return self.owner.get_simulator_variable_value(simulator_variable=simulator_variable, default=default)
        logger.warning(f"formula {self.display_name}: no get_simulator_variable_value for {simulator_variable}")
        return None

    def get_state_variable_value(self, state_variable):
        """Get button state variable value from owner

        Owner should be a StateVariableValueProvider.

        Returns:
            [type]: [value from state variable]
        """
        if hasattr(self.owner, "get_state_variable_value"):
            return self.owner.get_state_variable_value(state_variable)
        logger.warning(f"formula {self.display_name}: no get_state_variable_value for {state_variable}")
        return None

    def get_activation_value(self):
        """Get activation value from owner

        Owner should be a ActivationValueProvider.

        Returns:
            [type]: [value from activation]
        """
        if hasattr(self.owner, "get_activation_value"):
            return self.owner.get_activation_value()
        logger.warning(f"formula {self.display_name}: no get_activation_value")
        return None

    def get_formula_result(self):
        """Get formuala result value from owner

        Owner should be a button.

        Returns:
            str: retult value as string from formula evaluation
        """
        if hasattr(self.owner, "get_formula_result"):
            return self.owner.get_formula_result()
        logger.warning(f"formula {self.display_name}: no get_activation_value")
        return None

    def variable_changed(self, data: Variable):
        """Called when a constituing variable has changed.

        Recompute its value, and notifies listener of change if any.

        Args:
            data (Variable): [variable that has changed]
        """
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
        if self.formula is None or type(self.formula) is not str:
            return self._variables

        if "${" not in self.formula:  # formula is simple expression, constant or single dataref without ${}
            # Is formula is single internal variable?
            if Variable.is_internal_variable(self.formula) or Variable.is_state_variable(self.formula):
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

    def init(self):
        if self._inited:
            return

        for name in self.get_variables():
            var = self.owner.get_variable(name=name)
            if var is not None:
                var.add_listener(self)
        self._inited = True

    def substitute_values(self, store: bool = False, cascade: bool = False) -> str:
        """Substitute values for each variable.

        Vamue can come from cockpit, simulator, button internal state or activation.

        Returns:
            str: [Formula string with substitutions]
        """
        text = self.formula

        for token in self._tokens:
            value = self.default_value
            if token == f"${{{CONFIG_KW.FORMULA.value}}}":  # ${formula} gets replaced by the result of the formula:
                value = self.owner.get_formula_result()
            elif token.startswith(INTERNAL_DATA_PREFIX):
                value = self.owner.get_variable_value(token)
            elif token.startswith(INTERNAL_STATE_PREFIX):
                value = self.owner.get_state_variable_value(token)

            if value is None:
                logger.warning(f"{token}: value is null, substitued empty string")
                value = ""
            text = text.replace(token, str(value))

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

    def __init__(self, owner, formula: str | None = None, data_type: str = "float", default_value=0.0, format_str: str | None = None):
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

    @property
    def formula(self):
        """we remain read-only here"""
        return self.owner._config.get(CONFIG_KW.FORMULA.value)

    def variable_changed(self, data: Variable):
        """Called when a constituing variable has changed.

        Recompute its value, and notifies listener of change if any.

        Args:
            data (Variable): [variable that has changed]
        """
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
        logger.debug(
            f"executeformula: value {self.display_name}: {self.formula} => {expr} => {value}",
        )
        valuestr = self.format_value(value)
        if store:
            self.update_value(new_value=valuestr, cascade=cascade)
        return value

    def format_value(self, value) -> str:
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

    def __init__(self, owner, config: dict, prefix: str):
        self._config = config
        self.prefix = prefix
        message = config.get(prefix)
        StringWithVariable.__init__(self, owner=owner, message=message)

    # ##################################
    # Text substitution
    #
    def get_text_detail(self, config, which_text):
        DEFAULT_VALID_TEXT_POSITION = "cm"

        text = self.get_text(config, which_text)
        text_format = config.get(f"{which_text}-format")
        page = self.owner.page

        dflt_system_font = self.owner.get_attribute(f"system-font")
        if dflt_system_font is None:
            logger.error(f"button {self.owner.name}: no system font")

        dflt_text_font = self.owner.get_attribute(f"{which_text}-font")
        if dflt_text_font is None:
            dflt_text_font = self.owner.get_attribute("label-font")
            if dflt_text_font is None:
                logger.warning(f"button {self.owner.name}: no default label font, using system font")
                dflt_text_font = dflt_system_font

        text_font = config.get(f"{which_text}-font", dflt_text_font)

        dflt_text_size = self.owner.get_attribute(f"{which_text}-size")
        if dflt_text_size is None:
            dflt_text_size = self.owner.get_attribute("label-size")
            if dflt_text_size is None:
                dflt_text_size = 16
                logger.warning(f"button {self.owner.name}: no default label size, using {dflt_text_size}px")
        text_size = config.get(f"{which_text}-size", dflt_text_size)

        dflt_text_color = self.owner.get_attribute(f"{which_text}-color")
        if dflt_text_color is None:
            dflt_text_color = self.owner.get_attribute("label-color")
            if dflt_text_color is None:
                dflt_text_color = DEFAULT_COLOR
                logger.warning(f"button {self.owner.name}: no default label color, using {dflt_text_color}")
        text_color = config.get(f"{which_text}-color", dflt_text_color)
        text_color = convert_color(text_color)

        dflt_text_position = self.owner.get_attribute(f"{which_text}-position")
        if dflt_text_position is None:
            dflt_text_position = self.owner.get_attribute("label-position")
            if dflt_text_position is None:
                dflt_text_position = DEFAULT_VALID_TEXT_POSITION  # middle of icon
                logger.warning(f"button {self.owner.name}: no default label position, using {dflt_text_position}")
        text_position = config.get(f"{which_text}-position", dflt_text_position)
        if text_position[0] not in "lcr":
            text_position = DEFAULT_VALID_TEXT_POSITION
            logger.warning(f"button {self.owner.name}: {type(self).__name__}: invalid horizontal label position code {text_position}, using default")
        if text_position[1] not in "tmb":
            text_position = DEFAULT_VALID_TEXT_POSITION
            logger.warning(f"button {self.owner.name}: {type(self).__name__}: invalid vertical label position code {text_position}, using default")

        # print(f">>>> {self.owner.get_id()}:{which_text}", dflt_text_font, dflt_text_size, dflt_text_color, dflt_text_position)

        if text is not None and not isinstance(text, str):
            logger.warning(f"button {self.owner.name}: converting text {text} to string (type {type(text)})")
            text = str(text)

        return text, text_format, text_font, text_color, text_size, text_position

    def get_text(self, base: dict, root: str = CONFIG_KW.LABEL.value):  # root={label|text}
        """
        Extract label or text from base and perform formula and dataref values substitution if present.
        (I.e. replaces ${formula} and ${dataref} with their values.)
        """
        text = base.get(root)
        if text is None:
            return None

        # HACK 1: Special icon font substitution
        default_font = self.owner.get_attribute("label-font")
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
                        logger.debug(f"button {self.owner.name}: substituing font icon {i}")

        # Formula in text
        # If text contains ${formula}, it is replaced by the value of the formula calculation.
        text_format = base.get(f"{root}-format")
        KW_FORMULA_STR = f"${{{CONFIG_KW.FORMULA.value}}}"  # "${formula}"
        if KW_FORMULA_STR in str(text):
            res = ""
            formula = self.get_formula(base)
            if formula is not None:
                res = self.execute_formula(formula=formula)
                if res != "":  # Format output if format present
                    if text_format is not None:
                        logger.debug(f"button {self.owner.name}: {root}-format {text_format}: res {res} => {text_format.format(res)}")
                        res = text_format.format(res)
                    else:
                        res = str(res)
            else:
                logger.warning(f"button {self.owner.name}: text contains {KW_FORMULA_STR} but no {CONFIG_KW.FORMULA.value} attribute found")

            text = text.replace(KW_FORMULA_STR, res)

        # Rest of text: substitution of ${}
        if root != CONFIG_KW.LABEL.value:
            text = self.substitute_values(text, formatting=text_format, default="---")
        return text
