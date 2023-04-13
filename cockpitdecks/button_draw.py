# ###########################
# Buttons that are drawn on render()
#
import logging
import threading
import time
import math
from random import randint

from PIL import Image, ImageDraw

from .constant import WEATHER_ICON_FONT, ICON_FONT, DEFAULT_LABEL_FONT
from .color import convert_color, light_off
from .resources.icons import icons as FA_ICONS        # Font Awesome Icons
from .resources.weathericons import WEATHER_ICONS     # Weather Icons
from .button_representation import Icon
from .button_annunciator import ICON_SIZE, TRANSPARENT_PNG_COLOR

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# DISPLAY-ONLY REPRESENTATION
#
#
class DrawBase(Icon):

    def __init__(self, config: dict, button: "Button"):

        Icon.__init__(self, config=config, button=button)

        self.cockpit_color = config.get("cockpit-color", self.button.page.cockpit_color)


class DataIcon(DrawBase):

    def __init__(self, config: dict, button: "Button"):
        DrawBase.__init__(self, config=config, button=button)

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE))                     # annunciator text and leds , color=(0, 0, 0, 0)
        draw = ImageDraw.Draw(image)
        inside = round(0.04 * image.width + 0.5)

        # Display Data
        data = self._config.get("data")
        if data is None:
            logger.warning(f"get_image_for_icon: button {self.button.name}: no data")
            return image

        # Icon
        icon, icon_format, icon_font, icon_color, icon_size, icon_position = self.get_text_detail(data, "icon")
        #print(">"*10, "ICON", icon, icon_format, icon_font, icon_color, icon_size, icon_position)

        icon_name = data.get("icon-name")  # not "icon"...
        if icon_name is not None:
            icon_str = FA_ICONS.get(icon_name, "*")
        else:
            icon_str = "*"

        icon_font = data.get("icon-font", ICON_FONT)
        font = self.get_font(icon_font, int(icon_size))
        inside = round(0.04 * image.width + 0.5)
        w = inside
        h = image.height / 2
        draw.text((w, h),  # (image.width / 2, 15)
                  text=icon_str,
                  font=font,
                  anchor="lm",
                  align="left",
                  fill=icon_color)

        # Data
        DATA_UNIT_SEP = " "
        data_value, data_format, data_font, data_color, data_size, data_position = self.get_text_detail(data, "data")
        #print(">"*10, "DATA", data_value, data_format, data_font, data_color, data_size, data_position)

        if data_format is not None:
            data_str = data_format.format(float(data_value))
        else:
            data_str = str(data_value)

        data_unit = data.get("data-unit")
        # if data_unit is not None:
        #     data_str = data_str + DATA_UNIT_SEP + data_unit

        data_progress = data.get("data-progress")

        font = self.get_font(data_font, data_size)
        font_unit = self.get_font(data_font, int(data_size * 0.50))
        inside = round(0.04 * image.width + 0.5)
        w = image.width - inside
        h = image.height / 2 + data_size / 2 - inside
        # if dataprogress is not None:
        #     h = h - DATAPROGRESS_SPACE - DATAPROGRESS / 2
        if data_unit is not None:
            w = w - draw.textlength(DATA_UNIT_SEP + data_unit, font=font_unit)
        draw.text((w, h),  # (image.width / 2, 15)
                  text=data_str,
                  font=font,
                  anchor="rs",
                  align="right",
                  fill=data_color)

        if data_unit is not None:
            w = image.width - inside
            draw.text((w, h),  # (image.width / 2, 15)
                      text=DATA_UNIT_SEP + data_unit,
                      font=font_unit,
                      anchor="rs",
                      align="right",
                      fill=data_color)

        # Progress bar
        DATA_PROGRESS_SPACE = 8
        DATA_PROGRESS = 6

        if data_progress is not None:
            w = icon_size + 4 * inside
            h = 3 * image.height / 4 - 2 * DATA_PROGRESS
            pct = float(data_value) / float(data_progress)
            if pct > 1:
                pct = 1
            full_color = light_off(data_color, 0.30)
            l = w + pct * ((image.width - inside) - w)
            draw.line([(w, h), (image.width - inside, h)],fill=full_color, width=DATA_PROGRESS, joint="curve") # 100%
            draw.line([(w, h), (l, h)], fill=data_color, width=DATA_PROGRESS, joint="curve")

        # Bottomline (forced at CENTER BOTTOM line of icon)
        bottom_line, botl_format, botl_font, botl_color, botl_size, botl_position = self.get_text_detail(data, "bottomline")
        #print(">"*10, "BOTL", bottom_line, botl_format, botl_font, botl_color, botl_size, botl_position)

        if bottom_line is not None:
            font = self.get_font(botl_font, botl_size)
            w = image.width / 2
            h = image.height / 2
            h = image.height - inside - botl_size / 2  # forces BOTTOM position
            draw.multiline_text((w, h),  # (image.width / 2, 15)
                      text=bottom_line,
                      font=font,
                      anchor="md",
                      align="center",
                      fill=botl_color)

        return image.convert("RGB")


