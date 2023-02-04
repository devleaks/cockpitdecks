# Behringer X-Touch Mini deck
#
import os
import re
import yaml
import logging

from .deck import Deck
from .page import Page

from .constant import CONFIG_DIR, CONFIG_FILE, RESOURCES_FOLDER, INIT_PAGE, DEFAULT_LAYOUT, DEFAULT_PAGE_NAME
from .constant import YAML_BUTTONS_KW

from .button import Button

from .XTouchMini.Devices.xtouchmini import LED_MODE, MAKIE_MAPPING

logger = logging.getLogger("XTouchDeck")
logger.setLevel(logging.DEBUG)


class XTouchMini(Deck):

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device = None):

        Deck.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.numkeys = 16

        self.start()
        # self.device.test()
        self.load_default_page()
        self.load()
        self.init()

    def valid_indices(self):
        encoders = [f"e{i}" for i in range(8)]
        buttons = [str(i) for i in range(16)]
        return encoders + buttons + ["A", "B", "slider"]

    def valid_activations(self):
        return super().valid_activations() + ["push", "onoff", "updown", "longpress", "encoder", "encoder-push", "encoder-onoff", "knob"]

    def valid_representations(self):
        return super().valid_representations() + ["led", "multi-leds"]

    def load_default_page(self):
        # Add index 0 only button:
        page_config = {
            "name": DEFAULT_PAGE_NAME
        }
        page0 = Page(name=DEFAULT_PAGE_NAME, config=page_config, deck=self)
        button0 = Button(config={
                                    "index": 8,
                                    "name": "X-Plane Map",
                                    "type": "push",
                                    "command": "sim/map/show_current",
                                    "options": "counter"
                                }, page=page0)
        page0.add_button(button0.index, button0)
        self.pages = { DEFAULT_PAGE_NAME: page0 }
        self.home_page = None
        self.current_page = page0
        self.device.set_callback(self.key_change_callback)
        self.running = True

    def key_change_processing(self, deck, key, state):
        """
        This is the function that is called when a key is pressed.
        """
        # logger.debug(f"key_change_processing: Deck {deck.id()} Key {key} = {state}")
        # logger.debug(f"key_change_processing: Deck {deck.id()} Keys: {self.current_page.buttons.keys()}")
        KEY_MAP = dict((v,k) for k, v in MAKIE_MAPPING.items())
        key1 = None
        if key >= 16 and key <= 23:     # turn encode
            key1 = f"encoder{key - 16}"
        elif key >= 32 and key <= 39:   # push on encoder
            key1 = f"encoder{key - 32}"
        elif key == 8:                  # slider
            key1 = f"slider"
        else:                           # push a button
            key1 = KEY_MAP[key]
        logger.debug(f"key_change_callback: {key} => {key1} {state}")
        if self.current_page is not None and key1 in self.current_page.buttons.keys():
            self.current_page.buttons[key1].activate(state)

    # High-level (functional)calls for feedback/visualization
    #
    def set_key_image(self, button):
        if isinstance(button, Knob):
            self.set_encoder_led(button)
        else:
            self.set_button_led(button)

    def set_encoder_led(self, button):
        # logger.debug(f"test: button {button.name}: {'='*50}")
        # self.device.test()
        # logger.debug(f"test: button {button.name}: {'='*50}")
        # return
        value, mode = button.get_led()
        # find index in string
        nums = re.findall("\\d+(?:\\.\\d+)?$", button.index)
        if len(nums) < 1:
            logger.warning(f"set_encoder_led: button {button.name}: {button.index} => cannot determine numeric index")
            return
        i = int(nums[0])
        logger.debug(f"set_encoder_led: button {button.name}: {button.index} => {i}, value={value}, mode={mode.name}")
        self.set_control(key=i, value=value, mode=mode)

    def set_button_led(self, button):
        logger.debug(f"set_button_led: button {button.name}: {button.index} => on={button.is_on()} (blink={button.has_option('blink')})")
        self.set_key(key=button.index, on=button.is_on(), blink=button.has_option("blink"))

    # Low-level wrapper around device API (direct forward)
    #
    def set_key(self, key: int, on:bool=False, blink:bool=False):
        if self.device is not None:
            self.device.set_key(key=key, on=on, blink=blink)

    def set_control(self, key: int, value:int, mode: LED_MODE = LED_MODE.SINGLE):
        if self.device is not None:
            self.device.set_control(key=key, value=value, mode=mode)

    # Start/stop device management & control
    #
    def start(self):
        if self.device is None:
            logger.warning(f"start: deck {self.name}: no device")
            return
        self.device.set_callback(self.key_change_callback)
        self.device.start()
        logger.debug(f"start: deck {self.name}: started")

    def terminate(self):
        super().terminate()  # cleanly unload current page, if any
        self.device.stop()
        logger.debug(f"terminate: {self.name} stopped")
