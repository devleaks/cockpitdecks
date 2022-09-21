# Behringer X-Touch Mini deck
#
import logging

from .deck import Deck
from .page import Page
from .button import XTOUCH_MINI_BUTTON_TYPES

logger = logging.getLogger("XTouchMini")

DEFAULT_PAGE_NAME = "X-Plane"


class XTouchMini(Deck):

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device = None):

        Deck.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.init()


    def init(self):
        self.device.set_callback(self.key_change_callback)
        self.start()
        # self.device.test()
        self.load_default_page()

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


    def start(self):
        self.device.start()
        logger.debug(f"start: {self.name} started")


    def terminate(self):
        self.device.stop()
        logger.debug(f"terminate: {self.name} stopped")