#
# ###############################
# SWITCH BUTTON REPRESENTATION
#
#
class SwitchCommonBase(DrawBase):

    def __init__(self, config: dict, button: "Button", switch_type: str):

        DrawBase.__init__(self, config=config, button=button)

        self.switch = config.get(switch_type)

        self.switch_type = self.switch.get("type")
        self.switch_style = self.switch.get("switch-style")

        # Base and handle
        self.button_size = self.switch.get("button-size", int(2 * ICON_SIZE / 4))
        self.button_fill_color = self.switch.get("button-fill-color", "(150,150,150)")
        self.button_fill_color = convert_color(self.button_fill_color)
        self.button_stroke_color = self.switch.get("button-stroke-color", "white")
        self.button_stroke_color = convert_color(self.button_stroke_color)
        self.button_stroke_width = self.switch.get("button-stroke-width", 4)
        self.button_underline_color = self.switch.get("button-underline-color", "white")
        self.button_underline_color = convert_color(self.button_underline_color)
        self.button_underline_width = self.switch.get("button-underline-width", 4)

        self.handle_fill_color = self.switch.get("handle-fill-color", "(100,100,100)")
        self.handle_fill_color = convert_color(self.handle_fill_color)
        self.handle_stroke_color = self.switch.get("handle-stroke-color", "white")
        self.handle_stroke_color = convert_color(self.handle_stroke_color)
        self.handle_stroke_width = self.switch.get("handle-stroke-width", 4)

        # Ticks
        self.tick_space = self.switch.get("tick-space", 10)
        self.tick_length = self.switch.get("tick-length", 16)
        self.tick_width = self.switch.get("tick-width", 4)
        self.tick_color = self.switch.get("tick-color", "white")
        self.tick_color = convert_color(self.tick_color)
        self.tick_underline_color = self.switch.get("tick-underline-color", "white")
        self.tick_underline_color = convert_color(self.tick_underline_color)
        self.tick_underline_width = self.switch.get("tick-underline-width", 0)

        # Labels
        self.tick_labels = self.switch.get("tick-labels")
        self.tick_label_space = self.switch.get("tick-label-space", 10)
        self.tick_label_font = self.switch.get("tick-label-font", "DIN")
        self.tick_label_size = self.switch.get("tick-label-size", 50)
        self.tick_label_color = self.switch.get("tick-label-color", "white")
        self.tick_label_color = convert_color(self.tick_label_color)

        # Handle needle
        self.needle_width = self.switch.get("needle-width", 8)
        self.needle_length = self.switch.get("needle-length", 50)  # % of radius
        self.needle_length = int(self.needle_length * self.button_size / 200)
        self.needle_color = self.switch.get("needle-color", "white")
        self.needle_color = convert_color(self.needle_color)
        # Options
        self.needle_underline_width = self.switch.get("needle-underline-width", 4)
        self.needle_underline_color = self.switch.get("needle-underline-color", "black")
        self.needle_underline_color = convert_color(self.needle_underline_color)

    def move_and_send(self, image):
        # Move whole drawing around
        a = 1
        b = 0
        c = self.switch.get("left", 0) + self.switch.get("right", 0)
        d = 0
        e = 1
        f = self.switch.get("up", 0) - self.switch.get("down", 20)  # up/down (i.e. 5/-5)
        if c != 0 or f != 0:
            image = image.transform(image.size, Image.AFFINE, (a, b, c, d, e, f))

        # Paste image on cockpit background and return it.
        bg = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=self.cockpit_color)
        bg.alpha_composite(image)
        return bg.convert("RGB")


