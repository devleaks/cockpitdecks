# ###########################
# Annunciator Rendering
#
import logging
import threading
from typing import Dict, List
from enum import Enum
from PIL import Image, ImageDraw, ImageFilter

from cockpitdecks import CONFIG_KW, ANNUNCIATOR_STYLES, ICON_SIZE
from cockpitdecks.resources.color import DEFAULT_COLOR, convert_color, light_off
from cockpitdecks.resources.rpc import RPC
from cockpitdecks.simulator import Dataref

from .draw import DrawBase

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

# Local default values
ANNUNCIATOR_DEFAULT_MODEL = "A"
ANNUNCIATOR_DEFAULT_MODEL_PART = "A0"

DEFAULT_INVERT_COLOR = "white"


class GUARD_TYPES(Enum):
    COVER = "cover"  # Full filled cover over the button
    GRID = "grid"  # Plastic grid over the button


class ANNUNCIATOR_LED(Enum):
    BARS = "bars"  # Three (or more) horizontal bars
    BLOCK = "block"  # Single rectangular led
    DEFAULT = "block"  # Single rectangular led
    DOT = "dot"  # Circular dot
    LED = "led"  # Single rectangular led
    LGEAR = "lgear"  # Triangular (hollow, downward pointing) shape used for landing gear representation


