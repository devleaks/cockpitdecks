# Behringer X-Touch Mini deck
#
import os
import yaml
import logging

from .deck import Deck
from .page import Page
from .button import XTOUCH_MINI_BUTTON_TYPES

from .constant import CONFIG_DIR, RESOURCES_FOLDER, INIT_PAGE, DEFAULT_LAYOUT
from .XTouchMini.Devices.xtouchmini import LED_MODE

logger = logging.getLogger("XTouchMini")
# logger.setLevel(logging.DEBUG)


DEFAULT_PAGE_NAME = "X-Plane"


class XTouchMini(Deck):

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device = None):

        Deck.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.numkeys = 16

        self.init()


    def init(self):
        self.device.set_callback(self.key_change_callback)
        self.start()
        # self.device.test()
        self.load_default_page()
        self.load()

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
                                                "label": "Map"
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
        YAML_BUTTONS_KW = "buttons"  # keywork in yaml file
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
            if p.endswith("yaml") or p.endswith("yml"):
                name = ".".join(p.split(".")[:-1])  # remove extension from filename
                fn = os.path.join(dn, p)

                if os.path.exists(fn):
                    with open(fn, "r") as fp:
                        page_config = yaml.safe_load(fp)

                        if not YAML_BUTTONS_KW in page_config:
                            logger.error(f"load: {fn} has no action")
                            continue

                        if "name" in page_config:
                            name = page_config["name"]

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

                        logger.info(f"load: page {name} added (from file {fn.replace(self.cockpit.acpath, '... ')})")
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

    def set_key_image(self, button):
        self.device.set_key(key=button.index - 8, on=button.is_pushed())
        logger.debug(f"set_key_image: button {button.name} rendered")

    def set_key(self, key: int, on:bool=False, blink:bool=False):
        if self.device is not None:
            self.device.set_key(key=key, on=on, blink=blink)

    def set_control(self, key: int, value:int, mode: LED_MODE = LED_MODE.SINGLE):
        if self.device is not None:
            self.device.set_control(key=key, value=value, mode=mode)


    def start(self):
        self.device.start()
        logger.debug(f"start: {self.name} started")


    def terminate(self):
        super().terminate()  # cleanly unload current page, if any
        self.device.stop()
        logger.debug(f"terminate: {self.name} stopped")
