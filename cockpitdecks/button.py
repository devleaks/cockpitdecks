"""
Container object for one "button".
Contains how to interact with (_activation) and how to represent it (_representation).
Has options.
Manage interaction with X-Plane, fetch or write datarefs.
Maintain a "value", and some internal attributes.
"""

from __future__ import annotations

import re
import logging
import sys
from pprint import pformat
from abc import ABC, abstractmethod


from .buttons.activation import ACTIVATION_VALUE, ActivationValueProvider
from .buttons.representation import Annunciator
from .variable import Variable, ValueProvider, InternalVariable, VariableListener, InternalVariableType
from .simulator import SimulatorVariable, SimulatorVariableValueProvider
from .strvar import StringWithVariables
from .value import Value
from .instruction import Instruction

from cockpitdecks import (
    ID_SEP,
    SPAM_LEVEL,
    CONFIG_KW,
    yaml,
    DEFAULT_ATTRIBUTE_PREFIX,
    parse_options,
)

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class CockpitdecksError(Exception):
    pass


class StateVariableValueProvider(ABC, ValueProvider):
    def __init__(self, name: str, button: Button):
        ValueProvider.__init__(self, name=name, provider=button)

    @abstractmethod
    def get_state_variable_value(self, name: str):
        pass


class Button(VariableListener, SimulatorVariableValueProvider, StateVariableValueProvider, ActivationValueProvider):
    def __init__(self, config: dict, page: "Page"):
        VariableListener.__init__(self)

        # Definition and references
        self._config = config
        self.page = page

        self.cockpit.set_logging_level(__name__)

        self.index = config.get(
            CONFIG_KW.INDEX.value
        )  # button_type: button, index: 4 (user friendly) -> _key = B4 (internal, to distinguish from type: push, index: 4).
        self._key = config.get(
            CONFIG_KW.INTERNAL_KEY.value, self.index
        )  # internal key, mostly equal to index, but not always. Index is for users, _key is for this software.

        self._definition = self.deck.deck_type.get_button_definition(self.index)  # kind of meta data capabilties of button
        if self._definition is None:
            logger.warning(f"button {self.name}: no definition")

        self.name = config.get(CONFIG_KW.NAME.value, str(self.index))
        self.num_index = None
        if type(self.index) is str:
            idxnum = re.findall("\\d+(?:\\.\\d+)?$", self.index)  # just the numbers of a button index name knob3 -> 3.
            if len(idxnum) > 0:
                self.num_index = idxnum[0]

        self.mosaic = self._definition.is_tile()
        self._part_of_multi = False

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
        self.initial_value = config.get(CONFIG_KW.INITIAL_VALUE.value)
        self.current_value = None
        self.previous_value = None

        #### Options
        #
        self.options = parse_options(config.get(CONFIG_KW.OPTIONS.value))
        self.managed = None
        self.guarded = None

        #### Activation
        #
        self._activation = None
        atype = Button.guess_activation_type(config)
        if atype is not None and atype in self.deck.cockpit.all_activations:
            self._activation = self.deck.cockpit.all_activations[atype](self)
            logger.debug(f"button {self.name} activation {atype}")
        else:
            logger.info(f"button {self.name} has no activation defined, using default activation 'none'")
            self._activation = self.deck.cockpit.all_activations["none"](self)

        #### Representation
        #
        self._representation = None

        idx = Button.guess_index(config)
        rtype = Button.guess_representation_type(
            config, all_representations=self.deck.cockpit.all_representations, all_hardware_representations=self.deck.cockpit.all_hardware_representations
        )
        if rtype is not None and rtype in self.deck.cockpit.all_representations:
            self._representation = self.deck.cockpit.all_representations[rtype](button=self)
            logger.debug(f"button {self.name} representation {rtype}")
        else:
            logger.info(f"button {self.name} has no representation defined, using default representation 'none'")
            self._representation = self.deck.cockpit.all_representations["none"](self)

        self._hardware_representation = None
        if self.deck.is_virtual_deck() and self._definition.has_hardware_representation():
            rtype = self._definition.get_hardware_representation()
            if rtype is not None and rtype in self.deck.cockpit.all_representations:
                logger.debug(f"button {self.name} has hardware representation {rtype}")
                self._hardware_representation = self.deck.cockpit.all_representations[rtype](self)

        #### Datarefs
        #
        self.manager = config.get(CONFIG_KW.MANAGED.value)
        if self.manager is not None:
            self.managed = self.manager.get(CONFIG_KW.SIM_VARIABLE.value)
            if self.managed is None:
                logger.warning(f"button {self.name} has manager but no dataref")

        self.guarded = config.get(CONFIG_KW.GUARD.value)
        self._guard_dref = None
        if self.guarded is not None and type(self.guarded) is dict:
            guard_dref_path = self.guarded.get(CONFIG_KW.SIM_VARIABLE.value)
            if guard_dref_path is None:
                logger.warning(f"button {self.name} has guard but no dataref")
            else:
                self._guard_dref = self.sim.get_variable(guard_dref_path)
                self._guard_dref.update_value(new_value=0, cascade=False)  # need initial value,  especially for internal drefs
                logger.debug(f"button {self.name} has guard {self._guard_dref.name}")

        # String datarefs
        # self.string_datarefs are string datarefs as declared in the button
        # they are not all string datarefs collected from activation and/or representation.
        self.string_datarefs = set()

        self._value = Value(self.name, config=config, provider=self)
        self._value.add_listener(self)

        # Regular datarefs
        self.all_datarefs = None  # all datarefs used by this button
        self.all_datarefs = self.get_variables()  # this does not contain string datarefs
        if len(self.all_datarefs) > 0:
            self.page.register_simulator_variable(self)  # when the button's page is loaded, we monitor these datarefs
            # string-datarefs are not monitored by the page, they get sent by the XPPython3 plugin
        # add string datarefs to all_datarefs after their registration at the page level
        self.all_datarefs = self.all_datarefs

        self.wallpaper = self.deck.cockpit.locate_image(config.get(CONFIG_KW.WALLPAPER.value))
        if self.wallpaper is not None:
            self._definition.set_block_wallpaper(self.wallpaper)

        # Initialize value providers
        SimulatorVariableValueProvider.__init__(self, name=self.name, simulator=self.sim)
        StateVariableValueProvider.__init__(self, name=self.name, button=self)
        ActivationValueProvider.__init__(self, name=self.name, activation=self._activation)

        self.init()

    @staticmethod
    def guess_index(config):
        return str(config.get(CONFIG_KW.INDEX.value))

    @staticmethod
    def guess_activation_type(config):
        a = config.get(CONFIG_KW.TYPE.value)
        if a is None or a == CONFIG_KW.NONE.value:
            logger.debug("no type attribute, assuming type is none")
            return CONFIG_KW.NONE.value
        return a

    @staticmethod
    def guess_representation_type(config, all_representations, all_hardware_representations):
        a = [r for r in all_representations.keys() if r in config and r not in all_hardware_representations.keys()]
        if len(a) == 1:
            return a[0]
        elif len(a) == 0:
            logger.debug(f"no representation in \n{pformat(config)},\n assuming none, add representation: none to suppress warning message")
        else:
            logger.warning(f"multiple representations {a} found in {config}")
        return CONFIG_KW.NONE.value

    @property
    def deck(self):
        return self.page.deck

    @property
    def cockpit(self):
        return self.page.deck.cockpit

    @property
    def sim(self):
        if self.page.deck.cockpit.sim is None:
            raise CockpitdecksError("simulator no longer accessible")
        return self.page.deck.cockpit.sim

    def get_id(self):
        return ID_SEP.join([self.page.get_id(), str(self.index)])

    def inc(self, name: str, amount: float = 1.0, cascade: bool = False):
        self.sim.inc_internal_variable(name=ID_SEP.join([self.get_id(), name]), amount=amount, cascade=cascade)

    def get_button_value(self, name):
        # Parses name into cockpit:deck:page:button and see if button is self
        # in which case it returns its value.
        if name is None or len(name) == 0:
            v = self.value
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
            v = self.value
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
                for d in self.get_variables():
                    v = self.get_simulator_variable_value(simulator_variable=d)
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
            logger.warning(f"button {self.name} fetched default attribute {attribute}")
        else:
            if not attribute.startswith("cockpit-"):  # no "default" for global cockpit-* attirbutes
                default_attribute = DEFAULT_ATTRIBUTE_PREFIX + attribute

        value = self._config.get(attribute)
        if value is not None:  # found!
            if silence:
                logger.debug(f"button {self.name} returning {attribute}={value}")
            else:
                logger.info(f"button {self.name} returning {attribute}={value}")
            return self.deck.cockpit.convert_if_color_attribute(attribute=attribute, value=value, silence=silence)

        if propagate:
            if not silence:
                logger.info(f"button {self.name} propagate {default_attribute} to page for {attribute}")
            return self.page.get_attribute(default_attribute, default=default, propagate=propagate, silence=silence)

        if not silence:
            logger.warning(f"button {self.name}: attribute not found {attribute}, returning default ({default})")

        return self.deck.cockpit.convert_if_color_attribute(attribute=attribute, value=default, silence=silence)

    def on_current_page(self):
        """
        Returns whether button is on current page
        """
        return self.deck.current_page == self.page

    def init(self):
        """
        Install button
        """
        # Register itself as listener of its variables

        # Set initial value if not already set
        if self._first_value_not_saved:
            logger.debug(f"button {self.name} setting initial value..")
            if self.initial_value is not None:
                logger.debug(f"button {self.name} .. from initial-value")
                self.value = self.initial_value
            else:
                logger.debug(f"button {self.name} .. from compute_value")
                self.value = self.compute_value()
            logger.debug(f"button {self.name}: ..has value {self.current_value}.")
        else:
            logger.debug(f"button {self.name}: already has a value ({self.current_value}), initial value ignored")
        # logger.debug(f"button {self.name}: {self.id()}")

    def register_simulator_variable(self):
        # Declared string dataref must be create FIRST so that they get the proper type.
        # If they are later used (in expression), at least they were created with STRING type first.
        stars = 3
        for d in self.get_variables():
            ref = self.sim.get_variable(d)  # creates or return already defined dataref
            if ref is not None:
                ref.add_listener(self)
            else:
                logger.error(f"button {self.name}: failed to create dataref {d}")

        logger.debug(f"button {self.name} variables registered")

    @property
    def value(self):
        """
        Gets the current value, but does not provoke a calculation, just returns the current value.
        """
        logger.debug(f"button {self.name}: {self.current_value}")
        return self.current_value

    @value.setter
    def value(self, value):
        if self._first_value_not_saved:
            self._first_value = value
            self._first_value_not_saved = False
        if value != self.current_value:
            self.previous_value = self.current_value
            self.current_value = value
            logger.debug(f"button {self.name}: {self.current_value}")

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

    def get_variables(self, base: dict | None = None) -> set:
        """
        Returns all datarefs used by this button from label, texts, computed datarefs, and explicitely
        listed dataref and datarefs attributes.
        This can be applied to the entire button or to a subset (for annunciator parts)
        """
        if base is None:  # local, button-level ones
            base = self._config

        # 1a. Datarefs in base: dataref, set-dataref
        datarefs = self._value.get_variables()

        # 1b. Managed values
        managed = None
        managed_dict = base.get(CONFIG_KW.MANAGED.value)
        if managed_dict is not None:
            managed = managed_dict.get(CONFIG_KW.SIM_VARIABLE.value)
        if managed is not None:
            datarefs.add(managed)
            logger.debug(f"button {self.name}: added managed dataref {managed}")

        # 1c. Guarded buttons
        guarded = None
        guard_dict = base.get(CONFIG_KW.GUARD.value)
        if guard_dict is not None:
            guarded = guard_dict.get(CONFIG_KW.SIM_VARIABLE.value)
        if guarded is not None:
            datarefs.add(guarded)
            logger.debug(f"button {self.name}: added guarding dataref {guarded}")

        # Activation datarefs
        if self._activation is not None:
            r = self._activation.get_variables()
            if r is not None and len(r) > 0:
                datarefs = datarefs | r
                self._value.add_variables(r, reason="activation")
                logger.debug(f"button {self.name}: added activation datarefs {r}")

        # Representation datarefs
        if self._representation is not None:
            r = self._representation.get_variables()
            if r is not None and len(r) > 0:
                datarefs = datarefs | r
                self._value.add_variables(r, reason="representation")
                logger.debug(f"button {self.name}: added representation datarefs {r}")

        # Hardware Representation datarefs
        if self._hardware_representation is not None:
            r = self._hardware_representation.get_variables()
            if r is not None and len(r) > 0:
                datarefs = datarefs | r
                self._value.add_variables(r, reason="hardware representation")
                logger.debug(f"button {self.name}: added hardware representation datarefs {r}")

        return datarefs

    def get_variable(self, name: str, is_string: bool = False) -> InternalVariable | SimulatorVariable:
        """Returns data or create a new one, internal if path requires it"""
        if self.cockpit.variable_database.exists(name):
            return self.cockpit.variable_database.get(name)
        if InternalVariable.is_internal_variable(path=name):
            return self.cockpit.variable_database.register(variable=self.cockpit.variable_factory(name=name, is_string=is_string, creator=self.name))
        return self.cockpit.variable_database.register(variable=self.sim.variable_factory(name=name, is_string=is_string, creator=self.name))

    # ##################################
    # Dataref processing
    #
    def is_managed(self):
        if self.managed is None:
            logger.debug(f"button {self.name}: is managed is none.")
            return False
        d = self.get_simulator_variable_value(simulator_variable=self.managed, default=0)
        if d != 0:
            logger.debug(f"button {self.name}: is managed ({d}).")
            return True
        logger.debug(f"button {self.name}: is not managed ({d}).")
        return False
        # return self.managed is not None and self.get_simulator_variable_value(simulator_variable=dataref=self.managed, default=0) != 0

    def has_guard(self):
        return self._guard_dref is not None

    def is_guarded(self):
        if not self.has_guard():
            return False
        d = self._guard_dref.value
        if d == 0:
            logger.debug(f"button {self.name}: is guarded ({d}).")
            return True
        return False

    def _set_guarded(self, value: int):
        if not self.has_guard():
            return
        d = self._guard_dref.value
        if d == value:
            logger.debug(f"button {self.name}: is already {'guarded' if d==1 else 'open'} ({value}).")
            return
        self._guard_dref.update_value(new_value=value, cascade=False)
        self._guard_dref.save()
        logger.debug(f"button {self.name}: {'guarded' if value==1 else 'open'} ({value}).")

    def set_guard_on(self):
        self._set_guarded(value=0)

    def set_guard_off(self):
        self._set_guarded(value=1)

    # ##################################
    # Value provider
    #
    def get_internal_variable_value(self, internal_variable, default=None):
        return self.cockpit.get_variable_value(name=internal_variable, default=default)

    def get_simulator_variable_value(self, simulator_variable, default=None):
        return self.page.get_simulator_variable_value(simulator_variable=simulator_variable, default=default)

    def get_state_variable_value(self, name, default: str = "0"):
        value = None
        status = self.get_state_variables()
        source = "all sources"
        if name in status:
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
        if value == "True":
            value = "1"
        elif value == "False":
            value = "0"
        elif value == "None":
            value = default
        logger.debug(f"button {self.name}: state {name} = {value} (from {source})")
        return value

    def get_activation_value(self):
        if self._activation is not None:
            return self._activation.get_activation_value()
        return None

    def get_formula_result(self, default="0.0") -> str | None:
        """Returns the result of the formula of this button"""
        if self._value.has_formula:
            return self._value._formula.value  # must cll value() to force computation, in case not computed before, .current_value might be None.
        return default

    # ##################################
    # Value
    #
    def compute_value(self):
        """
        Button ultimately returns either one value or an array of values.
        Used in
        - Button initialisation to get its first value
        - After dataref is updated
        - After activation
        """

        # 1. Special cases (Annunciator): Each annunciator part has its own evaluation
        if isinstance(self._representation, Annunciator):
            logger.debug(f"button {self.name}: is Annunciator, getting part values")
            return self._representation.get_current_values()

        # 2. dataref or formula based
        #    note that a formula may also use state variables,
        #    but the value knows how to get them if needed.
        dataref = self._config.get(CONFIG_KW.SIM_VARIABLE.value)
        formula = self._config.get(CONFIG_KW.FORMULA.value)
        if dataref is not None or formula is not None or (self.all_datarefs is not None and len(self.all_datarefs) > 0):
            logger.debug(f"button {self.name}: use simulator variable(s)")
            return self._value.value

        # 3. internal button state based
        logger.debug(f"button {self.name}: use internal state")

        # 3a. The activation explicitely has a dedicated attribute with its value(s)
        self._last_activation_state = self._activation.get_state_variables()
        if ACTIVATION_VALUE in self._last_activation_state:
            logger.debug(f"button {self.name}: getting activation value ({self._last_activation_state[ACTIVATION_VALUE]})")
            return self._last_activation_state.get(ACTIVATION_VALUE)

        # 3b. The activation has no "dedicated" attributes, we return all we have from activation.
        logger.warning(f"button {self.name}: getting entire state ({self._last_activation_state})")
        return self._last_activation_state

    def trend(self) -> int:
        if self.current_value is not None and self.previous_value is not None:
            if self.previous_value > self.current_value:
                return -1
            elif self.previous_value < self.current_value:
                return 1
        return 0

    # ##################################
    # External API
    #
    def variable_changed(self, data: Variable):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        if not isinstance(data, (SimulatorVariable, InternalVariable, StringWithVariables)):
            logger.error(f"button {self.name}: not a simulator or internal variable ({type(data).__name__})")
            return

        logger.debug(f"button {self.name}: {data.name} changed")

        if data == self._value:
            logger.log(SPAM_LEVEL, "self value changed, rendering")
            self.render()
            return

        self.value = self.compute_value()
        if self.has_changed() or data.has_changed():
            logger.log(
                SPAM_LEVEL,
                f"button {self.name}: {self.previous_value} -> {self.current_value}",
            )
            self.render()
        else:
            logger.debug(f"button {self.name}: no change")

    def activate(self, event) -> bool:
        """
        @todo: Return a status from activate()
        """

        def always_render():
            if self._representation is not None:
                if hasattr(self._representation, "always_render"):
                    return self._representation.always_render
            return False

        logger.log(SPAM_LEVEL, f"ACTIVATE {self.name} ({event})")
        if self._activation is not None:
            if not self._activation.is_valid():
                logger.warning(f"button {self.name}: activation is not valid, nothing executed")
                return False
            # self.inc(COCKPITDECKS_INTVAR.BUTTON_ACTIVATIONS.value, cascade=False)
            try:
                self._activation.handle(event)
            except:
                logger.warning(f"button {self.name}: problem during activation", exc_info=True)
                logger.warning(f"button {self.name}: not completing activation/rendering")
                return False
        else:
            logger.debug(f"button {self.name}: no activation")

        self.value = self.compute_value()
        self._value.save()  # write set-dataref with the button value and cascade effects

        if self.has_changed():
            logger.log(
                SPAM_LEVEL,
                f"activate: button {self.name}: {self.previous_value} -> {self.current_value}",
            )
            self.render()
        else:
            logger.debug(f"button {self.name}: no change")
            if self.deck.is_virtual_deck() or always_render():  # representation has not changed, but hardware representation might have
                self.render()
        return True

    def get_state_variables(self):
        a = {
            "managed": self.managed,
            "guarded": self.guarded,
        }
        if self._activation is not None:
            a = a | self._activation.get_state_variables()
        if self._representation is not None:
            a = a | self._representation.get_state_variables()
        return a

    def get_representation(self):
        """
        Called from deck to get what's necessary for displaying this button on the deck.
        It can be an image, a color, a binary value on/off...
        """
        if not self._representation.is_valid():
            logger.warning(f"button {self.name}: representation is not valid")
            return None
        # self.inc(COCKPITDECKS_INTVAR.BUTTON_self.deck.cockpit.all_representations.value, cascade=False)
        return self._representation.render()

    def get_representation_metadata(self):
        return {}

    def get_hardware_representation(self):
        """
        Called from deck to get what's necessary for displaying this button on the deck.
        It can be an image, a color, a binary value on/off...
        """
        if self._hardware_representation is None:
            return None
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
                self.deck.vibrate(self)
                # self.inc("vibrate", cascade=False)
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
            if self.on_current_page() and not self.mosaic and not self._part_of_multi:
                # Mosaic and buttons parts of a multi-buttons cannot take the initiative to render themselves.
                # Instruction to render has to come from "parent" button.
                try:
                    self.deck.render(self)
                    logger.log(SPAM_LEVEL, f"RENDER {self.name} ({self.value})")
                except:
                    logger.warning(f"button {self.name}: problem during rendering", exc_info=True)
                    return
                # self.inc(COCKPITDECKS_INTVAR.BUTTON_RENDERS.value, cascade=False)
                logger.debug(f"button {self.name} rendered")
            else:
                logger.debug(f"button {self.name} not on current page")
        else:
            logger.warning(f"button {self.name} has no deck")  # error

    def clean(self):
        """
        Button removes itself from device
        """
        # self.inc(COCKPITDECKS_INTVAR.BUTTON_CLEAN.value, cascade=False)
        self.previous_value = None  # this will provoke a refresh of the value on data reload
        self._representation.clean()


