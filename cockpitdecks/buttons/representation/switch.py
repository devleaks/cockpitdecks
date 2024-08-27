# ###########################
# Buttons that are drawn on render()
#
import logging
import math
from random import randint
from enum import Enum

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.resources.iconfonts import ICON_FONTS

from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR, convert_color, light_off
from .draw import DrawBase  # explicit Icon from file to avoid circular import

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# SWITCH BUTTON REPRESENTATION
#
#
def grey(i: int):
    return (i, i, i)


class SWITCH_STYLE(Enum):
    ROUND = "round"
    FLAT = "rect"
    RECT = "rect"
    DOT3 = "3dot"


SWITCH_BASE_FILL_COLOR = grey(40)
SWITCH_BASE_STROKE_COLOR = grey(240)
SWITCH_BASE_UNDERLINE_COLOR = "orange"

SCREW_HOLE_COLOR = grey(80)
SCREW_HOLE_UNDERLINE = grey(40)
SCREW_HOLE_UWIDTH = 1

SWITCH_HANDLE_BASE_COLOR = grey(200)

SWITCH_HANDLE_FILL_COLOR = grey(140)
SWITCH_HANDLE_STROKE_COLOR = grey(230)

SWITCH_HANDLE_TOP_FILL_COLOR = grey(100)
SWITCH_HANDLE_TOP_STROKE_COLOR = grey(150)

HANDLE_TIP_COLOR = grey(255)

NEEDLE_COLOR = grey(255)
NEEDLE_UNDERLINE_COLOR = grey(0)
MARKER_COLOR = "lime"

TICK_COLOR = grey(255)
LABEL_COLOR = grey(255)


class SwitchBase(DrawBase):

    REPRESENTATION_NAME = "switch-base"

    def __init__(self, button: "Button", switch_type: str):
        DrawBase.__init__(self, button=button)

        self.switch = self._config.get(switch_type)
        if self.switch is None:
            logger.warning("no switch configuration")
            return

        self.switch_type: str | None = self.switch.get("type")
        self.switch_style: str | None = self.switch.get("switch-style")

        # Base and handle
        self.button_size = self.switch.get("button-size", int(2 * ICON_SIZE / 4))
        self.button_fill_color = self.get_attribute("button-fill-color", SWITCH_BASE_FILL_COLOR)
        self.button_fill_color = convert_color(self.button_fill_color)
        self.button_stroke_color = self.get_attribute("button-stroke-color", SWITCH_BASE_STROKE_COLOR)
        self.button_stroke_color = convert_color(self.button_stroke_color)
        self.button_stroke_width = self.get_attribute("button-stroke-width", 2)
        self.button_underline_color = self.get_attribute("button-underline-color", SWITCH_BASE_UNDERLINE_COLOR)
        self.button_underline_color = convert_color(self.button_underline_color)
        self.button_underline_width = self.get_attribute("button-underline-width", 0)

        self.handle_base_fill_color = self.get_attribute("handle-fill-color", SWITCH_HANDLE_BASE_COLOR)
        self.handle_base_fill_color = convert_color(self.handle_base_fill_color)

        self.handle_fill_color = self.get_attribute("handle-fill-color", SWITCH_HANDLE_FILL_COLOR)
        self.handle_fill_color = convert_color(self.handle_fill_color)
        self.handle_stroke_color = self.get_attribute("handle-stroke-color", SWITCH_HANDLE_STROKE_COLOR)
        self.handle_stroke_color = convert_color(self.handle_stroke_color)
        self.handle_stroke_width = self.get_attribute("handle-stroke-width", 0)

        self.top_fill_color = self.get_attribute("top-fill-color", SWITCH_HANDLE_TOP_FILL_COLOR)
        self.top_fill_color = convert_color(self.top_fill_color)
        self.top_stroke_color = self.get_attribute("top-stroke-color", SWITCH_HANDLE_TOP_STROKE_COLOR)
        self.top_stroke_color = convert_color(self.top_stroke_color)
        self.top_stroke_width = self.get_attribute("top-stroke-width", 2)

        self.handle_tip_fill_color = self.get_attribute("handle-fill-color", HANDLE_TIP_COLOR)
        self.handle_tip_fill_color = convert_color(self.handle_tip_fill_color)

        # Ticks
        self.tick_space = self.get_attribute("tick-space", 10)
        self.tick_length = self.get_attribute("tick-length", 16)
        self.tick_width = self.get_attribute("tick-width", 4)
        self.tick_color = self.get_attribute("tick-color", TICK_COLOR)
        self.tick_color = convert_color(self.tick_color)
        self.tick_underline_color = self.get_attribute("tick-underline-color", TICK_COLOR)
        self.tick_underline_color = convert_color(self.tick_underline_color)
        self.tick_underline_width = self.get_attribute("tick-underline-width", 4)

        # Labels
        self.tick_labels = self.switch.get("tick-labels", {})
        self.tick_label_space = self.get_attribute("tick-label-space", 10)
        self.tick_label_font = self.get_attribute("tick-label-font", self.get_attribute("label-font"))
        self.tick_label_size = self.get_attribute("tick-label-size", 50)
        self.tick_label_color = self.get_attribute("tick-label-color", LABEL_COLOR)
        self.tick_label_color = convert_color(self.tick_label_color)

        # Handle needle
        self.needle_width = self.get_attribute("needle-width", 8)
        self.needle_start = self.get_attribute("needle-start", 10)  # from center of button
        self.needle_length = self.get_attribute("needle-length", 50)  # end = start + length
        self.needle_tip = self.switch.get("needle-tip")  # arro, arri, ball
        self.needle_tip_size = self.get_attribute("needle-tip-size", 5)
        # self.needle_length = int(self.needle_length * self.button_size / 200)
        self.needle_color = self.get_attribute("needle-color", NEEDLE_COLOR)
        self.needle_color = convert_color(self.needle_color)
        # Options
        self.needle_underline_width = self.get_attribute("needle-underline-width", 4)
        self.needle_underline_color = self.get_attribute("needle-underline-color", NEEDLE_UNDERLINE_COLOR)
        self.needle_underline_color = convert_color(self.needle_underline_color)

        self.marker_color = self.get_attribute("marker-color", MARKER_COLOR)

        # Reposition for move_and_send(), found locally in switch config
        self.draw_scale = float(self.switch.get("scale", 1))
        if self.draw_scale < 0.5 or self.draw_scale > 2:
            logger.warning(f"button {self.button.name}: invalid scale {self.draw_scale}, must be in interval [0.5, 2]")
            self.draw_scale = 1
        self.draw_left = self.switch.get("left", 0) - self.switch.get("right", 0)
        self.draw_up = self.switch.get("up", 0) - self.switch.get("down", 0)