class AnnunciatorPart:
    ANNUNCIATOR_PARTS = {
        "A0": [0.50, 0.50],
        "B0": [0.50, 0.25],
        "B1": [0.50, 0.75],
        "C0": [0.25, 0.50],
        "C1": [0.75, 0.50],
        "D0": [0.50, 0.25],
        "D1": [0.25, 0.75],
        "D2": [0.75, 0.75],
        "E0": [0.25, 0.25],
        "E1": [0.75, 0.25],
        "E2": [0.50, 0.75],
        "F0": [0.25, 0.25],
        "F1": [0.75, 0.25],
        "F2": [0.25, 0.75],
        "F3": [0.75, 0.75],
    }

    def __init__(self, name: str, config: dict, annunciator: "Annunciator"):
        self.name = name
        self._config = config
        self.annunciator = annunciator
        self.datarefs = None
        self.lit = False
        self.color = config.get("color")

        self._width = None
        self._height = None
        self._center_w = None
        self._center_h = None

        if self.name not in AnnunciatorPart.ANNUNCIATOR_PARTS.keys():
            logger.error(f"invalid annunciator part name {self.name}")

    def set_sizes(self, annun_width, annun_height):
        if self.name not in AnnunciatorPart.ANNUNCIATOR_PARTS.keys():
            logger.error(f"invalid annunciator part name {self.name}, sizes not set")
            return
        w, h = AnnunciatorPart.ANNUNCIATOR_PARTS[self.name]
        self._width = annun_width if w == 0.5 else annun_width / 2
        self._height = annun_height if h == 0.5 else annun_height / 2
        self._center_w = int(w * annun_width)
        self._center_h = int(h * annun_height)

    def width(self):
        return self._width

    def height(self):
        return self._height

    def center_w(self):
        return self._center_w

    def center_h(self):
        return self._center_h

    def get_datarefs(self):
        if self.datarefs is None:
            self.datarefs = self.annunciator.button.scan_datarefs(base=self._config)
        return self.datarefs

    def get_attribute(self, attribute: str, default = None, propagate: bool = True, silence: bool = True):
        # Is there such an attribute directly in the button defintion?
        if attribute.startswith(DEFAULT_ATTRIBUTE_PREFIX):
            logger.warning(f"annunciator part fetched default attribute {attribute}")

        value = self._config.get(attribute)
        if value is not None: # found!
            if silence:
                logger.debug(f"annunciator part returning {attribute}={value}")
            else:
                logger.info(f"annunciator part returning {attribute}={value}")
            return value

        if propagate: # we just look at the button. level, not above.
            if not silence:
                logger.info(f"annunciator part propagate to annunciator for {attribute}")
            return self.annunciator.get_attribute(attribute, default=default, propagate=False, silence=silence)

        if not silence:
            logger.warning(f"annunciator part attribute not found {attribute}, returning default ({default})")

        return default

    def get_current_value(self):
        def is_number(n):
            try:
                float(n)
            except ValueError:
                return False
            return True

        ret = None
        if CONFIG_KW.FORMULA.value in self._config:
            calc = self._config[CONFIG_KW.FORMULA.value]
            expr = self.annunciator.button.substitute_values(calc)
            rpc = RPC(expr)
            ret = rpc.calculate()
            logger.debug(f"button {self.annunciator.button.name}: {self.name}: {expr}={ret}")
        elif CONFIG_KW.DATAREF.value in self._config:
            dataref = self._config[CONFIG_KW.DATAREF.value]
            ret = self.annunciator.button.get_dataref_value(dataref)
            logger.debug(f"button {self.annunciator.button.name}: {self.name}: {dataref}={ret}")
        else:
            logger.debug(f"button {self.annunciator.button.name}: {self.name}: no dataref and no formula, set to {ret}")
        self.lit = ret is not None and is_number(ret) and float(ret) > 0
        logger.debug(f"button {self.annunciator.button.name}: {self.name}: {ret} ({self.lit})")
        return ret

    def is_lit(self):
        return self.lit

    def is_invert(self):
        return "invert" in self._config or "invert-color" in self._config

    def invert_color(self):
        if self.is_invert():
            if "invert" in self._config:
                return convert_color(self._config.get("invert"))
            else:
                return convert_color(self._config.get("invert-color"))
        logger.debug(f"button {self.annunciator.button.name}: no invert color, returning {DEFAULT_INVERT_COLOR}")
        return convert_color(DEFAULT_INVERT_COLOR)

    def get_text(self, attr: str):  # = "text"
        return self.annunciator.button.get_text(self._config, attr)

    def get_led(self):
        return self._config.get("led")

    def get_color(self):
        color = self._config.get("color")

        text_color = self._config.get("text-color")
        if color is not None and text_color is not None:
            logger.info(f"button {self.annunciator.button.name}: has both color and text-color set, using color {color}")
        elif color is None and text_color is not None:
            color = text_color
            logger.debug(f"button {self.annunciator.button.name}: color not set but text-color set, using color {color}")
        elif color is None:
            color = self.annunciator.button.get_attribute("text-color")
            if color is not None:
                logger.debug(f"button {self.annunciator.button.name}: no color found, using default text color")
            else:
                color = DEFAULT_COLOR
                logger.warning(f"button {self.annunciator.button.name}: no color found, using default")

        before = color
        if not self.is_lit():
            try:
                lux = self.annunciator.button.get_attribute("light-off-intensity")
                dimmed = light_off(color, lightness=lux / 100)
                color = self._config.get("off-color")
                if color is None:
                    logger.debug(f"button {self.annunciator.button.name}: no off-color, using dimmed")
                    color = dimmed
            except ValueError:
                logger.debug(f"button {self.annunciator.button.name}: color {color} cannot change brightness")
                color = before

        # print(
        #     f">>>> {self.annunciator.button.get_id()}",
        #     self._config.get("color"),
        #     text_color,
        #     self.annunciator.button.get_attribute("text-color"),
        #     color,
        # )

        return convert_color(color)

    def has_frame(self):
        """
        Tries (hard) keyword frame and framed in attributes or options.

        :param      part:  The part
        :type       part:  dict
        """
        framed = self._config.get("framed")
        if framed is None:
            framed = self._config.get("frame")
            if framed is None:
                return False
        if type(framed) == bool:
            return framed
        elif type(framed) == int:
            return framed == 1
        elif type(framed) == str:
            return framed.lower() in ["true", "on", "yes", "1"]
        return False

    def render(self, draw, bgrd_draw, icon_size, annun_width, annun_height, inside, size):
        self.set_sizes(annun_width, annun_height)
        TEXT_SIZE = int(self.height() / 2)  # @todo: find optimum variable text size depending on text length
        color = self.get_color()
        # logger.debug(f"button {self.button.name}: annunc {annun_width}x{annun_height}, offset ({width_offset}, {height_offset}), box {box}")
        # logger.debug(f"button {self.button.name}: part {partname}: {self.width()}x{self.height()}, center ({self.center_w()}, {self.center_h()})")
        # logger.debug(f"button {self.button.name}: part {partname}: {is_lit}, {color}")
        text = self.get_text("text")
        if text is not None:
            #
            # Annunciator part will display text
            #
            fontname = self._config.get("text-font")
            fontsize = int(self._config.get("text-size", TEXT_SIZE))
            font = self.annunciator.get_font(fontname, fontsize)

            if self.is_lit() or not self.annunciator.annunciator_style == ANNUNCIATOR_STYLES.VIVISUN:
                if self.is_lit() and self.is_invert():
                    frame = (
                        (
                            self.center_w() - self.width() / 2,
                            self.center_h() - self.height() / 2,
                        ),
                        (
                            self.center_w() + self.width() / 2,
                            self.center_h() + self.height() / 2,
                        ),
                    )
                    bgrd_draw.rectangle(frame, fill=self.invert_color())
                    logger.debug(f"button {self.annunciator.button.name}: part {self.name}: lit reverse")

                # logger.debug(f"button {self.button.name}: text '{text}' at ({self.center_w()}, {self.center_h()})")
                if not self.is_lit() and type(self.annunciator) != AnnunciatorAnimate:
                    logger.debug(f"button {self.annunciator.button.name}: part {self.name}: not lit (Korry)")
                draw.multiline_text(
                    (self.center_w(), self.center_h()),
                    text=text,
                    font=font,
                    anchor="mm",
                    align="center",
                    fill=color,
                )

                if self.has_frame():
                    txtbb = draw.multiline_textbbox(
                        (self.center_w(), self.center_h()),
                        text=text,
                        font=font,
                        anchor="mm",
                        align="center",  # min frame, just around the text
                    )
                    text_margin = 3 * inside  # margin "around" text, line will be that far from text
                    framebb = (
                        (txtbb[0] - text_margin, txtbb[1] - text_margin),
                        (txtbb[2] + text_margin, txtbb[3] + text_margin),
                    )
                    side_margin = 4 * inside  # margin from side of part of annunciator
                    framemax = (
                        (
                            self.center_w() - self.width() / 2 + side_margin,
                            self.center_h() - self.height() / 2 + side_margin,
                        ),
                        (
                            self.center_w() + self.width() / 2 - side_margin,
                            self.center_h() + self.height() / 2 - side_margin,
                        ),
                    )
                    frame = (
                        (
                            min(framebb[0][0], framemax[0][0]),
                            min(framebb[0][1], framemax[0][1]),
                        ),
                        (
                            max(framebb[1][0], framemax[1][0]),
                            max(framebb[1][1], framemax[1][1]),
                        ),
                    )
                    thick = int(self.height() / 16)
                    # logger.debug(f"button {self.button.name}: part {partname}: {framebb}, {framemax}, {frame}")
                    draw.rectangle(frame, outline=color, width=thick)
            else:
                if not self.is_lit() and type(self.annunciator) != AnnunciatorAnimate:
                    logger.debug(f"button {self.annunciator.button.name}: part {self.name}: not lit (type vivisun)")
            return

        led = self.get_led()
        if led is None:
            logger.warning(f"button {self.annunciator.button.name}: part {self.name}: no text, no led")
            return

        if self.is_lit() or not self.annunciator.annunciator_style == ANNUNCIATOR_STYLES.VIVISUN:
            ninside = 6
            if led in [ANNUNCIATOR_LED.BLOCK.value, ANNUNCIATOR_LED.LED.value]:
                LED_BLOC_HEIGHT = int(self.height() / 2)
                if size == "large":
                    LED_BLOC_HEIGHT = int(LED_BLOC_HEIGHT * 1.25)
                frame = (
                    (
                        self.center_w() - self.width() / 2 + ninside * inside,
                        self.center_h() - LED_BLOC_HEIGHT / 2,
                    ),
                    (
                        self.center_w() + self.width() / 2 - ninside * inside,
                        self.center_h() + LED_BLOC_HEIGHT / 2,
                    ),
                )
                draw.rectangle(frame, fill=color)
            elif led in ["bar", ANNUNCIATOR_LED.BARS.value]:
                LED_BAR_COUNT = int(self._config.get("bars", 3))
                LED_BAR_HEIGHT = max(int(self.height() / (2 * LED_BAR_COUNT)), 2)
                if size == "large":
                    LED_BAR_HEIGHT = int(LED_BAR_HEIGHT * 1.25)
                LED_BAR_SPACER = max(int(LED_BAR_HEIGHT / 3), 2)
                hstart = self.center_h() - (LED_BAR_COUNT * LED_BAR_HEIGHT + (LED_BAR_COUNT - 1) * LED_BAR_SPACER) / 2
                for i in range(LED_BAR_COUNT):
                    frame = (
                        (self.center_w() - self.width() / 2 + ninside * inside, hstart),
                        (
                            self.center_w() + self.width() / 2 - ninside * inside,
                            hstart + LED_BAR_HEIGHT,
                        ),
                    )
                    draw.rectangle(frame, fill=color)
                    hstart = hstart + LED_BAR_HEIGHT + LED_BAR_SPACER
            elif led == ANNUNCIATOR_LED.DOT.value:
                DOT_RADIUS = int(min(self.width(), self.height()) / 5)
                # Plot a series of circular dot on a line
                frame = (
                    (self.center_w() - DOT_RADIUS, self.center_h() - DOT_RADIUS),
                    (self.center_w() + DOT_RADIUS, self.center_h() + DOT_RADIUS),
                )
                draw.ellipse(frame, fill=color)
            elif led == ANNUNCIATOR_LED.LGEAR.value:
                STROKE_THICK = int(min(self.width(), self.height()) / 8) + 1
                tr_hwidth = int(self.width() / 2.5 - ninside)  # triangle half length of width
                tr_hheight = int(self.height() / 2.5 - ninside)  # triangle half height
                origin = (self.center_w() - tr_hwidth, self.center_h() - tr_hheight)
                triangle = [
                    origin,
                    (self.center_w() + tr_hwidth, self.center_h() - tr_hheight),
                    (
                        self.center_w(),
                        self.center_h() + tr_hheight,
                    ),  # lower center point
                    origin,
                ]
                draw.polygon(triangle, outline=color, width=STROKE_THICK)
            else:
                logger.warning(f"button {self.annunciator.button.name}: part {self.name}: invalid led {led}")