class CircularSwitch(SwitchCommonBase):

    def __init__(self, config: dict, button: "Button"):

        SwitchCommonBase.__init__(self, config=config, button=button, switch_type="circular-switch")

        self.tick_from = self.switch.get("tick-from", 90)
        self.tick_to = self.switch.get("tick-to", 270)
        if hasattr(self.button._activation, "stops"):
            self.tick_steps = self.button._activation.stops
            logger.debug(f"__init__: button {self.button.name}: button has {self.tick_steps} steps")
        else:
            self.tick_steps = self.switch.get("tick-steps", 2)
        if self.tick_steps < 2:
            logger.warning(f"__init__: button {self.button.name}: insuficient number of steps: {self.tick_steps}, forcing 2")
            self.tick_steps = 2
        logger.debug(f"__init__: button {self.button.name}: {self.tick_steps} steps")
        self.angular_step = (self.tick_to - self.tick_from) / (self.tick_steps - 1)
        if len(self.tick_labels) < self.tick_steps:
            logger.warning(f"__init__: button {self.button.name}: not enough label ({len(self.tick_labels)}/{self.tick_steps})")

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        def red(a):
            if a > 360:
                a = a - 360
                return red(a)
            elif a < 0:
                a = a + 360
                return red(a)
            return a

        image = Image.new(mode="RGBA", size=(ICON_SIZE*2, ICON_SIZE*2), color=TRANSPARENT_PNG_COLOR)                     # annunciator text and leds , color=(0, 0, 0, 0)
        draw = ImageDraw.Draw(image)

        # Button
        center = [ICON_SIZE, ICON_SIZE]

        tl = [center[0]-self.button_size/2, center[1]-self.button_size/2]
        br = [center[0]+self.button_size/2, center[1]+self.button_size/2]
        draw.ellipse(tl+br, fill=self.button_fill_color, outline=self.button_stroke_color, width=self.button_stroke_width)

        # Ticks
        tick_start = self.button_size/2 + self.tick_space
        tick_end   = tick_start + self.tick_length
        tick_lbl   = tick_end + self.tick_label_space

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
            draw.line([(x0,y0), (x1, y1)], width=self.tick_width, fill=self.tick_color)


        # Tick run mark
        if self.tick_underline_width > 0:
            tl = [center[0]-tick_start, center[1]-tick_start]
            br = [center[0]+tick_start, center[1]+tick_start]
            draw.arc(tl+br, fill=self.tick_underline_color, start=self.tick_from+90, end=self.tick_to+90, width=self.tick_underline_width)

        # Labels
        # print("-<-<", label_anchors)
        font = self.get_font(self.tick_label_font, int(self.tick_label_size))
        for i in range(self.tick_steps):
            angle = int(label_anchors[i][0])
            tolerence = 30
            if angle > tolerence and angle < 180-tolerence:
                anchor="rs"
                align="right"
            elif angle > 180+tolerence and angle < 360-tolerence:
                anchor="ls"
                align="left"
            else:  # 0, 180, 360
                anchor="ms"
                align="center"
            # print(self.tick_labels[i], label_anchors[i], label_anchors[i][1:3], anchor, align)
            draw.text(label_anchors[i][1:3],
                      text=self.tick_labels[i],
                      font=font,
                      anchor=anchor,
                      align=align,
                      fill=self.tick_label_color)

        # Needle
        value = self.button.get_current_value()
        if value is None:
            value = 0
        if value >= self.tick_steps:
            logger.warning(f"__init__: button {self.button.name} invalid initial value {value}. Set to {self.tick_steps - 1}")
            value = self.tick_steps - 1
        angle = red(self.tick_from + value * self.angular_step)

        if self.switch_style in ["medium", "large", "xlarge"]:   # handle style
            overlay = Image.new(mode="RGBA", size=(ICON_SIZE*2, ICON_SIZE*2))                     # annunciator text and leds , color=(0, 0, 0, 0)
            overlay_draw = ImageDraw.Draw(overlay)
            inner = self.button_size

            # Base circle
            tl = [center[0]-inner, center[1]-inner]
            br = [center[0]+inner, center[1]+inner]
            overlay_draw.ellipse(tl+br, fill=self.button_fill_color, outline=self.button_stroke_color, width=self.button_stroke_width)

            # Button handle needle
            home = Image.new(mode="RGBA", size=(ICON_SIZE*2, ICON_SIZE*2))                     # annunciator text and leds , color=(0, 0, 0, 0)
            home_drawing = ImageDraw.Draw(home)
            handle_width = int(2*inner/3)
            handle_height = int(2*inner/3)

            if self.switch_style == "large":   # big handle style
                handle_width = int(inner)
            elif self.switch_style == "xlarge":   # big handle style
                handle_width = int(4*inner/3)

            r = 10
            side = handle_width / math.sqrt(2) + r / 2
            tl = [center[0]-side/2, center[1]-side/2]
            br = [center[0]+side/2, center[1]+side/2]
            home_drawing.rounded_rectangle(tl+br, radius=r, fill=self.handle_fill_color)
            home = home.rotate(45)
            a = 1
            b = 0
            c = 0  # left/right (i.e. 5/-5)
            d = 0
            e = 1
            f = - handle_height + r/2  # up/down (i.e. 5/-5)
            home = home.transform(overlay.size, Image.AFFINE, (a, b, c, d, e, f))

            # # Button handle
            home_drawing = ImageDraw.Draw(home)
            tl = [center[0]-handle_width/2, center[1]-handle_height]
            br = [center[0]+handle_width/2, center[1]+handle_height]
            home_drawing.rounded_rectangle(tl+br, radius=r, fill=self.handle_fill_color)

            overlay.alpha_composite(home)
            overlay = overlay.rotate(red(-angle))  # ;-)
            image.alpha_composite(overlay)
            # Overlay tick mark on top of button
            if self.needle_underline_width > 0:
                start = r
                end = handle_height + side / 2 - r / 2
                xr = center[0] - start * math.sin(math.radians(angle))
                yr = center[1] + start * math.cos(math.radians(angle))
                length = self.button_size/2 - self.needle_length
                xc = center[0] - end * math.sin(math.radians(angle))
                yc = center[1] + end * math.cos(math.radians(angle))
                draw.line([(xc, yc), (xr, yr)],
                          width=self.needle_width+2*self.needle_underline_width,
                          fill=self.needle_underline_color)
                draw.line([(xc, yc), (xr, yr)], width=self.needle_width, fill=self.needle_color)
        else:  # Just a needle
            xr = center[0] - self.button_size/2 * math.sin(math.radians(angle))
            yr = center[1] + self.button_size/2 * math.cos(math.radians(angle))
            length = self.button_size/2 - self.needle_length
            xc = center[0] - length * math.sin(math.radians(angle))
            yc = center[1] + length * math.cos(math.radians(angle))
            # print(f"***> {value} => {angle}")
            if self.needle_underline_width > 0:
                draw.line([(xc, yc), (xr, yr)],
                          width=self.needle_width+2*self.needle_underline_width,
                          fill=self.needle_underline_color)
            draw.line([(xc, yc), (xr, yr)], width=self.needle_width, fill=self.needle_color)

        # Move whole drawing around
        a = 1
        b = 0
        c = self.switch.get("left", 0) + self.switch.get("right", 0)
        d = 0
        e = 1
        f = self.switch.get("up", 0) - self.switch.get("down", 0)  # up/down (i.e. 5/-5)
        if c != 0 or f != 0:
            image = image.transform(image.size, Image.AFFINE, (a, b, c, d, e, f))

        cl = ICON_SIZE/2
        ct = ICON_SIZE/2
        image = image.crop((cl, ct, cl+ICON_SIZE, ct+ICON_SIZE))

        # Paste image on cockpit background and return it.
        bg = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=self.cockpit_color)                     # annunciator text and leds , color=(0, 0, 0, 0)
        bg.alpha_composite(image)
        return bg.convert("RGB")


