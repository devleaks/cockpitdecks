# Loupedeck LoupedeckLive decks
#
import os
import logging
import pickle
from time import sleep
from enum import Enum
from PIL import Image, ImageOps

from Loupedeck.ImageHelpers import PILHelper

from .constant import CONFIG_FOLDER, CONFIG_FILE, RESOURCES_FOLDER, DEFAULT_LAYOUT, DEFAULT_PAGE_NAME
from .color import convert_color, is_integer, DEFAULT_COLOR
from .deck import DeckWithIcons
from .page import Page
from .button import Button
from .button_representation import Icon, ColoredLED  # valid representations for this type of deck

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
# Warning, the logger in package Loupedeck is also called "Loupedeck".

SIDE_INDIVIDUAL_KEYS = False

VIBRATION_MODES = [
    "SHORT",
    "MEDIUM",
    "LONG",
    "LOW",
    "SHORT_LOW",
    "SHORT_LOWER",
    "LOWER",
    "LOWEST",
    "DESCEND_SLOW",
    "DESCEND_MED",
    "DESCEND_FAST",
    "ASCEND_SLOW",
    "ASCEND_MED",
    "ASCEND_FAST",
    "REV_SLOWEST",
    "REV_SLOW",
    "REV_MED",
    "REV_FAST",
    "REV_FASTER",
    "REV_FASTEST",
    "RISE_FALL",
    "BUZZ",
    "RUMBLE5", # lower frequencies in descending order
    "RUMBLE4",
    "RUMBLE3",
    "RUMBLE2",
    "RUMBLE1",
    "VERY_LONG"  # 10 sec high freq (!)
]

# Note:
# Keys are large icon-backed portions of the LCD screen.
# Buttons are smaller, colored push buttons labeled 0 (dotted circle) to 7.
# Knobs are rotating knobs on either side.
BUTTON_PREFIX = "b"
KNOB_PREFIX = "knob"

