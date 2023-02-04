"""
Different button classes for different purpose.
Button base class does not perform any action, it mainly is an ABC.

Buttons do
1. Execute zero or more X-Plane command
2. Optionally update their representation to confirm the action

Button phases:
1. button_value() compute the unique value that will become an index in an array.
   Value is stored in current_value
2. if current_value has changed, provoke render()
3. render: set_key_icon(): get the key icon from the array of available icons and the index (current_value)
   render: get_image(): builds an image from the key icon and text overlay(s)
   render returns the image to the deck for display in the proper key.
"""
import re
import logging
import threading
import time
from datetime import datetime

from PIL import ImageDraw, ImageFont

from .button_activation import ACTIVATIONS
from .button_representation import REPRESENTATIONS
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
        btype = config.get("type")
        if btype is not None and btype in ACTIVATIONS:
            self._activation = ACTIVATIONS[btype](config, self)
            logger.debug(f"__init__: button {self.name} activation {btype}")
        else:
            logger.warning(f"__init__: button {self.name} has no activation")
            self._activation = ACTIVATIONS["none"](config, self)

        self._representation = None
        i = 0
        avail = list(REPRESENTATIONS.keys())
        while self._representation is None and i < len(avail):
            if avail[i] in config:
                self._representation = REPRESENTATIONS[avail[i]](config, self)
                logger.debug(f"__init__: button {self.name} representation {avail[i]}")
            i = i + 1
        if self._representation is None:
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

    @classmethod
    def new(cls, config: dict, page: "Page"):
        return cls(config=config, page=page)

    def id(self):
        return ":".join([self.deck.name, self.page.name, self.name])

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

        self.set_key_icon()

    def has_key_image(self):
        return True  # default

    def guard(self):
        return self.guarded if self.guarded is not None else False

    def set_current_value(self, value):
        self.previous_value = self.current_value
        self.current_value = value
        self.set_key_icon()

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

    def is_dotted(self, label: str):
        # check dataref status
        # AirbusFBW/ALTmanaged, AirbusFBW/HDGmanaged,
        # AirbusFBW/SPDmanaged, and AirbusFBW/BaroStdCapt
        hack = "AirbusFBW/BaroStdCapt" if label.upper() == "QNH" else f"AirbusFBW/{label}managed"
        status = self.is_pushed()
        if hack in self.xp.all_datarefs.keys():
            # logger.debug(f"is_dotted: {hack} = {self.xp.all_datarefs[hack].value()}")
            status = self.xp.all_datarefs[hack].value() == 1
        else:
            logger.warning(f"is_dotted: button {self.name} dataref {hack} not found")
        return status

    def get_datarefs(self, base:dict = None):
        """
        Returns all datarefs used by this button from label, computed datarefs, and explicitely
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

        # Use of datarefs in label:
        # 3. LABEL datarefs
        # 3.1 Label
        label = base.get("label")
        if label is not None and type(label) == str:
            datarefs = re.findall("\\${(.+?)}", label)
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"get_datarefs: button {self.name}: added label datarefs {datarefs}")

        if DATAREF_RPN in r:  # label: ${dataref-rpn}, "dataref-rpn" is not a dataref.
            r.remove(DATAREF_RPN)

        return list(set(r))  # removes duplicates

    # ##################################
    # Dataref processing
    #
    def get_dataref_value(self, dataref, default = None):
        d = self.page.datarefs.get(dataref)
        return d.current_value if d is not None else default

    def substitute_dataref_values(self, message: str, formatting = None, default: str = "0.0"):
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

    def execute_formula(self, default, formula: str = None):
        """
        replace datarefs variables with their (numeric) value and execute formula.
        Returns formula result.
        """
        if formula is not None:
            expr = self.substitute_dataref_values(formula)
            r = RPC(expr)
            value = r.calculate()
            # logger.debug(f"execute_formula: button {self.name}: {formula} => {expr}:  => {value}")
            logger.log(15, f"execute_formula: button {self.name}: {formula} => {expr} => {value}")
            return value

        logger.warning(f"execute_formula: button {self.name}: no formula")
        return default

    # ##################################
    # Icon image and label(s)
    #
    def get_label(self, base: dict):
        """
        Returns label, if any, with substitution of datarefs if any
        """
        DATAREF_RPN_STR = f"${{{DATAREF_RPN}}}"

        label = base.get("label")

        # If label contains ${dataref-rpn}, it is replaced by the value of the dataref-rpn calculation.
        # So we do it.
        if label is not None:
            if DATAREF_RPN in label:  # Perform substitution
                dataref_rpn = base.get(DATAREF_RPN)
                if dataref_rpn is not None:
                    res = self.execute_formula("", dataref_rpn)
                    if res != "":  # Format output if format present
                        label_format = base.get("label-format")
                        if label_format is not None:
                            logger.debug(f"get_label: button {self.name}: label_format {label_format} res {res} => {label_format.format(res)}")
                            res = label_format.format(res)
                        else:
                            res = str(res)
                    label = label.replace(DATAREF_RPN_STR, res)
                else:
                    logger.warning(f"get_label: button {self.name}: label contains {DATAREF_RPN_STR} but no {DATAREF_RPN} attribute found")
            else:
                label = self.substitute_dataref_values(label, formatting=label_format, default="---")

        return label

    # ##################################
    # Value and icon
    #
    def set_key_icon(self):
        v = self._activation.get_current_value()
        self._representation.set_current_value(v)

    def button_value(self):
        """
        Button ultimately returns one value that is either directly extracted from a single dataref,
        or computed from several dataref values (later).
        """
        # 1. Unique dataref
        if len(self.all_datarefs) == 1:
            # if self.all_datarefs[0] in self.page.datarefs.keys():  # unnecessary check
            logger.debug(f"button_value: button {self.name} get single dataref {self.all_datarefs[0]}")
            return self.execute_formula(default=self.get_dataref_value(self.all_datarefs[0]))
            # else:
            #     logger.warning(f"button_value: button {self.name}: {self.all_datarefs[0]} not in {self.page.datarefs.keys()}")
            #     return None
        # 2. Multiple datarefs
        elif len(self.all_datarefs) > 1:
            logger.debug(f"button_value: button {self.name} getting formula since more than one dataref")
            return self.execute_formula(default=0.0)
        # 3. A Dataref formula without dataref in it...
        elif self.dataref_rpn is not None:
            logger.debug(f"button_value: button {self.name} getting formula without dataref")
            return self.execute_formula(default=0.0)
        # 4. Special cases
        elif "counter" in self.options or "bounce" in self.options:
            logger.debug(f"button_value: button {self.name} has counter or bounce")
            return self._activation.get_current_value()
        if type(self).__name__ not in ["ColoredButton"] and not self.has_option("nostate"):  # command-only buttons without real "display"
            logger.debug(f"button_value: button {self.name}, datarefs: {len(self.all_datarefs)}, rpn: {self.dataref_rpn}, options: {self.options}")
            logger.warning(f"button_value: button {self.name}, no dataref, no formula, no counter, returning None (add options nostate to suppress this warning)")
        return None

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
        self.previous_value = None  # this will provoke a refresh of the value on data reload
