"""
Container object for one "button".
Contains how to interact with (_activation) and how to represent it (_representation).
Has options.
Manage interaction with X-Plane, fetch or write datarefs.
Maintain a "value", and some internal attributes.
"""

import re
import logging
import sys

from .buttons.activation import ACTIVATIONS
from .buttons.representation import REPRESENTATIONS, Annunciator
from .simulator import Dataref, DatarefListener, DatarefSetListener
from .resources.iconfonts import ICON_FONTS
from .resources.color import DEFAULT_COLOR, convert_color
from .value import Value, ValueProvider

from cockpitdecks import ID_SEP, SPAM_LEVEL, CONFIG_KW, yaml, DEFAULT_ATTRIBUTE_PREFIX, parse_options

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)

DECK_BUTTON_DEFINITION = "_deck_def"


class Button(DatarefListener, DatarefSetListener, ValueProvider):
    def __init__(self, config: dict, page: "Page"):
        DatarefListener.__init__(self)
        DatarefSetListener.__init__(self)
        # Definition and references
        self._config = config
        self._def = config.get(DECK_BUTTON_DEFINITION)
        self.page: "Page" = page
        self.deck = page.deck
        self.sim = self.deck.cockpit.sim  # shortcut alias
        # stats
        self._render = 0
        self._clean = 0
        self._activs = 0
        self._repres = 0

        self.deck.cockpit.set_logging_level(__name__)

        self.index = config.get("index")  # button_type: button, index: 4 (user friendly) -> _key = B4 (internal, to distinguish from type: push, index: 4).
        self._key = config.get("_key", self.index)  # internal key, mostly equal to index, but not always. Index is for users, _key is for this software.

        self._definition = self.deck.get_deck_type().get_button_definition(self.index)  # kind of meta data capabilties of button

        self.name = config.get("name", str(self.index))
        self.num_index = None
        if type(self.index) is str:
            idxnum = re.findall("\\d+(?:\\.\\d+)?$", self.index)  # just the numbers of a button index name knob3 -> 3.
            if len(idxnum) > 0:
                self.num_index = idxnum[0]

        # # Logging level
        # self.logging_level = config.get("logging-level", "INFO")
        # llvalue = getattr(logging, self.logging_level)
        # if llvalue is not None:
        #     logger.setLevel(llvalue)
        #     logger.debug(f"button {self.name}: logging level set to {self.logging_level}")

        # Working variables
        self._value = Value(self.name, config=config, button=self)
        self._first_value_not_saved = True
        self._first_value = None  # first value the button will get
        self._last_activation_state = None
        self.initial_value = config.get("initial-value")
        self.current_value = None
        self.previous_value = None

        #### Options
        #
        self.options = parse_options(config.get("options"))
        self.managed = None
        self.guarded = None

        #### Activation
        #
        self._activation = None
        atype = Button.guess_activation_type(config)
        if atype is not None and atype in ACTIVATIONS:
            self._activation = ACTIVATIONS[atype](self)
            logger.debug(f"button {self.name} activation {atype}")
        else:
            logger.info(f"button {self.name} has no activation defined, using default activation 'none'")
            self._activation = ACTIVATIONS["none"](self)

        #### Representation
        #
        self._representation = None

        idx = Button.guess_index(config)
        rtype = Button.guess_representation_type(config)
        if rtype is not None and rtype in REPRESENTATIONS:
            self._representation = REPRESENTATIONS[rtype](self)
            logger.debug(f"button {self.name} representation {rtype}")
        else:
            logger.info(f"button {self.name} has no representation defined, using default representation 'none'")
            self._representation = REPRESENTATIONS["none"](self)

        self._hardware_representation = None
        if self.deck.is_virtual_deck() and self._def.has_hardware_representation():
            rtype = self._def.get_hardware_representation()
            if rtype is not None and rtype in REPRESENTATIONS:
                logger.debug(f"button {self.name} has hardware representation {rtype}")
                self._hardware_representation = REPRESENTATIONS[rtype](self)

        #### Datarefs
        #
        self.dataref = config.get(CONFIG_KW.DATAREF.value)
        self.dataref_rpn = config.get(CONFIG_KW.FORMULA.value)
        self.manager = config.get(CONFIG_KW.MANAGED.value)
        if self.manager is not None:
            self.managed = self.manager.get(CONFIG_KW.DATAREF.value)
            if self.managed is None:
                logger.warning(f"button {self.name} has manager but no dataref")

        self.guard = config.get(CONFIG_KW.GUARD.value)
        if self.guard is not None:
            self.guarded = self.guard.get(CONFIG_KW.DATAREF.value)
            if self.guarded is None:
                logger.warning(f"button {self.name} has guard but no dataref")

        self.string_datarefs = config.get(CONFIG_KW.STRING_DATAREFS.value, [])
        if type(self.string_datarefs) is str:
            if "," in self.string_datarefs:
                self.string_datarefs = self.string_datarefs.replace(" ", "").split(",")
            else:
                self.string_datarefs = [self.string_datarefs]

        self.all_datarefs = None  # all datarefs used by this button
        self.all_datarefs = self.get_datarefs()  # this does not add string datarefs
        if len(self.all_datarefs) > 0:
            self.page.register_datarefs(self)  # when the button's page is loaded, we monitor these datarefs
            # string-datarefs are not monitored by the page, they get sent by the XPPython3 plugin

        self.all_datarefs = self.all_datarefs + self.string_datarefs

        self.dataref_collections = None
        self.dataref_collections = self.get_dataref_collections()
        if len(self.dataref_collections) > 0:
            self.page.register_dataref_collections(self)

        self.init()

    @staticmethod
    def guess_index(config):
        return str(config.get(CONFIG_KW.INDEX.value))

    @staticmethod
    def guess_activation_type(config):
        a = config.get(CONFIG_KW.TYPE.value)
        if a is None or a == CONFIG_KW.NONE.value:
            logger.debug(f"not type attribute, assuming 'none' type")
            return CONFIG_KW.NONE.value
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
            logger.debug(f"no representation in {config}")
        else:
            logger.debug(f"multiple representation {a} in {config}")
        return CONFIG_KW.NONE.value

    def button_name(self):
        return self.name

    def get_id(self):
        return ID_SEP.join([self.page.get_id(), self.name])

    def get_button_value(self, name):
        if name is None or len(name) == 0:
            v = self.get_current_value()
            if type(v) not in [int, float, str]:
                logger.warning(f"value of {name} is {type(v)}")
            return v
        a = name.split(":")
        if len(a) > 1:
            s = self.get_state_variables()
            if a[1] in s.keys():
                return s[a[1]]
            else:
                logger.warning(f"so such variable {a[1]}")
        else:
            v = self.get_current_value()
            if type(v) not in [int, float, str]:
                logger.warning(f"value of {name} is {type(v)}")
            return v
        return None

    def id(self):
        return self.get_id()

    def inspect(self, what: str | None = None):
        """
        Return information aout button status
        """
        if what is not None:
            if "invalid" in what:
                if not self.is_valid():
                    logger.info(f"Button {self.name} IS INVALID")
                    return
            logger.info(f"Button {self.name} -- {what}")
            if "dataref" in what:
                # logger.info("")
                for d in self.get_datarefs():
                    v = self.get_dataref_value(d)
                    logger.info(f"    {d} = {v}")
            if "activation" in what or "longpress" in what:
                logger.info("")
                self._activation.inspect(what)
            if "representation" in what:
                logger.info("")
                self._representation.inspect(what)
            if "status" in what:
                logger.info("")
                logger.info(yaml.dump(self.get_state_variables(), sys.stdout))
            if "valid" in what:
                logger.info(f"-- {'is valid' if self.is_valid() else 'IS INVALID'}")
            if "desc" in what:
                logger.info("")
                if self.is_valid():
                    logger.info(self.describe())
                else:
                    logger.info(f"button {self.name}: is invalid")
            if "config" in what:
                logger.info("")
                logger.info(f"\n{yaml.dump(self._config, sys.stdout)}")

    def describe(self) -> str:
        return "\n\r".join([self._activation.describe(), self._representation.describe()])

    def get_attribute(self, attribute: str, default=None, propagate: bool = True, silence: bool = True):
        # Is there such an attribute directly in the button defintion?
        default_attribute = attribute
        if attribute.startswith(DEFAULT_ATTRIBUTE_PREFIX):
            logger.warning(f"button {self.button_name()} fetched default attribute {attribute}")
        else:
            if not attribute.startswith("cockpit-"):  # no "default" for global cockpit-* attirbutes
                default_attribute = DEFAULT_ATTRIBUTE_PREFIX + attribute

        value = self._config.get(attribute)
        if value is not None:  # found!
            if silence:
                logger.debug(f"button {self.button_name()} returning {attribute}={value}")
            else:
                logger.info(f"button {self.button_name()} returning {attribute}={value}")
            return value

        if propagate:
            if not silence:
                logger.info(f"button {self.button_name()} propagate {default_attribute} to page for {attribute}")
            return self.page.get_attribute(default_attribute, default=default, propagate=propagate, silence=silence)

        if not silence:
            logger.warning(f"button {self.button_name()}: attribute not found {attribute}, returning default ({default})")

        return default

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
            logger.debug(f"button {self.name} setting initial value..")
            if self.initial_value is not None:
                logger.debug(f"button {self.name} .. from initial-value")
                self.set_current_value(self.initial_value)
            else:
                logger.debug(f"button {self.name} .. from button_value")
                self.set_current_value(self.button_value())
            logger.debug(f"button {self.name}: ..has value {self.current_value}.")
        else:
            logger.debug(f"button {self.name}: already has a value ({self.current_value}), initial value ignored")
        # logger.debug(f"button {self.name}: {self.id()}")

    def set_current_value(self, value):
        if self._first_value_not_saved:
            self._first_value = value
            self._first_value_not_saved = False
        if value != self.current_value:
            self.previous_value = self.current_value
            self.current_value = value
            logger.debug(f"button {self.name}: {self.current_value}")

    def get_current_value(self):
        """
        Gets the current value, but does not provoke a calculation, just returns the current value.
        """
        logger.debug(f"button {self.name}: {self.current_value}")
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
            logger.warning(f"button {self.name} has no deck")
            return False
        if self.index is None:
            logger.warning(f"button {self.name} has no index")
            return False
        if self._activation is None:
            logger.warning(f"button {self.name} has no activation")
            return False
        if not self._activation.is_valid():
            logger.warning(f"button {self.name} activation is not valid")
            return False
        if self._representation is None:
            logger.warning(f"button {self.name} has no representation")
            return False
        if not self._representation.is_valid():
            logger.warning(f"button {self.name} representation is not valid")
            return False
        return True

    def has_option(self, option):
        # Check whether a button has an option.
        for opt in self.options:
            if opt.split("=")[0].strip() == option:
                return True
        return False

    def option_value(self, option, default=None):
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

    def parse_dataref_array(self, path):
        """Transform path[4:6] in to [ path[4], path[5] ]"""
        MAXRANGE = 20
        if "[" in path and path[-1] == "]":
            ret = []
            slc = path[path.index("[") + 1 : -1]
            pathroot = path[: path.index("[")]
            if slc == "":  # "whole" array
                return [f"{pathroot}[{i}]" for i in range(MAXRANGE)]
            elif ":" in slc:
                arr = slc.split(":")
                start = 0 if arr[0] == "" else int(arr[0])
                end = MAXRANGE if arr[1] == "" else int(arr[1])
                cnt = end - start
                if cnt > MAXRANGE:
                    logger.warning(f"path {path} has {cnt} elements which is beyond {MAXRANGE} max.")
                return [f"{pathroot}[{i}]" for i in range(start, end)]
        return [path]

    def get_dataref_collections(self):
        if self.dataref_collections is not None:
            return self.dataref_collections

        dc = self._config.get("dataref-collections")
        if dc is None:
            logger.debug("no collection")
            self.dataref_collections = {}
            return self.dataref_collections

        collections = {}
        for collection in dc:
            name = collection.get("name", self.name + "-collection#" + str(len(collections)))
            count = collection.get("array")
            if count is None:  # no repetition
                collections[name] = collection
                drefs = collection["datarefs"]
                # Expand datarefs into a list of individual datarefs
                these_drefs = []
                for dref in drefs:
                    these_drefs = these_drefs + self.parse_dataref_array(dref)
                collection["datarefs"] = these_drefs
            else:
                for i in range(count):
                    new_collection = collection.copy()
                    new_name = f"{name}#{i}"
                    new_collection["datarefs"] = [f"{d}[{i}]" for d in collection["datarefs"]]
                    new_collection["name"] = new_name
                    collections[new_name] = new_collection

        self.dataref_collections = collections
        logger.debug(f"button {self.name}: loaded {len(collections)} collections")
        return self.dataref_collections

    def get_string_datarefs(self) -> list:
        return self.string_datarefs

    def get_datarefs(self, base: dict | None = None) -> list:
        """
        Returns all datarefs used by this button from label, texts, computed datarefs, and explicitely
        listed dataref and datarefs attributes.
        This can be applied to the entire button or to a subset (for annunciator parts)
        """
        if base is None:  # local, button-level ones
            if self.all_datarefs is not None:  # cached if globals (base is None)
                return self.all_datarefs
            base = self._config

        # 1a. Datarefs in base: dataref, multi-datarefs, set-dataref
        r = self._value.get_datarefs(extra_keys=[CONFIG_KW.FORMULA.value, "text"])

        # 1b. Managed values
        managed = None
        managed_dict = base.get(CONFIG_KW.MANAGED.value)
        if managed_dict is not None:
            managed = managed_dict.get(CONFIG_KW.DATAREF.value)
        if managed is not None:
            r.append(managed)
            logger.debug(f"button {self.name}: added managed dataref {managed}")

        # 1c. Guarded buttons
        guarded = None
        guard_dict = base.get(CONFIG_KW.GUARD.value)
        if guard_dict is not None:
            guarded = guard_dict.get(CONFIG_KW.DATAREF.value)
        if guarded is not None:
            r.append(guarded)
            logger.debug(f"button {self.name}: added guarding dataref {guarded}")

        # Activation datarefs
        if self._activation is not None:
            datarefs = self._activation.get_datarefs()
            if datarefs is not None:
                r = r + datarefs
                logger.debug(f"button {self.name}: added activation datarefs {datarefs}")

        # Representation datarefs
        if self._representation is not None:
            datarefs = self._representation.get_datarefs()
            if datarefs is not None:
                r = r + datarefs
                logger.debug(f"button {self.name}: added representation datarefs {datarefs}")

        return list(set(r))  # removes duplicates

    def scan_datarefs(self, base: dict) -> list:
        """
        scan all datarefs in texts, computed datarefs, or explicitely listed.
        This is applied to the entire button or to a subset (for annunciator parts for example).
        """
        return self._value.scan_datarefs(base)

    # ##################################
    # Dataref processing
    #
    def is_managed(self):
        if self.managed is None:
            logger.debug(f"button {self.name}: is managed is none.")
            return False
        d = self.get_dataref_value(self.managed, default=0)
        if d != 0:
            logger.debug(f"button {self.name}: is managed ({d}).")
            return True
        logger.debug(f"button {self.name}: is not managed ({d}).")
        return False
        # return self.managed is not None and self.get_dataref_value(dataref=self.managed, default=0) != 0

    def is_guarded(self):
        if self.guarded is None:
            return False
        d = self.get_dataref_value(self.guarded, default=0)
        if d == 0:
            logger.debug(f"button {self.name}: is guarded ({d}).")
            return True
        return False
        # return self.guarded is not None and self.get_dataref_value(dataref=self.guarded, default=0) != 0

    # ##################################
    # Value provider
    #
    def get_dataref_value(self, dataref, default=None):
        return self.page.get_dataref_value(dataref=dataref, default=default)

    def get_state_value(self, name):
        value = None
        status = self.get_state_variables()
        source = "all sources"
        if name in status:  #
            value = str(status.get(name))
            source = "status"
        elif hasattr(self._activation, name):
            value = str(getattr(self._activation, name))
            source = "activation attribute"
        elif hasattr(self, name):
            value = str(getattr(self, name))
            source = "button attribute"
        else:
            logger.debug(f"button {self.name}: state {name} not found")
        logger.debug(f"button {self.name}: state {name} = {value} (from {source})")
        return value

    # ##################################
    # Value substitution
    #
    def substitute_values(self, text, default: str = "0.0", formatting=None):
        return self._value.substitute_values(text=text, default=default, formatting=formatting)

    def execute_formula(self, formula, default: float = 0.0):
        """
        replace datarefs variables with their (numeric) value and execute formula.
        Returns formula result.
        """
        return self._value.execute_formula(formula=formula, default=default)

    # ##################################
    # Text(s)
    #
    def get_text_detail(self, config, which_text):
        DEFAULT_VALID_TEXT_POSITION = "cm"

        text = self.get_text(config, which_text)
        text_format = config.get(f"{which_text}-format")
        page = self.page

        dflt_system_font = self.get_attribute(f"system-font")
        if dflt_system_font is None:
            logger.error(f"button {self.button_name()}: no system font")

        dflt_text_font = self.get_attribute(f"{which_text}-font")
        if dflt_text_font is None:
            dflt_text_font = self.get_attribute("label-font")
            if dflt_text_font is None:
                logger.warning(f"button {self.button_name()}: no default label font, using system font")
                dflt_text_font = dflt_system_font

        text_font = config.get(f"{which_text}-font", dflt_text_font)

        dflt_text_size = self.get_attribute(f"{which_text}-size")
        if dflt_text_size is None:
            dflt_text_size = self.get_attribute("label-size")
            if dflt_text_size is None:
                logger.warning(f"button {self.button_name()}: no default label size, using 10")
                dflt_text_size = 16
        text_size = config.get(f"{which_text}-size", dflt_text_size)

        dflt_text_color = self.get_attribute(f"{which_text}-color")
        if dflt_text_color is None:
            dflt_text_color = self.get_attribute("label-color")
            if dflt_text_color is None:
                logger.warning(f"button {self.button_name()}: no default label color, using {DEFAULT_COLOR}")
                dflt_text_color = DEFAULT_COLOR
        text_color = config.get(f"{which_text}-color", dflt_text_color)
        text_color = convert_color(text_color)

        dflt_text_position = self.get_attribute(f"{which_text}-position")
        if dflt_text_position is None:
            dflt_text_position = self.get_attribute("label-position")
            if dflt_text_position is None:
                logger.warning(f"button {self.button_name()}: no default label position, using cm")
                dflt_text_position = DEFAULT_VALID_TEXT_POSITION  # middle of icon
        text_position = config.get(f"{which_text}-position", dflt_text_position)
        if text_position[0] not in "lcr":
            text_position = DEFAULT_VALID_TEXT_POSITION
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: invalid horizontal label position code {text_position}, using default")
        if text_position[1] not in "tmb":
            text_position = DEFAULT_VALID_TEXT_POSITION
            logger.warning(f"button {self.button_name()}: {type(self).__name__}: invalid vertical label position code {text_position}, using default")

        # print(f">>>> {self.get_id()}:{which_text}", dflt_text_font, dflt_text_size, dflt_text_color, dflt_text_position)

        if text is not None and not isinstance(text, str):
            logger.warning(f"button {self.button_name()}: converting text {text} to string (type {type(text)})")
            text = str(text)

        return text, text_format, text_font, text_color, text_size, text_position

    def get_text(self, base: dict, root: str = "label"):  # root={label|text}
        """
        Extract label or text from base and perform formula and dataref values substitution if present.
        (I.e. replaces ${formula} and ${dataref} with their values.)
        """
        text = base.get(root)
        if text is None:
            return None

        # HACK 1: Special icon font substitution
        default_font = self.get_attribute("label-font")
        if default_font is None:
            logger.warning("no default font")

        text_font = base.get(root + "-font", default_font)
        for k, v in ICON_FONTS.items():
            if text_font.lower().startswith(v[0]):
                s = "\\${%s:([^\\}]+?)}" % (k)
                icons = re.findall(s, text)
                for i in icons:
                    if i in v[1].keys():
                        text = text.replace(f"${{{k}:{i}}}", v[1][i])
                        logger.debug(f"button {self.name}: substituing font icon {i}")

        # Formula in text
        text_format = base.get(f"{root}-format")
        KW_FORMULA_STR = f"${{{CONFIG_KW.FORMULA.value}}}"  # "${formula}"
        if KW_FORMULA_STR in str(text):
            # If text contains ${formula}, it is replaced by the value of the formula calculation.
            dataref_rpn = base.get(CONFIG_KW.FORMULA.value)
            if dataref_rpn is not None:
                res = self.execute_formula(formula=dataref_rpn)
                if res != "":  # Format output if format present
                    if text_format is not None:
                        logger.debug(f"button {self.name}: {root}-format {text_format}: res {res} => {text_format.format(res)}")
                        res = text_format.format(res)
                    else:
                        res = str(res)
                text = text.replace(KW_FORMULA_STR, res)
            else:
                logger.warning(f"button {self.name}: text contains {KW_FORMULA_STR} but no {CONFIG_KW.FORMULA.value} attribute found")

        text = self.substitute_values(text, formatting=text_format, default="---")

        # HACK 2: Change text if managed
        # Note: we have to go through the whole text substitution before, because sometimes the text gets displayed anyway
        if self.is_managed():  # managed
            # • does not exist in all charsets, * is ok. I made my own font with b'\\u2022' (dec. 8226) set to "•"
            DOT = "•"

            txtmod = self.manager.get(f"{root}-modifier", "dot").lower()  # type: ignore
            if txtmod == "dot":  # label
                return text + DOT  # ---•
            elif txtmod in ["std", "standard"]:  # QNH Std
                return "Std"
            elif txtmod == "dash":  # --- dash=4 or simply dash (defaults to dash=3)
                n = self.option_value("dash", self.option_value("dashes", True))
                if type(n) == bool:
                    n = 3
                return "-" * int(n) + " " + DOT

        return text

    # ##################################
    # Value
    #
    def has_external_value(self) -> bool:
        return self.all_datarefs is not None and len(self.all_datarefs) > 1

    def button_value(self):
        """
        Button ultimately returns either one value or an array of values if representation requires it.
        """

        # 1. Special cases (Annunciator): Each annunciator part has its own evaluation
        if isinstance(self._representation, Annunciator):
            logger.debug(f"button {self.name}: is Annunciator, getting part values")
            return self._representation.get_current_values()

        # 2. Formula or dataref based
        if self.dataref_rpn is not None or (self.all_datarefs is not None and len(self.all_datarefs) > 0):
            return self._value.get_value()

        # 3. Button state based
        if not self.use_internal_state():
            logger.warning(f"button {self.name}: use internal state")
        self._last_activation_state = self._activation.get_state_variables()

        if "current_value" in self._last_activation_state:
            logger.debug(f"button {self.name}: getting activation current value ({self._last_activation_state['current_value']})")
            return self._last_activation_state["current_value"]

        logger.debug(f"button {self.name}: getting entire state ({self._last_activation_state})")
        return self._last_activation_state

    # ##################################
    # External API
    #
    def use_internal_state(self) -> bool:
        return self.all_datarefs is None or len(self.all_datarefs) == 0

    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        if not isinstance(dataref, Dataref):
            logger.error(f"button {self.name}: not a dataref")
            return
        logger.debug(f"{self.button_name()}: {dataref.path} changed")
        self.set_current_value(self.button_value())
        if self.has_changed() or dataref.has_changed():
            logger.log(
                SPAM_LEVEL,
                f"button {self.name}: {self.previous_value} -> {self.current_value}",
            )
            self.render()
        else:
            logger.debug(f"button {self.name}: no change")

    def dataref_collection_changed(self, dataref_collection):
        logger.log(
            SPAM_LEVEL,
            f"button {self.name}: dataref collection {dataref_collection.name} changed",
        )
        self.render()

    def activate(self, event):
        """
        @todo: Return a status from activate()
        """
        if self._activation is not None:
            if not self._activation.is_valid():
                logger.warning(f"button {self.name}: activation is not valid, nothing executed")
                return
            self._activs = self._activs + 1
            self._activation.activate(event)
        else:
            logger.debug(f"button {self.name}: no activation")
        if self.use_internal_state():
            logger.debug(f"button {self.name}: uses internal state, setting value")
            self.set_current_value(self.button_value())
        if self.has_changed():
            logger.log(
                SPAM_LEVEL,
                f"activate: button {self.name}: {self.previous_value} -> {self.current_value}",
            )
            self.render()
        else:
            logger.debug(f"button {self.name}: no change")
            if self.deck.is_virtual_deck():  # representation has not changed, but hardware representation might have
                self.render()

    def get_state_variables(self):
        """ """
        a = {
            "render": self._render,
            "clean": self._clean,
            "repres": self._repres,
            "active": self._activs,
            "managed": self.managed,
            "guarded": self.guarded,
        }
        return self._activation.get_state_variables() | a
        # if self._representation is not None:
        #     return self._representation.get_state_variables()

    def get_representation(self):
        """
        Called from deck to get what's necessary for displaying this button on the deck.
        It can be an image, a color, a binary value on/off...
        """
        if not self._representation.is_valid():
            logger.warning(f"button {self.name}: representation is not valid")
            return None
        self._repres = self._repres + 1
        return self._representation.render()

    def get_representation_metadata(self):
        return {}

    def get_hardware_representation(self):
        """
        Called from deck to get what's necessary for displaying this button on the deck.
        It can be an image, a color, a binary value on/off...
        """
        if not self._hardware_representation.is_valid():
            logger.warning(f"button {self.name}: hardware representation is not valid")
            return None
        return self._hardware_representation.render()

    def get_hardware_representation_metadata(self):
        """
        Called from deck to get what's necessary for displaying this button on the deck.
        It can be an image, a color, a binary value on/off...
        """
        if not self._hardware_representation.is_valid():
            logger.warning(f"button {self.name}: hardware representation is not valid")
            return {}
        return self._hardware_representation.get_meta()

    def get_vibration(self):
        return self.get_representation().get_vibration()

    def vibrate(self):
        """
        Ask deck to vibrate.
        """
        if self.deck is not None:
            if self.on_current_page():
                self._render = self._render + 1
                self.deck.vibrate(self)
                # logger.debug(f"button {self.name} rendered")
            else:
                logger.debug(f"button {self.name} not on current page")
        else:
            logger.warning(f"button {self.name} has no deck")  # error

    def render(self):
        """
        Ask deck to render this buttonon the deck. From the button's rendering, the deck will know what
        to ask to the button and render it.
        """
        if self.deck is not None:
            if self.on_current_page():
                self._render = self._render + 1
                self.deck.render(self)
                # logger.debug(f"button {self.name} rendered")
            else:
                logger.debug(f"button {self.name} not on current page")
        else:
            logger.warning(f"button {self.name} has no deck")  # error

    def clean(self):
        """
        Button removes itself from device
        """
        self._clean = self._clean + 1
        self.previous_value = None  # this will provoke a refresh of the value on data reload
        self._representation.clean()

    @staticmethod
    def mk_button(config, deck, page):
        idx = Button.guess_index(config)
        if idx is None:
            logger.error(f"button has no index, ignoring {config}")
            return None
        if idx not in deck.valid_indices():
            logger.error(f"button has invalid index '{idx}' (valid={deck.valid_indices()}), ignoring '{config}'")
            return None

        # How the button will behave, it is does something
        aty = Button.guess_activation_type(config)
        if aty is None or aty not in deck.valid_activations(idx):
            logger.error(f"button has invalid activation type {aty} not in {deck.valid_activations(idx)} for index {idx}, ignoring {config}")
            return None

        # How the button will be represented, if it is
        rty = Button.guess_representation_type(config)
        if rty not in deck.valid_representations(idx):
            logger.error(f"button has invalid representation type {rty} for index {idx}, ignoring {config}")
            return None
        if rty == "none":
            logger.debug(f"button has no representation but it is ok")

        config[DECK_BUTTON_DEFINITION] = deck.get_deck_button_definition(idx)
        return Button(config=config, page=page)
