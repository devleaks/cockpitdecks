# Behringer X-Touch Mini decks
#
import os
import re
import logging

from XTouchMini.Devices.xtouchmini import LED_MODE, MAKIE_MAPPING

from cockpitdecks import DEFAULT_PAGE_NAME
from cockpitdecks.deck import Deck
from cockpitdecks.page import Page
from cockpitdecks.button import Button
from cockpitdecks.buttons.representation import LED, MultiLEDs

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
# Warning, the logger in package XTouchMini is called "XTouchMini".

ENCODE_PREFIX = "e"
SLIDER = "slider"


class XTouchMini(Deck):
    """
    Loads the configuration of a X-Touch Mini.
    """

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device=None):
        Deck.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.cockpit.set_logging_level(__name__)
        self.init()

    # #######################################
    # Deck Specific Functions
    #
    # #######################################
    # Deck Specific Functions : Definition
    #
    def make_default_page(self):
        logger.debug(f"loading default page {DEFAULT_PAGE_NAME} for {self.name}..")
        # Add index 0 only button:
        page_config = {"name": DEFAULT_PAGE_NAME}
        page0 = Page(name=DEFAULT_PAGE_NAME, config=page_config, deck=self)
        button0 = Button(
            config={"index": 0, "name": "X-Plane Map (default page)", "type": "push", "command": "sim/map/show_current", "led": "single"}, page=page0
        )
        page0.add_button(button0.index, button0)
        self.pages = {DEFAULT_PAGE_NAME: page0}
        self.home_page = page0
        self.current_page = page0
        logger.debug(f"..loaded default page {DEFAULT_PAGE_NAME} for {self.name}, set as home page")

    def load_icons(self):
        pass

    def make_icon_for_device(self):
        pass

    # #######################################
    # Deck Specific Functions : Activation
    #
    def key_change_processing(self, deck, key, state):
        """
        This is the function that is called when a key is pressed.
        """
        # logger.debug(f"Deck {deck.id()} Key {key} = {state}")
        # logger.debug(f"Deck {deck.id()} Keys: {self.current_page.buttons.keys()}")
        KEY_MAP = dict((v, k) for k, v in MAKIE_MAPPING.items())
        key1 = None
        if key >= 16 and key <= 23:  # turn encode
            key1 = f"{ENCODE_PREFIX}{key - 16}"
        elif key >= 32 and key <= 39:  # push on encoder
            key1 = f"{ENCODE_PREFIX}{key - 32}"
        elif key == 8:  # slider
            key1 = SLIDER
        else:  # push a button
            key1 = KEY_MAP[key]
        logger.debug(f"{key} => {key1} {state}")
        if self.current_page is not None and key1 in self.current_page.buttons.keys():
            self.current_page.buttons[key1].activate(state)

    # #######################################
    # Deck Specific Functions : Representation
    #
    def get_display_for_pil(self, b: str = None):
        """
        Return device or device element to use for PIL.
        In this case, no image, no PIL
        """
        return None

    def _set_encoder_led(self, button):
        # logger.debug(f"button {button.name}: {'='*50}")
        # self.device.test()
        # logger.debug(f"button {button.name}: {'='*50}")
        # return
        value, mode = button.get_representation()
        # find index in string
        i = int(button.index[1:])
        logger.debug(f"button {button.name}: {button.index} => {i}, value={value}, mode={mode.name}")
        self._set_control(key=i, value=value, mode=mode)

    def _set_button_led(self, button):
        is_on = button.get_current_value()
        logger.debug(f"button {button.name}: {button.index} => on={is_on} (blink={button.has_option('blink')})")
        self._set_key(key=button.index, on=is_on, blink=button.has_option("blink"))

    # Low-level wrapper around device API (direct forward)
    #
    def _set_key(self, key: int, on: bool = False, blink: bool = False):
        if self.device is not None:
            self.device.set_key(key=key, on=on, blink=blink)

    def _set_control(self, key: int, value: int, mode: LED_MODE = LED_MODE.SINGLE):
        if self.device is not None:
            self.device.set_control(key=key, value=value, mode=mode)

    def render(self, button: Button):  # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning(f"no device ({hasattr(self, 'device')}, {type(self)})")
            return
        if str(button.index) == SLIDER:
            logger.debug(f"button type {button.index} has no representation")
            return

        representation = button._representation
        if isinstance(representation, LED):
            self._set_button_led(button)
        elif isinstance(representation, MultiLEDs):
            self._set_encoder_led(button)
        else:
            logger.warning(f"button: {button.name}: not a valid representation type {type(representation).__name__} for {type(self).__name__}")

    # #######################################
    # Deck Specific Functions : Device
    #
    def start(self):
        if self.device is None:
            logger.warning(f"deck {self.name}: no device")
            return
        self.device.set_callback(self.key_change_callback)
        self.device.start()
        logger.debug(f"deck {self.name}: started")

    def terminate(self):
        super().terminate()  # cleanly unload current page, if any
        XTouchMini.terminate_device(self.device, self.name)
        del self.device
        self.device = None
        logger.debug(f"{self.name} stopped")

    @staticmethod
    def terminate_device(device, name: str = "unspecified"):
        device.stop()  # terminates the loop.
        del device
        device = None
        logger.info(f"{name} terminated")
