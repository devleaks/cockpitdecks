# ###########################
# Special Airbus Button Rendering
#
import logging
import threading
import time
import colorsys
import traceback

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageColor
from mergedeep import merge

from .constant import ANNUNCIATOR_DEFAULTS, ANNUNCIATOR_STYLES, LIGHT_OFF_BRIGHTNESS, convert_color, print_stack
from .button_core import Button
from .rpc import RPC

logger = logging.getLogger("AnnunciatorButton")
# logger.setLevel(logging.DEBUG)

DATAREF_RPN = "dataref-rpn"

def convert_color_string(instr) -> tuple:  # tuple of int 0-255
    # process either a color name or a color tuple as a string "(1, 2, 3)"
    # and returns a tuple of 3 or 4 intergers in range [0,255].
    # If case of failure to convert, returns middle grey values.
    if type(instr) == tuple or type(instr) == list:
        return tuple(instr)
    if type(instr) != str:
        logger.debug(f"convert_color_string: color {instr} ({type(instr)}) not found, using grey")
        return (128, 128, 128)
    # it's a string...
    instr = instr.strip()
    if "," in instr and instr.startswith("("):  # "(255, 7, 2)"
        a = instr.replace("(", "").replace(")", "").split(",")
        return tuple([int(e) for e in a])
    else:  # it may be a color name...
        try:
            color = ImageColor.getrgb(instr)
        except ValueError:
            logger.debug(f"convert_color_string: fail to convert color {instr} ({type(instr)}), using grey")
            color = (128, 128, 128)
        return color
    logger.debug(f"convert_color_string: not a string {instr} ({type(instr)}), using grey")
    return (128, 128, 128)


