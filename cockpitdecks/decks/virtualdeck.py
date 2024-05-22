# Cockpitdecks Virtual Deck driver.
#
# Sends update to VirtualDeckUI through TCP/IP socket
# Receives interactions from VirtualDeckUI
#
import socket
import struct
import threading
import logging

from PIL import Image, ImageOps

from cockpitdecks import DEFAULT_PAGE_NAME, COCKPITDECKS_HOST
from cockpitdecks.deck import DeckWithIcons
from cockpitdecks.event import PushEvent
from cockpitdecks.page import Page
from cockpitdecks.button import Button
from cockpitdecks.buttons.representation import (
    Representation,
    Icon,
)  # valid representations for this type of deck

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class VirtualDeck(DeckWithIcons):
    """
    Loads the configuration of a virtual deck
    """

    DECK_NAME = "virtualdeck"
    DRIVER_NAME = "virtualdeck"
    MIN_DRIVER_VERSION = "0.1.0"

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device=None):
        DeckWithIcons.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.cockpit.set_logging_level(__name__)

        # Address and port of virtual deck
        self.address = config.get("address")
        self.port = config.get("port")

        # Address and port of virtual deck
        self.web_address = "127.0.0.1"
        self.web_port = "7699"

        self.pil_helper = self

        self.valid = True

        self.init()

    # #######################################
    # Deck Specific PILHelper (provided by self! What a Duck Typing!)
    # These three functions are usually provided by PILHelper.
    # For virtualdecks, they are included in here, inside the class.
    #
    def get_dimensions(self, display: str):
        # works for now for all virtual decks, to be resized more formally later (display == button name)
        b = list(self.deck_type._buttons.values())
        return b[0].image

    def create_image(self, deck, background="black", display="button"):
        return Image.new("RGB", self.get_dimensions(display=display), background)

    def create_scaled_image(self, deck, image, margins=[0, 0, 0, 0], background="black", display="button"):
        if len(margins) != 4:
            raise ValueError("Margins should be given as an array of four integers.")

        final_image = self.create_image(deck, background=background, display=display)

        thumbnail_max_width = final_image.width - (margins[1] + margins[3])
        thumbnail_max_height = final_image.height - (margins[0] + margins[2])

        thumbnail = image.convert("RGBA")
        thumbnail.thumbnail((thumbnail_max_width, thumbnail_max_height), Image.LANCZOS)

        thumbnail_x = margins[3] + (thumbnail_max_width - thumbnail.width) // 2
        thumbnail_y = margins[0] + (thumbnail_max_height - thumbnail.height) // 2

        final_image.paste(thumbnail, (thumbnail_x, thumbnail_y), thumbnail)
        return final_image

    def to_native_key_format(self, image):
        # Final resize of image
        if image.size != self.get_dimensions(display="button"):
            image.thumbnail(self.get_dimensions(display="button"))
        return image

    # #######################################
    # Deck Specific Functions : Definition
    #
    def make_default_page(self):
        # Generates an image that is correctly sized to fit across all keys of a given
        #
        # The following two helper functions are stolen from streamdeck example scripts (tiled_image)
        page0 = Page(name=DEFAULT_PAGE_NAME, config={"name": DEFAULT_PAGE_NAME}, deck=self)
        button0 = Button(
            config={
                "index": "0",
                "name": "X-Plane Map (default page)",
                "type": "push",
                "command": "sim/map/show_current",
                "text": "MAP",
            },
            page=page0,
        )
        page0.add_button(button0.index, button0)
        self.pages = {DEFAULT_PAGE_NAME: page0}
        self.home_page = page0
        self.current_page = page0
        logger.debug(f"..loaded default page {DEFAULT_PAGE_NAME} for {self.name}, set as home page")

    def create_icon_for_key(self, index, colors, texture, name: str = None):
        if name is not None and name in self.icons.keys():
            return self.icons.get(name)

        image = None
        bg = self.create_image(deck=self.device, background=colors)
        image = self.get_icon_background(
            name=str(index),
            width=bg.width,
            height=bg.height,
            texture_in=texture,
            color_in=colors,
            use_texture=True,
            who="VirtualDeck",
        )
        if image is not None:
            image = image.convert("RGB")
            if name is not None:
                self.icons[name] = image
        return image

    def scale_icon_for_key(self, index, image, name: str = None):
        if name is not None and name in self.icons.keys():
            return self.icons.get(name)

        image = self.create_scaled_image(self.device, image, margins=[0, 0, 0, 0])
        if image is not None:
            image = image.convert("RGB")
            if name is not None:
                self.icons[name] = image
        return image

    # #######################################
    # Deck Specific Functions : Activation
    #
    # nothing...

    # #######################################
    # Deck Specific Functions : Representation
    #
    def send_code(self, code):
        # Send interaction event to Cockpitdecks virtual deck driver
        # Virtual deck driver transform into Event and enqueue for Cockpitdecks processing
        # Payload is key, pressed(0 or 1), and deck name (bytes of UTF-8 string)
        content = bytes(self.name, "utf-8")
        payload = struct.pack(f"IIIII{len(content)}s", int(code), 0, 0, 0, len(content), content)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.address, self.port))
                s.sendall(payload)
        except:
            logger.warning(f"{self.name}: problem sending code", exc_info=True)

    def _send_key_image_to_device(self, key, image):
        # Sends the PIL Image bytes with a few meta
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        width, height = image.size
        content = image.tobytes()
        code = 0
        payload = struct.pack(f"IIIII{len(content)}s", int(code), int(key), width, height, len(content), content)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.address, self.port))
                s.sendall(payload)
        except:
            logger.warning(f"key: {key}: problem sending image to virtual deck")
        logger.debug(f"key: {key}: image sent to ({self.address}, {self.port})")
        self._send_key_image_to_web(key, image)

    def _send_key_image_to_web(self, key, image):
        # Sends the PIL Image bytes with a few meta to Flask for web display
        # Need to supply deck name as well.
        width, height = image.size
        content = image.tobytes()
        code = 0
        content2 = bytes(self.name, "utf-8")
        payload = struct.pack(f"IIIIII{len(content2)}s{len(content)}s", int(code), int(key), width, height, len(content2), len(content), content2, content)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.web_address, self.web_port))
                s.sendall(payload)
        except:
            logger.warning(f"key: {key}: problem sending image to web")
        logger.debug(f"key: {key}: image sent to ({self.web_address}, {self.web_port})")

    def _set_key_image(self, button: Button):  # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("no device")
            return
        representation = button._representation
        if not isinstance(representation, Icon):
            logger.warning(f"button: {button.name}: not a valid representation type {type(representation).__name__} for {type(self).__name__}")
            return

        image = button.get_representation()
        if image is None:
            logger.warning("button returned no image, using default")
            image = self.icons[self.get_attribute("default-icon-name")]

        image = self.to_native_key_format(image)

        self._send_key_image_to_device(button.index, image)

    def print_page(self, page: Page):
        """
        Ask each button to send its representation and create an image of the deck.
        """
        pass

    def render(self, button: Button):  # idx: int, image: str, label: str = None):
        representation = button._representation
        if isinstance(representation, Icon):
            self._set_key_image(button)
        elif isinstance(representation, Representation):
            logger.info(f"button: {button.name}: do nothing representation for {type(self).__name__}")
        else:
            logger.warning(f"button: {button.name}: not a valid representation type {type(representation).__name__} for {type(self).__name__}")

    # #######################################
    # Deck Specific Functions : Device
    #
    def get_display_for_pil(self, b: str = None):
        """
        Return device or device element to use for PIL.
        """
        return self.device

    def key_change_callback(self, deck, key, state):
        """
        This is the function that is called when a key is pressed.
        """
        # logger.debug(f"Deck {self.name} Key {key} = {state}")
        PushEvent(deck=self, button=key, pressed=state)  # autorun enqueues it in cockpit.event_queue for later execution
        logger.debug(f"PushEvent deck {self.name} key {key} = {state}")

    def start(self):
        pass

    def stop(self):
        pass

    @staticmethod
    def terminate_device(device, name: str = "unspecified"):
        logger.info(f"{name} terminated")
