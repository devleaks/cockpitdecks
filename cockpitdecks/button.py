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
from .simulator import Dataref, DatarefListener, DatarefSetListener, INTERNAL_DATAREF_PREFIX
from .resources.rpc import RPC
from .resources.iconfonts import ICON_FONTS

from cockpitdecks import ID_SEP, SPAM_LEVEL, KW, yaml

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)

PATTERN_DOLCB = "\\${([^\\}]+?)}"  # ${ ... }: dollar + anything between curly braces.
VARIABLE_PREFIX = ["button", "state"]


class Button(DatarefListener, DatarefSetListener):
    def __init__(self, config: dict, page: "Page"):
        DatarefListener.__init__(self)
        DatarefSetListener.__init__(self)
        # Definition and references
        self._config = config
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

        self._definition = self.deck.get_deck_type_description().get_button_definition(self.index)  # kind of meta data capabilties of button

        self.name = config.get("name", str(self.index))
        self.num_index = None
        if type(self.index) == str:
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
        self._first_value_not_saved = True
        self._first_value = None  # first value the button will get
        self._last_activation_state = None
        self.initial_value = config.get("initial-value")
        self.current_value = None
        self.previous_value = None

        # Options
        self.options = []
        new = config.get("options")
        if new is not None:  # removes all spaces around = sign and ,. a = b, c, d=e -> a=b,c,d=e -> [a=b, c, d=e]
            old = ""  # a, c, d are options, b, e are option values. c option value is boolean True.
            while len(old) != len(new):
                old = new
                new = old.strip().replace(" =", "=").replace("= ", "=").replace(" ,", ",").replace(", ", ",")
            self.options = [a.strip() for a in new.split(",")]

        # What it will do and how it will appear
        self._activation = None
        atype = Button.guess_activation_type(config)
        if atype is not None and atype in ACTIVATIONS:
            self._activation = ACTIVATIONS[atype](config, self)
            logger.debug(f"button {self.name} activation {atype}")
        else:
            logger.warning(f"button {self.name} has no activation defined, using default")
            self._activation = ACTIVATIONS["none"](config, self)

        self._representation = None

        idx = Button.guess_index(config)
        valid_representations = self.deck.valid_representations(str(idx))
        rtype = Button.guess_representation_type(config, valid_representations)
        if rtype is not None and rtype in REPRESENTATIONS:
            self._representation = REPRESENTATIONS[rtype](config, self)
            logger.debug(f"button {self.name} representation {rtype}")
        else:
            logger.warning(f"button {self.name} has no representation defined, using default")
            self._representation = REPRESENTATIONS["none"](config, self)

        # Datarefs
        self.dataref = config.get(KW.DATAREF.value)
        self.dataref_rpn = config.get(KW.FORMULA.value)
        self.managed = None
        self.manager = config.get(KW.MANAGED.value)
        if self.manager is not None:
            self.managed = self.manager.get(KW.DATAREF.value)
            if self.managed is None:
                logger.warning(f"button {self.name} has manager but no dataref")

        self.guarded = None
        self.guard = config.get(KW.GUARD.value)
        if self.guard is not None:
            self.guarded = self.guard.get(KW.DATAREF.value)
            if self.guarded is None:
                logger.warning(f"button {self.name} has guard but no dataref")

        self.all_datarefs = None  # all datarefs used by this button
        self.all_datarefs = self.get_datarefs()  # cache them
        if len(self.all_datarefs) > 0:
            self.page.register_datarefs(self)  # when the button's page is loaded, we monitor these datarefs

        self.dataref_collections = None
        self.dataref_collections = self.get_dataref_collections()
        if len(self.dataref_collections) > 0:
            self.page.register_dataref_collections(self)

        self.init()

    @staticmethod
    def guess_index(config):
        return str(config.get("index"))

    @staticmethod
    def guess_activation_type(config):
        a = config.get("type")
        if a is None:
            logger.debug(f"not type attribute, assuming 'none' type")
            a = "none"
        if a not in ACTIVATIONS.keys():
            logger.warning(f"invalid activation type {a} in {config}")
            return None
        return a

    @staticmethod
    def guess_representation_type(config, valid_representations: list):
        a = []
        for r in REPRESENTATIONS.keys():
            if r in config:
                a.append(r)
        if len(a) == 1:
            return a[0]
        elif len(a) == 0:
            if "none" not in valid_representations:
                logger.warning(f"no representation in {config}")
            elif "representation" in config:
                r = config.get("representation")
                if r is None:
                    logger.debug(f"no representation")
            else:
                logger.debug(f"no representation in {config}, but no representation is OK (should be in {', '.join(REPRESENTATIONS.keys())})")
        else:
            logger.warning(f"multiple representation {a} in {config}")
        return "none"

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
            s = self.get_status()
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
                logger.info(yaml.dump(self.get_status(), sys.stdout))
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

    def describe(self):
        return "\n\r".join([self._activation.describe(), self._representation.describe()])

    def get_attribute(self, attribute: str, silence: bool = False):
        ATTRNAME = "_defaults"
        val = None
        if hasattr(self, ATTRNAME):
            ld = getattr(self, ATTRNAME)
            if isinstance(ld, dict):
                val = ld.get(attribute)
        return val if val is not None else self.page.get_attribute(attribute, silence=silence)

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
        """Transform path[4:6] in to path[4], path[5]"""
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

    def get_datarefs(self, base: dict | None = None):
        """
        Returns all datarefs used by this button from label, texts, computed datarefs, and explicitely
        listed dataref and datarefs attributes.
        This can be applied to the entire button or to a subset (for annunciator parts)
        """
        if base is None:  # local, button-level ones
            if self.all_datarefs is not None:  # cached if globals (base is None)
                return self.all_datarefs

        r = self.scan_datarefs(self._config)
        logger.debug(f"button {self.name}: added button datarefs {r}")
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

    def scan_datarefs(self, base: dict):
        """
        scan all datarefs in texts, computed datarefs, or explicitely listed.
        This is applied to the entire button or to a subset (for annunciator parts for example).
        """

        def is_dref(r):
            # ${state:button-value} is not a dataref, BUT ${data:path} is a "local" dataref
            PREFIX = list(ICON_FONTS.keys()) + VARIABLE_PREFIX
            SEP = ":"
            for s in PREFIX:
                if r.startswith(s + SEP):
                    return False
            return r != KW.FORMULA.value

        r = []

        # Direct use of datarefs:
        #
        # 1. Single
        dataref = base.get(KW.DATAREF.value)
        if dataref is not None:
            r.append(dataref)
            logger.debug(f"button {self.name}: added single dataref {dataref}")

        # 1b. Managed values
        managed = None
        managed_dict = base.get(KW.MANAGED.value)
        if managed_dict is not None:
            managed = managed_dict.get(KW.DATAREF.value)
        if managed is not None:
            r.append(managed)
            logger.debug(f"button {self.name}: added managed dataref {managed}")

        # 1c. Guarded buttons
        guarded = None
        guard_dict = base.get(KW.GUARD.value)
        if guard_dict is not None:
            guarded = guard_dict.get(KW.DATAREF.value)
        if guarded is not None:
            r.append(guarded)
            logger.debug(f"button {self.name}: added guarding dataref {guarded}")

        # logger.debug(f"button {base.name}: {r}, {base.datarefs}")

        # Use of datarefs in formula:
        #
        # 2. Formula datarefs
        dataref_rpn = base.get(KW.FORMULA.value)
        if dataref_rpn is not None and type(dataref_rpn) == str:
            datarefs = re.findall(PATTERN_DOLCB, dataref_rpn)
            datarefs = list(filter(is_dref, datarefs))
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"button {self.name}: added label datarefs {datarefs}")

        # Use of datarefs in label or text
        #
        # 3.1 Label datarefs (should be avoided, label should be static message)
        # label = base.get("label")
        # if label is not None and type(label) == str:
        #     datarefs = re.findall(PATTERN_DOLCB, label)
        #     datarefs = list(filter(is_dref, datarefs))
        #     if len(datarefs) > 0:
        #         r = r + datarefs
        #         logger.debug(f"button {self.name}: added label datarefs {datarefs}")
        # commented out 02-MAY-2023

        # 3.2 Text datarefs
        text = base.get("text")
        if text is not None and type(text) == str:
            datarefs = re.findall(PATTERN_DOLCB, text)
            datarefs = list(filter(lambda x: is_dref(x), datarefs))
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"button {self.name}: added text datarefs {datarefs}")

        # 4.1 Multiple datarefs
        datarefs = base.get("multi-datarefs", [])
        if len(datarefs) > 0:
            r = r + datarefs

        # Clean up
        if KW.FORMULA.value in r:  # label or text may contain like ${{KW.FORMULA.value}}, but {KW.FORMULA.value} is not a dataref.
            r.remove(KW.FORMULA.value)

        return list(set(r))  # removes duplicates

    # ##################################
    # Dataref processing
    #
    def get_dataref_value(self, dataref, default=None):
        return self.page.get_dataref_value(dataref=dataref, default=default)

    def get_dataref_value_from_collection(self, dataref, collection, default=None):
        return self.sim.collector.get_dataref_value_from_collection(dataref=dataref, collection=collection, default=default)

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

    def substitute_dataref_values(self, message: str, default: str = "0.0", formatting=None):
        """
        Replaces ${dataref} with value of dataref in labels and execution formula.
        @todo: should take into account dataref value type (Dataref.xp_data_type or Dataref.data_type).
        """
        if type(message) == int or type(message) == float:  # probably formula is a constant value
            value_str = message
            if formatting is not None:
                if formatting is not None:
                    value_str = formatting.format(message)
                    logger.debug(f"button {self.name}: received int or float, returning as is.")
                else:
                    value_str = str(message)
                    logger.debug(f"button {self.name}: received int or float, returning formatted {formatting}.")
            return value_str

        dataref_names = re.findall(PATTERN_DOLCB, message)

        if len(dataref_names) == 0:
            return message

        if formatting is not None:
            if type(formatting) == list:
                if len(dataref_names) != len(formatting):
                    logger.warning(
                        f"button {self.name}: number of datarefs {len(dataref_names)} not equal to the number of format {len(formatting)}, cannot proceed."
                    )
                    return message
            elif type(formatting) != str:
                logger.warning(f"button {self.name}: single format is not a string, cannot proceed.")
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

        more = re.findall(PATTERN_DOLCB, retmsg)  # XXXHERE
        if len(more) > 0:
            logger.warning(f"button {self.name}: unsubstituted dataref values {more}")

        return retmsg

    def substitute_state_values(self, text, default: str = "0.0", formatting=None):
        status = self.get_status()
        txtcpy = text
        # more = re.findall("\\${status:([^\\}]+?)}", txtcpy)
        for k, v in status.items():
            s = f"${{state:{k}}}"  # @todo: !!possible injection!!
            if s in txtcpy:
                if v is None:
                    logger.warning(f"button {self.name}: {k} has no value")
                    v = str(default)
                else:
                    v = str(v)  # @todo: later: use formatting
                txtcpy = txtcpy.replace(s, v)
                logger.debug(f"button {self.name}: replaced {s} by {str(v)}. ({k})")
        more = re.findall("\\${status:([^\\}]+?)}", txtcpy)
        if len(more) > 0:
            logger.warning(f"button {self.name}: unsubstituted status values {more}")
        return txtcpy

    def substitute_data_values(self, text, default: str = "0.0", formatting=None):
        # !!!IMPORTANT!!! INTERNAL_DATAREF_PREFIX "data:" is hardcoded in regexp
        txtcpy = text
        more = re.findall("\\${" + INTERNAL_DATAREF_PREFIX + "([^\\}]+?)}", txtcpy)
        for k in more:
            s = f"${{{INTERNAL_DATAREF_PREFIX}{k}}}"  # @todo: !!possible injection!!
            value = self.sim.get_data(k)
            if value is not None:
                txtcpy = txtcpy.replace(s, value)
            else:
                txtcpy = txtcpy.replace(s, default)
        more = re.findall("\\${" + INTERNAL_DATAREF_PREFIX + "([^\\}]+?)}", txtcpy)
        if len(more) > 0:
            logger.warning(f"button {self.name}: unsubstituted data values {more}")
        return txtcpy

    # def substitute_button_values(self, text, default: str = "0.0", formatting = None):
    #     txtcpy = text
    #     more = re.findall("\\${button:([^\\}]+?)}", txtcpy)
    #     if len(more) > 0:
    #         for m in more:
    #             v = self.deck.cockpit.get_button_value(m)  # starts at the top
    #             if v is None:
    #                 logger.warning(f"button {self.name}: {m} has no value")
    #                 v = str(default)
    #             else:
    #                 v = str(v)  # @todo: later: use formatting
    #             m_str = f"${{button:{m}}}"   # "${formula}"
    #             txtcpy = txtcpy.replace(m_str, v)
    #             logger.debug(f"button {self.name}: replaced {m_str} by {str(v)}. ({m})")
    #     more = re.findall("\\${button:([^\\}]+?)}", txtcpy)
    #     if len(more) > 0:
    #         logger.warning(f"button {self.name}: unsubstituted button values {more}")
    #     return txtcpy

    def substitute_values(self, text, default: str = "0.0", formatting=None):
        if type(text) != str or "$" not in text:  # no ${..} to stubstitute
            return text
        t1 = self.substitute_state_values(text, default=default, formatting=formatting)
        if text != t1:
            logger.log(SPAM_LEVEL, f"substitute_values: button {self.name}: {text} => {t1}")
        # t2 = self.substitute_button_values(t1, default=default, formatting=formatting)
        # logger.log(SPAM_LEVEL, f"substitute_values: button {self.name}: {t1} => {t2}")
        t2 = t1
        t3 = self.substitute_dataref_values(t2, default=default, formatting=formatting)
        if t3 != t2:
            logger.log(SPAM_LEVEL, f"substitute_values: button {self.name}: {t2} => {t3}")
        return t3

    def execute_formula(self, formula, default: float = 0.0):
        """
        replace datarefs variables with their (numeric) value and execute formula.
        Returns formula result.
        """
        expr = self.substitute_values(text=formula, default=str(default))
        # logger.debug(f"button {self.name}: {formula} => {expr}")
        r = RPC(expr)
        value = r.calculate()
        # print("FORMULA", formula, "=>", expr, "=", value)
        logger.log(SPAM_LEVEL, f"execute_formula: button {self.name}: {formula} => {expr}:  => {value}")
        return value

    # ##################################
    # Text(s)
    #
    def get_text(self, base: dict, root: str = "label"):  # root={label|text}
        """
        Extract label or text from base and perform formula and dataref values substitution if present.
        (I.e. replaces ${formula} and ${dataref} with their values.)
        """
        text = base.get(root)
        if text is None:
            return None

        # HACK 1: Special icon font substitution
        default_font = self.get_attribute("default-label-font")
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
        KW_FORMULA_STR = f"${{{KW.FORMULA.value}}}"  # "${formula}"
        if KW_FORMULA_STR in str(text):
            # If text contains ${formula}, it is replaced by the value of the formula calculation.
            dataref_rpn = base.get(KW.FORMULA.value)
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
                logger.warning(f"button {self.name}: text contains {KW_FORMULA_STR} but no {KW.FORMULA.value} attribute found")

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

        # 2. No dataref
        if len(self.all_datarefs) == 0:
            if self.dataref_rpn is not None:
                logger.debug(f"button {self.name}: formula without dataref")
                return self.execute_formula(formula=self.dataref_rpn)

        # 3. One dataref
        if len(self.all_datarefs) == 1:
            # if self.all_datarefs[0] in self.page.datarefs.keys():  # unnecessary check
            logger.debug(f"button {self.name}: single dataref {self.all_datarefs[0]}")
            if self.dataref_rpn is not None:
                logger.debug(f"button {self.name} formula with one dataref")
                return self.execute_formula(formula=self.dataref_rpn)
            else:  # if no formula, returns dataref as it is
                return self.get_dataref_value(self.all_datarefs[0])

        # 4. Multiple datarefs
        if len(self.all_datarefs) > 1:
            # 4.1 Mutiple Dataref with a formula, returns only one value
            if self.dataref_rpn is not None:
                logger.debug(f"button {self.name}: getting formula with more than one datarefs")
                return self.execute_formula(formula=self.dataref_rpn)
            # 4.1 bis: If button has a dataref in its attribute, we may favor that dataref first?
            # if self.dataref is not None:
            #     logger.debug(f"button {self.name}: more than one datarefs, but returning dataref attribute {self.dataref} value")
            #     return self.get_dataref_value(self.dataref)
            # 4.2 Mutiple Dataref but no formula, returns an array of values of datarefs in multi-datarefs
            # !! May be we should return them all?
            r = {}
            for d in self.all_datarefs:
                v = self.get_dataref_value(d)
                r[d] = v
            logger.debug(f"button {self.name}: getting dict of datarefs")
            return r

        # 5. Value is based on activation state:
        if not self.use_internal_state():
            logger.warning(f"button {self.name}: use internal state")
        self._last_activation_state = self._activation.get_status()

        if "current_value" in self._last_activation_state:
            logger.debug(f"button {self.name}: getting activation current value ({self._last_activation_state['current_value']})")
            return self._last_activation_state["current_value"]

        logger.debug(f"button {self.name}: getting entire state ({self._last_activation_state})")
        return self._last_activation_state

    # ##################################
    # External API
    #
    def use_internal_state(self) -> bool:
        return len(self.all_datarefs if self.all_datarefs is not None else []) == 0 or (self._activation is not None and self._activation._has_no_value)

    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        if not isinstance(dataref, Dataref):
            logger.error(f"button {self.name}: not a dataref")
            return
        self.set_current_value(self.button_value())
        if self.has_changed() or dataref.has_changed():
            logger.log(SPAM_LEVEL, f"button {self.name}: {self.previous_value} -> {self.current_value}")
            self.render()
        else:
            logger.debug(f"button {self.name}: no change")

    def dataref_collection_changed(self, dataref_collection):
        logger.log(SPAM_LEVEL, f"button {self.name}: dataref collection {dataref_collection.name} changed")
        self.render()

    def activate(self, state: bool):
        """
        @todo: Return a status from activate()
        """
        if self._activation is not None:
            if not self._activation.is_valid():
                logger.warning(f"button {self.name}: activation is not valid, nothing executed")
                return
            self._activs = self._activs + 1
            self._activation.activate(state)
        else:
            logger.debug(f"button {self.name}: no activation")
        if self.use_internal_state():
            logger.debug(f"button {self.name}: uses internal state, setting value")
            self.set_current_value(self.button_value())
        if self.has_changed():
            logger.log(SPAM_LEVEL, f"activate: button {self.name}: {self.previous_value} -> {self.current_value}")
            self.render()
        else:
            logger.debug(f"button {self.name}: no change")

    def get_status(self):
        """ """
        a = {"render": self._render, "clean": self._clean, "repres": self._repres, "active": self._activs, "managed": self.managed, "guarded": self.guarded}
        return self._activation.get_status() | a
        # if self._representation is not None:
        #     return self._representation.get_status()

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
