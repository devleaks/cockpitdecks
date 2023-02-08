# ###########################
# Special Airbus Button Rendering
#
import logging
import threading
import time
import colorsys
import traceback

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageColor
# from mergedeep import merge

from .constant import DATAREF_RPN, ANNUNCIATOR_DEFAULTS, ANNUNCIATOR_STYLES, LIGHT_OFF_BRIGHTNESS
from .color import convert_color, light_off
from .rpc import RPC
from .button_representation import Icon

logger = logging.getLogger("Annunciator")
logger.setLevel(logging.DEBUG)


# Yeah, shouldn't be globals.
# Localized here for convenience
# Can be moved lated.


class AnnunciatorPart:

    ANNUNCIATOR_TYPES = {
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
        "F3": [0.75, 0.75]
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

        if self.name not in AnnunciatorPart.ANNUNCIATOR_TYPES.keys():
            logger.error(f"__init__: invalid annunciator part name {self.name}")

    def set_sizes(self, annun_width, annun_height):
        if self.name not in AnnunciatorPart.ANNUNCIATOR_TYPES.keys():
            logger.error(f"set_sizes: invalid annunciator part name {self.name}, sizes not set")
            return
        w, h = AnnunciatorPart.ANNUNCIATOR_TYPES[self.name]
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
            self.datarefs = self.annunciator.button.get_datarefs(base=self._config)
        return self.datarefs

    def get_current_value(self):
        def is_number(n):
            try:
                float(n)
            except ValueError:
                return False
            return True

        ret = None
        if DATAREF_RPN in self._config:
            calc = self._config[DATAREF_RPN]
            expr = self.annunciator.button.substitute_dataref_values(calc)
            rpc = RPC(expr)
            ret = rpc.calculate()
            logger.debug(f"get_current_value: button {self.annunciator.button.name}: {self.name}: {expr}={ret}")
        elif "dataref" in self._config:
            dataref = self._config["dataref"]
            ret = self.annunciator.button.get_dataref_value(dataref)
            logger.debug(f"get_current_value: button {self.annunciator.button.name}: {self.name}: {dataref}={ret}")
        else:
            logger.debug(f"get_current_value: button {self.annunciator.button.name}: {self.name}: no dataref and no formula, set to {ret}")
        self.lit = ret is not None and is_number(ret) and float(ret) > 0
        logger.debug(f"get_current_value: button {self.annunciator.button.name}: {self.name}: {ret} ({self.lit})")
        return ret

    def is_lit(self):
        return self.lit

    def is_invert(self):
        return "invert" in self._config or "invert-color" in self._config

    def invert_color(self):
        DEFAULT_INVERT_COLOR = "white"
        if self.is_invert():
            if "invert" in self._config:
                return convert_color(self._config.get("invert"))
            else:
                return convert_color(self._config.get("invert-color"))
        logger.debug(f"invert_color: button {self.annunciator.button.name}: no invert color, returning {DEFAULT_INVERT_COLOR}")
        return convert_color(DEFAULT_INVERT_COLOR)

    def get_text(self, attr:str):  # = "text"
        return self.annunciator.button.get_text(self._config, attr)

    def get_led(self):
        return self._config.get("led")

    def get_color(self):
        color = self._config.get("color")
        if color is None:
            logger.warning(f"render: button {self.annunciator.button.name}: not color found, using grey")
            color = (128, 128, 128)
        if type(color) == tuple or type(color) == list:  # we transfort it back to a string, read on...
            color = "(" + ",".join([str(i) for i in color]) + ")"

        if not self.is_lit():
            try:
                color = self._config.get("off-color", light_off(color))
            except ValueError:
                logger.debug(f"render: button {self.annunciator.button.name}: color {color} ({type(color)}) not found, using grey")
                color = (128, 128, 128)
        elif color.startswith("("):
            color = convert_color(color)
        else:
            try:
                color = ImageColor.getrgb(color)
            except ValueError:
                logger.debug(f"render: color {color} not found, using grey")
                color = (128, 128, 128)
        return color

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
        # logger.debug(f"render: button {self.button.name}: annunc {annun_width}x{annun_height}, offset ({width_offset}, {height_offset}), box {box}")
        # logger.debug(f"render: button {self.button.name}: part {partname}: {self.width()}x{self.height()}, center ({self.center_w()}, {self.center_h()})")
        # logger.debug(f"render: button {self.button.name}: part {partname}: {is_lit}, {color}")
        text = self.get_text("text")
        if text is not None:
            #
            # Annunciator part will display text
            #
            fontname = self.annunciator.get_font(self._config.get("font"))
            fontsize = int(self._config.get("text-size", TEXT_SIZE))
            font = ImageFont.truetype(fontname, fontsize)
            if self.is_lit() or not self.annunciator.button.page.annunciator_style == ANNUNCIATOR_STYLES.VIVISUN:

                if self.is_lit() and self.is_invert():
                    frame = ((self.center_w() - self.width()/2, self.center_h() - self.height()/2), (self.center_w() + self.width()/2, self.center_h() + self.height()/2))
                    bgrd_draw.rectangle(frame, fill=self.invert_color())

                # logger.debug(f"render: button {self.button.name}: text '{text}' at ({self.center_w()}, {self.center_h()})")
                draw.multiline_text((self.center_w(), self.center_h()),
                          text=text,
                          font=font,
                          anchor="mm",
                          align="center",
                          fill=color)

                if self.has_frame():
                    txtbb = draw.multiline_textbbox((self.center_w(), self.center_h()),  # min frame, just around the text
                              text=text,
                              font=font,
                              anchor="mm",
                              align="center")
                    text_margin = 3 * inside  # margin "around" text, line will be that far from text
                    framebb = ((txtbb[0]-text_margin, txtbb[1]-text_margin), (txtbb[2]+text_margin, txtbb[3]+text_margin))
                    side_margin = 4 * inside  # margin from side of part of annunciator
                    framemax = ((self.center_w() - self.width()/2 + side_margin, self.center_h() - self.height()/2 + side_margin), (self.center_w() + self.width()/2 - side_margin, self.center_h() + self.height()/2 - side_margin))
                    frame = ((min(framebb[0][0], framemax[0][0]),min(framebb[0][1], framemax[0][1])), (max(framebb[1][0], framemax[1][0]), max(framebb[1][1], framemax[1][1])))
                    thick = int(self.height() / 16)
                    # logger.debug(f"render: button {self.button.name}: part {partname}: {framebb}, {framemax}, {frame}")
                    draw.rectangle(frame, outline=color, width=thick)
            else:
                logger.debug(f"draw: button {self.annunciator.button.name}: part {self.name}: not lit")
            return

        led = self.get_led()
        if led is None:
            logger.warning(f"draw: button {self.annunciator.button.name}: part {self.name}: no text, no led")
            return

        LED_HEIGHT = 40
        LED_BAR_HEIGHT = 12
        LED_BAR_COUNT = 3
        LED_BAR_SPACER = 4
        DOT_RADIUS = self.width() / 16

        ninside = 6
        if led in ["block", "led"]:
            if size == "large":
                LED_HEIGHT = int(LED_HEIGHT * 1.25)
            frame = ((self.center_w() - self.width()/2 + ninside * inside, self.center_h() - LED_HEIGHT / 2), (self.center_w() + self.width()/2 - ninside * inside, self.center_h() + LED_HEIGHT / 2))
            draw.rectangle(frame, fill=color)
        elif led in ["bar", "bars"]:
            if size == "large":
                LED_BAR_HEIGHT = int(LED_BAR_HEIGHT * 1.25)
            hstart = self.center_h() - (LED_BAR_COUNT * LED_BAR_HEIGHT + (LED_BAR_COUNT - 1) * LED_BAR_SPACER) / 2
            for i in range(LED_BAR_COUNT):
                frame = ((self.center_w() - self.width()/2 + ninside * inside, hstart), (self.center_w() + self.width()/2 - ninside * inside, hstart + LED_BAR_HEIGHT))
                draw.rectangle(frame, fill=color)
                hstart = hstart + LED_BAR_HEIGHT + LED_BAR_SPACER
        elif led == "dot":
            # Plot a series of circular dot on a line
            frame = ((self.center_w() - DOT_RADIUS, self.center_h() - DOT_RADIUS), (self.center_w() + DOT_RADIUS, self.center_h() + DOT_RADIUS))
            draw.ellipse(frame, fill=color)
        elif led == "lgear":
            vert_ninside = 4
            origin = (self.center_w() - self.width()/2 + ninside * inside, self.center_h() - self.height()/2 + vert_ninside * inside)
            triangle = [
                origin,
                (self.center_w() + self.width()/2 - ninside * inside, self.center_h() - self.height()/2 + vert_ninside * inside),
                (self.center_w(), self.center_h() + self.height()/2 - vert_ninside * inside),  # lower center point
                origin
            ]
            thick = int(min(self.width(), self.height()) / 8)
            draw.polygon(triangle, outline=color, width=thick)
        else:
            logger.warning(f"draw: button {self.annunciator.button.name}: part {self.name}: invalid led {led}")


class Annunciator(Icon):

    def __init__(self, config: dict, button: "Button"):

        self.button = button        # we need the reference before we call Icon.__init__()...
        self.annunciator = config.get("annunciator")  # keep raw

        # Normalize annunciator parts in parts attribute if not present
        if self.annunciator is None:
            logger.error(f"__init__: button {button.name}: annunciator has no property")
            return

        # self.annunciator = merge({}, ANNUNCIATOR_DEFAULTS, self.annunciator)
        self._part_iterator = None  # cache
        self.annunciator_parts = None
        parts = self.annunciator.get("parts")
        if parts is None:  # if only one annunciator
            arr = {}
            for part_name in self.part_iterator():
                p = self.annunciator.get(part_name)
                if p is not None:
                    arr[part_name] = AnnunciatorPart(name=part_name, config=p, annunciator=self)
            if len(arr) > 0:
                self.annunciator_parts = arr
                logger.debug(f"__init__: button {self.button.name}: annunciator parts normalized ({list(self.annunciator['parts'].keys())})")
            else:
                self.annunciator["type"] = "A"
                arr["A0"] = AnnunciatorPart(name="A0", config=self.annunciator, annunciator=self)
                self.annunciator_parts = arr
                logger.debug(f"__init__: button {self.button.name}: annunciator has no part, assuming single A0 part")
        else:
            self.annunciator_parts = dict([(k, AnnunciatorPart(name=k, config=v, annunciator=self)) for k, v in parts.items()])

        for a in ["dataref", "multi-datarefs", "datarefs", "dataref-rpn"]:
            if a in config:
                logger.warning(f"__init__: button {self.button.name}: annunciator parent button has property {a} which is ignored")

        if self.annunciator_parts is None:
            logger.error(f"__init__: button {self.button.name}: annunciator has no part")

        # Working variables
        self.lit = {}  # parts of annunciator that are lit
        self.part_controls = {}

        self.annunciator_datarefs = None          # cache
        self.annunciator_datarefs = self.get_annunciator_datarefs()

        Icon.__init__(self, config=config, button=button)


    def is_valid(self):
        if self.button is None:
            logger.warning(f"is_valid: button {self.button.name}: {type(self).__name__}: no button")
            return False
        if self.annunciator is None:
            logger.warning(f"is_valid: button {self.button.name}: {type(self).__name__}: no annunciator attribute")
            return False
        return True

    def part_iterator(self):
        """
        Build annunciator part index list
        """
        if self._part_iterator is None:
            t = self.annunciator.get("type", "A")
            n = 1
            if t in "BC":
                n = 2
            elif t in "DE":
                n = 3
            elif t == "F":
                n = 4
            self._part_iterator = [t + str(partnum) for partnum in range(n)]
        return self._part_iterator

    def get_annunciator_datarefs(self, base:dict = None):
        """
        Complement button datarefs with annunciator special lit datarefs
        """
        if self.annunciator_datarefs is not None:
            # logger.debug(f"get_annunciator_datarefs: button {self.button.name}: returned from cache")
            return self.annunciator_datarefs
        r = []
        for k, v in self.annunciator_parts.items():
            datarefs = v.get_datarefs()
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"get_annunciator_datarefs: button {self.button.name}: added {k} datarefs {datarefs}")
        self.annunciator_datarefs = list(set(r))
        return self.annunciator_datarefs

    def get_current_values(self):
        """
        There is a get_current_value value per annunciator part.
        """
        v = dict([(k, v.get_current_value()) for k,v in self.annunciator_parts.items()])
        l = dict([(k, v.is_lit()) for k,v in self.annunciator_parts.items()])
        logger.debug(f"get_current_values: button {self.button.name}: {type(self).__name__}: {v} => {l}")
        return v

    def get_image_for_icon(self):
        # If the part is not lit, a darker version is printed unless dark option is added to button
        # in which case nothing gets added to the button.
        # CONSTANTS
        ICON_SIZE = 256 # px
        SEAL_WIDTH = 8  # px
        SQUARE = self.button.has_option("square")
        inside = ICON_SIZE / 32 # ~8px for 256x256 image
        page = self.button.page

        # MAIN
        logger.debug(f"render: button {self.button.name}: creating..")

        # Button overall size: full, large, medium, small.
        # Box is the top area where label will go if any
        size = self.annunciator.get("size", "full")
        annun_width = ICON_SIZE
        spare16 = 2
        if size == "small":  # 1/2, starts at 128
            annun_height = int(ICON_SIZE / 2)
            height_offset = (ICON_SIZE - annun_height) / 2
            width_offset  = (ICON_SIZE - annun_width ) / 2
            box = (0, int(ICON_SIZE/4))
        elif size == "medium":  # 5/8, starts at 96
            annun_height = int(10 * ICON_SIZE / 16)
            height_offset = (ICON_SIZE - annun_height) / 2
            width_offset  = (ICON_SIZE - annun_width ) / 2
            box = (0, int(3 * ICON_SIZE / 16))
        elif size == "full":  # starts at 0
            annun_height = ICON_SIZE
            height_offset = 0
            width_offset  = 0
            box = (0, 0)
            # box2 = (0, int(spare16 * ICON_SIZE / 16))
        else:  # "large", full size, leaves spare16*1/16 at the top
            annun_height = int((16 - spare16) * ICON_SIZE / 16)
            if SQUARE:
                annun_width = annun_height
            height_offset = ICON_SIZE - annun_height
            width_offset  = (ICON_SIZE - annun_width ) / 2
            box = (0, int(spare16 * ICON_SIZE / 16))

        # PART 1:
        # Texts that will glow if Korry style goes on glow.
        # Drawing that will not glow go on bgrd.
        annun_bg = convert_color(self.annunciator.get("background-color", "black"))
        bgrd = Image.new(mode="RGBA", size=(annun_width, annun_height), color=annun_bg)     # annunciator background color, including invert ON modes
        bgrd_draw = ImageDraw.Draw(bgrd)
        glow = Image.new(mode="RGBA", size=(annun_width, annun_height))                     # annunciator text and leds , color=(0, 0, 0, 0)
        draw = ImageDraw.Draw(glow)
        guard = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=(0, 0, 0, 0))     # annunuciator optional guard
        guard_draw = ImageDraw.Draw(guard)

        for part in self.annunciator_parts.values():
            part.render(draw, bgrd_draw, ICON_SIZE, annun_width, annun_height, inside, size)

        # PART 1.2: Glowing texts, later because not nicely perfect.
        if page.annunciator_style == ANNUNCIATOR_STYLES.KORRY:
            # blurred_image = glow.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=10))
            blurred_image1 = glow.filter(ImageFilter.GaussianBlur(10)) # self.annunciator.get("blurr", 10)
            blurred_image2 = glow.filter(ImageFilter.GaussianBlur(4)) # self.annunciator.get("blurr", 10)
            # blurred_image = glow.filter(ImageFilter.BLUR)
            glow.alpha_composite(blurred_image1)
            glow.alpha_composite(blurred_image2)
            # glow = blurred_image
            # logger.debug("render: blurred")

        # PART 1.2: Make annunciator
        # Paste the transparent text/glow into the annunciator background (and optional seal):
        annunciator = Image.new(mode="RGB", size=(annun_width, annun_height), color=(0, 0, 0))
        annunciator.paste(bgrd)               # potential inverted colors
        annunciator.paste(glow, mask=glow)    # texts

        # PART 2: Background
        # Paste the annunciator into the button background:
        image = Image.new(mode="RGB", size=(ICON_SIZE, ICON_SIZE), color=self.button.page.cockpit_color)
        draw = ImageDraw.Draw(image)
        image.paste(annunciator, box=(int(width_offset), int(height_offset)))

        # PART 4: Guard
        # image.paste(guard)

        # PART 5: Label
        # Label will be added in Icon.get_image()
        return image

        # if self.label is not None:
        #     title_pos = self.label_position
        #     fontname = self.get_font()
        #     fontsize = 2 * self.label_size
        #     font = ImageFont.truetype(fontname, fontsize)
        #     w = image.width / 2
        #     p = "m"
        #     a = "center"
        #     if title_pos[0] == "l":
        #         w = inside
        #         p = "l"
        #         a = "left"
        #     elif title_pos[0] == "r":
        #         w = image.width - inside
        #         p = "r"
        #         a = "right"

        #     b = box[1]
        #     h = 1 + max(b, self.label_size) / 2  # smallest to fit text
        #     # logger.debug(f"render: button {self.button.name}: label '{self.label}' at ({w}, {h}) (box: {box})")
        #     draw.multiline_text((w, h),  # (image.width / 2, 15)
        #               text=self.label,
        #               font=font,
        #               anchor=p+"m",
        #               align=a,
        #               fill=self.label_color)

        # # logger.debug(f"render: button {self.button.name}: ..done")

        # return image


class AnnunciatorAnimate(Annunciator):
    """
    """
    def __init__(self, config: dict, page: "Page"):
        self.running = None  # state unknown
        self.thread = None
        self.finished = None
        self.counter = 0
        Annunciator.__init__(self, config=config, page=page)
        self.speed = float(self.option_value("animation_speed", 0.5))

        self.render()