class Annunciator(DrawBase):

    REPRESENTATION_NAME = "annunciator"

    PARAMETERS = {
        "icon": {"type": "icon", "prompt": "Icon"},
        "type": {"type": "choice", "prompt": "Type", "choices": ["A", "B", "C", "D", "E", "F"]},
        "style": {"type": "choice", "prompt": "Style", "choices": ["Korry", "Vivisun"]},
        "color": {"type": "string", "prompt": "Background color"},
        "texture": {"type": "icon", "prompt": "Background texture"},
        "annunciator-parts": {
            "type": "multi",
            "multi": {
                "led": {"type": "boolean", "prompt": "LED"},
                "text": {"type": "string", "prompt": "Text"},
                "text-font": {"type": "font", "prompt": "Font"},
                "text-size": {"type": "integer", "prompt": "Size"},
                "text-color": {"type": "string", "prompt": "Color"},
                "text-position": {"type": "choice", "prompt": "Position", "choices": ["lt", "ct", "rt", "lm", "cm", "rm", "lb", "cb", "rb"]},
                "framed": {"type": "boolean", "prompt": "Frame"},
            },
            "prompt": "Parts",
        },
    }

    def __init__(self, config: dict, button: "Button"):
        self.button = button  # we need the reference before we call Icon.__init__()...
        self.icon = config.get("icon")
        self.annunciator = config.get("annunciator")  # keep raw
        self.annunciator_style = config.get("annunciator-style", button.get_attribute("annunciator-style"))
        self.model = None

        self.annun_color = config.get("annunciator-color", button.get_attribute("annunciator-color"))
        self.annun_color = convert_color(self.annun_color)
        self.annun_texture = config.get("annunciator-texture", button.get_attribute("annunciator-texture"))

        # Normalize annunciator parts in parts attribute if not present
        if self.annunciator is None:
            logger.error(f"button {button.name}: annunciator has no property")
            return

        self._part_iterator = None  # cache
        self.annunciator_parts: Dict[str, AnnunciatorPart] | None = None
        parts = self.annunciator.get("parts")
        if parts is None:  # if only one annunciator
            arr = {}
            for part_name in self.part_iterator():
                p = self.annunciator.get(part_name)
                if p is not None:
                    arr[part_name] = AnnunciatorPart(name=part_name, config=p, annunciator=self)
            if len(arr) > 0:
                ctrl = list(set([k[0] for k in arr.keys()]))
                if len(ctrl) != 1:
                    logger.error(f"button {self.button.name}: multiple annunciator models {ctrl}")
                self.model = ctrl[0]
                self.annunciator_parts = arr
                logger.debug(f"button {self.button.name}: annunciator parts normalized ({list(self.annunciator_parts.keys())})")
            else:
                self.annunciator[CONFIG_KW.ANNUNCIATOR_MODEL.value] = ANNUNCIATOR_DEFAULT_MODEL
                self.model = ANNUNCIATOR_DEFAULT_MODEL
                arr[ANNUNCIATOR_DEFAULT_MODEL_PART] = AnnunciatorPart(
                    name=ANNUNCIATOR_DEFAULT_MODEL_PART,
                    config=self.annunciator,
                    annunciator=self,
                )
                self.annunciator_parts = arr
                logger.debug(f"button {self.button.name}: annunciator has no part, assuming single {ANNUNCIATOR_DEFAULT_MODEL_PART} part")
        else:
            ctrl = list(set([k[0] for k in parts.keys()]))
            if len(ctrl) != 1:
                logger.error(f"button {self.button.name}: multiple annunciator models {ctrl}")
            self.model = ctrl[0]
            self.annunciator_parts = dict([(k, AnnunciatorPart(name=k, config=v, annunciator=self)) for k, v in parts.items()])

        for a in [CONFIG_KW.DATAREF.value, CONFIG_KW.FORMULA.value]:
            if a in config:
                logger.warning(f"button {self.button.name}: annunciator parent button has property {a} which is ignored")

        if self.annunciator_parts is None:
            logger.error(f"button {self.button.name}: annunciator has no part")

        if self.model is None:
            logger.error(f"button {self.button.name}: annunciator has no model")

        self.annunciator_datarefs: List[Dataref] | None = None
        self.annunciator_datarefs = self.get_datarefs()

        DrawBase.__init__(self, config=config, button=button)

    def is_valid(self):
        if self.button is None:
            logger.warning(f"button {self.button.name}: {type(self).__name__}: no button")
            return False
        if self.annunciator is None:
            logger.warning(f"button {self.button.name}: {type(self).__name__}: no annunciator attribute")
            return False
        return True

    def part_iterator(self):
        """
        Build annunciator part index list
        """
        if self._part_iterator is None:
            t = self.annunciator.get(CONFIG_KW.ANNUNCIATOR_MODEL.value, ANNUNCIATOR_DEFAULT_MODEL)
            if t not in "ABCDEF":
                logger.warning(f"button {self.button.name}: invalid annunciator type {t}")
                return []
            n = 1
            if t in "BC":
                n = 2
            elif t in "DE":
                n = 3
            elif t == "F":
                n = 4
            self._part_iterator = [t + str(partnum) for partnum in range(n)]
        return self._part_iterator

    def get_datarefs(self) -> List[Dataref]:
        """
        Complement button datarefs with annunciator special lit datarefs
        """
        if self.annunciator_datarefs is not None:
            # logger.debug(f"button {self.button.name}: returned from cache")
            return self.annunciator_datarefs
        r: List[Dataref] = []
        if self.annunciator_parts is not None:
            for k, v in self.annunciator_parts.items():
                datarefs = v.get_datarefs()
                if len(datarefs) > 0:
                    r = r + datarefs
                    logger.debug(f"button {self.button.name}: added {k} datarefs {datarefs}")
        else:
            logger.warning("no annunciator parts to get datarefs from")
        self.annunciator_datarefs = list(set(r))
        return self.annunciator_datarefs

    def get_current_values(self):
        """
        There is a get_current_value value per annunciator part.
        """
        v = dict([(k, v.get_current_value()) for k, v in self.annunciator_parts.items()])
        l = dict([(k, v.is_lit()) for k, v in self.annunciator_parts.items()])
        logger.debug(f"button {self.button.name}: {type(self).__name__}: {v} => {l}")
        return v

    def get_annunciator_background(self, width: int, height: int, use_texture: bool = True):
        """
        Returns a **Pillow Image** of size width x height with either the file specified by texture or a uniform color
        """
        image = None
        if use_texture:
            if self.annun_texture is not None:
                if self.button.deck.cockpit.get_icon(self.annun_texture) is not None:
                    image = self.button.deck.cockpit.get_icon_image(self.annun_texture)
                    logger.debug(f"using texture {self.annun_texture}")
                    if image is not None:  # found a texture as requested
                        image = image.resize((width, height))
                        return image
                logger.debug(f"proble with texture {self.annun_texture}, using uniform color")
            else:
                logger.debug(f"should use texture but no texture provided, using uniform color")

        image = Image.new(mode="RGBA", size=(width, height), color=self.annun_color)
        logger.debug(f"using uniform color {self.annun_color}")
        return image

    def get_image_for_icon(self):
        # If the part is not lit, a darker version is printed unless dark option is added to button
        # in which case nothing gets added to the button.
        # CONSTANTS
        SEAL_WIDTH = 8  # px
        SQUARE = self.button.has_option("square")
        inside = ICON_SIZE / 32  # ~8px for 256x256 image
        page = self.button.page

        # Button overall size: full, large, medium, small.
        # Box is the top area where label will go if any
        size = self.annunciator.get("size", "full")
        annun_width = ICON_SIZE
        spare16 = 2
        if size == "small":  # 1/2, starts at 128
            annun_height = int(ICON_SIZE / 2)
            height_offset = (ICON_SIZE - annun_height) / 2
            width_offset = (ICON_SIZE - annun_width) / 2
            box = (0, int(ICON_SIZE / 4))
        elif size == "medium":  # 5/8, starts at 96
            annun_height = int(10 * ICON_SIZE / 16)
            height_offset = (ICON_SIZE - annun_height) / 2
            width_offset = (ICON_SIZE - annun_width) / 2
            box = (0, int(3 * ICON_SIZE / 16))
        elif size == "full":  # starts at 0
            annun_height = ICON_SIZE
            height_offset = 0
            width_offset = 0
            box = (0, 0)
            # box2 = (0, int(spare16 * ICON_SIZE / 16))
        else:  # "large", full size, leaves spare16*1/16 at the top
            annun_height = int((16 - spare16) * ICON_SIZE / 16)
            if SQUARE:
                annun_width = annun_height
            height_offset = ICON_SIZE - annun_height
            width_offset = (ICON_SIZE - annun_width) / 2
            box = (0, int(spare16 * ICON_SIZE / 16))

        # PART 1:
        # Texts that will glow if Korry style goes on glow.
        # Drawing that will not glow go on bgrd.
        # bgrd = Image.new(mode="RGBA", size=(annun_width, annun_height), color=self.annun_color)  # annunciator background color, including invert ON modes
        bgrd = self.get_annunciator_background(width=annun_width, height=annun_height)

        bgrd_draw = ImageDraw.Draw(bgrd)
        annun_color = (*self.annun_color, 0) if len(self.annun_color) == 3 else self.annun_color

        glow = Image.new(mode="RGBA", size=(annun_width, annun_height), color=annun_color)  # annunciator text and leds , color=(0, 0, 0, 0)
        draw = ImageDraw.Draw(glow)
        guard = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=annun_color)  # annunuciator optional guard
        guard_draw = ImageDraw.Draw(guard)

        for part in self.annunciator_parts.values():
            part.render(draw, bgrd_draw, ICON_SIZE, annun_width, annun_height, inside, size)

        # PART 1.2: Glowing texts, later because not nicely perfect.
        if self.annunciator_style == ANNUNCIATOR_STYLES.KORRY:
            # blurred_image = glow.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=10))
            blurred_image1 = glow.filter(ImageFilter.GaussianBlur(10))  # self.annunciator.get("blurr", 10)
            blurred_image2 = glow.filter(ImageFilter.GaussianBlur(4))  # self.annunciator.get("blurr", 10)
            # blurred_image = glow.filter(ImageFilter.BLUR)
            glow.alpha_composite(blurred_image1)
            glow.alpha_composite(blurred_image2)
            # glow = blurred_image
            # logger.debug("blurred")

        # PART 1.3: Seal
        if self.button.has_option("seal"):
            seal_width = int(self.button._config.get("seal-width", 16))
            seal_color = self.button._config.get("seal-color", "darkslategray")
            sw2 = seal_width / 2
            bgrd_draw.line(
                [(sw2, sw2), (annun_width - sw2, sw2)],
                fill=seal_color,
                width=seal_width,
            )
            bgrd_draw.line(
                [(sw2, annun_height - sw2), (annun_width - sw2, annun_height - sw2)],
                fill=seal_color,
                width=seal_width,
            )
            bgrd_draw.line(
                [(sw2, sw2), (sw2, annun_height - sw2)],
                fill=seal_color,
                width=seal_width,
            )
            bgrd_draw.line(
                [(annun_width - sw2, sw2), (annun_width - sw2, annun_height - sw2)],
                fill=seal_color,
                width=seal_width,
            )

        # PART 2: Make annunciator
        # Paste the transparent text/glow into the annunciator background (and optional seal):
        annunciator = Image.new(mode="RGBA", size=(annun_width, annun_height), color=annun_color)
        annunciator.alpha_composite(bgrd)  # potential inverted colors
        # annunciator.alpha_composite(glow)    # texts
        annunciator.paste(glow, mask=glow)  # texts

        # PART 3: Background
        # Paste the annunciator into the button background:
        image = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=self.icon_texture,
            color_in=self.icon_color,
            use_texture=True,
            who="Annunciator",
        )
        draw = ImageDraw.Draw(image)
        image.paste(annunciator, box=(int(width_offset), int(height_offset)))

        # PART 4: Guard
        if self.button.guard is not None:
            cover = self.button.guard.get(CONFIG_KW.ANNUNCIATOR_MODEL.value, GUARD_TYPES.COVER.value)
            guard_color = self.button.guard.get("color", "red")
            guard_color = convert_color(guard_color)
            sw = self.button.guard.get("grid-width", 16)
            topp = self.button.guard.get("top", int(ICON_SIZE / 8))
            tl = (ICON_SIZE / 8, 0)
            br = (int(7 * ICON_SIZE / 8), topp)
            guard_draw.rectangle(tl + br, fill=guard_color)
            if self.button.is_guarded():
                if cover == GUARD_TYPES.GRID.value:
                    for i in range(3):
                        x = int((i * ICON_SIZE / 2) - (i - 1) * sw / 2)
                        guard_draw.line([(x, topp), (x, ICON_SIZE)], fill=guard_color, width=sw)
                    for i in range(3):
                        y = int(topp + (i * (7 * ICON_SIZE / 8) / 2) - (i - 1) * sw / 2)
                        guard_draw.line([(0, y), (ICON_SIZE, y)], fill=guard_color, width=sw)
                else:
                    tl = (0, topp)
                    br = (ICON_SIZE, ICON_SIZE)
                    guard_draw.rectangle(tl + br, fill=guard_color)
            image.alpha_composite(guard)

        # PART 5: Label
        # Label will be added in Icon.get_image()
        return image

    def all_lit(self, on: bool):
        if self.annunciator_parts is not None:
            for v in self.annunciator_parts.values():
                v.lit = on
        else:
            logger.warning("no annunciator parts to light")

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        t = self.annunciator.get(CONFIG_KW.ANNUNCIATOR_MODEL.value, ANNUNCIATOR_DEFAULT_MODEL)
        a = [f"The representation displays an annunciator of type {t}."]
        return "\n\r".join(a)


