"""
Container object for one button.
Contains how to interact with (_activation) and how to represent it (_representation).
Has options.
Manage interaction with X-Plane, fetch or write datarefs.
Maintain a value.
"""
import re
import logging
import math
import yaml
from datetime import datetime

from .button_activation import ACTIVATIONS
from .button_representation import REPRESENTATIONS, Annunciator
from .xplane import Dataref
from .constant import ID_SEP, SPAM, FORMULA, WEATHER_ICON_FONT, ICON_FONT
from .rpc import RPC

from .resources.icons import icons as FA_ICONS        # Font Awesome Icons ${fa-arrow-up}
from .resources.weathericons import WEATHER_ICONS     # Weather Icons


logger = logging.getLogger("Button")
logger.setLevel(SPAM)
# logger.setLevel(logging.DEBUG)


PATTERN_DOLCB = "\\${([^\\}]+?)}"  # ${ ... }: dollar + anything between curly braces.

# ##########################################
# BUTTONS
#
class Button:

    def __init__(self, config: dict, page: "Page"):

        # Definition and references
        self._config = config
        self.page = page
        self.deck = page.deck
        self.xp = self.deck.cockpit.xp  # shortcut alias
        self.index = config.get("index")  # type: button, index: 4 (user friendly) -> _key = B4 (internal, to distinguish from type: push, index: 4).
        self._key = config.get("_key", self.index)  # internal key, mostly equal to index, but not always. Index is for users, _key is for this software.

        self.name = config.get("name", "-".join((self.page.name, str(self.index))))
        self.num_index = None
        if type(self.index) == str:
            idxnum = re.findall("\\d+(?:\\.\\d+)?$", self.index)  # just the numbers of a button index name knob3 -> 3.
            if len(idxnum) > 0:
                self.num_index = idxnum[0]

        # Working variables
        self._first_value_not_saved = True
        self._first_value = None    # first value the button will get
        self._use_activation_state = False
        self._last_activation_state = None
        self.initial_value = config.get("initial-value")
        self.current_value = None
        self.previous_value = None

        # Options
        self.options = []
        new = config.get("options")
        if new is not None:  # removes all spaces around = sign and ,. a = b, c, d=e -> a=b,c,d=e -> [a=b, c, d=e]
            old = ""         # a, c, d are options, b, e are option values. c option value is boolean True.
            while len(old) != len(new):
                old = new
                new = old.strip().replace(" =", "=").replace("= ", "=").replace(" ,", ",").replace(", ", ",")
            self.options = [a.strip() for a in new.split(",")]

        # What it will do and how it will appear
        self._activation = None
        atype = Button.guess_activation_type(config)
        if atype is not None and atype in ACTIVATIONS:
            self._activation = ACTIVATIONS[atype](config, self)
            logger.debug(f"__init__: button {self.name} activation {atype}")
        else:
            logger.warning(f"__init__: button {self.name} has no activation")
            self._activation = ACTIVATIONS["none"](config, self)

        self._representation = None
        rtype = Button.guess_representation_type(config)
        if rtype is not None and rtype in REPRESENTATIONS:
            self._representation = REPRESENTATIONS[rtype](config, self)
            logger.debug(f"__init__: button {self.name} representation {rtype}")
        else:
            logger.warning(f"__init__: button {self.name} has no representation")
            self._representation = REPRESENTATIONS["none"](config, self)

        # Datarefs
        self.dataref = config.get("dataref")
        self.dataref_rpn = config.get(FORMULA)
        self.managed = config.get("managed")

        self.guarded = None
        self.guard = config.get("guard")
        if self.guard is not None:
            self.guarded = self.guard.get("dataref")
            if self.guarded is None:
                logger.warning(f"__init__: button {self.name} has guard but no dataref")

        self.all_datarefs = None                # all datarefs used by this button
        self.all_datarefs = self.get_datarefs() # cache them
        if len(self.all_datarefs) > 0:
            self.page.register_datarefs(self)   # when the button's page is loaded, we monitor these datarefs

        self.init()

    @staticmethod
    def guess_index(config):
        return config.get("index")

    @staticmethod
    def guess_activation_type(config):
        a = config.get("type")
        if a is None:
            logger.debug(f"guess_activation_type: not type attribute, assuming 'none' type")
            a = "none"
        if a not in ACTIVATIONS.keys():
            logger.warning(f"guess_activation_type: invalid activation type {a} in {config}")
            return None
        return a

    @staticmethod
    def guess_representation_type(config):
        a = []
        for r in REPRESENTATIONS.keys():
            if r in config:
                a.append(r)
        if len(a) == 1:
            return a[0]
        elif len(a) == 0:
            idx = config.get("index", "")
            if not str(idx).startswith("knob"):
                logger.warning(f"guess_representation_type: no represetation in {config}")
        else:
            logger.warning(f"guess_representation_type: multiple represetation {a} in {config}")
        return "none"

    def get_id(self):
        return ID_SEP.join([self.page.get_id(), self.name])

    def get_button_value(self, name):
        if name is None or len(name) == 0:
            v = self.get_current_value()
            if type(v) not in [int, float, str]:
                logger.warning(f"get_button_value: value of {name} is {type(v)}")
            return v
        a = name.split(":")
        if len(a) > 1:
            s = self.get_status()
            if a[1] in s.keys():
                return s[a[1]]
            else:
                logger.warning(f"get_button_value: so such variable {a[1]}")
        else:
            v = self.get_current_value()
            if type(v) not in [int, float, str]:
                logger.warning(f"get_button_value: value of {name} is {type(v)}")
            return v
        return None

    def id(self):
        return self.get_id()

    def inspect(self, what: str = None):
        """
        Return information aout button status
        """
        logger.info(f"Button {self.name} -- {what}")
        if "datarefs" in what:
            logger.info("-- Datarefs:")
            for d in self.get_datarefs():
                v = self.get_dataref_value(d)
                logger.info(f"    {d} = {v}")
        if "activation" in what:
            logger.info("-- Activation:")
            self._activation.inspect(what)
        if "representation" in what:
            logger.info("-- Representation:")
            self._representation.inspect(what)
        if "status" in what:
            logger.info("-- Status:")
            logger.info(yaml.dump(self.get_status()))
        if "desc" in what:
            logger.info("-- Description:")
            logger.info(self.describe())
        if "config" in what:
            logger.info("-- Config:")
            logger.info(f"\n{yaml.dump(self._config)}")

    def describe(self):
        return "\n\r".join([self._activation.describe(), self._representation.describe()])

    def on_current_page(self):
        """
        Returns whether button is on current page
        """
        return self.deck.current_page == self.page

    def init(self):
        """
        Install button
        """
        # Set initial value if not already set
        if self._first_value_not_saved:
            logger.debug(f"init: button {self.name} setting initial value..")
            if self.initial_value is not None:
                logger.debug(f"init: button {self.name} .. from initial-value")
                self.set_current_value(self.initial_value)
            else:
                logger.debug(f"init: button {self.name} .. from button_value")
                self.set_current_value(self.button_value())
            logger.debug(f"init: button {self.name}: ..has value {self.current_value}.")
        else:
            logger.debug(f"init: button {self.name}: already has a value ({self.current_value}), initial value ignored")
        # logger.info(f"init: button {self.name}: {self.id()}")

    def set_current_value(self, value):
        if self._first_value_not_saved:
            self._first_value = value
            self._first_value_not_saved = False
        self.previous_value = self.current_value
        self.current_value = value
        logger.debug(f"set_current_value: button {self.name}: {self.current_value}")

    def get_current_value(self):
        """
        Gets the current value, but does not provoke a calculation, just returns the current value.
        """
        logger.debug(f"get_current_value: button {self.name}: {self.current_value}")
        return self.current_value

    def has_changed(self) -> bool:
        if self.previous_value is None and self.current_value is None:
            return False
        elif self.previous_value is None and self.current_value is not None:
            return True
        elif self.previous_value is not None and self.current_value is None:
            return True
        return self.current_value != self.previous_value

    def is_valid(self) -> bool:
        """
        Validate button data once and for all
        """
        if self.deck is None:
            logger.warning(f"is_valid: button {self.name} has no deck")
            return False
        if self.index is None:
            logger.warning(f"is_valid: button {self.name} has no index")
            return False
        if self._activation is None:
            logger.warning(f"is_valid: button {self.name} has no activation")
            return False
        if not self._activation.is_valid():
            logger.warning(f"is_valid: button {self.name} activation is not valid")
            return False
        if self._representation is None:
            logger.warning(f"is_valid: button {self.name} has no representation")
            return False
        if not self._representation.is_valid():
            logger.warning(f"is_valid: button {self.name} representation is not valid")
            return False
        return True

    def has_option(self, option):
        # Check whether a button has an option.
        for opt in self.options:
            if opt.split("=")[0].strip() == option:
                return True
        return False

    def option_value(self, option, default = None):
        # Return the value of an option or the supplied default value.
        for opt in self.options:
            opt = opt.split("=")
            name = opt[0]
            if name == option:
                if len(opt) > 1:
                    return opt[1]
                else:  # found just the name, so it may be a boolean, True if present
                    return True
        return default

    def get_datarefs(self, base:dict = None):
        """
        Returns all datarefs used by this button from label, texts, computed datarefs, and explicitely
        listed dataref and datarefs attributes.
        This can be applied to the entire button or to a subset (for annunciator parts)
        """
        if base is None:  # local, button-level ones
            if self.all_datarefs is not None:  # cached if globals (base is None)
                return self.all_datarefs

        r = self.scan_datarefs(self._config)
        # Activation datarefs
        if self._activation is not None:
            datarefs = self._activation.get_datarefs()
            if datarefs is not None:
                r = r + datarefs
                logger.debug(f"get_datarefs: button {self.name}: added activation datarefs {datarefs}")
        # Representation datarefs
        if self._representation is not None:
            datarefs = self._representation.get_datarefs()
            if datarefs is not None:
                r = r + datarefs
                logger.debug(f"get_datarefs: button {self.name}: added representation datarefs {datarefs}")
        return list(set(r))  # removes duplicates

    def scan_datarefs(self, base:dict):
        """
        scan all datarefs in texts, computed datarefs, or explicitely listed.
        This is applied to the entire button or to a subset (for annunciator parts for example).
        """
        def is_dref(r):
            PREFIX = ["fa", "wi", "button", "state"]
            SEP = ":"
            for s in PREFIX:
                if r.startswith(s+SEP):
                    return False
            return True

        r = []

        # Direct use of datarefs:
        #
        # 1. Single
        dataref = base.get("dataref")
        if dataref is not None:
            r.append(dataref)
            logger.debug(f"scan_datarefs: button {self.name}: added single dataref {dataref}")

        # 1b. Managed values
        managed = base.get("managed")
        if managed is not None:
            r.append(managed)
            logger.debug(f"scan_datarefs: button {self.name}: added managed dataref {managed}")

        # 1c. Guarded buttons
        guarded = None
        guard_dict = base.get("guard")
        if guard_dict is not None:
            guarded = guard_dict.get("dataref")
        if guarded is not None:
            r.append(guarded)
            logger.debug(f"scan_datarefs: button {self.name}: added guarding dataref {guarded}")

        # logger.debug(f"get_datarefs: button {base.name}: {r}, {base.datarefs}")

        # Use of datarefs in formula:
        #
        # 2. Formula datarefs
        dataref_rpn = base.get(FORMULA)
        if dataref_rpn is not None and type(dataref_rpn) == str:
            datarefs = re.findall(PATTERN_DOLCB, dataref_rpn)
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"scan_datarefs: button {self.name}: added formula datarefs {datarefs}")

        # Use of datarefs in label or text
        #
        # 3. LABEL datarefs
        # 3.1 Label
        label = base.get("label")
        if label is not None and type(label) == str:
            datarefs = re.findall(PATTERN_DOLCB, label)
            datarefs = list(filter(lambda x: is_dref(x), datarefs))
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"scan_datarefs: button {self.name}: added label datarefs {datarefs}")

        # 3.2 Button Text
        text = base.get("text")
        if text is not None and type(text) == str:
            datarefs = re.findall(PATTERN_DOLCB, text)
            datarefs = list(filter(lambda x: is_dref(x), datarefs))
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"scan_datarefs: button {self.name}: added text datarefs {datarefs}")

        # Clean up
        if FORMULA in r:  # label or text may contain ${formula}, FORMULA is not a dataref.
            r.remove(FORMULA)

        return list(set(r))  # removes duplicates

    # ##################################
    # Dataref processing
    #
    def get_dataref_value(self, dataref, default = None):
        d = self.page.datarefs.get(dataref)
        return d.current_value if d is not None else default

    def is_managed(self):
        if self.managed is None:
            return False
        d = self.get_dataref_value(self.managed, default= 0)
        if d != 0:
            logger.log(SPAM, f"is_managed: button {self.name}: is managed ({d}).")
            return True
        return False
        # return self.managed is not None and self.get_dataref_value(dataref=self.managed, default=0) != 0

    def is_guarded(self):
        if self.guarded is None:
            return False
        d = self.get_dataref_value(self.guarded, default=0)
        if d == 0:
            logger.log(SPAM, f"is_guarded: button {self.name}: is guarded ({d}).")
            return True
        return False
        # return self.guarded is not None and self.get_dataref_value(dataref=self.guarded, default=0) != 0

    def substitute_dataref_values(self, message: str, default: str = "0.0", formatting = None):
        """
        Replaces ${dataref} with value of dataref in labels and execution formula.
        """
        if type(message) == int or type(message) == float:  # probably formula is a contant value
            value_str = message
            if formatting is not None:
                if formatting is not None:
                    value_str = formatting.format(message)
                    logger.debug(f"substitute_dataref_values: button {self.name}: received int or float, returning as is.")
                else:
                    value_str = str(message)
                    logger.debug(f"substitute_dataref_values: button {self.name}: received int or float, returning formatted {formatting}.")
            return value_str

        dataref_names = re.findall(PATTERN_DOLCB, message)
        if len(dataref_names) == 0:
            return message
        if formatting is not None:
            if type(formatting) == list:
                if len(dataref_names) != len(formatting):
                    logger.warning(f"substitute_dataref_values: button {self.name}: number of datarefs {len(dataref_names)} not equal to the number of format {len(formatting)}, cannot proceed.")
                    return message
            elif type(formatting) != str:
                logger.warning(f"substitute_dataref_values: button {self.name}: single format is not a string, cannot proceed.")
                return message
        retmsg = message
        cnt = 0
        for dataref_name in dataref_names:
            value = self.get_dataref_value(dataref_name)
            value_str = ""
            if formatting is not None and value is not None:
                if type(formatting) == list:
                    value_str = formatting[cnt].format(value)
                elif formatting is not None and type(formatting) == str:
                    value_str = formatting.format(value)
            else:
                value_str = str(value) if value is not None else str(default)  # default gets converted in float sometimes!
            retmsg = retmsg.replace(f"${{{dataref_name}}}", value_str)
            cnt = cnt + 1

        more = re.findall(PATTERN_DOLCB, retmsg) # XXXHERE
        if len(more) > 0:
            logger.warning(f"substitute_dataref_values: button {self.name}: unsubstituted dataref values {more}")

        return retmsg

    def substitute_state_values(self, text, default: str = "0.0", formatting = None):
        status = self.get_status()
        txtcpy = text
        # more = re.findall("\\${status:([^\\}]+?)}", txtcpy)
        for k, v in status.items():
            s = f"${{state:{k}}}"      # @todo: !!possible injection!!
            if s in txtcpy:
                if v is None:
                    logger.warning(f"substitute_status_value: button {self.name}: {k} has no value")
                    v = str(default)
                else:
                    v = str(v)  # @todo: later: use formatting
                txtcpy = txtcpy.replace(s, v)
                logger.debug(f"substitute_status_value: button {self.name}: replaced {s} by {str(v)}. ({k})")
        more = re.findall("\\${status:([^\\}]+?)}", txtcpy)
        if len(more) > 0:
            logger.warning(f"substitute_status_value: button {self.name}: unsubstituted status values {more}")
        return txtcpy

    def substitute_button_values(self, text, default: str = "0.0", formatting = None):
        txtcpy = text
        more = re.findall("\\${button:([^\\}]+?)}", txtcpy)
        if len(more) > 0:
            for m in more:
                v = self.deck.cockpit.get_button_value(m)  # starts at the top
                if v is None:
                    logger.warning(f"substitute_button_values: button {self.name}: {m} has no value")
                    v = str(default)
                else:
                    v = str(v)  # @todo: later: use formatting
                m_str = f"${{button:{m}}}"   # "${formula}"
                txtcpy = txtcpy.replace(m_str, v)
                logger.debug(f"substitute_button_values: button {self.name}: replaced {m_str} by {str(v)}. ({m})")
        more = re.findall("\\${button:([^\\}]+?)}", txtcpy)
        if len(more) > 0:
            logger.warning(f"substitute_button_values: button {self.name}: unsubstituted button values {more}")
        return txtcpy

    def substitute_values(self, text, default: str = "0.0", formatting = None):
        if type(text) != str or "$" not in text:  # no ${..} to stubstitute
            return text
        t1 = self.substitute_state_values(text, default=default, formatting=formatting)
        if text != t1:
            logger.log(SPAM, f"substitute_values: button {self.name}: {text} => {t1}")
        # t2 = self.substitute_button_values(t1, default=default, formatting=formatting)
        # logger.log(SPAM, f"substitute_values: button {self.name}: {t1} => {t2}")
        t2 = t1
        t3 = self.substitute_dataref_values(t2, default=default, formatting=formatting)
        if t3 != t2:
            logger.log(SPAM, f"substitute_values: button {self.name}: {t2} => {t3}")
        return t3

    def execute_formula(self, formula, default: float = 0.0):
        """
        replace datarefs variables with their (numeric) value and execute formula.
        Returns formula result.
        """
        expr = self.substitute_values(text=formula, default=str(default))
        # logger.debug(f"execute_formula: button {self.name}: {formula} => {expr}")
        r = RPC(expr)
        value = r.calculate()
        logger.log(SPAM, f"execute_formula: button {self.name}: {formula} => {expr}:  => {value}")
        return value

    # ##################################
    # Text(s)
    #
    def get_text(self, base: dict, root: str = "label"):  # root={label|text}
        """
        Extract label or text from base and perform formula and dataref values substitution if present.
        (I.e. replaces ${formula} and ${dataref} with their values.)
        """
        DOT = "."
        DATEREF_RPN_INF = "---"
        text = base.get(root)
        if text is not None:
            if self.is_managed():  # managed
                if root == "label" and self.has_option("dot"): # we just append a DOT next to the label
                    return text + DOT
                elif root == "label" and self.has_option("std"): # QNH Std
                    return "Std"
                elif root == "text":
                    return DATEREF_RPN_INF + " " + DOT

            # HACK
            bizfonts = {
                "fa": (ICON_FONT, FA_ICONS),
                "wi": (WEATHER_ICON_FONT, WEATHER_ICONS)
            }
            text_font = base.get(root+"-font", self.page.default_label_font)
            for k, v in bizfonts.items():
                if text_font.lower().startswith(v[0]):
                    s = "\\${%s:([^\\}]+?)}" % (k)
                    icons = re.findall(s, text)
                    for i in icons:
                        if i in v[1].keys():
                            text = text.replace(f"${{{k}:{i}}}", v[1][i])
                            logger.debug(f"get_text_detail: button {self.name}: substituing {i}")

            text_format = base.get(f"{root}-format")
            if FORMULA in str(text):
                # If text contains ${formula}, it is replaced by the value of the formula calculation.
                dataref_rpn = base.get(FORMULA)
                if dataref_rpn is not None:
                    res = self.execute_formula(formula=dataref_rpn)
                    if res == math.inf:
                        res = DATEREF_RPN_INF
                    elif res != "":  # Format output if format present
                        if text_format is not None:
                            logger.debug(f"get_text: button {self.name}: {root}-format {text_format}: res {res} => {text_format.format(res)}")
                            res = text_format.format(res)
                        else:
                            res = str(res)
                    FORMULA_STR = f"${{{FORMULA}}}"   # "${formula}"
                    text = text.replace(FORMULA_STR, res)
                else:
                    logger.warning(f"get_text: button {self.name}: text contains {FORMULA_STR} but no {FORMULA} attribute found")
            text = self.substitute_values(text, formatting=text_format, default="---")

        return text

    # ##################################
    # Value
    #
    def button_value(self):
        """
        Button ultimately returns either one value or an array of values if representation requires it.
        """
        def has_no_state():
            return self._activation._has_no_value or self._config.get("type") == "none"

        # 1. Special cases (Annunciator): Each annunciator part has its own evaluation
        if isinstance(self._representation, Annunciator):
            logger.debug(f"button_value: button {self.name}: is Annunciator, returning part values")
            return self._representation.get_current_values()

        # 2. No dataref
        if len(self.all_datarefs) == 0:
            if self.dataref_rpn is not None:
                logger.debug(f"button_value: button {self.name}: getting formula without dataref")
                return self.execute_formula(formula=self.dataref_rpn)

        # 3. One dataref
        if len(self.all_datarefs) == 1:
            # if self.all_datarefs[0] in self.page.datarefs.keys():  # unnecessary check
            logger.debug(f"button_value: button {self.name}: getting single dataref {self.all_datarefs[0]}")
            if self.dataref_rpn is not None:
                logger.debug(f"button_value: button {self.name} getting formula with one dataref")
                return self.execute_formula(formula=self.dataref_rpn)
            else:  # if no formula, returns dataref as it is
                return self.get_dataref_value(self.all_datarefs[0])

        # 4. Multiple datarefs
        if len(self.all_datarefs) > 1:
            # 4.1 Mutiple Dataref with a formula, returns only one value
            if self.dataref_rpn is not None:
                logger.debug(f"button_value: button {self.name}: getting formula with several datarefs")
                return self.execute_formula(formula=self.dataref_rpn)
            # 4.2 Mutiple Dataref but no formula, returns an array of values of datarefs in multi-dateref
            # !! May be we should return them all?
            r = {}
            for d in self.all_datarefs:
                v = self.get_dataref_value(d)
                r[d] = v
            logger.debug(f"button_value: button {self.name}: returning dict of datarefs")
            return r

        # 5. Value is based on activation state:
        if not has_no_state():
            logger.warning(f"button_value: button {self.page.name}/{self.index}/{self.name}: use internal activation value")
        self._use_activation_state = True
        self._last_activation_state = self._activation.get_status()
        # logger.log(SPAM, f"button_value: button {self.name}: returning activation current value ({self._last_activation_state})")
        if "current_value" in self._last_activation_state:
            logger.debug(f"button_value: button {self.name}: returning activation current value ({self._last_activation_state['current_value']})")
            return self._last_activation_state["current_value"]
        return self._last_activation_state

    # ##################################
    # External API
    #
    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        if not isinstance(dataref, Dataref):
            logger.error(f"dataref_changed: button {self.name}: not a dataref")
            return
        self.set_current_value(self.button_value())
        if self.has_changed() or dataref.has_changed():
            logger.log(SPAM, f"dataref_changed: button {self.name}: {self.previous_value} -> {self.current_value}")
            self.render()
        else:
            logger.debug(f"dataref_changed: button {self.name}: no change")

    def activate(self, state: bool):
        """
        @todo: Return a status from activate()
        """
        if not self._activation.is_valid():
            logger.warning(f"activate: button {self.name}: activation is not valid")
            return
        self._activation.activate(state)
        if self.has_changed():
            logger.log(SPAM, f"activate: button {self.name}: {self.previous_value} -> {self.current_value}")
            self.render()
        else:
            logger.debug(f"activate: button {self.name}: no change")

    def get_status(self):
        """
        """
        a = {
            "managed": self.managed,
            "guarded": self.guarded
        }
        return self._activation.get_status() | a
        # if self._representation is not None:
        #     return self._representation.get_status()

    def get_representation(self):
        """
        Called from deck to get what's necessary for displaying this button on the deck.
        It can be an image, a color, a binary value on/off...
        """
        if not self._representation.is_valid():
            logger.warning(f"get_representation: button {self.name}: representation is not valid")
            return None
        return self._representation.render()

    def render(self):
        """
        Ask deck to render this buttonon the deck. From the button's rendering, the deck will know what
        to ask to the button and render it.
        """
        if self.deck is not None:
            if self.on_current_page():
                self.deck.render(self)
                # logger.debug(f"render: button {self.name} rendered")
            else:
                logger.debug(f"render: button {self.name} not on current page")
        else:
            logger.debug(f"render: button {self.name} has no deck")

    def clean(self):
        """
        Button removes itself from device
        """
        self.previous_value = None  # this will provoke a refresh of the value on data reload
        self._representation.clean()
