# Cockpitdecks Virtual Deck driver.
#
# Sends update to VirtualDeckUI through TCP/IP socket
# Receives interactions from VirtualDeckUI
#
import socket
import logging
import io
import base64
from datetime import datetime

from PIL import Image, ImageDraw

from cockpitdecks import DEFAULT_PAGE_NAME
from cockpitdecks.deck import DeckWithIcons
from cockpitdecks.event import Event, PushEvent, EncoderEvent, TouchEvent, SwipeEvent, SlideEvent
from cockpitdecks.page import Page
from cockpitdecks.button import Button
from cockpitdecks.buttons.representation import (
    Representation,
    Icon,
)  # valid representations for this type of deck

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
WEB_LOG = False


class VirtualDeck(DeckWithIcons):
    """
    Loads the configuration of a virtual deck
    """

    DECK_NAME = "virtualdeck"
    DRIVER_NAME = "virtualdeck"
    MIN_DRIVER_VERSION = "0.0.0"

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device=None):
        DeckWithIcons.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.cockpit.set_logging_level(__name__)

        self.valid = True
        self.clients = 0

        self.init()

    def add_client(self):
        self.clients = self.clients + 1

    def remove_client(self):
        if self.clients > 0:
            self.clients = self.clients - 1

    def has_clients(self) -> bool:
        return True
        # return self.clients > 0

    # #######################################
    #
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

    # #######################################
    #
    # Deck Specific Functions : Activation
    #
    def key_change_callback(self, deck, key, state, data: dict | None = None) -> Event | None:
        """
        This is the function that is called when a key is pressed.
        For virtual decks, this function is quite complex
        since it has to take the "shape" of any "real physical deck" it virtualize
        """
        # logger.debug(f"Deck {self.name} Key {key} = {state}")
        # print("===== handle_event", deck.name, key, state, data)
        if state in [0, 1, 4]:
            PushEvent(deck=self, button=key, pressed=state)  # autorun enqueues it in cockpit.event_queue for later execution
            logger.debug(f"PushEvent deck {self.name} key {key} = {state}")
            return  # no other possible handling
        if state in [2, 3]:
            EncoderEvent(deck=self, button=key, clockwise=state == 2)
            return  # no other possible handling
        if state in [9]:
            if data is not None and "value" in data:
                SlideEvent(deck=self, button=key, value=int(data.get("value")))
                return  # no other possible handling
            else:
                logger.warning(f"deck {deck.name}: SliderEvent has no value ({data})")
        logger.warning(f"deck {deck.name}: unhandled event ({deck}, {key}, {state}, {data})")
        return None


    # #######################################
    #
    # Deck Specific Functions : Representation
    #
    def send_code(self, code):
        # Send interaction event to Cockpitdecks virtual deck driver
        # Virtual deck driver transform into Event and enqueue for Cockpitdecks processing
        # Payload is key, pressed(0 or 1), and deck name (bytes of UTF-8 string)
        payload = {"code": code, "deck": self.name, "meta": {"ts": datetime.now().timestamp()}}
        self.cockpit.send(deck=self.name, payload=payload)

    def set_key_icon(self, key, image):
        # Sends the PIL Image bytes with a few meta to Flask for web display
        # Image is sent as a stream of bytes which is the file content of the image saved in PNG format
        # Need to supply deck name as well.
        def add_corners(im, rad):
            circle = Image.new("L", (rad * 2, rad * 2), 0)
            draw = ImageDraw.Draw(circle)
            draw.ellipse((0, 0, rad * 2 - 1, rad * 2 - 1), fill=255)
            alpha = Image.new("L", im.size, 255)
            w, h = im.size
            alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
            alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
            alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
            alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
            im.putalpha(alpha)
            return im

        if not self.has_clients():
            logger.debug(f"deck {self.name} has no client")
            return

        buttondef = self.deck_type.get_button_definition(key)
        rc = buttondef.get_option("corner_radius")
        # rc = int(image.width / 8)
        if rc is not None:
            image = add_corners(image, int(rc))
        width, height = image.size
        img_byte_arr = io.BytesIO()
        # transformed = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)  # ?!
        image.save(img_byte_arr, format="PNG")
        content = img_byte_arr.getvalue()
        meta = {"ts": datetime.now().timestamp()}  # dummy
        payload = {"code": 0, "deck": self.name, "key": key, "image": base64.encodebytes(content).decode("ascii"), "meta": meta}
        self.cockpit.send(deck=self.name, payload=payload)

    def _send_hardware_key_image_to_device(self, key, image, metadata):
        def add_corners(im, rad):
            circle = Image.new("L", (rad * 2, rad * 2), 0)
            draw = ImageDraw.Draw(circle)
            draw.ellipse((0, 0, rad * 2 - 1, rad * 2 - 1), fill=255)
            alpha = Image.new("L", im.size, 255)
            w, h = im.size
            alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
            alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
            alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
            alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
            im.putalpha(alpha)
            return im

        if not self.has_clients():
            logger.debug(f"deck {self.name} has no client")
            return

        buttondef = self.deck_type.get_button_definition(key)
        rc = buttondef.get_option("corner_radius")
        # rc = int(image.width / 8)
        if rc is not None:
            image = add_corners(image, int(rc))
        width, height = image.size
        img_byte_arr = io.BytesIO()
        # transformed = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)  # ?!
        image.save(img_byte_arr, format="PNG")
        content = img_byte_arr.getvalue()
        meta = {"ts": datetime.now().timestamp()}  # dummy
        payload = {"code": 0, "deck": self.name, "key": key, "image": base64.encodebytes(content).decode("ascii"), "meta": meta}
        self.cockpit.send(deck=self.name, payload=payload)

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
            default_icon_name = self.get_attribute("default-icon-name")
            image = self.cockpit.get_icon_image(default_icon_name)

        if image is None:
            logger.warning(f"no image for default icon {default_icon_name}")
            return

        if image.size != self.get_image_size(button.index):
            image.thumbnail(self.get_image_size(button.index))

        self.set_key_icon(button.index, image)

    def _set_hardware_image(self, button: Button):  # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("no device")
            return

        representation = button._hardware_representation
        image = button.get_hardware_representation()
        if image is None:
            logger.warning("button returned no hardware image")
            return

        metadata = button.get_hardware_representation_metadata()

        self._send_hardware_key_image_to_device(button.index, image, metadata)

    def print_page(self, page: Page):
        """
        Ask each button to send its representation and create an image of the deck.
        """
        pass

    def render(self, button: Button):  # idx: int, image: str, label: str = None):
        # Regular representation
        representation = button._representation
        if isinstance(representation, Icon):
            self._set_key_image(button)
        elif isinstance(representation, Representation):
            logger.debug(f"button: {button.name}: do nothing representation for {type(self).__name__}")
        else:
            logger.warning(f"button: {button.name}: not a valid representation type {type(representation).__name__} for {type(self).__name__}")
        # "Hardware" representation
        if button._hardware_representation is not None:
            self._set_hardware_image(button)

    # #######################################
    #
    # Deck Specific Functions : Operations
    #
    def start(self):
        pass

    def stop(self):
        pass

    @staticmethod
    def terminate_device(device, name: str = "unspecified"):
        logger.info(f"{name} terminated")