class Loupedeck(DeckWithIcons):
    """
    Loads the configuration of a Loupedeck.
    """

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device = None):

        DeckWithIcons.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

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
                image = ImageOps.fit(image, (deck_width, deck_height), Image.LANCZOS)
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
        page0 = Page(name=DEFAULT_PAGE_NAME,
                     config={
                                "name": DEFAULT_PAGE_NAME
                     },
                     deck=self)
        button0 = Button(config={
                                    "index": 0,
                                    "name": "X-Plane Map (default page)",
                                    "type": "push",
                                    "command": "sim/map/show_current",
                                    "text": "MAP"
                                }, page=page0)
        page0.add_button(button0.index, button0)
        button1 = Button(config={
                                    "index": 1,
                                    "name": "Exit",
                                    "type": "stop",
                                    "icon": "PANIC"
                                }, page=page0)
        page0.add_button(button1.index, button1)
        self.pages = { DEFAULT_PAGE_NAME: page0 }
        self.home_page = page0
        logger.debug(f"make_default_page: ..loaded default page {DEFAULT_PAGE_NAME} for {self.name}, set as home page")

    def side_individual_keys(self):
        return [f"L{i}" for i in range(3)] + [f"R{i}" for i in range(3)]


    def valid_indices_with_image(self):
        if SIDE_INDIVIDUAL_KEYS:
            return [str(i) for i in range(12)] + self.side_individual_keys()
        else:
            return [str(i) for i in range(12)] + ["left", "right"]

    def valid_indices(self):
        encoders = ["knobTL", "knobCL", "knobBL", "knobTR", "knobCR", "knobBR"]
        keys = [str(i) for i in range(12)]
        buttons = [f"{BUTTON_PREFIX}{i}" for i in range(8)]
        if SIDE_INDIVIDUAL_KEYS:
            return encoders + keys + buttons + self.side_individual_keys()
        else:
            return encoders + keys + buttons + ["left", "right"]

    def valid_activations(self, index = None):
        valid_key = super().valid_activations() + ["push", "onoff", "updown", "longpress"]
        valid_push_encoder = valid_key + ["encoder", "encoder-push", "encoder-onoff", "encoder-value", "knob"]
        valid_colored_button = valid_key

        if index is not None:
            if index in self.valid_indices():
                if index.startswith(KNOB_PREFIX):
                    return valid_push_encoder
                if index.startswith(BUTTON_PREFIX) or is_integer(index):
                    return valid_colored_button
                if is_integer(index):
                    return valid_key
            else:
                logger.warning(f"valid_activations: invalid index for {type(self).__name__}")
                return []
        return set(valid_key + valid_push_encoder + valid_colored_button)

    def valid_representations(self, index = None):
        valid_side_icon = ["none", "side"]
        valid_key_icon = [
            "none",
            "icon",
            "text",
            "icon-color",
            "multi-icons",
            "icon-animate",
            "annunciator",
            "annunciator-animate",
            "data",
            "weather",
            "switch",
            "circular-switch",
            "push-switch"
        ]
        valid_colored_button = ["colored-led"]
        valid_knob = ["none"]

        if index is not None:
            if index in self.valid_indices():
                if index in ["left", "right"]:
                    return valid_side_icon
                if index.startswith(KNOB_PREFIX):
                    return valid_knob
                if index.startswith(BUTTON_PREFIX):
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
            """
            Either execute function direactly or enqueue it for later dequeue.
            """
            logger.debug(f"key_change_callback: Deck {this_deck.id()} Key {this_key} = {this_state}")
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

        L = 270
        key = msg["id"]
        action = msg["action"]

        if action == "push":
            state = 1 if msg["state"] == "down" else 0
            num = -1
            if not key.startswith(KNOB_PREFIX):
                if key == "circle":
                    key = 0
                try:
                    num = int(key)
                    key = f"{BUTTON_PREFIX}{key}"
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
                if SIDE_INDIVIDUAL_KEYS:
                    k = None
                    i = 0
                    while k is None and i < 3:
                        if msg["y"] >= int(i*L/3) and msg["y"] < int((i+1)*L/3):
                            k = f"{msg['screen'][0].upper()}{i}"
                        i = i + 1
                    logger.debug(f"key_change_callback: side bar pressed, SIDE_INDIVIDUAL_KEYS event {k} = {state}")
                    # This transfer a (virtual) button push event
                    transfer(deck, k, state)
                    # WATCH OUT! If the release occurs in another key (virtual or not),
                    # the corresponding release event will be not be sent to the same, original key
                else:
                    logger.warning(f"key_change_callback: side bar touched, no processing")
                    logger.debug(f"key_change_callback: side bar touched, no processing msg={msg}")

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
                    kstart = self.touches[msg["id"]]["key"] if self.touches[msg["id"]]["key"] is not None else self.touches[msg["id"]]["screen"]
                    kend = msg["key"] if msg["key"] is not None else msg["screen"]
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
                    if same_key and SIDE_INDIVIDUAL_KEYS:
                        # if the press and the release occurs in the same key, we send an individual release of virtual button.
                        # if the release occurs in another button (virtual or not), we send the release in the button that
                        # was pressed, and not the button where it was released.
                        # 1. Where the pressed occured:
                        pressed = None
                        i = 0
                        while pressed is None and i < 3:
                            if event_dict["begin_y"] >= int(i*L/3) and event_dict["begin_y"] < int((i+1)*L/3):
                                pressed = f"{event_dict['begin_key'][0].upper()}{i}"
                            i = i + 1

                        released = None
                        i = 0
                        while released is None and i < 3:
                            if event_dict["end_y"] >= int(i*L/3) and event_dict["end_y"] < int((i+1)*L/3):
                                released = f"{event_dict['end_key'][0].upper()}{i}"
                            i = i + 1

                        if pressed is None:
                            logger.warning(f"key_change_callback: side bar released but no button press found, ignoring")
                        else:
                            if pressed != released:
                                logger.warning(f"key_change_callback: side bar pressed in {pressed} but released {released}, assuming release in {pressed}")
                            event_dict["small_key"] = pressed
                            event = event + [pressed]
                            logger.debug(f"key_change_callback: side bar released, SIDE_INDIVIDUAL_KEYS event {pressed} = {state}")
                            # This transfer a (virtual) button release event
                            transfer(deck, pressed, state)

                    transfer(deck, kstart, event)
            else:
                logger.error(f"key_change_callback: received touchend but no matching touchstart found")
        else:
            if action != "touchmove":
                logger.debug(f"key_change_callback: unprocessed {msg}")

    # #######################################
    # Deck Specific Functions : Representation
    #
    def get_display_for_pil(self, b: str = None):
        """
        Return device or device element to use for PIL.
        """
        if b not in ["full", "center", "left", "right"]:
            return "button"
        return b

    def create_icon_for_key(self, button, colors):
        if self.pil_helper is not None:
            display = self.get_display_for_pil(button.index)
            return self.pil_helper.create_image(deck=self.device, background=colors, display=display)
        return None

    def scale_icon_for_key(self, button, image):
        if self.pil_helper is not None:
            display = self.get_display_for_pil(button.index)
            return self.pil_helper.create_scaled_image(deck=self.device, image=image, display=display)
        return None

    def _vibrate(self, pattern: str):
        self.device.vibrate(pattern)

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
                        image = self.pil_helper.create_scaled_image(deck=self.device, image=image, display=self.get_display_for_pil(button.index))
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
            color = DEFAULT_COLOR
        idx = button.index.lower().replace(BUTTON_PREFIX, "")
        if idx == "0":
            idx = "circle"
        self.device.set_button_color(idx, color)

    def print_page(self, page: Page):
        """
        Ask each button to send its representation and create an image of the deck.
        """
        if page is None:
            page = self.current_page

        nw, nh = self.device.key_layout()
        iw, ih = (90, 90)
        sw = 60
        sh = 270

        ICON_SIZE = iw
        INTER_ICON = int(iw/10)
        w = nw * ICON_SIZE + (nw + 1) * INTER_ICON + 2 * sw
        h = nh * ICON_SIZE + (nw - 1) * INTER_ICON
        i = 0

        image = Image.new(mode="RGBA", size=(w, h))
        logger.debug(f"print_page: page {self.name}: image {image.width}x{image.height}..")
        for button in page.buttons.values():
            logger.debug(f"print_page: doing {button.name}..")
            if str(button.index).startswith(BUTTON_PREFIX):
                logger.debug(f"print_page: ..color led has no image")
                continue
            if str(button.index).startswith(KNOB_PREFIX):
                logger.debug(f"print_page: ..encoder has no image")
                continue
            if button.index in ["left", "right"]:
                x = 0 if button.index == "left" else (sw + INTER_ICON + nw * (ICON_SIZE + INTER_ICON))
                y = INTER_ICON
                b = button.get_representation()
                bs = b.resize((sw, sh))
                image.paste(bs, (x, y))
                logger.debug(f"print_page: added {button.name} at ({x}, {y})")
                continue
            i = int(button.index)
            mx = i % nw
            x = (sw + INTER_ICON) + mx * (ICON_SIZE + INTER_ICON)
            my = int(i/nw)
            y = my * (ICON_SIZE + INTER_ICON)
            b = button.get_representation()
            bs = b.resize((ICON_SIZE, ICON_SIZE))
            image.paste(bs, (x, y))
            logger.debug(f"print_page: added {button.name} (index={button.index}) at ({x}, {y})")
        logger.debug(f"print_page: page {self.name}: ..saving..")
        with open(page.name + ".png", "wb") as im:
            image.save(im, format="PNG")
        logger.debug(f"print_page: page {self.name}: ..done")

    def render(self, button: Button): # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("render: no device")
            return
        if str(button.index).startswith(KNOB_PREFIX):
            logger.debug(f"render: button type {button.index} has no representation")
            return
        representation = button._representation
        if isinstance(representation, Icon):
            self._set_key_image(button)
        elif isinstance(representation, ColoredLED):
            self._set_button_color(button)
        else:
            logger.warning(f"render: button: {button.name}: not a valid representation type {type(representation).__name__} for {type(self).__name__}")

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
        Loupedeck.terminate_device(self.device, self.name)
        self.running = False
        # logger.debug(f"terminate: closing {type(self.device).__name__}..")
        # del self.device     # closes connection and stop serial _read thread
        # self.device = None
        # logger.debug(f"terminate: closed")
        logger.info(f"terminate: deck {self.name} terminated")

    @staticmethod
    def terminate_device(device, name: str = "unspecified"):
        with device:
            device.set_callback(None)
            device.reset()
            device.stop()  # terminates the loop.
        logger.info(f"terminate_device: {name} terminated")

