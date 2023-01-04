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

from .constant import ANNUNCIATOR_DEFAULTS, LIGHT_OFF_BRIGHTNESS, convert_color, print_stack
from .button_core import Button
from .rpc import RPC

logger = logging.getLogger("AnnunciatorButton")
# logger.setLevel(logging.DEBUG)


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

        self.lit_display = False
        self.lit_dual = False

        self.multi_icons = config.get("multi-icons")
        self.icon = config.get("icon")

        self.annunciator = None                   # working def
        self.annunciator_datarefs = None          # cache
        self._annunciator = config.get("annunciator")  # keep raw
        if self._annunciator is not None:
            self.annunciator = merge({}, ANNUNCIATOR_DEFAULTS, self._annunciator)
        else:
            logger.error(f"__init__: button {self.name}: has no annunciator property")

        Button.__init__(self, config=config, page=page)

        if self.annunciator is not None and (config.get("icon") is not None or config.get("multi-icons") is not None):
            logger.warning(f"__init__: button {self.name}: has annunciator property with icon/multi-icons, ignoring icons")

        if self.annunciator is not None:
            self.icon = None
            self.multi_icons = None

    def get_annunciator_datarefs(self, base:dict = None):
        """
        Complement button datarefs with annunciator special lit datarefs
        """
        # print_stack(logger)
        if self.annunciator_datarefs is not None:
            # logger.debug(f"get_annunciator_datarefs: button {self.name}: returned from cache")
            return self.annunciator_datarefs
        r = []
        for key in ["display", "dual"]:
            if key in self.annunciator:
                datarefs = super().get_datarefs(base=self.annunciator[key])
                if len(datarefs) > 0:
                    self.annunciator_datarefs = datarefs
                    r = r + datarefs
                    logger.debug(f"get_annunciator_datarefs: button {self.name}: added {key} datarefs {datarefs}")
        return list(set(r))

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
        if "dataref-rpn" in r:  # label: ${dataref-rpn}, "dataref-rpn" is not a dataref.
            r.remove("dataref-rpn")
        return list(set(r))

    def button_level_driven(self) -> bool:
        """
        Determine if we need to consider either the global button-level value or
        individula display/dual -level values
        """
        button_level = True
        # Is there material to decide at display/dual level?
        for key in ["display", "dual"]:
            if key in self.annunciator:
                c = self.annunciator[key]
                if "dataref-rpn" in c or "dataref" in c:
                    button_level = False
                # else remains button-level True
        if not button_level:
            logger.debug(f"button_level_driven: button {self.name}: driven at display/dual level")
            datarefs = self.get_annunciator_datarefs()
            if len(datarefs) < 1:
                logger.warning(f"button_level_driven: button {self.name}: no display/dual dataref")
            return False
        # Is there material to decide at button level?
        logger.debug(f"button_level_driven: button {self.name}: driven at button level")
        if self.dataref is None and self.datarefs is None and self.dataref_rpn is None:  # Airbus button is driven by button-level dataref
            logger.warning(f"button_level_driven: button {self.name}: no button dataref")
        return True

    def button_value(self):
        """
        Same as button value, but exclusively for Airbus-type buttons with two distinct values (display and dual).
        If button is driven by single dataref, we forward to button class.
        Else, we basically check with the supplied dataref/dataref-rpn that the button is lit or not for each button part.
        """
        r = []
        if self.button_level_driven():
            logger.debug(f"button_value: button {self.name}: driven by button-level dataref")
            return super().button_value()

        for key in ["display", "dual"]:
            if key in self.annunciator:
                c = self.annunciator[key]
                if "dataref-rpn" in c:
                    calc = c["dataref-rpn"]
                    expr = self.substitute_dataref_values(calc)
                    rpc = RPC(expr)
                    res = rpc.calculate()
                    logger.debug(f"button_value: button {self.name}: {key}: {expr}={res}")
                    r.append(1 if (res is not None and res > 0) else 0)
                elif "dataref" in c:
                    dataref = c["dataref"]
                    res = self.get_dataref_value(dataref)
                    logger.debug(f"button_value: button {self.name}: {key}: {dataref}={res}")
                    r.append(1 if (res is not None and res > 0) else 0)
                else:
                    logger.debug(f"button_value: button {self.name}: {key}: no formula, set to 0")
                    r.append(0)
            else:
                r.append(0)
                logger.debug(f"button_value: button {self.name}: {key}: key not found, set to 0")
        # logger.debug(f"annunciator_button_value: button {self.name} returning: {r}")
        return r

    def set_key_icon(self):
        logger.debug(f"set_key_icon: button {self.name} has current value {self.current_value}")
        if self.current_value is not None and type(self.current_value) in [list, tuple] and len(self.current_value) > 1:
            logger.debug(f"set_key_icon: button {self.name}: driven by display/dual-level dataref")
            self.lit_display = (self.current_value[0] != 0)
            self.lit_dual = (self.current_value[1] != 0)
        elif self.current_value is not None and type(self.current_value) in [int, float]:
            logger.debug(f"set_key_icon: button {self.name}: driven by button-level dataref")
            self.lit_display = (self.current_value != 0)
            self.lit_dual = (self.current_value != 0)
        # else: leave untouched

    def get_image(self):
        """
        """
        self.set_key_icon()
        return self.mk_annunciator()

    def mk_annunciator(self):
        # If the display or dual is not lit, a darker version is printed unless dark option is added to button
        # in which case nothing gets added to the button.

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
            if type(color) == tuple or type(color) == list:  # we transfort it back to a string, read on...
                color = "(" + ",".join([str(i) for i in color]) + ")"

            if not lit:
                try:
                    color = display.get("off-color", light_off(color))
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
            DATAREF_RPN = "${dataref-rpn}"
            label = base.get("text")

            # logger.debug(f"get_text: button {self.name}: raw: {label}")
            # If text contains ${dataref-rpn}, it is replaced by the value of the dataref-rpn calculation.
            # So we do it.
            if label is not None:
                if DATAREF_RPN in label:
                    dataref_rpn = base.get("dataref-rpn")
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
                        label = label.replace(DATAREF_RPN, res)
                    else:
                        logger.warning(f"get_text: button {self.name}: text contains {DATAREF_RPN} not no attribute found")
                else:
                    label = self.substitute_dataref_values(label, formatting=text_format, default="---")
                # logger.debug(f"get_text: button {self.name}: returned: {label}")
            return label


        ICON_SIZE = 256  # px
        inside = ICON_SIZE / 32 # 8px

        # Button
        #
        # Overall button size: full, large, medium, small.
        #
        size = self.annunciator.get("size", "large")
        if size == "small":  # about 1/2, starts at 128
            button_height = int(ICON_SIZE / 2)
            box = (0, int(ICON_SIZE/4))
        elif size == "medium":  # about 2/3, starts at 96
            button_height = int(10 * ICON_SIZE / 16)
            box = (0, int(3 * ICON_SIZE / 16))
        elif size == "full":  # starts at 0
            button_height = ICON_SIZE
            box = (0, 0)
        else:  # "large", full size, default, starts at 48
            button_height = int(13 * ICON_SIZE / 16)
            box = (0, int(3 * ICON_SIZE / 16))

        led_offset = inside

        # PART 1:
        # Texts that will glow
        glow = Image.new(mode="RGBA", size=(ICON_SIZE, button_height), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)

        # 1.1 First/top/main item (called "display")
        display = self.annunciator.get("display")
        dual = self.annunciator.get("dual")

        if display is not None:
            display_pos = display.get("position", "mm")
            text = get_text(display)  # display.get("text")
            if text is not None:
                fontname = self.get_font(display.get("font"))
                font = ImageFont.truetype(fontname, display.get("size"))
                w = glow.width / 2
                p = "m"
                a = "center"
                if display_pos[0] == "l":
                    w = inside
                    p = "l"
                    a = "left"
                elif display_pos[0] == "r":
                    w = glow.width - inside
                    p = "r"
                    a = "right"
                h = int(button_height / 2)  # center of button
                if dual is not None and dual.get("text") is not None: # middle of top part
                    h = int(button_height / 4)
                # logger.debug(f"mk_annunciator: position {display_pos}: {(w, h)}, {dual}")
                color = get_color(display, self.lit_display)
                if self.lit_display or not self.has_option("dark"):
                    draw.multiline_text((w, h),  # (glow.width / 2, 15)
                              text=text,
                              font=font,
                              anchor=p+"m",
                              align=a,
                              fill=color)
                else:
                    logger.debug("mk_annunciator: full dark display")
            else:
                # If there is no text, we display a LED light.
                # For large and medium, it is a 3 LED bar light
                # For small, it is a single block LED.
                # Alternatively, it can be a series of circular dots (options: dot=3)
                color = get_color(display, self.lit_display)
                if self.has_option("dot"):
                    # Plot a series of circular dot on a line
                    ndot = self.option_value("dot", default=2)
                    ndot = 2 if type(ndot) == bool else int(ndot)
                    radius = ICON_SIZE / 16  # LED diameter
                    space  = (ICON_SIZE - 2 * inside) / ndot  # space between dots, tries to evenly space them "inside" button space
                    dot_left = ICON_SIZE / 2 - ((ndot - 1) * space) / 2
                    dot_height = button_height / 2 # Middle of button
                    if dual is not None:
                        dot_height = button_height / 4 # middle of button's top half
                    for i in range(ndot):
                        frame = ((dot_left + i * space - radius, dot_height - radius), (dot_left + i * space + radius, dot_height + radius))
                        draw.ellipse(frame, fill=color)
                else:
                    # Plot one or three LED bars.
                    dot_left = ICON_SIZE / 4      # space left and right of LED
                    if self.has_option("single_led"):  # single horizontal led
                        thick = 30
                        if size == "large":
                            thick = 40
                        dot_height = button_height / 2 - thick
                        frame = ((dot_left, dot_height), (glow.width - dot_left, dot_height + thick))
                        draw.rectangle(frame, fill=color)
                    else:  # 3 horizontal leds
                        thick = 10             # LED thickness
                        if size == "small":
                            thick = 6
                        dot_height = button_height / 4 - 1.5 * thick - (16 - thick)
                        for i in range(3):
                            s = dot_height + i * 16
                            frame = ((dot_left, s), (glow.width - dot_left, s+thick))
                            draw.rectangle(frame, fill=color)

        # 1.2 Optional second/bottom item (called "dual")
        if dual is not None:
            dual_pos = dual.get("position", "mm")
            text = get_text(dual)  # = dual.get("text")
            if text is not None:
                fontname = self.get_font(dual.get("font"))
                font = ImageFont.truetype(fontname, dual.get("size"))
                w = glow.width / 2
                p = "m"
                a = "center"
                if dual_pos[0] == "l":
                    w = inside
                    p = "l"
                    a = "left"
                elif dual_pos[0] == "r":
                    w = glow.width - inside
                    p = "r"
                    a = "right"
                h = int(3 * button_height / 4)  # middle of bottom part
                # logger.debug(f"mk_annunciator: {dual.get('text')}: size {dual.get('size')}, position {dual_pos}: {(w, h)}")
                color = get_color(dual, self.lit_dual)
                if self.lit_dual or not self.has_option("dark"):
                    draw.multiline_text((w, h),
                              text=text,
                              font=font,
                              anchor=p+"m",
                              align=a,
                              fill=color)
                    if has_frame(dual):
                        txtbb = draw.multiline_textbbox((w, h),  # min frame, just around the text
                                  text=dual.get("text"),
                                  font=font,
                                  anchor=p+"m",
                                  align=a)
                        margin = 3 * inside
                        framebb = ((txtbb[0]-margin, txtbb[1]-margin), (txtbb[2]+margin, txtbb[3]+margin))

                        start = button_height / 2 + inside      # max frame, just inside button
                        height = int(button_height / 2 - 2 * inside)
                        thick = int(button_height / 16)
                        e = inside * 4
                        framemax = ((e, start), (glow.width-e, start + height))
                        # optimal frame, largest possible in button and that surround text
                        frame = ((min(framebb[0][0], framemax[0][0]),min(framebb[0][1], framemax[0][1])), (max(framebb[1][0], framemax[1][0]), max(framebb[1][1], framemax[1][1])))
                        draw.rectangle(frame, outline=color, width=thick)

        # Glowing texts, later because not nicely perfect.
        if not self.has_option("no_blurr") or self.has_option("sharp"):
            # blurred_image = glow.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=10))
            blurred_image1 = glow.filter(ImageFilter.GaussianBlur(16)) # self.annunciator.get("blurr", 10)
            blurred_image2 = glow.filter(ImageFilter.GaussianBlur(6)) # self.annunciator.get("blurr", 10)
            # blurred_image = glow.filter(ImageFilter.BLUR)
            glow.alpha_composite(blurred_image1)
            glow.alpha_composite(blurred_image2)
            # glow = blurred_image
            # logger.debug("mk_annunciator: blurred")

        # We paste the transparent glow into a button:
        color = get_color(self.annunciator, True)
        button = Image.new(mode="RGB", size=(ICON_SIZE, button_height), color=color)
        button.paste(glow, mask=glow)

        # Background
        image = Image.new(mode="RGB", size=(ICON_SIZE, ICON_SIZE), color=self.annunciator.get("background", "lightsteelblue"))
        draw = ImageDraw.Draw(image)

        # Title
        if self.label is not None:
            title_pos = self.label_position
            fontname = self.get_font()
            size = 2 * self.label_size
            font = ImageFont.truetype(fontname, size)
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
            h = (box[1] + self.label_size ) / 2  # middle of "title" box
            # logger.debug(f"mk_annunciator: position {title_pos}: {(w, h)}")
            draw.multiline_text((w, h),  # (image.width / 2, 15)
                      text=self.label,
                      font=font,
                      anchor=p+"m",
                      align=a,
                      fill=self.label_color)

        # Button
        image.paste(button, box=box)

        # logger.debug(f"mk_annunciator: button {self.name}: ..done")

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
            self.lit_display = not self.lit_display
            self.lit_dual = not self.lit_dual
#            logger.debug(f"set_key_icon: button {self.name}: running")
        else:
#            logger.debug(f"set_key_icon: button {self.name}: NOT running")
            self.lit_display = False
            self.lit_dual = False
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
