# Cockpitdecks Virtual simple decks
#
import socket
import struct
import threading
import logging

from PIL import Image, ImageOps

from .resources.virtualdeck import VirtualDeck as VirtualDeckDevice
from .resources.ImageHelpers import PILHelper

from cockpitdecks import DEFAULT_PAGE_NAME
from cockpitdecks.deck import DeckWithIcons
from cockpitdecks.event import PushEvent
from cockpitdecks.page import Page
from cockpitdecks.button import Button
from cockpitdecks.buttons.representation import (
    Representation,
    Icon,
)  # valid representations for this type of deck

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Device specific data
SOCKET_TIMEOUT = 5  # seconds


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
        self.address = config.get("address", "127.0.0.1")
        self.port = config.get("port", 7700)
        self.my_port = config.get("my-port", 7770)

        self.rcv_event = None
        self.rcv_thread = None

        self.pil_helper = PILHelper

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
        logger.debug(f"deck {self.name}: create_icon_for_key {type(self).__name__}")

    def scale_icon_for_key(self, index, image, name: str = None):
        logger.debug(f"deck {self.name}: scale_icon_for_key {type(self).__name__}")

    # #######################################
    # Deck Specific Functions : Activation
    #
    # nothing...

    # #######################################
    # Deck Specific Functions : Representation
    #
    def _send_touchscreen_image_to_device(self, image):
        logger.debug(f"deck {self.name}: _send_touchscreen_image_to_device {type(self).__name__}")

    def _send_key_image_to_device(self, key, image):
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        width, height = image.size
        content = image.tobytes()
        payload = struct.pack(f"IIII{len(content)}s", key, width, height, len(content), content)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.address, self.port))
                s.sendall(payload)
        except:
            logger.warning(f"key: {key}: problem sending message")
        logger.debug(f"key: {key}: message sent")

    def _set_key_image(self, button: Button):  # idx: int, image: str, label: str = None):
        logger.debug(f"button: {button.name}: _set_key_image {type(self).__name__}")

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
        logger.debug(f"Deck {deck.id()} Key {key} = {state}")
        PushEvent(deck=self, button=key, pressed=state)  # autorun enqueues it in cockpit.event_queue for later execution

    def touchscreen_callback(self, deck, action, value):
        """
        This is the function that is called when the touchscreen is touched swiped.
        """
        pass

    def handle_event(self, data):
        # need to try/except unpack for wrong data
        key, event = struct.unpack("II", data)
        e = PushEvent(deck=self, button=key, pressed=event == "pressed")

    def receive_events(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", self.my_port))
            s.listen()
            s.settimeout(SOCKET_TIMEOUT)
            while self.rcv_event is not None and not self.rcv_event.is_set():
                buff = bytes()
                try:
                    conn, addr = s.accept()
                    with conn:
                        while True:
                            data = conn.recv(BUFFER_SIZE)
                            if not data:
                                break
                            buff = buff + data
                        self.handle_event(buff)
                except TimeoutError:
                    pass
                    # logger.debug(f"receive event", exc_info=True)
                except:
                    logger.warning(f"receive events: abnormal exception", exc_info=True)

    def start(self):
        if self.rcv_event is None:  # Thread for X-Plane datarefs
            self.rcv_event = threading.Event()
            self.rcv_thread = threading.Thread(target=self.receive_events, name="VirtualDeck::event_listener")
            self.rcv_thread.start()
            logger.info("virtual deck event listener started")
        else:
            logger.info("virtual deck event listener already running")

    def stop(self):
        if self.rcv_event is not None:
            self.rcv_event.set()
            logger.debug("stopping virtual deck event listener..")
            wait = SOCKET_TIMEOUT
            logger.debug(f"..asked to stop virtual deck event listener (this may last {wait} secs. for accept to timeout)..")
            self.rcv_thread.join(wait)
            if self.rcv_thread.is_alive():
                logger.warning("..thread may hang in socket.accept()..")
            self.rcv_event = None
            logger.debug("..virtual deck event listener stopped")
        else:
            logger.debug("virtual deck event listener not running")

    def terminate(self):
        self.stop()
        super().terminate()  # cleanly unload current page, if any

    @staticmethod
    def terminate_device(device, name: str = "unspecified"):
        pass
        logger.info(f"{name} terminated")
