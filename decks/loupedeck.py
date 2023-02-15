# Loupedeck LoupedeckLive decks
#
import os
import logging
import yaml
import threading
import pickle
from time import sleep
from enum import Enum
from PIL import Image, ImageOps

from .Loupedeck.ImageHelpers import PILHelper

from .constant import CONFIG_DIR, CONFIG_FILE, RESOURCES_FOLDER, DEFAULT_LAYOUT, DEFAULT_PAGE_NAME
from .color import convert_color, is_integer
from .deck import Deck
from .page import Page
from .button import Button
from .button_representation import Icon, ColoredLED  # valid representations for this type of deck

logger = logging.getLogger("Loupedeck")
# logger.setLevel(logging.DEBUG)


class Loupedeck(Deck):
    """
    Loads the configuration of a Loupedeck.
    """

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device = None):

        Deck.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.pil_helper = PILHelper

        self.touches = {}
        self.monitoring_thread = None

        self.valid = True

        self.init()

    # #######################################
    # Deck Specific Functions
    #
    # #######################################
    # Deck Specific Functions : Definition
    #
    def make_default_page(self):
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
                logger.warning(f"make_default_page: deck {self.name}: no wallpaper image {image_filename} found, using default")
                image = Image.new(mode="RGBA", size=(deck_width, deck_height), color=self.default_icon_color)
                fn = os.path.join(os.path.dirname(__file__), RESOURCES_FOLDER, self.logo)
                if os.path.exists(fn):
                    inside = 20
                    logo = Image.open(fn).convert("RGBA")
                    logo2 = ImageOps.fit(logo, (deck_width - 2*inside, deck_height - 2*inside), Image.LANCZOS)
                    image.paste(logo2, (inside, inside), logo2)
                else:
                    logger.warning(f"make_default_page: deck {self.name}: no logo image {fn} found, using default")

            image = ImageOps.fit(image, (deck_width, deck_height), Image.LANCZOS)
            return image

        logger.debug(f"load: loading default page {DEFAULT_PAGE_NAME} for {self.name}..")

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
        button0 = Button(config={
                                    "index": 0,
                                    "name": "X-Plane Map (default page)",
                                    "type": "push",
                                    "command": "sim/map/show_current",
                                    "label": "Map",
                                    "icon": self.default_icon_name
                                }, page=page0)
        page0.add_button(button0.index, button0)
        self.pages = { DEFAULT_PAGE_NAME: page0 }
        self.home_page = page0
        logger.debug(f"make_default_page: ..loaded default page {DEFAULT_PAGE_NAME} for {self.name}, set as home page")

    def valid_indices_with_image(self):
        return [str(i) for i in range(12)] + ["left", "right"]

    def valid_indices(self):
        encoders = ["knobTL", "knobCL", "knobBL", "knobTR", "knobCR", "knobBR"]
        keys = [str(i) for i in range(12)]
        buttons = [f"b{i}" for i in range(8)]
        return encoders + keys + buttons + ["left", "right"]

    def valid_activations(self, index = None):
        valid_key = super().valid_activations() + ["push", "onoff", "updown", "longpress"]
        valid_push_encoder = valid_key + ["encoder", "encoder-push", "encoder-onoff", "knob"]
        valid_colored_button = valid_key

        if index is not None:
            if index in self.valid_indices():
                if index.startswith("knob"):
                    return valid_push_encoder
                if index.startswith("b") or is_integer(index):
                    return valid_colored_button
                if is_integer(index):
                    return valid_key
            else:
                logger.warning(f"valid_activations: invalid index for {type(self).__name__}")
                return []
        return set(valid_key + valid_push_encoder + valid_colored_button)

    def valid_representations(self, index = None):
        valid_side_icon = ["none", "side"]
        valid_key_icon = ["none", "icon", "text", "icon-color", "multi-icons", "icon-animate", "annunciator", "annunciator-animate", "data", "weather"]
        valid_colored_button = ["colored-led"]
        valid_knob = ["none"]

        if index is not None:
            if index in self.valid_indices():
                if index in ["left", "right"]:
                    return valid_side_icon
                if index.startswith("knob"):
                    return valid_knob
                if index.startswith("b"):
                    return valid_colored_button
                if is_integer(index):
                    return valid_key_icon
            else:
                logger.warning(f"valid_activations: invalid index for {type(self).__name__}")
                return []
        return set(super().valid_representations() + valid_key_icon + valid_side_icon + valid_colored_button)

    # #######################################
    # Deck Specific Functions : Activation
    #
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
            if key == "circle":
                key = 0
            try:
                num = int(key)
                key = f"b{key}"
            except ValueError:
                logger.warning(f"key_change_callback: invalid button key {key}")
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
                    event_dict = {
                        "begin_key": kstart,
                        "begin_x": self.touches[msg["id"]]["x"],
                        "begin_y": self.touches[msg["id"]]["y"],
                        "end_key": kend,
                        "end_x": msg["x"],
                        "end_y": msg["y"],
                        "diff_x": dx,
                        "diff_y": dy,
                        "same_key": same_key
                    }
                    event = [self.touches[msg["id"]]["x"], self.touches[msg["id"]]["y"], kstart]
                    event = event + [msg["x"], msg["y"], kend]
                    event = event + [dx, dy, same_key]
                    logger.debug(f"key_change_callback: side bar touched, no processing event={event_dict}")
                    transfer(deck, kstart, event)
            else:
                logger.error(f"key_change_callback: received touchend but no matching touchstart found")
        else:
            if action != "touchmove":
                logger.debug(f"key_change_callback: unprocessed {msg}")

    # #######################################
    # Deck Specific Functions : Representation
    #
    def create_icon_for_key(self, button, colors):
        b = button.index
        if b not in ["full", "center", "left", "right"]:
            b = "button"
        if self.pil_helper is not None:
            return self.pil_helper.create_image(deck=b, background=colors)
        return None

    def scale_icon_for_key(self, button, image):
        b = button.index
        if b not in ["full", "center", "left", "right"]:
            b = "button"
        if self.pil_helper is not None:
            return self.pil_helper.create_scaled_image(deck=b, image=image)
        return None

    def _send_key_image_to_device(self, key, image):
        self.device.set_key_image(key, image)

    def _set_key_image(self, button: Button): # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("set_key_image: no device")
            return
        image = button.get_representation()
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
            self._send_key_image_to_device(button.index, image)
        else:
            logger.warning(f"set_key_image: no image for {button.name}")

    def _set_button_color(self, button: Button): # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("set_key_image: no device")
            return
        color = button.get_representation()
        if color is None:
            logger.warning("set_key_image: button returned no representation color, using default")
            color = (240, 240, 240)
        idx = button.index.lower().replace("b", "")
        if idx == "0":
            idx = "circle"
        self.device.set_button_color(idx, color)

    def render(self, button: Button): # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("render: no device")
            return
        if str(button.index).startswith("knob"):
            logger.debug(f"render: button type {button.index} has no representation")
            return
        representation = button._representation
        if isinstance(representation, Icon):
            self._set_key_image(button)
        elif isinstance(representation, ColoredLED):
            self._set_button_color(button)
        else:
            logger.warning(f"render: not a valid button type {type(representation).__name__} for {type(self).__name__}")

    # #######################################
    # Deck Specific Functions : Device
    #
    def start(self):
        if self.device is None:
            logger.warning(f"start: loupedeck {self.name}: no device")
            return
        self.device.set_callback(self.key_change_callback)
        self.device.start()  # restart it if it was terminated
        logger.info(f"start: loupedeck {self.name}: listening for key strokes")

    def terminate(self):
        super().terminate()  # cleanly unload current page, if any
        with self.device:
            self.device.set_callback(None)
            self.device.reset()
            self.device.stop()  # terminates the loop.
            self.running = False

        # logger.debug(f"terminate: closing {type(self.device).__name__}..")
        # del self.device     # closes connection and stop serial _read thread
        # logger.debug(f"terminate: closed")
        logger.info(f"terminate: deck {self.name} terminated")


