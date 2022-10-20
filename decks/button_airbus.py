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

from .constant import AIRBUS_DEFAULTS, LIGHT_OFF_BRIGHTNESS
from .button_core import Button
from .rpc import RPC

logger = logging.getLogger("AirbusButton")
logger.setLevel(logging.DEBUG)


class AirbusButton(Button):

    def __init__(self, config: dict, page: "Page"):

        self.lit_display = False
        self.lit_dual = False

        self.multi_icons = config.get("multi-icons")
        self.icon = config.get("icon")

        self.airbus = None                   # working def
        self._airbus = config.get("airbus")  # keep raw
        if self._airbus is not None:
            self.airbus = merge({}, AIRBUS_DEFAULTS, self._airbus)
        else:
            logger.error(f"__init__: button {self.name}: has no airbus property")

        Button.__init__(self, config=config, page=page)

        if self.airbus is not None and (config.get("icon") is not None or config.get("multi-icons") is not None):
            logger.warning(f"__init__: button {self.name}: has airbus property with icon/multi-icons, ignoring icons")

        if self.airbus is not None:
            self.icon = None
            self.multi_icons = None

    def get_datarefs(self, base:dict = None):
        """
        Complement button datarefs with airbus special lit datarefs
        """
        if self.all_datarefs is not None:  # cached
            return self.all_datarefs

        r = super().get_datarefs()
        for key in ["display", "dual"]:
            if key in self.airbus:
                datarefs = super().get_datarefs(base=self.airbus[key])
                if len(datarefs) > 0:
                    r = r + datarefs
                    logger.debug(f"get_datarefs: button {self.name}: added {key} datarefs {datarefs}")
        return r

    def button_value(self):
        """
        Same as button value, but exclusively for Airbus-type buttons.
        We basically check with the supplied dataref/dataref-rpn that the button is lit or not.
        """
        r = []
        for key in ["display", "dual"]:
            if key in self.airbus:
                c = self.airbus[key]
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
        # logger.debug(f"airbus_button_value: button {self.name} returning: {r}")
        return r

    def set_key_icon(self):
        if self.current_value is not None and type(self.current_value) == list and len(self.current_value) > 1:
            self.lit_display = (self.current_value[0] != 0)
            self.lit_dual = (self.current_value[1] != 0)
        # else: leave untouched

    def get_image(self):
        """
        """
        self.set_key_icon()
        return self.mk_airbus()

    def mk_airbus(self):
        # If the display or dual is not lit, a darker version is printed unless dark option is added to button
        # in which case nothing gets added to the button.

        def light_off(color, lightness: float = LIGHT_OFF_BRIGHTNESS / 100):
            # Darkens (or lighten) a color
            if type(color) == str:
                color = ImageColor.getrgb(color)
            a = list(colorsys.rgb_to_hls(*[c / 255 for c in color]))
            a[1] = lightness
            return tuple([int(c * 256) for c in colorsys.hls_to_rgb(*a)])

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

        ICON_SIZE = 256  # px
        inside = ICON_SIZE / 32 # 8px

        # Button
        #
        # Overall button size: full, large, medium, small.
        #
        size = self.airbus.get("size", "large")
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
        display = self.airbus.get("display")
        dual    = self.airbus.get("dual")

        if display is not None:
            display_pos = display.get("position", "mm")
            text = display.get("text")
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
                # logger.debug(f"mk_airbus: position {display_pos}: {(w, h)}, {dual}")
                color = display.get("color")
                if not self.lit_display:
                    color = display.get("off-color", light_off(color))
                if self.lit_display or not self.has_option("dark"):
                    draw.multiline_text((w, h),  # (glow.width / 2, 15)
                              text=display.get("text"),
                              font=font,
                              anchor=p+"m",
                              align=a,
                              fill=color)
                else:
                    logger.debug("mk_airbus: full dark display")
            else:
                # If there is no text, we display a LED light.
                # For large and medium, it is a 3 LED bar light
                # For small, it is a single block LED.
                # Alternatively, it can be a series of circular dots (options: dot=3)
                color = display.get("color")
                if not self.lit_display:
                    color = display.get("off-color", light_off(color))

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
                    if size == "small":  # 1 horizontal leds
                        thick = 30
                        dot_height = button_height / 2 - thick
                        frame = ((dot_left, dot_height), (glow.width - dot_left, dot_height + thick))
                        draw.rectangle(frame, fill=color)
                    else:  # 3 horizontal leds
                        thick = 10             # LED thickness
                        dot_height = button_height / 4 - 1.5 * thick - (16 - thick)
                        for i in range(3):
                            s = dot_height + i * 16
                            frame = ((dot_left, s), (glow.width - dot_left, s+thick))
                            draw.rectangle(frame, fill=color)

        # 1.2 Optional second/bottom item (called "dual")
        if dual is not None:
            dual_pos = dual.get("position", "mm")
            text = dual.get("text")
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
                # logger.debug(f"mk_airbus: {dual.get('text')}: size {dual.get('size')}, position {dual_pos}: {(w, h)}")

                color = dual.get("color")
                if not self.lit_dual:
                    color = dual.get("off-color", light_off(color))

                if self.lit_dual or not self.has_option("dark"):
                    draw.multiline_text((w, h),
                              text=dual.get("text"),
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
            blurred_image1 = glow.filter(ImageFilter.GaussianBlur(16)) # self.airbus.get("blurr", 10)
            blurred_image2 = glow.filter(ImageFilter.GaussianBlur(6)) # self.airbus.get("blurr", 10)
            # blurred_image = glow.filter(ImageFilter.BLUR)
            glow.alpha_composite(blurred_image1)
            glow.alpha_composite(blurred_image2)
            # glow = blurred_image
            # logger.debug("mk_airbus: blurred")

        # We paste the transparent glow into a button:
        button = Image.new(mode="RGB", size=(ICON_SIZE, button_height), color=self.airbus.get("color", "black"))
        button.paste(glow, mask=glow)

        # Background
        image = Image.new(mode="RGB", size=(ICON_SIZE, ICON_SIZE), color=self.airbus.get("background", "lightsteelblue"))
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
            h = size / 2  # middle of "title" box
            # logger.debug(f"mk_airbus: position {title_pos}: {(w, h)}")
            draw.multiline_text((w, h),  # (image.width / 2, 15)
                      text=self.label,
                      font=font,
                      anchor=p+"m",
                      align=a,
                      fill=self.label_color)

        # Button
        image.paste(button, box=box)

        # logger.debug(f"mk_airbus: button {self.name}: ..done")

        return image


class AirbusButtonPush(AirbusButton):
    """
    Execute command once when key pressed. Nothing is done when button is released.
    """
    def __init__(self, config: dict, page: "Page"):
        AirbusButton.__init__(self, config=config, page=page)

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


class AirbusButtonAnimate(AirbusButton):
    """
    """
    def __init__(self, config: dict, page: "Page"):
        self.running = False
        self.thread = None
        self.finished = None
        self.counter = 0
        AirbusButton.__init__(self, config=config, page=page)
        self.speed = float(self.option_value("animation_speed", 0.5))

    def loop(self):
        self.finished = threading.Event()
        while self.running:
            self.render()
            self.counter = self.counter + 1
            time.sleep(self.speed)
        self.finished.set()

    def anim_start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.name = f"button {self.name} animation"
            self.thread.start()
        else:
            logger.warning(f"anim_start: button {self.name}: already started")

    def anim_stop(self):
        if self.running:
            self.running = False
            if not self.finished.wait(timeout=2*self.speed):
                logger.warning(f"anim_stop: button {self.name}: did not get finished signal")
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
        else:
            super().set_key_icon()  # off

    # Works with activation on/off
    def activate(self, state: bool):
        super().activate(state)
        if state:
            if self.is_valid():
                # self.label = f"pressed {self.current_value}"
                self.xp.commandOnce(self.command)
                if self.pressed_count % 2 == 0:
                    self.anim_stop()
                    self.render()
                else:
                    self.anim_start()

    # Works if underlying dataref changed
    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        self.set_current_value(self.button_value())
        logger.debug(f"{self.name}: {self.previous_value} -> {self.current_value}")
        if self.current_value is not None and self.current_value == 1:
            self.anim_start()
        else:
            if self.running:
                self.anim_stop()
            self.render()

    def clean(self):
        self.anim_stop()