class Switch(SwitchCommonBase):

    def __init__(self, config: dict, button: "Button"):

        SwitchCommonBase.__init__(self, config=config, button=button, switch_type="switch")

        # Alternate defaults
        self.switch_style = self.switch.get("switch-style", "round")
        self.button_size = self.switch.get("button-size", 80)

        # Handle
        self.handle_dot_color = self.switch.get("switch-length", "white")

        # Switch
        self.switch_length = self.switch.get("switch-length", ICON_SIZE/3)
        self.switch_width = self.switch.get("switch-width", 32)

        # Options
        self.label_opposite = self.button.has_option("label-opposite")
        self.three_way = self.button.has_option("3way")
        self.invert = self.button.has_option("invert")
        self.vertical = not self.button.has_option("horizontal")
        self.hexabase = self.button.has_option("hexa")


    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        OUT = 8
        inside = ICON_SIZE / 32

        image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)
        draw = ImageDraw.Draw(image)

        # Button
        center = [ICON_SIZE/2, ICON_SIZE/2]

        # Offset to make room for labels
        offset = 0
        if len(self.tick_labels) > 0:
            offset = ICON_SIZE / 4
        if self.label_opposite:
            offset = - offset
        if self.vertical:
            center[0] = center[0] + offset
        else:
            center[1] = center[1] + offset


        tl = [center[0]-self.button_size/2, center[1]-self.button_size/2]
        br = [center[0]+self.button_size/2, center[1]+self.button_size/2]
        if self.hexabase:
            draw.regular_polygon((center[0], center[1], self.button_size/2), n_sides=6, rotation=randint(0, 60), fill=self.button_fill_color)
        else:
            draw.ellipse(tl+br, fill=self.button_fill_color)
        if self.button_underline_width > 0:
            tl1 = [center[0]-self.button_size/2-OUT, center[1]-self.button_size/2-OUT]
            br1 = [center[0]+self.button_size/2+OUT, center[1]+self.button_size/2+OUT]
            draw.ellipse(tl1+br1, outline=self.button_underline_color, width=self.button_underline_width)

        # Handle
        value = self.button.get_current_value()  # 0, 1, or 2 if three_way
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

        # 3dot specifics
        rw = ICON_SIZE / 4   # 3dot top of switch width, height=width/2
        cr = ICON_SIZE / 16  # 3dot dot radius
        cs = ICON_SIZE / 16  # 3dot space between dots

        if not (self.three_way and value == 1):  # extreme positions
            if self.vertical:
                y1 = center[1]+pos*self.switch_length
                ew = self.switch_width

                # top
                tl = [center[0]-ew/2, y1-ew/2]
                br = [center[0]+ew/2, y1+ew/2]
                if self.switch_style == "round":
                    draw.ellipse(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
                elif self.switch_style == "rect":
                    tl = [center[0]-ew, y1-ew/3]
                    br = [center[0]+ew, y1+ew/3]
                    draw.rectangle(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=int(self.handle_stroke_width * 1.5))
                else: # complicate 3 dot rectangle
                    tl = [center[0]-rw, y1-rw/3]
                    br = [center[0]+rw, y1+rw/3]
                    # draw.rectangle(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
                    draw.rounded_rectangle(tl+br, radius=rw/2, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=int(self.handle_stroke_width * 1.5))

                # Handle
                if self.handle_stroke_width > 0:
                    ew = ew + 2*self.handle_stroke_width
                    draw.line([tuple(center), (center[0], y1)],
                              width=ew,
                              fill=self.handle_stroke_color) #!STROKE color
                draw.line([tuple(center), (center[0], y1)],
                              width=self.switch_width,
                              fill=self.handle_fill_color)

                if self.switch_style == "3dot": # complicate 3 dot rectangle
                    cx = center[0] - cr - cs
                    tl = [cx-cr/2, y1-cr/2]
                    br = [cx+cr/2, y1+cr/2]
                    draw.ellipse(tl+br, fill=self.handle_dot_color)
                    cx = center[0]
                    tl = [cx-cr/2, y1-cr/2]
                    br = [cx+cr/2, y1+cr/2]
                    cx = center[0] + cr + cs
                    draw.ellipse(tl+br, fill=self.handle_dot_color)
                    tl = [cx-cr/2, y1-cr/2]
                    br = [cx+cr/2, y1+cr/2]
                    draw.ellipse(tl+br, fill=self.handle_dot_color)


                # small base ellipsis
                tl = [center[0]-ew/2, center[1]-ew/4]
                br = [center[0]+ew/2, center[1]+ew/4]
                draw.ellipse(tl+br, fill=self.handle_fill_color)

            else:
                x1 = center[0]+pos*self.switch_length
                ew = self.switch_width

                # top
                tl = [x1-ew/2, center[1]-ew/2]
                br = [x1+ew/2, center[1]+ew/2]
                if self.switch_style == "round":
                    draw.ellipse(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
                elif self.switch_style == "rect":
                    tl = [x1-ew/2, center[1]-ew]
                    br = [x1+ew/2, center[1]+ew]
                    draw.rectangle(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
                else: # complicate 3 dot rectangle
                    tl = [x1-rw/2, center[1]-rw]
                    br = [x1+rw/2, center[1]+rw]
                    # draw.rectangle(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
                    draw.rounded_rectangle(tl+br, radius=rw/2, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)

                # Tick
                if self.handle_stroke_width > 0:
                    ew = ew + 2*self.handle_stroke_width
                    draw.line([tuple(center), (x1, center[1])],
                              width=ew,
                              fill=self.handle_fill_color)
                draw.line([tuple(center), (x1, center[1])],
                              width=self.switch_width,
                              fill=self.handle_fill_color)

                if self.switch_style == "3dot": # complicate 3 dot rectangle
                    cy = center[1] - cr - cs
                    tl = [x1-cr/2, cy-cr/2]
                    br = [x1+cr/2, cy+cr/2]
                    draw.ellipse(tl+br, fill=self.handle_dot_color)
                    cy = center[1]
                    tl = [x1-cr/2, cy-cr/2]
                    br = [x1+cr/2, cy+cr/2]
                    cy = center[1] + cr + cs
                    draw.ellipse(tl+br, fill=self.handle_dot_color)
                    tl = [x1-cr/2, cy-cr/2]
                    br = [x1+cr/2, cy+cr/2]
                    draw.ellipse(tl+br, fill=self.handle_dot_color)

                # small base ellipsis
                tl = [center[0]-ew/4, center[1]-ew/2]
                br = [center[0]+ew/4, center[1]+ew/2]
                draw.ellipse(tl+br, fill=self.handle_fill_color)
        else:  # middle position
            ew = self.switch_width
            tl = [center[0]-ew/2, center[1]-ew/2]
            br = [center[0]+ew/2, center[1]+ew/2]
            if self.switch_style == "round":
                draw.ellipse(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
            elif self.switch_style == "rect":
                tl = [center[0]-ew, center[1]-ew/2]
                br = [center[0]+ew, center[1]+ew/2]
                draw.rectangle(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
            else: # complicate 3 dot rectangle
                if self.vertical:
                    tl = [center[0]-rw, center[1]-rw/2]
                    br = [center[0]+rw, center[1]+rw/2]
                    # draw.rectangle(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
                    draw.rounded_rectangle(tl+br, radius=rw/2, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
                    cx = center[0] - cr - cs
                    tl = [cx-cr/2, center[1]-cr/2]
                    br = [cx+cr/2, center[1]+cr/2]
                    draw.ellipse(tl+br, fill=self.handle_dot_color)
                    cx = center[0]
                    tl = [cx-cr/2, center[1]-cr/2]
                    br = [cx+cr/2, center[1]+cr/2]
                    cx = center[0] + cr + cs
                    draw.ellipse(tl+br, fill=self.handle_dot_color)
                    tl = [cx-cr/2, center[1]-cr/2]
                    br = [cx+cr/2, center[1]+cr/2]
                    draw.ellipse(tl+br, fill=self.handle_dot_color)
                else:
                    tl = [center[0]-rw/2, center[1]-rw]
                    br = [center[0]+rw/2, center[1]+rw]
                    # draw.rectangle(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
                    draw.rounded_rectangle(tl+br, radius=rw/2, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
                    cy = center[1] - cr - cs
                    tl = [center[0]-cr/2, cy-cr/2]
                    br = [center[0]+cr/2, cy+cr/2]
                    draw.ellipse(tl+br, fill=self.handle_dot_color)
                    cy = center[1]
                    tl = [center[0]-cr/2, cy-cr/2]
                    br = [center[0]+cr/2, cy+cr/2]
                    cy = center[1] + cr + cs
                    draw.ellipse(tl+br, fill=self.handle_dot_color)
                    tl = [center[0]-cr/2, cy-cr/2]
                    br = [center[0]+cr/2, cy+cr/2]
                    draw.ellipse(tl+br, fill=self.handle_dot_color)

        # Labels
        font = self.get_font(self.tick_label_font, int(self.tick_label_size))
        if self.vertical:
            label_left = ICON_SIZE/2 - self.tick_space - self.tick_length
            align="right"
            anchor="rm"
            if self.label_opposite:
                label_left = ICON_SIZE/2 + self.tick_space + self.tick_length
                align="left"
                anchor="lm"
            tick_end = ICON_SIZE / 2
            draw.text((label_left, ICON_SIZE/2 - self.switch_length),
                      text=self.tick_labels[0],
                      font=font,
                      anchor=anchor,
                      align=align,
                      fill=self.tick_label_color)
            n = 1
            if self.three_way:
                draw.text((label_left, ICON_SIZE/2),
                          text=self.tick_labels[1],
                          font=font,
                          anchor=anchor,
                          align=align,
                          fill=self.tick_label_color)
                n = 2
            draw.text((label_left, ICON_SIZE/2 + self.switch_length),
                      text=self.tick_labels[n],
                      font=font,
                      anchor=anchor,
                      align=align,
                      fill=self.tick_label_color)
        else:
            label_top = inside * 2 + self.tick_label_size
            align="center"
            anchor="ms"
            if self.label_opposite:
                label_top = ICON_SIZE - inside * 2
            tick_end = ICON_SIZE / 2
            draw.text((2*inside, label_top),
                      text=self.tick_labels[0],
                      font=font,
                      anchor="ls",
                      align=align,
                      fill=self.tick_label_color)
            n = 1
            if self.three_way:
                draw.text((ICON_SIZE/2, label_top),
                          text=self.tick_labels[1],
                          font=font,
                          anchor="ms",
                          align=align,
                          fill=self.tick_label_color)
                n = 2
            draw.text((ICON_SIZE-2*inside, label_top),
                      text=self.tick_labels[n],
                      font=font,
                      anchor="rs",
                      align=align,
                      fill=self.tick_label_color)

        # Ticks
        if self.tick_length > 0:
            if self.vertical:
                underline = ICON_SIZE/2 - self.tick_space
                tick_end = underline + self.tick_length
                if self.label_opposite:
                    underline = ICON_SIZE/2 + self.tick_space
                    tick_end = underline - self.tick_length

                draw.line([(underline, ICON_SIZE/2 - self.switch_length),(tick_end, ICON_SIZE/2 - self.switch_length)], width=self.tick_width, fill=self.tick_color)
                if self.three_way:
                    draw.line([(underline, ICON_SIZE/2),(tick_end, ICON_SIZE/2)], width=self.tick_width, fill=self.tick_color)
                draw.line([(underline, ICON_SIZE/2 + self.switch_length),(tick_end, ICON_SIZE/2 + self.switch_length)], width=self.tick_width, fill=self.tick_color)
                # underline bar
                # if self.label_opposite:
                #     draw.line([(underline, ICON_SIZE/2 - self.switch_length),(underline, ICON_SIZE/2 + self.switch_length)], width=self.tick_width, fill=self.tick_color)
                # else:
                if self.tick_underline_width > 0:
                    draw.line([(underline, ICON_SIZE/2 - self.switch_length),(underline, ICON_SIZE/2 + self.switch_length)], width=self.tick_underline_width, fill=self.tick_color)
            else:
                underline = ICON_SIZE/2 - self.tick_length - self.tick_space
                tick_end = ICON_SIZE/2 - self.tick_space
                if self.label_opposite:
                    underline = ICON_SIZE/2 + self.tick_space
                    tick_end = underline + self.tick_length

                draw.line([(2*inside,underline),(2*inside,tick_end)], width=self.tick_width, fill=self.tick_color)
                if self.three_way:
                    draw.line([(ICON_SIZE/2,underline),(ICON_SIZE/2,tick_end)], width=self.tick_width, fill=self.tick_color)
                draw.line([(ICON_SIZE-2*inside,underline),(ICON_SIZE-2*inside,tick_end)], width=self.tick_width, fill=self.tick_color)
                # underline bar
                if self.tick_underline_width > 0:
                    if self.label_opposite:
                        draw.line([(2*inside,tick_end),(ICON_SIZE-2*inside,tick_end)], width=self.tick_underline_width, fill=self.tick_color)
                    else:
                        draw.line([(2*inside,underline),(ICON_SIZE-2*inside,underline)], width=self.tick_underline_width, fill=self.tick_color)

        return self.move_and_send(image)


class PushSwitch(SwitchCommonBase):

    def __init__(self, config: dict, button: "Button"):

        SwitchCommonBase.__init__(self, config=config, button=button, switch_type="push-switch")

        # Alternate defaults
        self.button_size = self.switch.get("button-size", 80)

        self.handle_size = self.switch.get("witness-size", min(self.button_size/2, 40))

        self.handle_fill_color = self.switch.get("witness-fill-color", (0,0,0,0))
        self.handle_fill_color = convert_color(self.handle_fill_color)
        self.handle_stroke_color = self.switch.get("witness-stroke-color", (255,255,255))
        self.handle_stroke_color = convert_color(self.handle_stroke_color)
        self.handle_stroke_width = self.switch.get("witness-stroke-width", 4)

        self.handle_off_fill_color = self.switch.get("witness-fill-off-color", (0,0,0,0))
        self.handle_off_fill_color = convert_color(self.handle_off_fill_color)
        self.handle_off_stroke_color = self.switch.get("witness-stroke-off-color", (255,255,255, 0))
        self.handle_off_stroke_color = convert_color(self.handle_off_stroke_color)
        self.handle_off_stroke_width = self.switch.get("witness-stroke-off-width", 4)


    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        OUT = 8
        inside = ICON_SIZE / 32

        image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)
        draw = ImageDraw.Draw(image)

        # Button
        center = [ICON_SIZE/2, ICON_SIZE/2]
        tl = [center[0]-self.button_size/2, center[1]-self.button_size/2]
        br = [center[0]+self.button_size/2, center[1]+self.button_size/2]
        draw.ellipse(tl+br, fill=self.button_fill_color, outline=self.button_stroke_color, width=self.button_stroke_width)

        if self.handle_size > 0:
            tl = [center[0]-self.handle_size/2, center[1]-self.handle_size/2]
            br = [center[0]+self.handle_size/2, center[1]+self.handle_size/2]
            if hasattr(self.button._activation, "is_off") and self.button._activation.is_off():
                logger.debug(f"get_image_for_icon: button {self.button.name}: has on/off state and IS OFF")
                draw.ellipse(tl+br, fill=self.handle_off_fill_color, outline=self.handle_off_stroke_color, width=self.handle_off_stroke_width)
            else:
                if not hasattr(self.button._activation, "is_on"):
                    logger.debug(f"get_image_for_icon: button {self.button.name}: has no on/off state")
                draw.ellipse(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)

        return self.move_and_send(image)

#
# ###############################
# ANIMATED DRAW REPRESENTATION
#
#
class DrawAnimation(Icon):
    """
    https://stackoverflow.com/questions/5114292/break-interrupt-a-time-sleep-in-python
    """

    def __init__(self, config: dict, button: "Button"):

        Icon.__init__(self, config=config, button=button)

        self._animation = config.get("animation", {})

        # Base definition
        self.speed = float(self._animation.get("speed", 1))

        # Working attributes
        self.tween = 0

        self.running = None  # state unknown
        self.exit = None
        self.thread = None

    def loop(self):
        self.exit = threading.Event()
        while not self.exit.is_set():
            self.animate()
            self.button.render()
            self.exit.wait(self.speed)
        logger.debug(f"loop: exited")

    def should_run(self) -> bool:
        """
        Check conditions to animate the icon.
        """
        return False

    def animate(self):
        """
        Where changes between frames occur

        :returns:   { description_of_the_return_value }
        :rtype:     { return_type_description }
        """
        self.tween = self.tween + 1
        # logger.debug(f"animate: tick")
        return super().render()

    def anim_start(self):
        """
        Starts animation
        """
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.name = f"ButtonAnimate::loop({self.button.name})"
            self.thread.start()
            logger.debug(f"anim_start: started")
        else:
            logger.warning(f"anim_start: button {self.button.name}: already started")

    def anim_stop(self):
        """
        Stops animation
        """
        if self.running:
            self.running = False
            self.exit.set()
            self.thread.join(timeout=2*self.speed)
            if self.thread.is_alive():
                logger.warning(f"anim_stop: button {self.button.name}: animation did not terminate")
            logger.debug(f"anim_stop: stopped")
        else:
            logger.debug(f"anim_stop: button {self.button.name}: already stopped")

    def clean(self):
        """
        Stops animation and remove icon from deck
        """
        logger.debug(f"clean: button {self.button.name}: cleaning requested")
        self.anim_stop()
        logger.debug(f"clean: button {self.button.name}: stopped")
        super().clean()

    def render(self):
        """
        Renders icon_off or current icon in list
        """
        logger.debug(f"render: button {self.button.name}: enter")
        if self.is_valid():
            logger.debug(f"render: button {self.button.name}: is valid {self.should_run()}, {self.running}")
            if self.should_run():
                if not self.running:
                    self.anim_start()
                return super().render()
            else:
                if self.running:
                    self.anim_stop()
                return super().render()
        return None


class DrawAnimationFTG(DrawAnimation):

    def __init__(self, config: dict, button: "Button"):

        DrawAnimation.__init__(self, config=config, button=button)


    def should_run(self):
        """
        I.e. only works with onoff activations.
        """
        return hasattr(self.button._activation, "is_on") and self.button._activation.is_on()

    def get_image_for_icon(self):
        """
        Can use self.running to check whether animated or not.
        Can use self.tween to increase iterations.
        Text, color, sizes are all hardcoded here.
        """
        image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=(20, 20, 20)) # self.button.page.cockpit_color
        draw = ImageDraw.Draw(image)

        # Button
        cs = 4  # light size, px
        lum = 5 # num flashing green center lines
        nb = 2 * lum  # num side bleu lights, i.e. twice more blue lights than green ones
        h0 = ICON_SIZE/16  # space from left/right sides
        h1 = ICON_SIZE / 2 - h0  # space from bottom of upper middle part
        s = (ICON_SIZE - (2*h0)) / (nb - 1) # spece between blue lights
        # Taxiway borders, blue lights
        for i in range(nb):
            for h in [h0, h1]:
                w = h0 + i * s
                tl = [w-cs, h-cs]
                br = [w+cs, h+cs]
                draw.ellipse(tl+br, fill="blue")
        # Taxiway center yellow line
        h = ICON_SIZE / 4
        draw.line([(h0, h), (ICON_SIZE - h0, h)], fill="yellow", width=4)

        # Taxiway center lights, lit if animated
        cs = 2 * cs
        for i in range(lum):
            w = h + i * s * 2 - s / 2
            w = ICON_SIZE - w
            tl = [w-cs, h-cs]
            br = [w+cs, h+cs]
            color = "lime" if self.running and (self.tween+i) % lum == 0 else "chocolate"
            draw.ellipse(tl+br, fill=color)

        # Text AVAIL (=off) or framed ON (=on)
        font = self.get_font(DEFAULT_LABEL_FONT, 80)
        inside = ICON_SIZE / 16
        cx = ICON_SIZE / 2
        cy = int( 3 * ICON_SIZE / 4 )
        if self.running:
            draw.multiline_text((cx, cy),
                      text="ON",
                      font=font,
                      anchor="mm",
                      align="center",
                      fill="deepskyblue")
            txtbb = draw.multiline_textbbox((cx, cy),  # min frame, just around the text
                      text="ON",
                      font=font,
                      anchor="mm",
                      align="center")
            text_margin = 2 * inside  # margin "around" text, line will be that far from text
            framebb = ((txtbb[0]-text_margin, txtbb[1]-text_margin/2), (txtbb[2]+text_margin, txtbb[3]+text_margin/2))
            side_margin = 4 * inside  # margin from side of part of annunciator
            framemax = ((cx - ICON_SIZE/2 + side_margin, cy - ICON_SIZE/4 + side_margin), (cx + ICON_SIZE/2 - side_margin, cy + ICON_SIZE/4 - side_margin))
            frame = ((min(framebb[0][0], framemax[0][0]),min(framebb[0][1], framemax[0][1])), (max(framebb[1][0], framemax[1][0]), max(framebb[1][1], framemax[1][1])))
            thick = int(ICON_SIZE / 32)
            # logger.debug(f"render: button {self.button.name}: part {partname}: {framebb}, {framemax}, {frame}")
            draw.rectangle(frame, outline="deepskyblue", width=thick)
        else:
            font = self.get_font(DEFAULT_LABEL_FONT, 60)
            draw.multiline_text((cx, cy),
                      text="AVAIL",
                      font=font,
                      anchor="mm",
                      align="center",
                      fill="lime")

        return image.convert("RGB")
