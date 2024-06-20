# Elgato Streamdeck decks
#
import datetime
import os
import logging
from datetime import datetime
from PIL import Image, ImageOps

from StreamDeck.ImageHelpers.PILHelper import to_native_format, to_native_key_format, to_native_touchscreen_format
from StreamDeck.Devices.StreamDeck import DialEventType, TouchscreenEventType

from cockpitdecks import DECK_FEEDBACK, RESOURCES_FOLDER, DEFAULT_PAGE_NAME, DECK_KW, DECK_ACTIONS
from cockpitdecks.deck import DeckWithIcons
from cockpitdecks.event import PushEvent, EncoderEvent, TouchEvent, SwipeEvent
from cockpitdecks.page import Page
from cockpitdecks.button import Button
from cockpitdecks.buttons.representation import (
    Representation,
    Icon,
)  # valid representations for this type of deck

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

# Device specific data
POLL_FREQ = 5  # default is 20
FLIP_DESCRIPTION = {
    (False, False): "not mirrored",
    (True, False): "mirrored horizontally",
    (False, True): "mirrored vertically",
    (True, True): "mirrored horizontally/vertically",
}

KW_TOUCHSCREEN = "touchscreen"  # must match resources.decks.streamdeck*plus*.buttons[].name


class Streamdeck(DeckWithIcons):
    """
    Loads the configuration of a Stream Deck.
    """

    DECK_NAME = "streamdeck"
    DRIVER_NAME = "streamdeck"
    MIN_DRIVER_VERSION = "0.9.5"

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device=None):
        DeckWithIcons.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.cockpit.set_logging_level(__name__)

        self.monitoring_thread = None
        self.valid = True

        if self.device is not None:
            self.device.set_poll_frequency(POLL_FREQ)

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
        def create_full_deck_sized_image(deck, key_spacing, image_filename):
            key_rows, key_cols = deck.key_layout()
            key_width, key_height = deck.key_image_format()["size"]
            spacing_x, spacing_y = key_spacing

            # Compute total size of the full StreamDeck image, based on the number of
            # buttons along each axis. This doesn't take into account the spaces between
            # the buttons that are hidden by the bezel.
            key_width *= key_cols
            key_height *= key_rows

            # Compute the total number of extra non-visible pixels that are obscured by
            # the bezel of the StreamDeck.
            spacing_x *= key_cols - 1
            spacing_y *= key_rows - 1

            # Compute final full deck image size, based on the number of buttons and
            # obscured pixels.
            full_deck_image_size = (key_width + spacing_x, key_height + spacing_y)

            # Resize the image to suit the StreamDeck's full image size. We use the
            # helper function in Pillow's ImageOps module so that the image's aspect
            # ratio is preserved.
            image = None
            deck_width, deck_height = full_deck_image_size
            if os.path.exists(image_filename):
                image = Image.open(image_filename).convert("RGBA")
                image = ImageOps.fit(image, full_deck_image_size, Image.LANCZOS)
            else:
                logger.warning(f"deck {self.name}: no wallpaper image {image_filename} found, using default")
                dic = self.get_attribute("default-icon-color")
                image = Image.new(mode="RGBA", size=(deck_width, deck_height), color=dic)
                fn = os.path.join(os.path.dirname(__file__), "..", RESOURCES_FOLDER, self.logo)
                if os.path.exists(fn):
                    inside = 20
                    logo = Image.open(fn).convert("RGBA")
                    logo2 = ImageOps.fit(
                        logo,
                        (deck_width - 2 * inside, deck_height - 2 * inside),
                        Image.LANCZOS,
                    )
                    image.paste(logo2, (inside, inside), logo2)
                else:
                    logger.warning(f"deck {self.name}: no logo image {fn} found, using default")
            return image

        # Crops out a key-sized image from a larger deck-sized image, at the location
        # occupied by the given key index.
        def crop_key_image_from_deck_sized_image(deck, image, key_spacing, key):
            key_rows, key_cols = deck.key_layout()
            key_width, key_height = deck.key_image_format()["size"]
            spacing_x, spacing_y = key_spacing

            # Determine which row and column the requested key is located on.
            row = key // key_cols
            col = key % key_cols

            # Compute the starting X and Y offsets into the full size image that the
            # requested key should display.
            start_x = col * (key_width + spacing_x)
            start_y = row * (key_height + spacing_y)

            # Compute the region of the larger deck image that is occupied by the given
            # key, and crop out that segment of the full image.
            region = (start_x, start_y, start_x + key_width, start_y + key_height)
            segment = image.crop(region)

            # Create a new key-sized image, and paste in the cropped section of the
            # larger image.
            key_image = self.create_empty_image_for_key(key)
            key_image.paste(segment)

            return to_native_format(deck, key_image)

        logger.debug(f"loading default page {DEFAULT_PAGE_NAME} for {self.name}..")
        fn = os.path.join(os.path.dirname(__file__), "..", RESOURCES_FOLDER, self.wallpaper)
        key_spacing = (36, 36)
        image = create_full_deck_sized_image(deck=self.device, key_spacing=key_spacing, image_filename=fn)
        key_images = dict()
        for k in range(self.device.key_count()):
            key_images[k] = crop_key_image_from_deck_sized_image(deck=self.device, image=image, key_spacing=key_spacing, key=k)

        with self.device:
            # Draw the individual key images to each of the keys.
            for k in range(self.device.key_count()):
                key_image = key_images[k]
                # Show the section of the main image onto the key.
                self.device.set_key_image(k, key_image)

        # Add index 0 only button:
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
    # Deck Specific Functions : Activation
    #
    # nothing...

    # #######################################
    # Deck Specific Functions : Representation
    #
    def _send_touchscreen_image_to_device(self, image):
        with self.device:
            i = to_native_touchscreen_format(deck=self.device, image=image)
            self.device.set_touchscreen_image(i, width=image.width, height=image.height)

    def _send_key_image_to_device(self, key, image):
        if key in self.get_deck_type().special_displays():
            self._send_touchscreen_image_to_device(image=image)
            return
        with self.device:
            i = to_native_key_format(deck=self.device, image=image)
            self.device.set_key_image(int(key), i)

    def _set_key_image(self, button: Button):  # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("no device")
            return
        representation = button._representation
        if not isinstance(representation, Icon):
            logger.warning(f"button: {button.name}: not a valid representation type {type(representation).__name__} for {type(self).__name__}")
            return

        image = button.get_representation()
        if button.index not in self.get_deck_type().special_displays():
            if image is None:
                logger.warning("button returned no image, using default")
                image = self.icons[self.get_attribute("default-icon-name")]
            self._send_key_image_to_device(button.index, image)
        else:
            if image is None:
                logger.warning("button returned no image, no default for touch screen, ignoring")
                return
            if button.index == KW_TOUCHSCREEN:
                self._send_touchscreen_image_to_device(image)

    def print_page(self, page: Page):
        """
        Ask each button to send its representation and create an image of the deck.
        """
        if page is None:
            page = self.current_page

        nh, nw = self.device.key_layout()
        iw, ih = self.device.key_image_format()["size"]

        icon_size = iw
        INTER_ICON = int(iw / 10)
        w = nw * icon_size + (nw - 1) * INTER_ICON
        h = nh * icon_size + (nw - 1) * INTER_ICON
        i = 0

        image = Image.new(mode="RGBA", size=(w, h))
        logger.debug(f"page {self.name}: image {image.width}x{image.height}..")
        for button in page.buttons.values():
            i = int(button.index)
            mx = i % nw
            x = mx * icon_size + mx * INTER_ICON
            my = int(i / nw)
            y = my * icon_size + my * INTER_ICON
            b = button.get_representation()
            bs = b.resize((icon_size, icon_size))
            image.paste(bs, (x, y))
            logger.debug(f"added {button.name} at ({x}, {y})")
        logger.debug(f"page {self.name}: ..saving..")

        # If print-page-dir is defined add this to the path
        print_page_dir = self.get_attribute("print-page-dir", silence=True)
        if print_page_dir is None:
            output_dst = page.name + ".png"
        else:
            output_dst = print_page_dir + "/" + page.deck.layout + "." + page.name + ".png"

        with open(output_dst, "wb") as im:
            image.save(im, format="PNG")
        logger.debug(f"page {self.name}: ..done")

    def render(self, button: Button):  # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("no device")
            return
        if self.deck_type.is_encoder(index=button.index):
            logger.debug(f"button type {button.index} has no representation")
            return
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
        print(f"KEY: {type(self).__name__}: {deck.id()}: {key}={state}")
        logger.debug(f"Deck {deck.id()} Key {key} = {state}")
        PushEvent(deck=self, button=key, pressed=state)  # autorun enqueues it in cockpit.event_queue for later execution

    def dial_callback(self, deck, key, action, value):
        """
        This is the function that is called when a dial is rotated.
        """
        print(f"DIAL: {type(self).__name__}: {deck.id()}: {key} {action} {value}")
        logger.debug(f"Deck {deck.id()} Key {key} = {action}, {value}")
        bdef = self.deck_type.filter({DECK_KW.ACTION.value: DECK_ACTIONS.ENCODER.value})
        prefix = bdef[0].get(DECK_KW.PREFIX.value)
        idx = f"{prefix}{key}"
        if action == DialEventType.PUSH:
            event = PushEvent(deck=self, button=idx, pressed=value)
        elif action == DialEventType.TURN:
            direction = 2 if value < 0 else 3
            for i in range(abs(value)):
                event = EncoderEvent(deck=self, button=idx, clockwise=direction == 2)
        else:
            logger.warning(f"deck {self.name}: invalid dial action {action}")

    def touchscreen_callback(self, deck, action, value):
        """
        This is the function that is called when the touchscreen is touched swiped.
        """
        print(f"TOUCHSCREEN: {type(self).__name__}: {deck.id()}: {key} {action} {value}")
        logger.debug(f"Deck {deck.id()} Action {action} = {value}")
        NUMVIRTUALKEYS = 4  # number of "virtual" keys across touchscreen
        KEY_SIZE = 800 / NUMVIRTUALKEYS

        idx = KW_TOUCHSCREEN
        logger.debug(f"Deck {deck.id()} Key {idx} = {action}, {value}")
        if action == TouchscreenEventType.SHORT:
            event = TouchEvent(deck=self, button=idx, pos_x=int(value["x"]), pos_y=int(value["y"]), start=datetime.now().timestamp())
        elif action == TouchscreenEventType.LONG:
            event = TouchEvent(deck=self, button=idx, pos_x=int(value["x"]), pos_y=int(value["y"]), start=datetime.now().timestamp())
        elif action == TouchscreenEventType.DRAG:
            event = SwipeEvent(
                deck=self,
                button=idx,
                start_pos_x=int(value["x"]),
                start_pos_y=int(value["y"]),
                start_ts=datetime.now().timestamp(),
                end_pos_x=int(value["x_out"]),
                end_pos_y=int(value["y_out"]),
                end_ts=datetime.now().timestamp(),
                autorun=True,
            )
        else:
            logger.warning(f"deck {self.name}: invalid touchscreen action {action}")

    def start(self):
        if self.device is None:
            logger.warning(f"deck {self.name}: no device")
            return
        self.device.set_poll_frequency(hz=POLL_FREQ)  # default is 20
        self.device.set_key_callback(self.key_change_callback)
        if hasattr(self.device, "dial_callback"):
            self.device.set_dial_callback(self.dial_callback)
        if hasattr(self.device, "touchscreen_callback"):
            self.device.set_touchscreen_callback(self.touchscreen_callback)

        logger.info(f"deck {self.name}: device started")

    def terminate(self):
        super().terminate()  # cleanly unload current page, if any
        Streamdeck.terminate_device(self.device, self.name)
        self.running = False
        logger.info(f"deck {self.name} terminated")

    @staticmethod
    def terminate_device(device, name: str = "unspecified"):
        with device:
            if device.is_open():
                device.reset()  # causes an issue when device was not set up
            device.set_key_callback(None)
            device._setup_reader(None)  # terminates the _read() loop on serial line (thread).
            # device.stop()  # terminates the loop.
        logger.info(f"{name} terminated")
