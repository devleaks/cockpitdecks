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
from cockpitdecks.resources.intvariables import COCKPITDECKS_INTVAR
from cockpitdecks.deck import DeckWithIcons
from cockpitdecks.decks.resources.virtualdeckmanager import VirtualDeckManager

from cockpitdecks.event import Event, PushEvent, EncoderEvent, TouchEvent, SlideEvent
from cockpitdecks.page import Page
from cockpitdecks.button import Button
from cockpitdecks.buttons.representation import (
    Representation,
    IconBase,
)  # valid representations for this type of deck


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

WEB_LOG = False
NOT_CONNECTED_WARNING = False


class VirtualDeck(DeckWithIcons):
    """
    Loads the configuration of a virtual deck
    """

    DECK_NAME = "virtualdeck"
    DRIVER_NAME = "virtualdeck"
    MIN_DRIVER_VERSION = "0.0.0"
    DEVICE_MANAGER = VirtualDeckManager

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device=None):
        DeckWithIcons.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.cockpit.set_logging_level(__name__)

        self.valid = True
        self.clients = 0

        self._touch_event_start = None

        self.init()

    def set_clients(self, clients):
        self.clients = clients
        if self.is_connected():
            self.reload_page()

    def add_client(self):
        self.clients = self.clients + 1

    def remove_client(self):
        if self.clients > 0:
            self.clients = self.clients - 1
        if not self.has_clients() and not self.is_connected():
            logger.debug("no more client, disconnecting..")
            self.disconnect()
            logger.debug("..disconnected")

    def has_clients(self) -> bool:
        return self.clients > 0

    def is_connected(self) -> bool:
        return self.cockpit.probe(self.name)

    def unload_current_page(self):
        if self.current_page is not None:
            logger.debug(f"deck {self.name} unloading page {self.current_page.name}..")
            logger.debug("..unloading simulator data..")
            self.cockpit.sim.remove_simulator_variables_to_monitor(
                simulator_variables=self.current_page.simulator_variable, reason=f"client disconnected from {self.name}"
            )
            logger.debug("..cleaning page..")
            self.current_page.clean()
        else:
            logger.debug("no current page to unload")
        logger.debug(f"..reset device {self.name}..")
        self.device.reset()
        logger.debug("..done")

    def disconnect(self):
        self.unload_current_page()

    def change_page(self, page: str | None = None) -> str | None:
        if self.has_clients():
            return super().change_page(page=page)
        logger.info(f"web deck {self.name} has no client")
        return None

    def reload_page(self):
        """Reloads page to take into account changes in definition

        Please note that this may loead to unexpected results if page was
        too heavily modified or interaction with other pages occurred.
        """
        if self.is_connected():
            self.inc(COCKPITDECKS_INTVAR.DECK_RELOADS.value)
            page = "index"
            if self.home_page is None:
                logger.debug(f"deck {self.name} has no home page, assuming index")
            else:
                page = self.home_page.name
            page = self.current_page.name if self.current_page is not None else page
            self.change_page(page)
        else:
            logger.debug(f"deck {self.name} is not connected")

    # #######################################
    #
    # Deck Specific Functions : Definition
    #
    def make_default_page(self):
        # Generates an image that is correctly sized to fit across all keys of a given
        #
        # The following two helper functions are stolen from streamdeck example scripts (tiled_image)
        page0 = Page(name=DEFAULT_PAGE_NAME, config={"name": DEFAULT_PAGE_NAME}, deck=self)
        indices = self.deck_type.valid_indices()
        if len(indices) > 0:
            first_index = indices[0]
            logger.debug(f"..first button is {first_index}..")
            button0 = Button(
                config={
                    "index": first_index,
                    "name": "Reload",
                    # "name": "X-Plane Map (default page)",
                    # "type": "push",
                    # "command": "sim/map/show_current",
                    # "text": "MAP",
                    "type": "reload",
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
    def key_change_callback(self, key, state: int, data: dict | None = None) -> Event | None:
        """
        This is the function that is called when a key is pressed.
        For virtual decks, this function is quite complex
        since it has to take the "shape" of any "real physical deck" it virtualize
        Event codes:
         0 = Push/press RELEASE
         1 = Push/press PRESS
         2 = Turned clockwise
         3 = Turned counter-clockwise
         4 = Pulled
         9 = Slider, event data contains value
        10 = Touch start, event data contains value
        11 = Touch end, event data contains value
        12 = Swipe, event data contains value
        14 = Tap, event data contains value

        """
        # logger.debug(f"Deck {self.name} Key {key} = {state}")
        # print("===== handle_event", self.name, key, state, data)
        if state in [0, 1, 4]:
            PushEvent(
                deck=self, button=key, pressed=(state != 0), pulled=(state == 4), code=state
            )  # autorun enqueues it in cockpit.event_queue for later execution
            logger.debug(f"PushEvent deck {self.name} key {key} = {state}")
            return  # no other possible handling
        if state in [2, 3]:
            logger.debug(f"EncoderEvent deck {self.name} key {key} = {state}")
            EncoderEvent(deck=self, button=key, clockwise=state == 2, code=state)
            return  # no other possible handling
        if state in [10, 11]:
            if data is None:
                logger.warning(f"TouchEvent deck {self.name} key {key} = {state}: no data")
                return
            logger.debug(f"TouchEvent deck {self.name} key {key} = {state}, {self._touch_event_start}, {data}")
            if state == 10:  # start
                self._touch_event_start = TouchEvent(deck=self, button=key, pos_x=data.get("x"), pos_y=data.get("y"), cli_ts=data.get("ts"), code=state)
                print("start set", self._touch_event_start)
            else:
                TouchEvent(deck=self, button=key, pos_x=data.get("x"), pos_y=data.get("y"), cli_ts=data.get("ts"), start=self._touch_event_start, code=state)
                print("start used", self._touch_event_start, "reset")
                self._touch_event_start = None
            return  # no other possible handling
        if state in [14]:
            TouchEvent(deck=self, button=key, pos_x=data.get("x"), pos_y=data.get("y"), cli_ts=data.get("ts"), code=state)
            logger.debug(f"TouchEvent deck {self.name} key {key} = {state} (press event)")
            return  # no other possible handling
        if state in [9]:
            logger.debug(f"SlideEvent deck {self.name} key {key} = {state}")
            if data is not None and "value" in data:
                SlideEvent(deck=self, button=key, value=int(data.get("value")), code=state)
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

    def play_sound(self, sound):
        content = self.cockpit.sounds.get(sound)
        if content is None:
            logger.warning(f"{self.name}: sound {sound} not found")
            return
        meta = {"ts": datetime.now().timestamp()}  # dummy
        typ = sound.split(".")[-1]
        payload = {"code": 2, "deck": self.name, "sound": base64.encodebytes(content).decode("ascii"), "type": typ, "meta": meta}
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

        # if not self.has_clients():
        #     logger.debug(f"deck {self.name} has no client")
        #     return

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

    def fill_empty_hardware_representation(self, key, page):
        config = self.deck_type.get_empty_button_config(key)
        if config is not None:
            btn = Button(config=config, page=page)
            self._set_hardware_image(btn)
            logger.debug(f"{self.name}: done for {key}")
        else:
            logger.warning(f"{self.name}: no empty hardware representation for {key}")

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
        if not isinstance(representation, IconBase):
            logger.warning(f"button: {button.name}: not a valid representation type {type(representation).__name__} for {type(self).__name__}")
            return

        image = button.get_representation()

        if image is None:
            logger.warning("button returned no image, using default")
            image = self.get_default_icon()

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
        if not self.is_connected():
            # If deck is not connected, we do not render. the button
            if NOT_CONNECTED_WARNING:
                logger.warning(f"button: {button.name}: virtual deck {self.name} not connected")
            return
        representation = button._representation
        if isinstance(representation, IconBase):
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
