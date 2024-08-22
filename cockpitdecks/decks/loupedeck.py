# Loupedeck LoupedeckLive decks
#
import os
import logging
from PIL import Image, ImageOps

from Loupedeck.Devices.LoupedeckLive import KW_LEFT, KW_RIGHT, KW_CIRCLE, HAPTIC, CALLBACK_KEYWORD, BUTTONS, KW_KNOB

from cockpitdecks import RESOURCES_FOLDER, DEFAULT_PAGE_NAME, DECK_KW, DECK_FEEDBACK
from cockpitdecks.deck import DeckWithIcons
from cockpitdecks.page import Page
from cockpitdecks.button import Button, DECK_BUTTON_DEFINITION
from cockpitdecks.event import PushEvent, EncoderEvent, SwipeEvent
from cockpitdecks.buttons.representation import Representation, IconBase, ColoredLED

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
# Warning, the logger in package Loupedeck is also called "Loupedeck".

SIDE_INDIVIDUAL_KEYS = False

VIBRATION_MODES = set(HAPTIC.keys())


class Loupedeck(DeckWithIcons):
    """
    Loads the configuration of a Loupedeck.
    """

    DECK_NAME = "loupedeck"
    DRIVER_NAME = "loupedeck"
    MIN_DRIVER_VERSION = "1.4.5"

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device=None):
        DeckWithIcons.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.cockpit.set_logging_level(__name__)

        self.touches = {}
        self.monitoring_thread = None

        self.valid = True

        self.init()
        logger.debug(f"created encoder mapping {self.get_encoder_map()}")

    # #######################################
    #
    # Deck Specific Functions : Definition
    #
    def get_encoder_map(self):
        bdef = self.deck_type.filter({DECK_KW.ACTION.value: "encoder"})
        prefix = bdef[0].get(DECK_KW.PREFIX.value)
        new_map = {}
        idx = 0
        for k in BUTTONS.values():
            if k.startswith(KW_KNOB):
                new_map[k] = f"{prefix}{idx}"
                idx = idx + 1
        return new_map

    def make_default_page(self):
        # Generates an image that is correctly sized to fit across all keys of a given
        #
        # The following two helper functions are stolen from streamdeck example scripts (tiled_image)
        # Generates an image that is correctly sized to fit across all keys of a given
        #
        # The following two helper functions are stolen from streamdeck example scripts (tiled_image)
        def create_full_deck_sized_image(image_filename):
            deck_width, deck_height = (60 + 4 * 90 + 60, 270)
            image = None
            if os.path.exists(image_filename):
                image = Image.open(image_filename).convert("RGBA")
                image = ImageOps.fit(image, (deck_width, deck_height), Image.LANCZOS)
            else:
                logger.warning(f"deck {self.name}: no wallpaper image {os.path.abspath(image_filename)} found, using default")
                image = Image.new(
                    mode="RGBA",
                    size=(deck_width, deck_height),
                    color=self.get_attribute("default-icon-color"),
                )
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

        logger.debug(f"loading default page {DEFAULT_PAGE_NAME} for {self.name}..")

        fn = os.path.join(os.path.dirname(__file__), "..", RESOURCES_FOLDER, self.wallpaper)
        image = create_full_deck_sized_image(fn)
        image_left = image.copy().crop((0, 0, 60, image.height))
        self.device.draw_left_image(image_left)
        image_center = image.copy().crop((60, 0, 420, image.height))
        self.device.draw_center_image(image_center)
        image_right = image.copy().crop((image.width - 60, 0, image.width, image.height))
        self.device.draw_right_image(image_right)

        # Add index 0 only button:
        page0 = Page(
            name=DEFAULT_PAGE_NAME,
            config={
                "name": DEFAULT_PAGE_NAME
            },
            deck=self)
        button0 = Button(
            config={
                "index": "0",
                DECK_BUTTON_DEFINITION: self.deck_type.get_button_definition("0"),
                "name": "X-Plane Map (default page)",
                "type": "push",
                "command": "sim/map/show_current",
                "text": {
                    "text": "MAP"
                }
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
    def key_change_callback(self, deck, msg):
        """
        This is the function that is called when a key is pressed.
        """
        # logger.debug(f"{msg}")
        if CALLBACK_KEYWORD.ACTION.value not in msg or CALLBACK_KEYWORD.IDENTIFIER.value not in msg:
            logger.debug(f"invalid message {msg}, no action and/or no id")
            return

        L = 270
        key = msg[CALLBACK_KEYWORD.IDENTIFIER.value]
        action = msg[CALLBACK_KEYWORD.ACTION.value]

        # Map between our convenient "e3" and Loupedeck naming knobTR
        ENCODER_MAP = self.get_encoder_map()
        if key in ENCODER_MAP.keys():
            key = ENCODER_MAP[key]

        # Map between Loupedeck indices and Cockpitdecks'
        if action == CALLBACK_KEYWORD.PUSH.value:
            num = -1
            if not self.deck_type.is_encoder(index=key):
                if key == KW_CIRCLE:
                    key = 0
                try:
                    num = int(key)
                    bdef = self.deck_type.filter({DECK_KW.FEEDBACK.value: "colored-led"})
                    prefix = bdef[0].get(DECK_KW.PREFIX.value)
                    key = f"{prefix}{key}"
                except ValueError:
                    logger.warning(f"invalid button key {key}")
            state = msg[CALLBACK_KEYWORD.STATE.value] == "down"
            logger.debug(f"Deck {deck.id()} Key {key} = {state}")
            event = PushEvent(deck=self, button=key, pressed=state)

        elif action == CALLBACK_KEYWORD.ROTATE.value:
            state = msg[CALLBACK_KEYWORD.STATE.value] != "left"
            logger.debug(f"Deck {deck.id()} Key {key} = {state}")
            event = EncoderEvent(deck=self, button=key, clockwise=state)

        # msg={'id': 24, 'action': 'touchstart', 'screen': 'left', 'key': None, 'x': 38, 'y': 199, 'ts': 1714656052.813476}
        elif action == CALLBACK_KEYWORD.TOUCH_START.value:  # we don't deal with slides now, just push on key
            state = True

            screen = msg[CALLBACK_KEYWORD.SCREEN.value]
            if screen in [KW_LEFT, KW_RIGHT]:
                logger.debug(f"Deck {deck.id()} Key {screen} = {state}")
                self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]] = msg  # we also register it as a touch event
                event = PushEvent(deck=self, button=screen, pressed=state)  # Push event

            elif CALLBACK_KEYWORD.KEY.value in msg and msg[CALLBACK_KEYWORD.KEY.value] is not None:  # we touched a key, not a side bar
                key = msg[CALLBACK_KEYWORD.KEY.value]
                try:
                    key = int(key)
                except ValueError:
                    logger.warning(f"invalid button key {key} {msg}")
                self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]] = msg
                logger.debug(f"Deck {deck.id()} Key {key} = {state}")
                event = PushEvent(deck=self, button=key, pressed=state)

            else:
                self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]] = msg
                if SIDE_INDIVIDUAL_KEYS:
                    k = None
                    i = 0
                    while k is None and i < 3:
                        if msg[CALLBACK_KEYWORD.Y.value] >= int(i * L / 3) and msg[CALLBACK_KEYWORD.Y.value] < int((i + 1) * L / 3):
                            k = f"{msg['screen'][0].upper()}{i}"
                        i = i + 1
                    logger.debug(f"side bar pressed, SIDE_INDIVIDUAL_KEYS event {k} = {state}")
                    # This transfer a (virtual) button push event
                    event = PushEvent(deck=self, button=k, pressed=state)
                    # WATCH OUT! If the release occurs in another key (virtual or not),
                    # the corresponding release event will be not be sent to the same, original key
                else:
                    logger.warning(f"side bar touched, no processing")
                    logger.debug(f"side bar touched, no processing msg={msg}")

        elif action == CALLBACK_KEYWORD.TOUCH_END.value:  # since user can "release" touch in another key, we send the touchstart one.
            state = False

            screen = msg[CALLBACK_KEYWORD.SCREEN.value]
            if screen in [KW_LEFT, KW_RIGHT]:
                logger.debug(f"Deck {deck.id()} Key {screen} = {state}")
                event = PushEvent(deck=self, button=screen, pressed=state)  # Release event

            if msg[CALLBACK_KEYWORD.IDENTIFIER.value] in self.touches:
                if (
                    CALLBACK_KEYWORD.KEY.value in self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]]
                    and self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.KEY.value] is not None
                ):
                    key = self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.KEY.value]
                    del self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]]
                    logger.debug(f"Deck {deck.id()} Key {key} = {state}")
                    event = PushEvent(deck=self, button=key, pressed=state)
                else:
                    dx = msg[CALLBACK_KEYWORD.X.value] - self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.X.value]
                    dy = msg[CALLBACK_KEYWORD.Y.value] - self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.Y.value]
                    dts = msg[CALLBACK_KEYWORD.TIMESTAMP.value] - self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.TIMESTAMP.value]
                    kstart = (
                        self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.KEY.value]
                        if self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.KEY.value] is not None
                        else self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.SCREEN.value]
                    )
                    kend = msg[CALLBACK_KEYWORD.KEY.value] if msg[CALLBACK_KEYWORD.KEY.value] is not None else msg[CALLBACK_KEYWORD.SCREEN.value]
                    same_key = kstart == kend
                    event_dict = {  # should normalise defs in Enum
                        "begin_key": kstart,
                        "begin_x": self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.X.value],
                        "begin_y": self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.Y.value],
                        "begin_ts": self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.TIMESTAMP.value],
                        "end_key": kend,
                        "end_x": msg[CALLBACK_KEYWORD.X.value],
                        "end_y": msg[CALLBACK_KEYWORD.Y.value],
                        "end_y": msg[CALLBACK_KEYWORD.TIMESTAMP.value],
                        "diff_x": dx,
                        "diff_y": dy,
                        "diff_ts": dts,
                        "same_key": same_key,
                    }
                    event = [
                        self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.X.value],
                        self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.Y.value],
                        kstart,
                    ]
                    event = event + [
                        msg[CALLBACK_KEYWORD.X.value],
                        msg[CALLBACK_KEYWORD.Y.value],
                        kend,
                    ]
                    event = event + [dx, dy, same_key]
                    if same_key and SIDE_INDIVIDUAL_KEYS:
                        # if the press and the release occurs in the same key, we send an individual release of virtual button.
                        # if the release occurs in another button (virtual or not), we send the release in the button that
                        # was pressed, and not the button where it was released.
                        # 1. Where the pressed occured:
                        pressed = None
                        i = 0
                        while pressed is None and i < 3:
                            if event_dict["begin_y"] >= int(i * L / 3) and event_dict["begin_y"] < int((i + 1) * L / 3):
                                pressed = f"{event_dict['begin_key'][0].upper()}{i}"
                            i = i + 1

                        released = None
                        i = 0
                        while released is None and i < 3:
                            if event_dict["end_y"] >= int(i * L / 3) and event_dict["end_y"] < int((i + 1) * L / 3):
                                released = f"{event_dict['end_key'][0].upper()}{i}"
                            i = i + 1

                        if pressed is None:
                            logger.warning(f"side bar released but no button press found, ignoring")
                        else:
                            if pressed != released:
                                logger.warning(f"side bar pressed in {pressed} but released {released}, assuming release in {pressed}")
                            event_dict["small_key"] = pressed
                            event = event + [pressed]
                            logger.debug(f"side bar released, SIDE_INDIVIDUAL_KEYS event {pressed} = {state}")
                            # This transfer a (virtual) button release event
                            logger.debug(f"Deck {deck.id()} Key {key} = {state}")
                            event = PushEvent(deck=self, button=key, pressed=state)

                    if same_key:
                        key = kstart
                    else:
                        key = msg[CALLBACK_KEYWORD.SCREEN.value]
                    logger.debug(f"swipe event key is {key}")

                    event = SwipeEvent(
                        deck=self,
                        button=key,
                        start_pos_x=event_dict["begin_x"],
                        start_pos_y=event_dict["begin_y"],
                        start_ts=self.touches[msg[CALLBACK_KEYWORD.IDENTIFIER.value]][CALLBACK_KEYWORD.TIMESTAMP.value],
                        end_pos_x=event_dict["end_x"],
                        end_pos_y=event_dict["end_y"],
                        end_ts=msg[CALLBACK_KEYWORD.TIMESTAMP.value],
                        autorun=True,
                    )

            else:
                logger.error(f"received touchend but no matching touchstart found")
        else:
            if action != "touchmove":
                logger.debug(f"unprocessed {msg}")

    # #######################################
    #
    # Deck Specific Functions : Representation
    #
    def _vibrate(self, pattern: str):
        self.device.vibrate(pattern)

    def set_key_icon(self, key, image):
        image = image.convert("RGB")
        self.device.set_key_image(key, image)

    def _set_key_image(self, button: Button):  # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("no device")
            return
        representation = button._representation
        if not isinstance(representation, IconBase):
            logger.warning(f"button: {button.name}: not a valid representation type {type(representation).__name__} for {type(self).__name__}")
            return
        image = button.get_representation()
        if image is not None:
            image = self.scale_icon_for_key(index=button.index, image=image)
            self.set_key_icon(button.index, image)
        else:
            logger.warning(f"no image for {button.name}")

    def _set_button_color(self, button: Button):  # idx: int, image: str, label: str = None):
        if self.device is None:
            logger.warning("no device")
            return
        color = button.get_representation()
        if color is None:
            logger.warning("button returned no representation color, using default")
            color = self.get_attribute("default-color")
        bdef = self.deck_type.filter({DECK_KW.FEEDBACK.value: "colored-led"})
        prefix = bdef[0].get(DECK_KW.PREFIX.value)
        key = button.index.lower().replace(prefix, "")
        if key == "0":
            key = KW_CIRCLE
        self.device.set_button_color(key, color)

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
        INTER_ICON = int(iw / 10)
        w = nw * ICON_SIZE + (nw + 1) * INTER_ICON + 2 * sw
        h = nh * ICON_SIZE + (nw - 1) * INTER_ICON
        i = 0

        image = Image.new(mode="RGBA", size=(w, h))
        logger.debug(f"page {self.name}: image {image.width}x{image.height}..")
        for button in page.buttons.values():
            logger.debug(f"doing {button.name}..")
            # bty = self.deck_type.get_button_definition(index=idx)
            bty = self.deck_type.get_button_definition(index=button.index)
            is_colored_led = False
            if bty is not None:
                is_colored_led = DECK_FEEDBACK.COLORED_LED.value in bty.feedbacks
            if is_colored_led:
                logger.debug(f"..color led has no image")
                continue
            if self.deck_type.is_encoder(index=button.index):
                logger.debug(f"..encoder has no image")
                continue
            if button.index in [KW_LEFT, KW_RIGHT]:
                x = 0 if button.index == KW_LEFT else (sw + INTER_ICON + nw * (ICON_SIZE + INTER_ICON))
                y = INTER_ICON
                b = button.get_representation()
                bs = b.resize((sw, sh))
                image.paste(bs, (x, y))
                logger.debug(f"added {button.name} at ({x}, {y})")
                continue
            i = int(button.index)
            mx = i % nw
            x = (sw + INTER_ICON) + mx * (ICON_SIZE + INTER_ICON)
            my = int(i / nw)
            y = my * (ICON_SIZE + INTER_ICON)
            b = button.get_representation()
            bs = b.resize((ICON_SIZE, ICON_SIZE))
            image.paste(bs, (x, y))
            logger.debug(f"added {button.name} (index={button.index}) at ({x}, {y})")
        logger.debug(f"page {self.name}: ..saving..")

        # If print-page-dir is defined add this to the path
        print_page_dir = self.get_attribute("print-page-dir")
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
        if isinstance(representation, IconBase):
            self._set_key_image(button)
        elif isinstance(representation, ColoredLED):
            self._set_button_color(button)
        elif isinstance(representation, Representation):
            logger.info(f"button: {button.name}: do nothing representation for {type(self).__name__}")
        else:
            logger.warning(f"button: {button.name}: not a valid representation type {type(representation).__name__} for {type(self).__name__}")

    # #######################################
    #
    # Deck Specific Functions : Operations
    #
    def start(self):
        if self.device is None:
            logger.warning(f"loupedeck {self.name}: no device")
            return
        self.device.set_callback(self.key_change_callback)
        self.device.start()  # restart it if it was terminated
        logger.info(f"loupedeck {self.name}: listening for key strokes")

    def terminate(self):
        super().terminate()  # cleanly unload current page, if any
        Loupedeck.terminate_device(self.device, self.name)
        self.running = False
        # logger.debug(f"closing {type(self.device).__name__}..")
        # del self.device    # closes connection and stop serial _read thread
        # self.device = None
        # logger.debug(f"closed")
        logger.info(f"deck {self.name} terminated")

    @staticmethod
    def terminate_device(device, name: str = "unspecified"):
        with device:
            device.set_callback(None)
            device.reset()
            device.stop()  # terminates the loop.
        logger.info(f"{name} terminated")
