"""
Container object for one button.
Contains how to interact with (_activation) and how to represent it (_representation).
Has options.
Manage interaction with X-Plane, fetch or write datarefs.
Maintain a value.
"""
import re
import logging
import threading
import time
from datetime import datetime

from PIL import ImageDraw, ImageFont

from .button_activation import ACTIVATIONS
from .button_representation import REPRESENTATIONS
from .button_annunciators import Annunciator
from .constant import DATAREF_RPN
from .color import convert_color
from .rpc import RPC


logger = logging.getLogger("Button")
logger.setLevel(15)
# logger.setLevel(logging.DEBUG)


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
        self.name = config.get("name", f"{type(self).__name__}-{config['index']}")
        self.index = config.get("index")  # type: button, index: 4 (user friendly) -> _key = B4 (internal, to distinguish from type: push, index: 4).
        self._key = config.get("_key", self.index)  # internal key, mostly equal to index, but not always. Index is for users, _key is for this software.
        self.num_index = None
        if type(self.index) == str:
            idxnum = re.findall("\\d+(?:\\.\\d+)?$", self.index)  # just the numbers of a button index name knob3 -> 3.
            if len(idxnum) > 0:
                self.num_index = idxnum[0]

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

        # Working variables
        self._first_value = None    # first value the button will get
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

        # Datarefs
        self.dataref = config.get("dataref")
        self.datarefs = config.get("multi-datarefs")
        self.dataref_rpn = config.get(DATAREF_RPN)

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
            logger.warning(f"guess_representation_type: no represetation in {config}")
        else:
            logger.warning(f"guess_representation_type: multiple represetation {a} in {config} which is not permitted")
        return "none"

    def id(self):
        return ":".join([self.deck.name, self.page.name, str(self.index)])

    def inspect(self):
        """
        Return information aout button status
        """
        logger.info(f"Button {self.name} -- Statistics")
        logger.info("Datarefs:")
        for d in self.get_datarefs():
            v = self.get_dataref_value(d)
            logger.info(f"    {d} = {v}")

    def register_activation(self, activation):
        self._activation = activation

    def register_representation(self, representation):
        self._representation = representation

    def on_current_page(self):
        """
        Returns whether button is on current page
        """
        return self.deck.current_page == self.page

    def init(self):
        """
        Install button
        """
        if self.has_option("bounce") and self.multi_icons is not None and len(self.multi_icons) > 0:
            stops = self.option_value(option="stops", default=len(self.multi_icons))
            self.bounce_arr = self.make_bounce_array(stops)

        # test: we try to immediately get a first value
        logger.debug(f"init: button {self.name} setting initial value..")
        if self.initial_value is not None:
            self.set_current_value(self.initial_value)
            self._first_value = self.initial_value
        else:
            self.set_current_value(self.button_value())
        if self._first_value is None and self.dataref is None and self.datarefs is None and self.dataref_rpn is None:  # won't get a value from datarefs
            self._first_value = self.current_value
        logger.debug(f"init: button {self.name}: ..has value {self.current_value}.")

        if self.has_option("guarded"):
            self.guarded = True   # guard type is option value: guarded=cover or grid.

    def guard(self):
        return self.guarded if self.guarded is not None else False

    def set_current_value(self, value):
        self.previous_value = self.current_value
        self.current_value = value
        # transfer changes in activation and representation
        # activation knows where to get its value from and may fetch this button's current value.
        self._representation.set_current_value(self._activation.get_current_value())

    def get_current_value(self):
        return self.current_value

    def value_has_changed(self) -> bool:
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
        if self._representation is None:
            logger.warning(f"is_valid: button {self.name} has no representation")
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
            if self.all_datarefs is not None:  # cached
                return self.all_datarefs
            base = self._config                # else, runs through config

        r = []
        # Use of datarefs in button:
        # 1. RAW datarefs
        # 1.1 Single
        dataref = base.get("dataref")
        if dataref is not None:
            r.append(dataref)
            logger.debug(f"get_datarefs: button {self.name}: added single dataref {dataref}")
        # 1.2 Multiple
        datarefs = base.get("multi-datarefs")  # base.get("datarefs")
        if datarefs is not None:
            r = r + datarefs
            logger.debug(f"get_datarefs: button {self.name}: added multiple datarefs {datarefs}")
        # logger.debug(f"get_datarefs: button {base.name}: {r}, {base.datarefs}")

        # Use of datarefs in formula:
        # 2. Formulae datarefs
        dataref_rpn = base.get(DATAREF_RPN)
        if dataref_rpn is not None and type(dataref_rpn) == str:
            datarefs = re.findall("\\${(.+?)}", dataref_rpn)
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"get_datarefs: button {self.name}: added formula datarefs {datarefs}")

        # Use of datarefs in label or text:
        # 3. LABEL datarefs
        # 3.1 Label
        label = base.get("label")
        if label is not None and type(label) == str:
            datarefs = re.findall("\\${(.+?)}", label)
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"get_datarefs: button {self.name}: added label datarefs {datarefs}")
        # 3.1 Button Text
        text = base.get("text")
        if text is not None and type(text) == str:
            datarefs = re.findall("\\${(.+?)}", text)
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"get_datarefs: button {self.name}: added text datarefs {datarefs}")

        if DATAREF_RPN in r:  # label or text may contain ${dataref-rpn}, "dataref-rpn" is not a dataref.
            r.remove(DATAREF_RPN)

        return list(set(r))  # removes duplicates

    # ##################################
    # Dataref processing
    #
    def get_dataref_value(self, dataref, default = None):
        d = self.page.datarefs.get(dataref)
        return d.current_value if d is not None else default

    def substitute_dataref_values(self, message: str, default: str = "0.0", formatting = None):
        """
        Replaces ${dataref} with value of dataref in labels and execution formula.
        """
        if type(message) == int or type(message) == float:  # probably dataref-rpn is a contant value
            logger.debug(f"substitute_dataref_values: button {self.name}: received int or float, returning as is.")
            return str(message)

        dataref_names = re.findall("\\${(.+?)}", message)
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
                elif formatting is not None and  type(formatting) == str:
                    value_str = formatting.format(value)
            else:
                value_str = str(value) if value is not None else default
            retmsg = retmsg.replace(f"${{{dataref_name}}}", value_str)
            cnt = cnt + 1
        return retmsg

    def execute_formula(self, formula, default: str = "0.0", formatting = None):
        """
        replace datarefs variables with their (numeric) value and execute formula.
        Returns formula result.
        """
        expr = self.substitute_dataref_values(message=formula, default=default)
        r = RPC(expr)
        value = r.calculate()
        # logger.debug(f"execute_formula: button {self.name}: {formula} => {expr}:  => {value}")
        logger.log(15, f"execute_formula: button {self.name}: {formula} => {expr} => {value}")
        if formatting is not None:
            logger.debug(f"execute_formula: button {self.name}: formatting {formatting}: res {value} => {formatting.format(value)}")
            value = formatting.format(value)
        return value

    # ##################################
    # Icon image and label(s)
    #
    def get_text(self, base: dict, root: str = "label"):  # root={label|text}
        """
        Extract label or text from base and perform dataref-rpn and dataref values substitution if present.
        (I.e. replaces ${dataref-rpn} and ${dataref} with their values.)
        """
        DATAREF_RPN_STR = f"${{{DATAREF_RPN}}}"

        text = base.get(root)

        if text is not None:
            if DATAREF_RPN in text:
                # If text contains ${dataref-rpn}, it is replaced by the value of the dataref-rpn calculation.
                dataref_rpn = base.get(DATAREF_RPN)
                if dataref_rpn is not None:
                    res = self.execute_formula(formula=dataref_rpn, default="")
                    if res != "":  # Format output if format present
                        text_format = base.get(f"{root}-format")
                        if text_format is not None:
                            logger.debug(f"get_text: button {self.name}: {root}-format {text_format}: res {res} => {text_format.format(res)}")
                            res = text_format.format(res)
                        else:
                            res = str(res)
                    text = text.replace(DATAREF_RPN_STR, res)
                else:
                    logger.warning(f"get_text: button {self.name}: text contains {DATAREF_RPN_STR} but no {DATAREF_RPN} attribute found")
            else:
                # If text contains ${dataref}s, they are replaced by their value.
                text_format = base.get(f"{root}-format")
                text = self.substitute_dataref_values(text, formatting=text_format, default="---")

        return text

    # ##################################
    # Value and icon
    #
    def button_value(self):
        """
        Button ultimately returns either one value or an array of values if representation requires it.
        """
        # 1. No dataref
        if len(self.all_datarefs) == 0:
            if self.dataref_rpn is not None:
                logger.debug(f"button_value: button {self.name}: getting formula without dataref")
                return self.execute_formula(formula=self.dataref_rpn, default=0.0)

        # 2. One dataref
        if len(self.all_datarefs) == 1:
            # if self.all_datarefs[0] in self.page.datarefs.keys():  # unnecessary check
            logger.debug(f"button_value: button {self.name}: getting single dataref {self.all_datarefs[0]}")
            if self.dataref_rpn is not None:
                logger.debug(f"button_value: button {self.name} getting formula with one dataref")
                return self.execute_formula(formula=self.dataref_rpn, default=0.0)
            else:  # if no formula, returns dataref as it is
                return self.get_dataref_value(self.all_datarefs[0])

        # 3. Multiple datarefs
        if len(self.all_datarefs) > 1:
            # 3.1 Mutiple Dataref with a formula, returns only one value
            if self.dataref_rpn is not None:
                logger.debug(f"button_value: button {self.name}: getting formula with several datarefs")
                return self.execute_formula(formula=self.dataref_rpn, default=0.0)
            # 3.1 Mutiple Dataref but no formula, returns an array of values of datarefs in multi-dateref
            r = []
            for d in self.multi_datarefs:
                v = self.get_dataref_value(d)
                r.append(v)
            logger.debug(f"button_value: button {self.name}: returning several individual datarefs")
            return r

        # 4. Special cases (Annunciator)
        if isinstance(self._representation, Annunciator):
            logger.debug(f"button_value: button {self.name}: is Annunciator, returning part values")
            return self._representation.part_values()

        # 5. Value is based on activation state:
        logger.debug(f"button_value: button {self.name}: returning state value")
        logger.debug(f"button_value: button {self.name}: datarefs: {len(self.all_datarefs)}, rpn: {self.dataref_rpn}, options: {self.options}")
        return self._activation.get_current_value()

    # ##################################
    # External API
    #
    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        self.set_current_value(self.button_value())
        if self._first_value is None:  # store first non None value received from datarefs
            self._first_value = self.current_value
        logger.debug(f"{self.name}: {self.previous_value} -> {self.current_value}")
        self.render()

    def activate(self, state: bool):
        """
        Function that is executed when a button is pressed (state=True) or released (state=False) on the Stream Deck device.
        Default is to tally number of times this button was pressed. It should have been released as many times :-D.
        **** No command gets executed here **** except if there is an associated view with the button.
        Also, removes guard if it was present. @todo: close guard
        """
        self._activation.activate(state)
        # logger.debug(f"activate: button {self.name} activated ({state}, {self.pressed_count})")

    def get_representation(self):
        """
        Called from deck to get what's necessary for displaying this button on the deck.
        It can be an image, a color, a binary value on/off...
        """
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