# ###############################
# ANNUNCIATOR-BASED ANIMATION
# (simple on/off blinking)
#
class AnnunciatorAnimate(Annunciator):
    """ """

    REPRESENTATION_NAME = "annunciator-animate"

    PARAMETERS = {"speed": {"type": "integer", "prompt": "Speed (seconds)"}, "icon-off": {"type": "icon", "prompt": "Icon when off"}}

    def __init__(self, config: dict, button: "Button"):
        config["annunciator"] = config.get("annunciator-animate")

        Annunciator.__init__(self, config=config, button=button)

        self.speed = float(self.annunciator.get("animation-speed", 0.5))  # type: ignore

        # Working attributes
        self.running = None  # state unknown
        self.thread = None
        self.exit = None
        self.blink = True

    def loop(self):
        self.exit = threading.Event()
        while not self.exit.is_set():
            self.button.render()
            self.blink = not self.blink
            self.all_lit(self.blink)
            self.exit.wait(self.speed)
        logger.debug(f"exited")

    def should_run(self) -> bool:
        """
        Check conditions to animate the icon.
        """
        value = self.get_current_value()
        if type(value) == dict:
            value = value[list(value.keys())[0]]
        return value is not None and value != 0

    def anim_start(self):
        """
        Starts animation
        """
        if not self.running:
            self.thread = threading.Thread(target=self.loop, name=f"ButtonAnimate::loop({self.button.name})")
            self.running = True
            self.thread.start()
        else:
            logger.warning(f"button {self.button.name}: already started")

    def anim_stop(self, render: bool = True):
        """
        Stops animation
        """
        if self.running:
            self.running = False
            self.exit.set()
            self.thread.join(timeout=2 * self.speed)
            if self.thread.is_alive():
                logger.warning(f"button {self.button.name}: did not get finished signal")
            self.all_lit(False)
            if render:
                return super().render()
        else:
            logger.debug(f"button {self.button.name}: already stopped")

    def clean(self):
        """
        Stops animation and remove icon from deck
        """
        logger.debug(f"button {self.button.name}: cleaning requested")
        self.anim_stop(render=False)
        logger.debug(f"button {self.button.name}: stopped")
        super().clean()

    def render(self):
        """
        Renders icon_off or current icon in list
        """
        if self.is_valid():
            if self.should_run():
                if not self.running:
                    self.anim_start()
                self.vibrate()
                return super().render()
            else:
                if self.running:
                    self.anim_stop()
                return super().render()
        return None

    def describe(self) -> str:
        """
        Describe what the button does in plain English
        """
        t = self.annunciator.get(CONFIG_KW.ANNUNCIATOR_MODEL.value, ANNUNCIATOR_DEFAULT_MODEL)
        a = [
            f"The representation displays an annunciator of type {t}.",
            f"This annunciator is blinking every {self.speed} seconds when it is ON.",
        ]
        return "\n\r".join(a)