class CircularSwitch(SwitchBase):

    REPRESENTATION_NAME = "circular-switch"

    def __init__(self, button: "Button"):
        SwitchBase.__init__(self, button=button, switch_type="circular-switch")

        if self.switch is None:
            logger.warning("no switch configuration")
            return

        self.tick_from = self.switch.get("tick-from", 90)
        self.tick_to = self.switch.get("tick-to", 270)
        if hasattr(self.button._activation, "stops"):
            self.tick_steps = self.button._activation.stops
            logger.debug(f"button {self.button.name}: button has {self.tick_steps} steps")
        else:
            self.tick_steps = self.switch.get("tick-steps", 2)
        if self.tick_steps < 2:
            logger.warning(f"button {self.button.name}: insuficient number of steps: {self.tick_steps}, forcing 2")
            self.tick_steps = 2
        logger.debug(f"button {self.button.name}: {self.tick_steps} steps")
        self.angular_step = (self.tick_to - self.tick_from) / (self.tick_steps - 1)
        if len(self.tick_labels) < self.tick_steps:
            logger.warning(f"button {self.button.name}: not enough label ({len(self.tick_labels)}/{self.tick_steps})")

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """

        def red(a):
            # reduce a to [0, 360[
            if a >= 360:
                return red(a - 360)
            elif a < 0:
                return red(a + 360)
            return a

        image, draw = self.double_icon()

        # Button
        center = [ICON_SIZE, ICON_SIZE]

        tl = [center[0] - self.button_size / 2, center[1] - self.button_size / 2]
        br = [center[0] + self.button_size / 2, center[1] + self.button_size / 2]
        draw.ellipse(
            tl + br,
            fill=self.button_fill_color,
            outline=self.button_stroke_color,
            width=self.button_stroke_width,
        )

        # Ticks
        tick_start = self.button_size / 2 + self.tick_space
        tick_end = tick_start + self.tick_length
        tick_lbl = tick_end + self.tick_label_space

        label_anchors = []
        for i in range(self.tick_steps):
            a = red(self.tick_from + i * self.angular_step)
            x0 = center[0] - tick_start * math.sin(math.radians(a))
            y0 = center[1] + tick_start * math.cos(math.radians(a))
            x1 = center[0] - tick_end * math.sin(math.radians(a))
            y1 = center[1] + tick_end * math.cos(math.radians(a))
            x2 = center[0] - tick_lbl * math.sin(math.radians(a))
            y2 = center[1] + tick_lbl * math.cos(math.radians(a))
            # print(f"===> ({x0},{y0}) ({x1},{y1}) a=({x2},{y2})")
            label_anchors.append([a, x2, y2])
            if self.tick_width > 0:
                draw.line([(x0, y0), (x1, y1)], width=self.tick_width, fill=self.tick_color)

        # Tick run mark
        if self.tick_underline_width > 0:
            tl = [center[0] - tick_start, center[1] - tick_start]
            br = [center[0] + tick_start, center[1] + tick_start]
            draw.arc(
                tl + br,
                fill=self.tick_underline_color,
                start=self.tick_from + 90,
                end=self.tick_to + 90,
                width=self.tick_underline_width,
            )

        # Labels
        # print("-<-<", label_anchors)
        if len(self.tick_labels) >= self.tick_steps:
            font = self.get_font(self.tick_label_font, int(self.tick_label_size))
            for i in range(self.tick_steps):
                angle = int(label_anchors[i][0])
                tolerence = 30
                if angle > tolerence and angle < 180 - tolerence:
                    anchor = "rs"
                    align = "right"
                elif angle > 180 + tolerence and angle < 360 - tolerence:
                    anchor = "ls"
                    align = "left"
                else:  # 0, 180, 360
                    anchor = "ms"
                    align = "center"
                # print(self.tick_labels[i], label_anchors[i], label_anchors[i][1:3], anchor, align)
                draw.text(
                    label_anchors[i][1:3],
                    text=self.tick_labels[i],
                    font=font,
                    anchor=anchor,
                    align=align,
                    fill=self.tick_label_color,
                )

        # Needle
        value = self.button.value
        if value is None:
            value = 0
        if value >= self.tick_steps:
            logger.warning(f"button {self.button.name} invalid initial value {value}. Set to {self.tick_steps - 1}")
            value = self.tick_steps - 1
        angle = red(self.tick_from + value * self.angular_step)

        if self.switch_style in ["small", "medium", "large", "xlarge"]:  # handle style
            overlay, overlay_draw = self.double_icon()
            inner = self.button_size  # medium

            # Base circle
            tl = [center[0] - inner, center[1] - inner]
            br = [center[0] + inner, center[1] + inner]
            overlay_draw.ellipse(
                tl + br,
                fill=self.button_fill_color,
                outline=self.button_stroke_color,
                width=self.button_stroke_width,
            )

            # Button handle needle
            home, home_drawing = self.double_icon()
            handle_width = int(2 * inner / 3)
            handle_height = int(2 * inner / 3)

            if self.switch_style == "small":
                handle_width = int(2 * inner / 3)
            elif self.switch_style == "large":
                handle_width = int(inner)
            elif self.switch_style == "xlarge":
                handle_width = int(4 * inner / 3)

            r = 10
            side = handle_width / math.sqrt(2) + r / 2
            tl = [center[0] - side / 2, center[1] - side / 2]
            br = [center[0] + side / 2, center[1] + side / 2]
            home_drawing.rounded_rectangle(tl + br, radius=r, fill=self.handle_fill_color)
            home = home.rotate(45)
            a = 1
            b = 0
            c = 0  # left/right (i.e. 5/-5)
            d = 0
            e = 1
            f = -handle_height + r / 2  # up/down (i.e. 5/-5)
            home = home.transform(overlay.size, Image.AFFINE, (a, b, c, d, e, f))

            # # Button handle
            home_drawing = ImageDraw.Draw(home)
            tl = [center[0] - handle_width / 2, center[1] - handle_height]
            br = [center[0] + handle_width / 2, center[1] + handle_height]
            home_drawing.rounded_rectangle(tl + br, radius=r, fill=self.handle_fill_color)

            overlay.alpha_composite(home)
            overlay = overlay.rotate(red(-angle))  # ;-)
            image.alpha_composite(overlay)

            # Overlay tick/line/needle mark on top of button
            start = self.needle_start
            # end = handle_height + side / 2 - r / 2
            length = self.needle_length
            end = start + length
            xr = center[0] - start * math.sin(math.radians(angle))
            yr = center[1] + start * math.cos(math.radians(angle))
            xc = center[0] - end * math.sin(math.radians(angle))
            yc = center[1] + end * math.cos(math.radians(angle))
            if self.needle_underline_width > 0:
                draw.line(
                    [(xc, yc), (xr, yr)],
                    width=self.needle_width + 2 * self.needle_underline_width,
                    fill=self.needle_underline_color,
                )
            draw.line([(xc, yc), (xr, yr)], width=self.needle_width, fill=self.needle_color)
            # needle tip
            if self.needle_tip is not None:
                # print("tip1", self.switch_style, self.button_size, self.needle_start, self.needle_length, self.needle_tip, self.needle_tip_size)
                tip_image, tip_draw = self.double_icon()
                if self.needle_tip.startswith("arr"):
                    orient = -1 if self.needle_tip == "arri" else 1
                    tip = (
                        (3 * self.needle_tip_size, 0),
                        (0, 4 * self.needle_tip_size * orient),
                        (-3 * self.needle_tip_size, 0),
                        (3 * self.needle_tip_size, 0),
                    )
                    tip = list(((center[0] + x[0], center[1] + x[1]) for x in tip))
                    tip_draw.polygon(tip, fill=self.needle_color)  # , outline="red", width=3
                else:
                    tl = [
                        center[0] - self.needle_tip_size / 2,
                        center[1] - self.needle_tip_size / 2,
                    ]
                    br = [
                        center[0] + self.needle_tip_size / 2,
                        center[1] + self.needle_tip_size / 2,
                    ]
                    tip_draw.ellipse(tl + br, fill=self.needle_color, outline="red", width=3)
                tip_image = tip_image.rotate(
                    red(-angle),
                    translate=(
                        -end * math.sin(math.radians(angle)),
                        end * math.cos(math.radians(angle)),
                    ),
                )  # ;-)
                image.alpha_composite(tip_image)

        else:  # Just a needle
            xr = center[0] - self.button_size / 2 * math.sin(math.radians(angle))
            yr = center[1] + self.button_size / 2 * math.cos(math.radians(angle))
            length = self.button_size / 2 - self.needle_length
            xc = center[0] - length * math.sin(math.radians(angle))
            yc = center[1] + length * math.cos(math.radians(angle))
            # print(f"***> {value} => {angle}")
            if self.needle_underline_width > 0:
                draw.line(
                    [(xc, yc), (xr, yr)],
                    width=self.needle_width + 2 * self.needle_underline_width,
                    fill=self.needle_underline_color,
                )
            draw.line([(xc, yc), (xr, yr)], width=self.needle_width, fill=self.needle_color)
            # needle tip
            if self.needle_tip is not None:
                # print("tip2", self.switch_style, self.button_size, self.needle_start, self.needle_length, self.needle_tip, self.needle_tip_size)
                tip_image, tip_draw = self.double_icon()
                if self.needle_tip.startswith("arr"):
                    orient = -1 if self.needle_tip == "arri" else 1
                    tip = (
                        (3 * self.needle_tip_size, 0),
                        (0, 4 * self.needle_tip_size * orient),
                        (-3 * self.needle_tip_size, 0),
                        (3 * self.needle_tip_size, 0),
                    )
                    tip = list(((center[0] + x[0], center[1] + x[1]) for x in tip))
                    tip_draw.polygon(tip, fill=self.needle_color)  # , outline="red", width=3
                else:
                    tl = [
                        center[0] - self.needle_tip_size / 2,
                        center[1] - self.needle_tip_size / 2,
                    ]
                    br = [
                        center[0] + self.needle_tip_size / 2,
                        center[1] + self.needle_tip_size / 2,
                    ]
                    tip_draw.ellipse(tl + br, fill=self.needle_color, outline="red", width=3)
                tip_image = tip_image.rotate(
                    red(-angle),
                    translate=(
                        -end * math.sin(math.radians(angle)),
                        end * math.cos(math.radians(angle)),
                    ),
                )  # ;-)
                image.alpha_composite(tip_image)

        return self.move_and_send(image)


class Switch(SwitchBase):

    REPRESENTATION_NAME = "switch"

    def __init__(self, button: "Button"):
        SwitchBase.__init__(self, button=button, switch_type="switch")

        if self.switch is None:
            logger.warning("no switch configuration")
            return

        # Alternate defaults
        self.switch_style = self.get_attribute("switch-style", "round")
        if self.switch_style is not None and self.switch_style == "flat":
            self.switch_style = "rect"  # synonym
        self.button_size = self.switch.get("button-size", int(ICON_SIZE / 5))

        # Handle
        self.handle_dot_color = self.get_attribute("switch-handle-dot-color", "white")

        # Switch
        self.switch_length = self.get_attribute("switch-length", ICON_SIZE / 2.75)
        self.switch_width = self.get_attribute("switch-width", 32)

        self.tick_label_size = self.get_attribute("tick-label-size", 40)

        # Options
        self.three_way = self.button.has_option("3way")
        self.label_opposite = self.button.has_option("label-opposite")
        self.invert = self.button.has_option("invert")
        self.vertical = not self.button.has_option("horizontal")
        self.hexabase = self.button.has_option("hexa")
        self.screw_rot = randint(0, 60)  # remembers it so that it does not "turn" between updates

        # Magic default resizing
        # Resizes default value switches to nice looking Airbus switches
        self.draw_scale = float(self.switch.get("scale", 0.8))
        if self.draw_scale < 0.5 or self.draw_scale > 2:
            logger.warning(f"button {self.button.name}: invalid scale {self.draw_scale}, must be in interval [0.5, 2]")
            self.draw_scale = 1
        if self.switch.get("left") is None and self.switch.get("right") is None:
            if self.vertical:
                if self.label_opposite:
                    self.draw_left = 40
                else:
                    self.draw_left = -40
        if self.switch.get("up") is None and self.switch.get("down") is None:
            if self.vertical:
                self.draw_up = -20
            else:
                self.draw_up = -40

    # The following functions draw switches centered on 0, 0 on a a canvas of ICON_SIZE x ICON_SIZE
    def draw_base(self, draw, radius: int = int(ICON_SIZE / 4)):
        # Base is either hexagonal or round
        if self.hexabase:
            draw.regular_polygon(
                (ICON_SIZE, ICON_SIZE, radius),
                n_sides=6,
                rotation=self.screw_rot,
                fill=self.button_fill_color,
                outline=self.button_stroke_color,
            )
            # screw hole is circular
            SCREW_HOLE_FRACT = 3
            tl = [
                ICON_SIZE - radius / SCREW_HOLE_FRACT,
                ICON_SIZE - radius / SCREW_HOLE_FRACT,
            ]
            br = [
                ICON_SIZE + radius / SCREW_HOLE_FRACT,
                ICON_SIZE + radius / SCREW_HOLE_FRACT,
            ]
            # print("H>", tl, br)
            draw.ellipse(
                tl + br,
                fill=SCREW_HOLE_COLOR,
                outline=SCREW_HOLE_UNDERLINE,
                width=SCREW_HOLE_UWIDTH,
            )
        else:
            if self.button.has_option("no-ublack"):
                tl = [ICON_SIZE - radius, ICON_SIZE - radius]
                br = [ICON_SIZE + radius, ICON_SIZE + radius]
                draw.ellipse(
                    tl + br,
                    fill=self.button_fill_color,
                    outline=self.button_stroke_color,
                    width=self.button_stroke_width,
                )
            else:
                # Add underline back
                tl = [ICON_SIZE - radius, ICON_SIZE - radius]
                br = [ICON_SIZE + radius, ICON_SIZE + radius]
                draw.ellipse(
                    tl + br,
                    fill="black",
                    outline=self.button_stroke_color,
                    width=self.button_stroke_width,
                )

                w = 12
                r = radius - w
                tl = [ICON_SIZE - r, ICON_SIZE - r]
                br = [ICON_SIZE + r, ICON_SIZE + r]
                draw.ellipse(tl + br, fill=self.button_fill_color)
            # print("B>", tl, br)
            # screw hole is oval (not elliptic)
            w = int(3 * radius / 8)
            l = int(radius / 2)
            tl = [ICON_SIZE - w, ICON_SIZE - l]
            br = [ICON_SIZE + w, ICON_SIZE + l]
            # print("rr>", tl, br)
            draw.rounded_rectangle(
                tl + br,
                radius=w,
                fill=SCREW_HOLE_COLOR,
                outline=SCREW_HOLE_UNDERLINE,
                width=SCREW_HOLE_UWIDTH,
            )

        if self.button_underline_width > 0:
            tl1 = [
                ICON_SIZE - radius - self.tick_space,
                ICON_SIZE - radius - self.tick_space,
            ]
            br1 = [
                ICON_SIZE + radius + self.tick_space,
                ICON_SIZE + radius + self.tick_space,
            ]
            # print("U>", tl1, br1)
            draw.ellipse(
                tl1 + br1,
                outline=self.button_underline_color,
                width=self.button_underline_width,
            )

    def draw_round_switch_from_top(self, draw, radius: int = int(ICON_SIZE / 16)):
        #### TOP
        tl = [ICON_SIZE - 2 * radius, ICON_SIZE - 2 * radius]
        br = [ICON_SIZE + 2 * radius, ICON_SIZE + 2 * radius]
        # print(">R", tl, br)
        draw.ellipse(
            tl + br,
            fill=self.top_fill_color,
            outline=self.top_stroke_color,
            width=self.top_stroke_width,
        )

        # (white) tip
        tl = [ICON_SIZE - radius, ICON_SIZE - radius]
        br = [ICON_SIZE + radius, ICON_SIZE + radius]
        # print(">tip", tl, br)
        draw.ellipse(tl + br, fill=self.handle_tip_fill_color)

    def draw_round_switch(self, draw, radius: int = int(ICON_SIZE / 16)):
        # A Handle is visible if not in "middle" position,
        # in which case the button, as seen from top, has not handle.
        # Base
        # Little ellipsis at base
        lr = radius - 4
        tl = [ICON_SIZE - lr, ICON_SIZE - lr / 2]
        br = [ICON_SIZE + lr, ICON_SIZE + lr / 2]
        # print("|b", tl, br)
        draw.ellipse(tl + br, fill=self.handle_base_fill_color)
        # Little start of handle (height of little part = lph)
        lph = radius
        tl = [ICON_SIZE - lr, ICON_SIZE - lph]
        br = [ICON_SIZE + lr, ICON_SIZE]
        # print("|B", tl, br)
        draw.rectangle(tl + br, fill=self.handle_base_fill_color)

        # # larger part of handle (high of larger part = hheight, width of larger part at top = hwidth)
        hheight = 5 * radius
        hwidth = 3 * radius
        swtop = ICON_SIZE - lph
        p1 = (ICON_SIZE - hwidth / 2, swtop - hheight)
        p2 = (ICON_SIZE + hwidth / 2, swtop - hheight)
        p3 = (ICON_SIZE + radius, swtop)
        p4 = (ICON_SIZE - radius, swtop)
        # print("|M", [p1, p2, p3, p4, p1])
        draw.polygon(
            [p1, p2, p3, p4, p1],
            fill=self.handle_fill_color,
            outline=self.handle_stroke_color,
            width=self.handle_stroke_width,
        )
        # #### TOP
        tl = [ICON_SIZE - hwidth / 2, swtop - hheight - hwidth / 4]
        br = [ICON_SIZE + hwidth / 2, swtop - hheight + hwidth / 4]
        # print("|T", tl, br)
        draw.ellipse(
            tl + br,
            fill=self.top_fill_color,
            outline=self.top_stroke_color,
            width=self.top_stroke_width,
        )

        # # (white) tip
        hwidth = int(hwidth / 2)
        tl = [ICON_SIZE - hwidth / 2, swtop - hheight - hwidth / 4]
        br = [ICON_SIZE + hwidth / 2, swtop - hheight + hwidth / 4]
        # print("|tip", tl, br)
        draw.ellipse(tl + br, fill=self.handle_tip_fill_color)

    def draw_flat_switch_from_top(self, draw, radius: int = int(ICON_SIZE / 16)):
        # Then the flat part
        w = 2 * radius
        h = radius
        tl = [ICON_SIZE - w, ICON_SIZE - h]
        br = [ICON_SIZE + w, ICON_SIZE + h]
        # print(">F", tl, br)
        # draw.rectangle(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
        draw.rounded_rectangle(
            tl + br,
            radius=4,
            fill=self.top_fill_color,
            outline=self.top_stroke_color,
            width=int(self.top_stroke_width * 1.5),
        )

        #### (white) tip
        # rrect in top 1/3 of flat part
        nlines = 4
        avail = int(8 * radius / 3)
        separ = int(avail / (nlines + 1))
        start = separ / 4
        w = int((2 * radius - 2 * start))
        h = int((radius - 2 * start) / 2)
        tl = [ICON_SIZE - w, ICON_SIZE - h]
        br = [ICON_SIZE + w, ICON_SIZE + h]
        # print(">tip", tl, br, "wxh", w, h, "separ", separ, "start", start)
        draw.rounded_rectangle(tl + br, radius=w / 2, fill=self.handle_tip_fill_color)

    def draw_flat_switch(self, draw, radius: int = int(ICON_SIZE / 16)):
        # Little ellipsis at base
        lr = radius - 4
        tl = [ICON_SIZE - lr, ICON_SIZE - lr / 2]
        br = [ICON_SIZE + lr, ICON_SIZE + lr / 2]
        # print("|b", tl, br)
        draw.ellipse(tl + br, fill=self.handle_base_fill_color)

        # Little start of handle (height of little part = lph)
        lph = radius
        tl = [ICON_SIZE - lr, ICON_SIZE - lph]
        br = [ICON_SIZE + lr, ICON_SIZE]
        # print("|B", tl, br)
        draw.rectangle(tl + br, fill=self.handle_base_fill_color)

        # First an enlargement of the little start of handle
        hheight = 2 * radius
        hwidth = 4 * radius
        swtop = ICON_SIZE - lph
        p1 = (ICON_SIZE - hwidth / 2, swtop - hheight)
        p2 = (ICON_SIZE + hwidth / 2, swtop - hheight)
        p3 = (ICON_SIZE + radius, swtop)
        p4 = (ICON_SIZE - radius, swtop)
        # print("|m", [p1, p2, p3, p4, p1])
        draw.polygon(
            [p1, p2, p3, p4, p1],
            fill=self.handle_fill_color,
            outline=self.handle_stroke_color,
            width=self.handle_stroke_width,
        )

        # # Then the flat part
        toph = 4 * radius
        tl = [ICON_SIZE - hwidth / 2, swtop - hheight - toph]
        br = [ICON_SIZE + hwidth / 2, swtop - hheight]
        # print("|M", [p1, p2, p3, p4, p1], "h", toph)
        draw.rectangle(
            tl + br,
            fill=self.handle_fill_color,
            outline=self.handle_stroke_color,
            width=self.handle_stroke_width,
        )

        # Decoration of the flat part
        # small lines in bottom 2/3 of flat part
        nlines = 4
        avail = int(2 * toph / 4)
        separ = int(avail / nlines)
        start = int(separ / 2)
        for i in range(nlines):
            h = swtop - hheight - start - i * separ
            l = ICON_SIZE - hwidth / 2 + separ
            e = ICON_SIZE + hwidth / 2 - separ
            # print("|-", [(l, h),(e, h)], "avail", avail, "separ", separ, "bot", swtop - hheight, "2/3", swtop - hheight - avail)
            draw.line([(l, h), (e, h)], width=2, fill=grey(210))

        # #### (white) tip
        # # rrect in top 1/3 of flat part
        mid = swtop - hheight - int(5 * toph / 6)
        # topw = int(hwidth / 4)
        # tl = [ICON_SIZE-hwidth/2 + separ, mid-topw/2]
        # br = [ICON_SIZE+hwidth/2 - separ, mid+topw/2]
        # # print("|=", [tl+br], "2/3=bot", swtop - avail, "top", swtop - hheight - toph, '5/6', swtop - hheight - int(5 * toph / 6))
        # draw.rounded_rectangle(tl+br, radius=topw/4, fill=self.handle_tip_fill_color)

        w = int((2 * radius - 2 * start))
        h = int((radius - 2 * start) / 2)
        tl = [ICON_SIZE - w, mid - h]
        br = [ICON_SIZE + w, mid + h]
        # print(">tip", tl, br, "wxh", w, h, "separ", separ, "start", start)
        draw.rounded_rectangle(tl + br, radius=w / 2, fill=self.handle_tip_fill_color)

    def draw_3dot_switch_from_top(self, draw, radius: int = int(ICON_SIZE / 16)):
        # Big rounded rect
        width = 10 * radius
        height = 4 * radius
        tl = [ICON_SIZE - width / 2, ICON_SIZE - height / 2]
        br = [ICON_SIZE + width / 2, ICON_SIZE + height / 2]
        # print(">3", tl, br)
        draw.rounded_rectangle(
            tl + br,
            radius=height / 2,
            fill=self.top_fill_color,
            outline=self.top_stroke_color,
            width=int(self.top_stroke_width * 1.5),
        )

        # Dots
        ndots = 3
        sep = width / (ndots + 1)
        start = sep
        dotr = 2 * radius
        left = ICON_SIZE - (width / 2) + start
        for i in range(ndots):
            x = left + i * sep
            tl = [x - dotr / 2, ICON_SIZE - dotr / 2]
            br = [x + dotr / 2, ICON_SIZE + dotr / 2]
            # print(">•", tl, br, "x", x, width, left, sep, start)
            draw.ellipse(tl + br, fill=self.handle_tip_fill_color)

    def draw_3dot_switch(self, draw, radius: int = int(ICON_SIZE / 16)):
        # Little ellipsis at base
        lr = radius - 4
        tl = [ICON_SIZE - lr, ICON_SIZE - lr / 2]
        br = [ICON_SIZE + lr, ICON_SIZE + lr / 2]
        # print("|b", tl, br)
        draw.ellipse(tl + br, fill=self.handle_base_fill_color)

        # Little start of handle (height of little part = lph)
        lph = radius
        tl = [ICON_SIZE - lr, ICON_SIZE - lph]
        br = [ICON_SIZE + lr, ICON_SIZE]
        # print("|B", tl, br)
        draw.rectangle(tl + br, fill=self.handle_base_fill_color)

        # Then the handle
        hh = 2 * radius
        hw = radius
        top0 = ICON_SIZE - lr
        tl = [ICON_SIZE - hw, top0 - hh]
        br = [ICON_SIZE + hw, top0]
        # print("|M", tl+br)
        draw.rectangle(
            tl + br,
            fill=self.handle_fill_color,
            outline=self.handle_stroke_color,
            width=self.handle_stroke_width,
        )

        # Big rounded rect
        radius = radius * 2
        width = 5 * radius
        height = 2 * radius
        top = top0 - hh - height / 2
        tl = [ICON_SIZE - width / 2, top - height / 2 + 2]
        br = [ICON_SIZE + width / 2, top + height / 2 - 2]
        # print(">3", tl, br)
        draw.rounded_rectangle(
            tl + br,
            radius=height / 2,
            fill=self.top_fill_color,
            outline=self.top_stroke_color,
            width=int(self.top_stroke_width * 1.5),
        )

        # Dots
        ndots = 3
        sep = width / (ndots + 1)
        start = sep
        dotr = int(radius)
        left = ICON_SIZE - (width / 2) + start
        for i in range(ndots):
            x = left + i * sep
            tl = [x - dotr / 2, top - dotr / 2 + 2]
            br = [x + dotr / 2, top + dotr / 2 - 2]
            # print(">•", tl, br, "x", x, width, left, sep, start)
            draw.ellipse(tl + br, fill=self.handle_tip_fill_color)

    def draw_ticks(self, draw):
        underline = ICON_SIZE - self.tick_space
        tick_end = underline + self.tick_length
        # top mark
        draw.line(
            [
                (underline, ICON_SIZE - self.switch_length),
                (tick_end, ICON_SIZE - self.switch_length),
            ],
            width=self.tick_width,
            fill=self.tick_color,
        )
        # middle mark
        if self.three_way:
            draw.line(
                [(underline, ICON_SIZE), (tick_end, ICON_SIZE)],
                width=self.tick_width,
                fill=self.tick_color,
            )
        # bottom mark
        draw.line(
            [
                (underline, ICON_SIZE + self.switch_length),
                (tick_end, ICON_SIZE + self.switch_length),
            ],
            width=self.tick_width,
            fill=self.tick_color,
        )
        # underline
        if self.tick_underline_width > 0:
            draw.line(
                [
                    (underline, ICON_SIZE - self.switch_length),
                    (underline, ICON_SIZE + self.switch_length),
                ],
                width=self.tick_underline_width,
                fill=self.tick_color,
            )

    def draw_labels(self, draw):
        inside = ICON_SIZE / 32
        font = self.get_font(self.tick_label_font, int(self.tick_label_size))
        if self.vertical:
            # Vertical
            # Distribute labels between [-switch_length and +switch_length]
            align = "right"
            anchor = "rm"
            if self.label_opposite:
                align = "left"
                anchor = "lm"
            hloc = ICON_SIZE + self.tick_label_space
            draw.text(
                (hloc, ICON_SIZE - self.switch_length),
                text=self.tick_labels[0],
                font=font,
                anchor=anchor,
                align=align,
                fill=self.tick_label_color,
            )
            n = 1
            if self.three_way:
                draw.text(
                    (hloc, ICON_SIZE),
                    text=self.tick_labels[1],
                    font=font,
                    anchor=anchor,
                    align=align,
                    fill=self.tick_label_color,
                )
                n = 2
            draw.text(
                (hloc, ICON_SIZE + self.switch_length),
                text=self.tick_labels[n],
                font=font,
                anchor=anchor,
                align=align,
                fill=self.tick_label_color,
            )
            return

        # Horizontal
        # Equally space labels (centers) inside button width - 2*inside (for borders)
        vloc = ICON_SIZE + self.tick_label_space
        draw.text(
            (ICON_SIZE - ICON_SIZE / 2 + inside, vloc),
            text=self.tick_labels[0],
            font=font,
            anchor="lm",
            align="center",
            fill=self.tick_label_color,
        )
        n = 1
        if self.three_way:
            draw.text(
                (ICON_SIZE, vloc),
                text=self.tick_labels[1],
                font=font,
                anchor="mm",
                align="center",
                fill=self.tick_label_color,
            )
            n = 2
        draw.text(
            (ICON_SIZE + ICON_SIZE / 2 - inside, vloc),
            text=self.tick_labels[n],
            font=font,
            anchor="rm",
            align="center",
            fill=self.tick_label_color,
        )

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        # Value
        value = self.button.value  # 0, 1, or 2 if three_way
        if value is None:
            value = 0
        pos = -1  # 1 or -1, or 0 if 3way
        if value != 0:
            if self.three_way:
                if value == 1:
                    pos = 0
                else:
                    pos = 1
            else:
                pos = 1  # force to 1 in case value > 1
        if self.invert:
            pos = pos * -1

        # Canvas
        image, draw = self.double_icon()

        # Switch
        self.draw_base(draw, radius=self.button_size)
        switch, switch_draw = self.double_icon()
        if pos == 0:  # middle position
            if self.switch_style == SWITCH_STYLE.ROUND.value:
                self.draw_round_switch_from_top(switch_draw, self.switch_width)
            elif self.switch_style == SWITCH_STYLE.FLAT.value:
                self.draw_flat_switch_from_top(switch_draw, self.switch_width)
            else:
                self.draw_3dot_switch_from_top(switch_draw, self.switch_width)
        else:
            if self.switch_style == SWITCH_STYLE.ROUND.value:
                self.draw_round_switch(switch_draw, self.switch_width)
            elif self.switch_style == SWITCH_STYLE.FLAT.value:
                self.draw_flat_switch(switch_draw, self.switch_width)
            else:
                self.draw_3dot_switch(switch_draw, self.switch_width)
        if pos < 0:
            switch = switch.transpose(method=Image.Transpose.FLIP_TOP_BOTTOM)
        if not self.vertical:
            switch = switch.transpose(method=Image.Transpose.ROTATE_90)
            image = image.transpose(method=Image.Transpose.ROTATE_90)
        # Tick marks
        if self.tick_length > 0:
            ticks, ticks_draw = self.double_icon()
            self.draw_ticks(ticks_draw)
            if not self.vertical:
                ticks = ticks.transpose(method=Image.Transpose.ROTATE_270)
            # Shift ticks
            space = self.button_size + self.tick_space
            if self.button_underline_width > 0:
                space = space + 2 * self.tick_space
            c = space if self.vertical else 0
            f = space if not self.vertical else 0
            ticks = ticks.transform(ticks.size, Image.AFFINE, (1, 0, c, 0, 1, f))
            if self.label_opposite:
                ticks = ticks.transpose(method=Image.Transpose.ROTATE_180)
            image.alpha_composite(ticks)
        # # Tick labels
        if len(self.tick_labels) > 0:
            tick_labels, tick_labels_draw = self.double_icon()
            self.draw_labels(tick_labels_draw)
            space = self.button_size + self.tick_length
            if self.button_underline_width > 0:
                space = space + self.tick_space
            c = (space + 2 * self.tick_space) if self.vertical else 0
            f = (space + 4 * self.tick_space) if not self.vertical else 0
            if self.label_opposite:
                c = -c
                f = -f
            tick_labels = tick_labels.transform(tick_labels.size, Image.AFFINE, (1, 0, c, 0, 1, f))
            image.alpha_composite(tick_labels)
        image.alpha_composite(switch)

        return self.move_and_send(image)


class PushSwitch(SwitchBase):

    REPRESENTATION_NAME = "push-switch"

    def __init__(self, button: "Button"):
        SwitchBase.__init__(self, button=button, switch_type="push-switch")

        # Alternate defaults
        self.button_size = self.get_attribute("button-size", 80)

        self.handle_size = self.get_attribute("witness-size", min(self.button_size / 2, 40))

        self.handle_fill_color = self.get_attribute("witness-fill-color", (0, 0, 0, 0))
        self.handle_fill_color = convert_color(self.handle_fill_color)
        self.handle_stroke_color = self.get_attribute("witness-stroke-color", (255, 255, 255))
        self.handle_stroke_color = convert_color(self.handle_stroke_color)
        self.handle_stroke_width = self.get_attribute("witness-stroke-width", 4)

        self.handle_off_fill_color = self.get_attribute("witness-fill-off-color", (0, 0, 0, 0))
        self.handle_off_fill_color = convert_color(self.handle_off_fill_color)
        self.handle_off_stroke_color = self.get_attribute("witness-stroke-off-color", (255, 255, 255, 0))
        self.handle_off_stroke_color = convert_color(self.handle_off_stroke_color)
        self.handle_off_stroke_width = self.get_attribute("witness-stroke-off-width", 4)

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image, draw = self.double_icon()

        # Button
        center = [ICON_SIZE, ICON_SIZE]
        tl = [center[0] - self.button_size / 2, center[1] - self.button_size / 2]
        br = [center[0] + self.button_size / 2, center[1] + self.button_size / 2]
        draw.ellipse(
            tl + br,
            fill=self.button_fill_color,
            outline=self.button_stroke_color,
            width=self.button_stroke_width,
        )

        if self.handle_size > 0:
            tl = [center[0] - self.handle_size / 2, center[1] - self.handle_size / 2]
            br = [center[0] + self.handle_size / 2, center[1] + self.handle_size / 2]
            if hasattr(self.button._activation, "is_off") and self.button._activation.is_off():
                logger.debug(f"button {self.button.name}: has on/off state and IS OFF")
                draw.ellipse(
                    tl + br,
                    fill=self.handle_off_fill_color,
                    outline=self.handle_off_stroke_color,
                    width=self.handle_off_stroke_width,
                )
            else:
                if not hasattr(self.button._activation, "is_on"):
                    logger.debug(f"button {self.button.name}: has no on/off state")
                draw.ellipse(
                    tl + br,
                    fill=self.handle_fill_color,
                    outline=self.handle_stroke_color,
                    width=self.handle_stroke_width,
                )

        return self.move_and_send(image)


class Knob(SwitchBase):

    REPRESENTATION_NAME = "knob"

    def __init__(self, button: "Button"):
        SwitchBase.__init__(self, button=button, switch_type="knob")

        if self.switch is None:
            logger.warning("no switch configuration")
            return

        self.knob_type = self.get_attribute("knob-type", "dent")
        self.knob_mark = self.get_attribute("knob-mark", "triangle")  # needle, triangle, bar (diameter)

        # Alternate defaults
        # self.button_size = self.switch.get("button-size", 80)
        self.base_size = self.switch.get("base-size", int(ICON_SIZE / 1.25))
        self.base_fill_color = self.get_attribute("base-fill-color", grey(128))
        self.base_stroke_color = self.get_attribute("base-stroke-color", grey(20))
        self.base_stroke_width = self.get_attribute("base-stroke-width", 16)

        self.base_underline_color = self.get_attribute("base-underline-color", grey(240))
        self.base_underline_width = self.get_attribute("base-underline-width", int(self.base_stroke_width / 2))

        self.button_fill_color = self.get_attribute("button-fill-color", grey(220))
        self.button_stroke_color = self.get_attribute("button-stroke-color", grey(0))
        self.button_stroke_width = self.get_attribute("button-stroke-width", 2)
        self.button_dents = self.get_attribute("button-dents", 36)
        self.button_dent_size = self.get_attribute("button-dent-size", 4)
        self.button_dent_extension = self.get_attribute("button-dent-extension", 4)
        self.button_dent = self.get_attribute("button-dent-negative", False)

        if self.button_dent_size < self.button_dent_extension:
            self.button_dent_size = self.button_dent_extension

        self.mark_underline_outer = self.get_attribute("mark-underline-outer", 12)
        self.mark_underline_color = self.get_attribute("mark-underline-color", "coral")
        self.mark_underline_width = self.get_attribute("mark-underline-width", 4)
        self.mark_size = self.get_attribute("witness-size", min(self.button_size / 2, 40))
        self.mark_fill_color = self.get_attribute("witness-fill-color", None)
        self.mark_fill_color = convert_color(self.mark_fill_color)
        self.mark_stroke_color = self.get_attribute("witness-stroke-color", "blue")
        self.mark_stroke_color = convert_color(self.mark_stroke_color)
        self.mark_stroke_width = self.get_attribute("witness-stroke-width", 8)

        self.mark_off_fill_color = self.get_attribute("witness-fill-off-color", (0, 0, 0, 0))
        self.mark_off_fill_color = convert_color(self.mark_off_fill_color)
        self.mark_off_stroke_color = self.get_attribute("witness-stroke-off-color", (255, 255, 255, 0))
        self.mark_off_stroke_color = convert_color(self.mark_off_stroke_color)
        self.mark_off_stroke_width = self.get_attribute("witness-stroke-off-width", 4)

        self.rotation = randint(0, 9) * 40

    def set_rotation(self, rotation):
        """Rotates a button's drawing

        May be an animation later?

        Args:
                rotation (float): Rotation of button in degrees
        """
        self.rotation = rotation

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """

        def mk_dent(count, center):
            dents_image, dents_draw = self.double_icon()

            bsize = self.button_dent_size  # radius of little bubble added
            bover = self.button_dent_extension  # size of button extention

            radius = self.button_size / 2 + bover - bsize
            if 360 % count != 0:  # must be a multiple of 360
                count = 12
            step = int(360 / count)
            for i in range(count):
                angle = math.radians(i * step)
                lc = [
                    center[0] + radius * math.cos(angle),
                    center[1] + radius * math.sin(angle),
                ]
                tl = [lc[0] - bsize, lc[1] - bsize]
                br = [lc[0] + bsize, lc[1] + bsize]
                dents_draw.ellipse(
                    tl + br,
                    fill=self.button_fill_color,
                    outline=self.button_stroke_color,
                    width=self.button_stroke_width,
                )
            return dents_image, dents_draw

        center = [ICON_SIZE, ICON_SIZE]
        #
        # Base
        base_image, base_draw = self.double_icon()
        base = self.base_size / 2
        tl = [center[0] - base, center[1] - base]
        br = [center[0] + base, center[1] + base]
        base_draw.ellipse(
            tl + br,
            fill=self.base_fill_color,
            outline=self.base_stroke_color,
            width=self.base_stroke_width,
        )

        # Base "underline", around it
        if self.base_underline_width > 0:
            base = self.base_size / 2 + self.base_underline_width / 2
            tl = [center[0] - base, center[1] - base]
            br = [center[0] + base, center[1] + base]
            base_draw.ellipse(
                tl + br,
                outline=self.base_underline_color,
                width=self.base_underline_width,
            )

        #
        # Button
        image, draw = self.double_icon()

        base = self.button_size / 2
        tl = [center[0] - base, center[1] - base]
        br = [center[0] + base, center[1] + base]

        if self.button_dents:
            # button with outline
            draw.ellipse(
                tl + br,
                fill=self.button_fill_color,
                outline=self.button_stroke_color,
                width=self.button_stroke_width,
            )
            # add dents over
            border_image, border = mk_dent(self.button_dents, center)
            image.alpha_composite(border_image)
            # button without outline
            image2, draw2 = self.double_icon()
            draw2.ellipse(tl + br, fill=self.button_fill_color)
            image.alpha_composite(image2)
        else:
            draw.ellipse(
                tl + br,
                fill=self.button_fill_color,
                outline=self.button_stroke_color,
                width=self.button_stroke_width,
            )

        # Button-top mark underline
        if self.mark_underline_width > 0:
            base = self.button_size / 2 - self.mark_underline_outer
            tl = [center[0] - base, center[1] - base]
            br = [center[0] + base, center[1] + base]
            draw.ellipse(
                tl + br,
                outline=self.mark_underline_color,
                width=self.mark_underline_width,
            )

        # Button-top mark
        mark_image, mark = self.double_icon()
        radius = int(ICON_SIZE / 8)
        mark.regular_polygon(
            (ICON_SIZE, ICON_SIZE, radius),
            n_sides=3,
            fill=self.mark_fill_color,
            outline=self.mark_stroke_color,
        )  # , width=self.mark_width, # https://github.com/python-pillow/Pillow/pull/7132

        image.alpha_composite(mark_image)
        self.rotation = randint(0, 9) * 40
        image = image.rotate(self.rotation, resample=Image.Resampling.NEAREST, center=center)
        base_image.alpha_composite(image)
        return self.move_and_send(base_image)
