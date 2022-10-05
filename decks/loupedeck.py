# Loupedeck LoupedeckLive deck
#
import os
import logging
import yaml
import threading
import pickle

from time import sleep

from enum import Enum

from .Loupedeck.ImageHelpers import PILHelper
from PIL import Image, ImageOps

from .constant import CONFIG_DIR, RESOURCES_FOLDER, INIT_PAGE, DEFAULT_LAYOUT
from .constant import convert_color
from .button import Button, LOUPEDECK_BUTTON_TYPES
from .page import Page

from .deck import Deck
from .Loupedeck.Devices.constants import BUTTONS as LOUPEDECK_BUTTON_NAMES

logger = logging.getLogger("Loupedeck")

DEFAULT_PAGE_NAME = "X-Plane"

VALID_STATE = {
    "down": 1,
    "up": 0,
    "left": 2,
    "right": 3
}


class Loupedeck(Deck):
    """
    Loads the configuration of a Loupedeck.
    A Loupedeck has a collection of Pages, and knows which one is currently being displayed.
    """

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device = None):

        Deck.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.pil_helper = PILHelper

        self.touches = {}
        self.monitoring_thread = None

        self.valid = True

        if self.valid:
            self.make_default_icon()
            self.make_icon_for_device()
            self.load()
            self.init()
            self.start()

    def load(self):
        """
        Loads Streamdeck pages during configuration
        """
        YAML_BUTTONS_KW = "buttons"  # keywork in yaml file
        YAML_INCLUDE_KW = "includes"
        if self.layout is None:
            self.load_default_page()
            return

        dn = os.path.join(self.cockpit.acpath, CONFIG_DIR, self.layout)
        if not os.path.exists(dn):
            logger.warning(f"load: loupedeck has no layout folder '{self.layout}', loading default page")
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

                        button_indices = [(b["type"],b["index"]) for b in page_config[YAML_BUTTONS_KW]]
                        if YAML_INCLUDE_KW in page_config:
                            includes = page_config[YAML_INCLUDE_KW]
                            if type(page_config[YAML_INCLUDE_KW]) == str:
                                includes = [includes]
                            for inc in includes:
                                fni = os.path.join(dn, inc + ".yaml")
                                with open(fni, "r") as fpi:
                                    inc_config = yaml.safe_load(fpi)
                                    # how to merge? for now, just merge buttons
                                    if YAML_BUTTONS_KW in inc_config:
                                        for add_button in inc_config[YAML_BUTTONS_KW]:
                                            if "index" in add_button and "type" in add_button and (add_button["type"],add_button["index"]) not in button_indices:
                                                # Add it if there is no button of that type with same index in page
                                                page_config[YAML_BUTTONS_KW].append(add_button)
                                                logger.debug(f"load: includes: added {add_button['type']} {add_button['index']} from {inc} to page {name}")

                        if "name" in page_config:
                            name = page_config["name"]

                        this_page = Page(name, page_config, self)
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
                                if idx not in list(LOUPEDECK_BUTTON_NAMES.values())[0:6]:
                                    logger.error(f"load: page {name}: button {a} has index '{idx}' ({type(idx)}) invalid for LoupedeckLive Device (keys={LOUPEDECK_BUTTON_NAMES.values()[:-7]}), ignoring")
                                    continue
                            elif bty == "button":
                                if idx < 0 or idx > 7:  # buttons are 0 to 7, circle is an alias for B0
                                    logger.error(f"load: page {name}: button {a} has index '{idx}' invalid for LoupedeckLive Device, ignoring")
                                    continue
                                if idx == 0:
                                    idx = "circle"
                                else:
                                    idx = f"B{idx}"
                            elif bty == "side":
                                if idx not in ["left", "right"]:  # large, side buttons
                                    logger.error(f"load: page {name}: button {a} has index '{idx}' invalid for LoupedeckLive Device, ignoring")
                                    continue

                            a["index"] = idx  # place adjusted index @todo: remove this
                            a["_key"]  = idx  # place adjusted index

                            if bty in LOUPEDECK_BUTTON_TYPES.keys():
                                button = LOUPEDECK_BUTTON_TYPES[bty].new(config=a, page=this_page)
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
            logger.info(f"load: loupedeck {self.name} init page {self.home_page.name}")

    def load_default_page(self):
        # Generates an image that is correctly sized to fit across all keys of a given
        #
        # The following two helper functions are stolen from streamdeck example scripts (tiled_image)
        # Generates an image that is correctly sized to fit across all keys of a given
        #
        # The following two helper functions are stolen from streamdeck example scripts (tiled_image)
        def create_full_deck_sized_image(image_filename):
            deck_width, deck_height = (60 + 4*90 + 60, 270)
            image = None
            if os.path.exists(image_filename):
                image = Image.open(image_filename).convert("RGBA")
            else:
                logger.warning(f"load_default_page: deck {self.name}: no wallpaper image {image_filename} found, using default")
                image = Image.new(mode="RGBA", size=(deck_width, deck_height), color=self.default_icon_color)
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, self.logo)
                if os.path.exists(fn):
                    inside = 20
                    logo = Image.open(fn).convert("RGBA")
                    logo2 = ImageOps.fit(logo, (deck_width - 2*inside, deck_height - 2*inside), Image.LANCZOS)
                    image.paste(logo2, (inside, inside), logo2)
                else:
                    logger.warning(f"load_default_page: deck {self.name}: no logo image {fn} found, using default")

            image = ImageOps.fit(image, (deck_width, deck_height), Image.LANCZOS)
            return image

        fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, self.wallpaper)
        image = create_full_deck_sized_image(fn)
        image_left = image.copy().crop((0, 0, 60, image.height))
        self.device.draw_image(image_left, display="left")
        image_center = image.copy().crop((60, 0, 420, image.height))
        self.device.draw_image(image_center, display="center")
        image_right = image.copy().crop((image.width-60, 0, image.width, image.height))
        self.device.draw_image(image_right, display="right")

        # Add index 0 only button:
        page_config = {
            "name": DEFAULT_PAGE_NAME
        }
        page0 = Page(name=DEFAULT_PAGE_NAME, config=page_config, deck=self)
        button0 = LOUPEDECK_BUTTON_TYPES["push"].new(config={
                                                "index": 0,
                                                "name": "X-Plane Map",
                                                "type": "push",
                                                "command": "sim/map/show_current",
                                                "label": "Map",
                                                "icon": self.default_icon_name
                                            }, page=page0)
        page0.add_button(button0.index, button0)
        self.pages = { DEFAULT_PAGE_NAME: page0 }
        self.home_page = None
        self.current_page = page0
        self.device.set_callback(self.key_change_callback)
        self.running = True

    def key_change_callback(self, deck, msg):
        """
        This is the function that is called when a key is pressed.
        """
        def transfer(this_deck, this_key, this_state):
            if self.cockpit.xp.use_flight_loop:  # if we use a flight loop, key_change_processing will be called from there
                self.cockpit.xp.events.put([self.name, this_key, this_state])
                # logger.debug(f"key_change_callback: {this_key} {this_state} enqueued")
            else:
                # logger.debug(f"key_change_callback: {key} {state}")
                self.key_change_processing(this_deck, this_key, this_state)

        # logger.debug(f"key_change_callback: {msg}")
        if "action" not in msg or "id" not in msg:
            logger.debug(f"key_change_callback: invalid message {msg}")
            return

        key = msg["id"]
        action = msg["action"]

        if action == "push":
            state = 1 if msg["state"] == "down" else 0
            num = -1
            try:
                num = int(key)
                if num == 0:
                    key = "circle"
                elif num > 0:
                    key = f"B{key}"
                else:
                    logger.warning(f"key_change_callback: invalid button key {key}")
            except ValueError:
                pass
            transfer(deck, key, state)

        elif action == "rotate":
            state = 2 if msg["state"] == "left" else 3
            transfer(deck, key, state)

        elif action == "touchstart":  # we don't deal with slides now, just push on key
            state = 1
            if "key" in msg and msg["key"] is not None:  # we touched a key, not a side bar
                key = msg["key"]
                try:
                    key = int(key)
                except ValueError:
                    logger.warning(f"key_change_callback: invalid button key {key} {msg}")
                self.touches[msg["id"]] = msg
                transfer(deck, key, state)
            else:
                self.touches[msg["id"]] = msg
                logger.warning(f"key_change_callback: side bar touched, no processing")

        elif action == "touchend":  # since user can "release" touch in another key, we send the touchstart one.
            state = 0
            if msg["id"] in self.touches:
                if "key" in self.touches[msg["id"]] and self.touches[msg["id"]]["key"] is not None:
                    key = self.touches[msg["id"]]["key"]
                    del self.touches[msg["id"]]
                    transfer(deck, key, state)
                else:
                    dx = msg["x"] - self.touches[msg["id"]]["x"]
                    dy = msg["y"] - self.touches[msg["id"]]["y"]
                    kstart = msg["key"] if msg["key"] is not None else msg["screen"]
                    kend = self.touches[msg["id"]]["key"] if self.touches[msg["id"]]["key"] is not None else self.touches[msg["id"]]["screen"]
                    same_key = kstart == kend
                    event = [self.touches[msg["id"]]["x"], self.touches[msg["id"]]["y"], kstart]
                    event = event + [msg["x"], msg["y"], kend]
                    event = event + [dx, dy, same_key]
                    # logger.debug(f"key_change_callback: side bar touched, no processing event={event}")
                    transfer(deck, kstart, event)
            else:
                logger.error(f"key_change_callback: received touchend but no matching touchstart found")
        else:
            if action != "touchmove":
                logger.debug(f"key_change_callback: unprocessed {msg}")

    # def key_change_processing(self, deck, key, state):
    #     """
    #     This is the function that is called when a key is pressed.
    #     """
    #     logger.debug(f"key_change_processing: Deck {deck.id()} Key {key} = {state}")
    #     if key in self.current_page.buttons.keys():
    #         self.current_page.buttons[key].activate(state)
    #     else:
    #         logger.debug(f"key_change_processing: Key {key} not in {self.current_page.buttons.keys()}")

    def create_icon_for_key(self, button, colors):
        if button not in ["full", "center", "left", "right"]:
            button = "button"
        return self.pil_helper.create_image(deck=button, background=colors)

    def make_icon_for_device(self):
        """
        Each device model requires a different icon format (size).
        We could build a set per Stream Deck model rather than stream deck instance...
        This makes the square icons for all square keys.
        Side keys (left and right) are treated separatey.
        """
        dn = self.cockpit.icon_folder
        if dn is not None:
            cache = os.path.join(dn, f"{self.name}_icon_cache.pickle")
            if os.path.exists(cache):
                with open(cache, "rb") as fp:
                    icons_temp = pickle.load(fp)
                    self.icons.update(icons_temp)
                logger.info(f"make_icon_for_device: {len(self.icons)} icons loaded from cache")
                return

        logger.info(f"make_icon_for_device: deck {self.name}..")
        if self.device is not None:
            for k, v in self.cockpit.icons.items():
                self.icons[k] = self.pil_helper.create_scaled_image("button", v)  # 90x90
            if dn is not None:
                cache = os.path.join(dn, f"{self.name}_icon_cache.pickle")
                with open(cache, "wb") as fp:
                    pickle.dump(self.icons, fp)
            logger.info(f"make_icon_for_device: deck {self.name} icons ready")
        else:
            logger.warning(f"make_icon_for_device: deck {self.name} has no device")

    def set_key_image(self, button: Button): # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("set_key_image: no device")
            return
        image = button.get_image()
        if image is None and button.index not in ["left", "right"]:
            logger.warning("set_key_image: button returned no image, using default")
            image = self.icons[self.default_icon_name]

        if image is not None and button.index in ["left", "right"]:
                self.device.set_key_image(button.index, image)
                return

        if image is not None:
            sizes = self.device.key_image_format()
            if sizes is not None:
                sizes = sizes.get("size")
                if sizes is not None:
                    sizes = list(sizes)
                    mw = sizes[0]
                    mh = sizes[1]
                    if image.width > mw or image.height > mh:
                        image = self.pil_helper.create_scaled_image("button", image)
                else:
                    logger.warning("set_key_image: cannot get device key image size")
            else:
                logger.warning("set_key_image: cannot get device key image format")
            self.device.set_key_image(button.index, image)
        else:
            logger.warning(f"set_key_image: no image for {button.name}")

    def set_button_color(self, button: Button): # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("set_key_image: no device")
            return
        color = button.get_color()
        if color is None:
            logger.warning("set_key_image: button returned no image, using default")
            color = (240, 240, 240)
        self.device.set_button_color(button.index.replace("B", ""), color)


    def start(self):
        if self.device is not None:
            self.device.set_callback(self.key_change_callback)
            self.device.start()  # restart it if it was terminated
        logger.info(f"start: loupedeck {self.name} listening for key strokes")

    def terminate(self):
        self.device.stop()  # stops our threads (reading, processing)
        # logger.debug(f"terminate: closing {type(self.device).__name__}..")
        # del self.device     # closes connection and stop serial _read thread
        # logger.debug(f"terminate: closed")
        logger.info(f"terminate: deck {self.name} terminated")