class ButtonInstruction(Instruction):
    """
    An Instruction to be performed by a button.
    Opens door to all custom instructions.
    Button has access to deck, cockpit, simulator...
    """

    INSTRUCTION_NAME = "button-instruction"
    PREFIX = "button-"

    def __init__(self, name: str, button: Button) -> None:
        Instruction.__init__(self, name=name, performer=button.cockpit)
        self._button = button

    @classmethod
    def new(cls, button: Button, name: str, instruction: str, instruction_block: dict):
        all_cockpit_instructions = {s.int_name(): s for s in Instruction.all_subclasses(ButtonInstruction)}
        instr = ButtonInstruction.button_instruction_root_name(instruction)
        if instr in all_cockpit_instructions:
            logger.debug(f"creating ButtonInstruction {instr}")
            return all_cockpit_instructions[instr](button=button, name=name)
        logger.warning(f"no ButtonInstruction {instr}")
        return None

    @property
    def button(self):
        return self._button

    # Button should be read-only
    # @button.setter
    # def button(self, button):
    #     self._button = button

    @staticmethod
    def is_button_instruction(instruction: str) -> bool:
        return instruction.startswith(ButtonInstruction.PREFIX)

    @staticmethod
    def cockpit_instruction(instruction: str) -> str:
        if ButtonInstruction.is_button_instruction(instruction):
            return instruction
        return ButtonInstruction.PREFIX + instruction

    @staticmethod
    def button_instruction_root_name(instruction: str) -> str:
        return instruction.replace(ButtonInstruction.PREFIX, "")

    def _check_condition(self):
        # condition checked in each individual instruction
        return True

    def _execute(self):
        raise NotImplementedError(f"Please implement ButtonInstruction._execute method ({self.name})")


class ButtonRenderInstruction(ButtonInstruction):
    """Instruction to render a button after update"""

    INSTRUCTION_NAME = "render"

    def __init__(self, name: str, button: Button) -> None:
        ButtonInstruction.__init__(self, button=button, name=self.INSTRUCTION_NAME)

    def _execute(self):
        self.button.render()


class ButtonUpdateInstruction(ButtonInstruction):
    """Instruction to render a button after update"""

    INSTRUCTION_NAME = "update"

    def __init__(self, name: str, button: Button, value, cascade: bool = True) -> None:
        ButtonInstruction.__init__(self, button=button, name=self.INSTRUCTION_NAME, instruction_block={})
        self.value = value

    def _execute(self):
        self.button.value = value
