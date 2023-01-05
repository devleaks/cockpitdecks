# Behringer X-Touch Mini deck
#
import os
import re
import yaml
import logging

from .deck import Deck
from .page import Page
from .button import XTOUCH_MINI_BUTTON_TYPES, Knob

from .constant import CONFIG_DIR, RESOURCES_FOLDER, INIT_PAGE, DEFAULT_LAYOUT, DEFAULT_PAGE_NAME
from .constant import YAML_BUTTONS_KW
from .constant import print_stack

from .XTouchMini.Devices.xtouchmini import LED_MODE

logger = logging.getLogger("XTouchDeck")
# logger.setLevel(logging.DEBUG)


class XTouchMini(Deck):

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device = None):

        Deck.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.numkeys = 16

        self.start()
        # self.device.test()
        self.load_default_page()
        self.load()
        self.init()

    def load_default_page(self):
        # Add index 0 only button:
        page_config = {
            "name": DEFAULT_PAGE_NAME
        }
        page0 = Page(name=DEFAULT_PAGE_NAME, config=page_config, deck=self)
        button0 = XTOUCH_MINI_BUTTON_TYPES["push"].new(config={
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

    def load(self):
        """
        Loads Streamdeck pages during configuration
        """
        if self.layout is None:
            self.load_default_page()
            return

        dn = os.path.join(self.cockpit.acpath, CONFIG_DIR, self.layout)
        if not os.path.exists(dn):
            logger.warning(f"load: stream deck has no layout folder '{self.layout}', loading default page")
            self.load_default_page()
            return

        pages = os.listdir(dn)
        for p in pages:
            if p == CONFIG_FILE:
                self.load_layout_config(os.path.join(dn, p))
            elif p.endswith("yaml") or p.endswith("yml"):
                name = ".".join(p.split(".")[:-1])  # remove extension from filename
                fn = os.path.join(dn, p)

                if os.path.exists(fn):
                    with open(fn, "r") as fp:
                        page_config = yaml.safe_load(fp)

                        if "name" in page_config:
                            name = page_config["name"]

                        logger.debug(f"load: loaded page {name} (from file {fn.replace(self.cockpit.acpath, '... ')}), adding..")

                        if name in self.pages.keys():
                            logger.warning(f"load: page {name}: duplicate name, ignored")
                            continue

                        if not YAML_BUTTONS_KW in page_config:
                            logger.error(f"load: {fn} has no action")
                            continue

                        this_page = Page(name, page_config, self)

                        this_page.fill_empty = page_config["fill-empty-keys"] if "fill-empty-keys" in page_config else self.fill_empty
                        self.pages[name] = this_page

                        for a in page_config[YAML_BUTTONS_KW]:
                            button = None
                            bty = None
                            idx = None

                            if "type" in a:
                                bty = a["type"]

                            if "index" in a:
                                idx = a["index"]
                                try:
                                    idx = int(idx)
                                except ValueError:
                                    pass
                            else:
                                logger.error(f"load: page {name}: button {a} has no index, ignoring")
                                continue

                            if bty == "knob":
                                if not idx.startswith("knob"):
                                    if idx < 1 or idx > 8:
                                        logger.error(f"load: page {name}: button {a} has index '{idx}' ({type(idx)}) invalid for XTouch Mini Device, ignoring")
                                        continue
                                    key = f"knob{idx}"

                            a["index"] = idx  # place adjusted index @todo: remove this
                            a["_key"]  = idx  # place adjusted index
                            a["icon"]  = "none"

                            if bty in XTOUCH_MINI_BUTTON_TYPES.keys():
                                button = XTOUCH_MINI_BUTTON_TYPES[bty].new(config=a, page=this_page)
                                this_page.add_button(idx, button)
                            else:
                                logger.error(f"load: page {name}: button {a} invalid button type {bty}, ignoring")

                        logger.info(f"load: ..page {name} added (from file {fn.replace(self.cockpit.acpath, '... ')})")
                else:
                    logger.warning(f"load: file {p} not found")

            else:  # not a yaml file
                logger.debug(f"load: {dn}: ignoring file {p}")

        if not len(self.pages) > 0:
            self.valid = False
            logger.error(f"load: {self.name}: has no page, ignoring")
        else:
            if INIT_PAGE in self.pages.keys():
                self.home_page = self.pages[INIT_PAGE]
            else:
                self.home_page = self.pages[list(self.pages.keys())[0]]  # first page
            logger.info(f"load: deck {self.name} init page {self.home_page.name}")

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
        logger.debug(f"set_encoder_led: button {button.name}: {button.index} => {i}, value={value}, mode={mode}")
        self.set_control(key=i, value=value, mode=mode)

    def set_button_led(self, button):
        logger.debug(f"set_button_led: button {button.name}: {button.index} => {button.is_on()} ({button.has_option('blink')})")
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