class AnnunciatorButton(Button):

    def __init__(self, config: dict, page: "Page"):

        self.lit = {}  # parts of annunciator that are lit
        self.part_controls = {}
        self._part_iterator = None

        self.multi_icons = config.get("multi-icons")
        self.icon = config.get("icon")

        self.annunciator = None                   # working def
        self.annunciator_datarefs = None          # cache
        self._annunciator = config.get("annunciator")  # keep raw
        if self._annunciator is not None:
            self.annunciator = merge({}, ANNUNCIATOR_DEFAULTS, self._annunciator)

            # Normalize annunciator in case of A type (single part)
            atyp = self.annunciator.get("type", "A")
            parts = self.annunciator.get("parts")
            if atyp == "A" and parts is None:  # if only one annunciator, no need for "parts" (special case)
                self.annunciator["parts"] = { "A0": self._annunciator }
                name = config.get("name", f"{type(self).__name__}-{config['index']}")
                logger.debug(f"__init__: button {name}: annunciator part normalized")
        else:
            logger.error(f"__init__: button {self.name}: has no annunciator property")

        Button.__init__(self, config=config, page=page)

        if self.annunciator is not None and (config.get("icon") is not None or config.get("multi-icons") is not None):
            logger.warning(f"__init__: button {self.name}: has annunciator property with icon/multi-icons, ignoring icons")

        if self.annunciator is not None:
            self.icon = None
            self.multi_icons = None

    def part_iterator(self):
        """
        Build annunciator part index list
        """
        if self._part_iterator is None:
            atyp = self.annunciator.get("type", "A")
            acnt = 1
            if atyp in "BC":
                acnt = 2
            elif atyp in "DE":
                acnt = 3
            elif atyp == "F":
                acnt = 4
            self._part_iterator = [atyp + str(partnum) for partnum in range(acnt)]
        return self._part_iterator

    def get_annunciator_datarefs(self, base:dict = None):
        """
        Complement button datarefs with annunciator special lit datarefs
        """
        # print_stack(logger)
        if self.annunciator_datarefs is not None:
            # logger.debug(f"get_annunciator_datarefs: button {self.name}: returned from cache")
            return self.annunciator_datarefs
        r = []
        parts = self.annunciator.get("parts")
        if parts is not None:
            for key in self.part_iterator():
                if key in parts.keys():
                    datarefs = super().get_datarefs(base=parts[key])
                    if len(datarefs) > 0:
                        r = r + datarefs
                        logger.debug(f"get_annunciator_datarefs: button {self.name}: added {key} datarefs {datarefs}")
        else:
            logger.debug(f"get_annunciator_datarefs: button {self.name}: annunciator has no part")
        self.annunciator_datarefs = list(set(r))
        return self.annunciator_datarefs

    def get_datarefs(self, base:dict = None):
        """
        Complement button datarefs with annunciator special lit datarefs
        """
        if self.all_datarefs is not None:  # cached
            logger.debug(f"get_datarefs: button {self.name}: returned from cache")
            return self.all_datarefs

        r = super().get_datarefs()
        a = self.get_annunciator_datarefs()
        if len(a) > 0:
            r = r + a
        if DATAREF_RPN in r:  # label: ${dataref-rpn}, DATAREF_RPN is not a dataref.
            r.remove(DATAREF_RPN)
        return list(set(r))

    # def button_level_driven(self) -> bool:
    #     """
    #     Determine if we need to consider either the global button-level value or
    #     individula part-level values
    #     """
    #     button_level = True
    #     part_has_rpn = {}
    #     # Is there material to decide at part level?
    #     parts = self.annunciator["parts"]
    #     for key in self.part_iterator():
    #         if key in parts:
    #             c = parts[key]
    #             part_has_rpn[key] = False
    #             if DATAREF_RPN in c or "dataref" in c:
    #                 button_level = False
    #             if DATAREF_RPN in c:
    #                 part_has_rpn[key] = True
    #             # else remains button-level True
    #     self.part_controls = part_has_rpn
    #     if not button_level:
    #         logger.debug(f"button_level_driven: button {self.name}: driven at part level")
    #         datarefs = self.get_annunciator_datarefs()
    #         if len(datarefs) < 1:
    #             logger.warning(f"button_level_driven: button {self.name}: no part dataref")
    #             if False in part_has_rpn:
    #                 logger.warning(f"button_level_driven: button {self.name}: some part has no dataref-rpn {part_has_rpn}")
    #                 return False
    #             else:
    #                 logger.debug(f"button_level_driven: button {self.name}: parts have dataref-rpn {part_has_rpn}")
    #         return False
    #     # Is there material to decide at button level?
    #     logger.debug(f"button_level_driven: button {self.name}: driven at button level")
    #     if self.dataref is None and self.datarefs is None and self.dataref_rpn is None:  # Airbus button is driven by button-level dataref
    #         logger.warning(f"button_level_driven: button {self.name}: no button dataref or dataref-rpn")
    #     return True

    def part_has_control(self, part: dict) -> bool:
        return DATAREF_RPN in part or "dataref" in part

    def part_value(self, part: dict, key: str = None):
        ret = None
        if DATAREF_RPN in part:
            calc = part[DATAREF_RPN]
            expr = self.substitute_dataref_values(calc)
            rpc = RPC(expr)
            ret = rpc.calculate()
            logger.debug(f"part_value: button {self.name}: {key}: {expr}={ret}")
        elif "dataref" in part:
            dataref = part["dataref"]
            ret = self.get_dataref_value(dataref)
            logger.debug(f"part_value: button {self.name}: {key}: {dataref}={ret}")
        else:
            logger.debug(f"part_value: button {self.name}: {key}: no formula, set to {ret}")
        return ret

    def button_value(self):
        """
        There is a button_value value per annunciator part.
        If part has not value or no wait to get value it is fetched from hosting button value.
        """
        button_level_value = super().button_value()

        r = {}
        parts = self.annunciator.get("parts")
        for key in self.part_iterator():
            if key in parts.keys():
                c = parts[key]
                if self.part_has_control(c):
                    v = self.part_value(parts[key], key)
                    logger.debug(f"button_value: button {self.name}: {key}: has control ({r})")
                    r[key] = 1 if v is not None and v > 0 else 0
                else:
                    logger.debug(f"button_value: button {self.name}: {key}: has no local control (button level value = {r})")
                    r[key] = 1 if button_level_value is not None and button_level_value > 0 else 0
            else:
                r[key] = 0
                logger.debug(f"button_value: button {self.name}: {key}: key not found, set to 0")
        # logger.debug(f"annunciator_button_value: button {self.name} returning: {r}")
        return r

    def set_key_icon(self):
        logger.debug(f"set_key_icon: button {self.name} has current value {self.current_value}")
        if self.current_value is not None and type(self.current_value) in [dict]:
            logger.debug(f"set_key_icon: button {self.name}: driven by part dataref")
            self.lit = {}
            for key in self.part_iterator():
                self.lit[key] = self.current_value[key] != 0
        elif self.current_value is not None and type(self.current_value) in [int, float]:
            logger.debug(f"set_key_icon: button {self.name}: driven by button-level dataref")
            self.lit = {}
            for key in self.part_iterator():
                self.lit[key] = self.current_value != 0
        logger.debug(f"set_key_icon: button {self.name}: {self.lit}")
        # else: leave untouched

    def get_image(self):
        """
        """
        self.set_key_icon()
        return self.mk_annunciator()

    def mk_annunciator(self):
        # If the part is not lit, a darker version is printed unless dark option is added to button
        # in which case nothing gets added to the button.
        # # CONSTANTS
        AC = {
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
        ICON_SIZE = 256  # px
        LED_HEIGHT = 40
        LED_BAR_HEIGHT = 12
        LED_BAR_COUNT = 3
        LED_BAR_SPACER = 4
        DOT_RADIUS = ICON_SIZE / 16
        SEAL_WIDTH = 8
        SQUARE = self.has_option("square")

        def light_off(color, lightness: float = LIGHT_OFF_BRIGHTNESS / 100):
            # Darkens (or lighten) a color
            if color.startswith("("):
                color = convert_color(color)
            if type(color) == str:
                color = ImageColor.getrgb(color)
            a = list(colorsys.rgb_to_hls(*[c / 255 for c in color]))
            a[1] = lightness
            return tuple([int(c * 256) for c in colorsys.hls_to_rgb(*a)])

        def get_color(disp:dict, lit: bool):
            color = disp.get("color")
            if color is None:
                logger.warning(f"mk_annunciator: button {self.name}: not color found, using grey")
                color = (128, 128, 128)
            if type(color) == tuple or type(color) == list:  # we transfort it back to a string, read on...
                color = "(" + ",".join([str(i) for i in color]) + ")"

            if not lit:
                try:
                    color = disp.get("off-color", light_off(color))
                except ValueError:
                    logger.debug(f"mk_annunciator: button {self.name}: color {color} ({type(color)}) not found, using grey")
                    color = (128, 128, 128)
            elif color.startswith("("):
                color = convert_color(color)
            else:
                try:
                    color = ImageColor.getrgb(color)
                except ValueError:
                    logger.debug(f"mk_annunciator: color {color} not found, using grey")
                    color = (128, 128, 128)
            return color

        def has_frame(part: dict):
            framed = part.get("framed")
            if framed is None:
                return False
            if type(framed) == bool:
                return framed
            elif type(framed) == int:
                return framed == 1
            elif type(framed) == str:
                return framed.lower() in ["true", "on", "yes", "1"]
            return False

        def get_text(base: dict, text_format: str = None):
            """
            Returns text, if any, with substitution of datarefs if any.
            Same as Button.get_label().
            """
            label = base.get("text")
            DATAREF_RPN_STR = f"${{{DATAREF_RPN}}}"

            # logger.debug(f"get_text: button {self.name}: raw: {label}")
            # If text contains ${dataref-rpn}, it is replaced by the value of the dataref-rpn calculation.
            # So we do it.
            if label is not None:
                if DATAREF_RPN_STR in label:
                    dataref_rpn = base.get(DATAREF_RPN)
                    if dataref_rpn is not None:
                        expr = self.substitute_dataref_values(dataref_rpn)
                        rpc = RPC(expr)
                        res = rpc.calculate()  # to be formatted
                        if text_format is None:
                            text_format = base.get("text-format")
                        if text_format is not None:
                            res = text_format.format(res)
                        else:
                            res = str(res)
                        label = label.replace(DATAREF_RPN_STR, res)
                    else:
                        logger.warning(f"get_text: button {self.name}: text contains {DATAREF_RPN_STR} not no attribute found")
                else:
                    label = self.substitute_dataref_values(label, formatting=text_format, default="---")
                # logger.debug(f"get_text: button {self.name}: returned: {label}")
            return label


        # MAIN
        logger.debug(f"mk_annunciator: button {self.name}: creating..")

        inside = ICON_SIZE / 32 # 8px

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

        parts = self.annunciator.get("parts")
        # DEBUG SIZES
        # logger.debug(f"mk_annunciator: " + "-" * 50)
        # logger.debug(f"mk_annunciator: button {self.name}: annunc {annun_width}x{annun_height}, offset ({width_offset}, {height_offset}), box {box}")
        # for partname in self.part_iterator():
        #     w, h = AC[partname]
        #     part_width = annun_width if w == 0.5 else annun_width / 2
        #     part_height = annun_height if h == 0.5 else annun_height / 2
        #     part_center_w = width_offset + int(w * annun_width)
        #     part_center_h = height_offset + int(h * annun_height)
        #     logger.debug(f"mk_annunciator: button {self.name}: part {partname}: {part_width}x{part_height}, center ({part_center_w}, {part_center_h})")
        # logger.debug(f"mk_annunciator: " + "-" * 50)
        for partname in self.part_iterator():
            part = parts.get(partname)
            if part is None:
                logger.warning(f"mk_annunciator: button {self.name}: part {partname}: nothing to display")
                continue

            w, h = AC[partname]
            part_width = annun_width if w == 0.5 else annun_width / 2
            part_height = annun_height if h == 0.5 else annun_height / 2
            part_center_w = int(w * annun_width)
            part_center_h = int(h * annun_height)

            TEXT_SIZE = int(part_height / 2)  # @todo: find optimum variable text size depending on text length

            is_lit = self.lit.get(partname, False)
            color = get_color(part, is_lit)

            # logger.debug(f"mk_annunciator: button {self.name}: annunc {annun_width}x{annun_height}, offset ({width_offset}, {height_offset}), box {box}")
            # logger.debug(f"mk_annunciator: button {self.name}: part {partname}: {part_width}x{part_height}, center ({part_center_w}, {part_center_h})")
            # logger.debug(f"mk_annunciator: button {self.name}: part {partname}: {is_lit}, {color}")

            txt = get_text(part)
            if txt is not None:
                #
                # Annunciator part will display text
                #
                text = get_text(part)  # part.get("text")
                if text is not None:
                    fontname = self.get_font(part.get("font"))
                    fontsize = int(part.get("font-size", TEXT_SIZE))
                    font = ImageFont.truetype(fontname, fontsize)
                    if is_lit or not self.page.annunciator_style == ANNUNCIATOR_STYLES.VIVISUN.value:
                        invert = part.get("invert")
                        if is_lit and invert is not None:
                            frame = ((part_center_w - part_width/2, part_center_h - part_height/2), (part_center_w + part_width/2, part_center_h + part_height/2))
                            invert_color = convert_color_string(invert)
                            bgrd_draw.rectangle(frame, fill=invert_color)

                        # logger.debug(f"mk_annunciator: button {self.name}: text '{text}' at ({part_center_w}, {part_center_h})")
                        draw.multiline_text((part_center_w, part_center_h),
                                  text=text,
                                  font=font,
                                  anchor="mm",
                                  align="center",
                                  fill=color)

                        if has_frame(part):
                            txtbb = draw.multiline_textbbox((part_center_w, part_center_h),  # min frame, just around the text
                                      text=text,
                                      font=font,
                                      anchor="mm",
                                      align="center")
                            text_margin = 3 * inside  # margin "around" text, line will be that far from text
                            framebb = ((txtbb[0]-text_margin, txtbb[1]-text_margin), (txtbb[2]+text_margin, txtbb[3]+text_margin))
                            side_margin = 4 * inside  # margin from side of part of annunciator
                            framemax = ((part_center_w - part_width/2 + side_margin, part_center_h - part_height/2 + side_margin), (part_center_w + part_width/2 - side_margin, part_center_h + part_height/2 - side_margin))
                            frame = ((min(framebb[0][0], framemax[0][0]),min(framebb[0][1], framemax[0][1])), (max(framebb[1][0], framemax[1][0]), max(framebb[1][1], framemax[1][1])))
                            thick = int(annun_height / 16)
                            # logger.debug(f"mk_annunciator: button {self.name}: part {partname}: {framebb}, {framemax}, {frame}")
                            draw.rectangle(frame, outline=color, width=thick)
            else:
                #
                # Annunciator part will display a LED
                #
                led = part.get("led")
                if led is not None:
                    ninside = 6
                    if led in ["block", "led"]:
                        if size == "large":
                            LED_HEIGHT = int(LED_HEIGHT * 1.25)
                        frame = ((part_center_w - part_width/2 + ninside * inside, part_center_h - LED_HEIGHT / 2), (part_center_w + part_width/2 - ninside * inside, part_center_h + LED_HEIGHT / 2))
                        draw.rectangle(frame, fill=color)
                    elif led in ["bar", "bars"]:
                        if size == "large":
                            LED_BAR_HEIGHT = int(LED_BAR_HEIGHT * 1.25)
                        hstart = part_center_h - (LED_BAR_COUNT * LED_BAR_HEIGHT + (LED_BAR_COUNT - 1) * LED_BAR_SPACER) / 2
                        for i in range(LED_BAR_COUNT):
                            frame = ((part_center_w - part_width/2 + ninside * inside, hstart), (part_center_w + part_width/2 - ninside * inside, hstart + LED_BAR_HEIGHT))
                            draw.rectangle(frame, fill=color)
                            hstart = hstart + LED_BAR_HEIGHT + LED_BAR_SPACER
                    elif led == "dot":
                        # Plot a series of circular dot on a line
                        frame = ((part_center_w - DOT_RADIUS, part_center_h - DOT_RADIUS), (part_center_w + DOT_RADIUS, part_center_h + DOT_RADIUS))
                        draw.ellipse(frame, fill=color)
                    elif led == "lgear":
                        vert_ninside = 4
                        origin = (part_center_w - part_width/2 + ninside * inside, part_center_h - part_height/2 + vert_ninside * inside)
                        triangle = [
                            origin,
                            (part_center_w + part_width/2 - ninside * inside, part_center_h - part_height/2 + vert_ninside * inside),
                            (part_center_w, part_center_h + part_height/2 - vert_ninside * inside),  # lower center point
                            origin
                        ]
                        thick = int(min(part_width, part_height) / 8)
                        draw.polygon(triangle, outline=color, width=thick)
                    else:
                        logger.warning(f"mk_annunciator: button {self.name}: part {partname}: invalid led {led}")
                else:
                    logger.warning(f"mk_annunciator: button {self.name}: part {partname}: no text, no led")


        # PART 1.2: Glowing texts, later because not nicely perfect.
        if self.page.annunciator_style == ANNUNCIATOR_STYLES.KORRY.value:
            # blurred_image = glow.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=10))
            blurred_image1 = glow.filter(ImageFilter.GaussianBlur(10)) # self.annunciator.get("blurr", 10)
            blurred_image2 = glow.filter(ImageFilter.GaussianBlur(4)) # self.annunciator.get("blurr", 10)
            # blurred_image = glow.filter(ImageFilter.BLUR)
            glow.alpha_composite(blurred_image1)
            glow.alpha_composite(blurred_image2)
            # glow = blurred_image
            # logger.debug("mk_annunciator: blurred")

        # PART 1.2: Make annunciator
        # Paste the transparent text/glow into the annunciator background (and optional seal):
        annunciator = Image.new(mode="RGB", size=(annun_width, annun_height), color=(0, 0, 0))
        annunciator.paste(bgrd)               # potential inverted colors
        annunciator.paste(glow, mask=glow)    # texts

        # PART 2: Background
        # Paste the annunciator into the button background:
        image = Image.new(mode="RGB", size=(ICON_SIZE, ICON_SIZE), color=self.page.cockpit_color)
        draw = ImageDraw.Draw(image)
        image.paste(annunciator, box=(int(width_offset), int(height_offset)))

        # PART 4: Guard
        # image.paste(guard)

        # PART 3: Title
        # Add a title on top, relative to box if requested
        if self.label is not None:
            title_pos = self.label_position
            fontname = self.get_font()
            fontsize = 2 * self.label_size
            font = ImageFont.truetype(fontname, fontsize)
            w = image.width / 2
            p = "m"
            a = "center"
            if title_pos[0] == "l":
                w = inside
                p = "l"
                a = "left"
            elif title_pos[0] == "r":
                w = image.width - inside
                p = "r"
                a = "right"

            b = box[1]
            h = 1 + max(b, self.label_size) / 2  # smallest to fit text
            # logger.debug(f"mk_annunciator: button {self.name}: label '{self.label}' at ({w}, {h}) (box: {box})")
            draw.multiline_text((w, h),  # (image.width / 2, 15)
                      text=self.label,
                      font=font,
                      anchor=p+"m",
                      align=a,
                      fill=self.label_color)

        logger.debug(f"mk_annunciator: button {self.name}: ..done")

        return image


class AnnunciatorButtonPush(AnnunciatorButton):
    """
    Execute command once when key pressed. Nothing is done when button is released.
    """
    def __init__(self, config: dict, page: "Page"):
        AnnunciatorButton.__init__(self, config=config, page=page)

    def is_valid(self):
        if self.command is None:
            logger.warning(f"is_valid: button {self.name} has no command")
            if not self.has_option("counter"):
                logger.warning(f"is_valid: button {self.name} has no command or counter option")
                return False
        return super().is_valid()

    def activate(self, state: bool):
        # logger.debug(f"ButtonPush::activate: button {self.name}: {state}")
        super().activate(state)
        if state:
            if self.is_valid():
                if self.command is not None:
                    self.xp.commandOnce(self.command)
                self.render()
            else:
                logger.warning(f"activate: button {self.name} is invalid")


class AnnunciatorButtonAnimate(AnnunciatorButton):
    """
    """
    def __init__(self, config: dict, page: "Page"):
        self.running = None  # state unknown
        self.thread = None
        self.finished = None
        self.counter = 0
        AnnunciatorButton.__init__(self, config=config, page=page)
        self.speed = float(self.option_value("animation_speed", 0.5))

        self.render()

    def should_run(self):
        """
        Check conditions to animate the icon.
        """
        logger.debug(f"should_run: button {self.name}: current value {self.current_value}, ({type(self.current_value)})")
        # If computed value:
        if self.has_option("counter"):
            self.current_value = self.pressed_count % 2 if self.pressed_count is not None else 0
            logger.debug(f"should_run: button {self.name}: current counter value {self.current_value}")
            return self.current_value == 0

        if self.current_value is None:
            logger.debug(f"should_run: button {self.name}: current value is None, returning False")
            return False

        # If scalar value:
        if type(self.current_value) in [int, float]:
            logger.debug(f"should_run: button {self.name}: current value is integer")
            if self.has_option("inverted_logic"):
                logger.debug(f"should_run: button {self.name}: inverted logic")
                return self.current_value == 0
            return self.current_value != 0

        # If array or tuple value
        for i in self.current_value:
            if i is not None:
                if type(i) == bool and i != False:
                    logger.debug(f"should_run: button {self.name}: complex current bool value {i}, returning True")
                    return True
                elif type(i) == int and i != 0:
                    logger.debug(f"should_run: button {self.name}: complex current int value {i}, returning True")
                    return True
                # else, do nothing, False assumed ("no clear sign to set it True")
            # else, do nothing, None assumed False
        logger.debug(f"should_run: button {self.name}: complex current value {self.current_value}, returning False")
        return False  # all individual scalar in array or tuple are None, or 0, or False

    def loop(self):
        self.finished = threading.Event()
        while self.running:
            self.render()
            self.counter = self.counter + 1
            time.sleep(self.speed)
        self.finished.set()

    def anim_start(self):
        if not self.running:
            logger.debug(f"anim_start: button {self.name}: starting..")
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.name = f"AnnunciatorButtonAnimate::loop({self.name})"
            self.thread.start()
            logger.debug(f"anim_start: button {self.name}: ..started")
        else:
            logger.warning(f"anim_start: button {self.name}: already started")

    def anim_stop(self):
        if self.running:
            logger.debug(f"anim_stop: button {self.name}: stopping..")
            self.running = False
            if not self.finished.wait(timeout=2*self.speed):
                logger.warning(f"anim_stop: button {self.name}: did not get finished signal")
            logger.debug(f"anim_start: button {self.name}: ..stopped")
            self.render()
        else:
            logger.debug(f"anim_stop: button {self.name}: already stopped")

    def set_key_icon(self):
        """
        If button has more icons, select one from button current value
        """
        if self.running:
            for k in self.lit.keys():
                self.lit[k] = not self.lit[k]
#            logger.debug(f"set_key_icon: button {self.name}: running")
        else:
#            logger.debug(f"set_key_icon: button {self.name}: NOT running")
            for k in self.lit.keys():
                self.lit[k] = False
            super().set_key_icon()  # set off icon

    # Works with activation on/off
    def activate(self, state: bool):
        super().activate(state)
        if state:
            if self.is_valid():
                # self.label = f"pressed {self.current_value}"
                self.xp.commandOnce(self.command)
                if self.should_run():
                    self.anim_start()
                else:
                    self.anim_stop()
                    self.render()  # renders default "off" icon
        logger.debug(f"activate: button {self.name}: {self.pressed_count}")

    # Works if underlying dataref changed
    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        self.set_current_value(self.button_value())
        logger.debug(f"{self.name}: {self.previous_value} -> {self.current_value}")
        if self.should_run():
            self.anim_start()
        else:
            self.anim_stop()
            self.render()  # renders default "off" icon

    def render(self):
        if self.running is None:  # state unknown?
            logger.debug(f"render: button {self.name}: unknown state")
            if self.should_run():
                self.anim_start()
            else:
                logger.debug(f"render: button {self.name}: stopping..")
                self.anim_stop()
                super().render() # renders default "off" icon
            logger.debug(f"render: button {self.name}: ..done")
        else:
            super().render()

    def clean(self):
        logger.debug(f"clean: button {self.name}: asking to stop..")
        self.anim_stop()
        self.running = None  # unknown state
        logger.debug(f"clean: button {self.name}: ..stopped")
