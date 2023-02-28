# ###########################
# Buttons that are drawn on render()
#
import logging
import threading
import time
import colorsys
import traceback
import math
from random import randint

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageColor
# from mergedeep import merge
from metar import Metar

from .constant import FORMULA, ANNUNCIATOR_DEFAULTS, ANNUNCIATOR_STYLES, LIGHT_OFF_BRIGHTNESS, WEATHER_ICON_FONT, ICON_FONT
from .color import convert_color, light_off
from .rpc import RPC
from .resources.icons import icons as FA_ICONS        # Font Awesome Icons
from .resources.weathericons import WEATHER_ICONS     # Weather Icons
from .button_representation import Icon
from .button_annunciator import ICON_SIZE, DEFAULT_INVERT_COLOR

logger = logging.getLogger("DrawIcon")
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

        self.metar = Metar.Metar("LFSB 201400Z 33008KT 7000 -SN SCT015 SCT030 01/M00 Q1025")

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
        fontname = self.get_font(icon_font)
        if fontname is None:
            logger.warning(f"get_image_for_icon: icon font not found, cannot overlay icon {icon_name} in {icon_font}")
        else:
            font = ImageFont.truetype(fontname, int(icon_size))
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

        fontname = self.get_font(data_font)
        if fontname is None:
            logger.warning(f"get_image_for_icon: data font {data_font} not found, cannot overlay data")
        else:
            font = ImageFont.truetype(fontname, data_size)
            font_unit = ImageFont.truetype(fontname, int(data_size * 0.50))
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
            fontname = self.get_font(botl_font)
            if fontname is None:
                logger.warning(f"get_image_for_icon: bottom line font {botl_font} not found, cannot print bottom line")
            else:
                font = ImageFont.truetype(fontname, botl_size)
                w = image.width / 2
                h = image.height / 2
                h = image.height - inside - botl_size / 2  # forces BOTTOM position
                draw.multiline_text((w, h),  # (image.width / 2, 15)
                          text=bottom_line,
                          font=font,
                          anchor="md",
                          align="center",
                          fill=botl_color)
        return image


class WeatherIcon(DrawBase):

    def __init__(self, config: dict, button: "Button"):
        DrawBase.__init__(self, config=config, button=button)

        self.metar = Metar.Metar("LFSB 201400Z 33008KT 7000 -SN SCT015 SCT030 01/M00 Q1025")
        self.weather_icon = "wi_day_sunny"

    def set_metar(self, metar):
        self.metar = metar
        self.to_icon()
        self.button.render()

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE))                     # annunciator text and leds , color=(0, 0, 0, 0)
        draw = ImageDraw.Draw(image)
        inside = round(0.04 * image.width + 0.5)

        self.to_icon()

        # Weather Icon
        icon_name = self.weather_icon
        if icon_name is not None:
            icon_str = WEATHER_ICONS.get(icon_name, "*")
        else:
            icon_str = "*"

        icon_font = self._config.get("icon-font", WEATHER_ICON_FONT)
        icon_size = int(image.width / 2)
        icon_color = "white"
        fontname = self.get_font(icon_font)
        if fontname is None:
            logger.warning(f"get_image_for_icon: icon font not found, cannot overlay icon")
        else:
            font = ImageFont.truetype(fontname, icon_size)
            inside = round(0.04 * image.width + 0.5)
            w = image.width / 2
            h = image.height / 2
            draw.text((w, h),  # (image.width / 2, 15)
                      text=icon_str,
                      font=font,
                      anchor="mm",
                      align="center",
                      fill=light_off(icon_color, 0.2))

        # Weather Data
        text_font = self._config.get("weather-font", self.label_font)
        fontname = self.get_font(text_font)
        if fontname is None:
            logger.warning(f"get_image_for_icon: text font not found, cannot overlay text")
        else:
            # logger.debug(f"get_image: font {fontname}")
            detailsize = int(image.width / 10)
            font = ImageFont.truetype(fontname, detailsize)
            w = inside
            p = "l"
            a = "left"
            h = image.height / 3
            il = detailsize
            draw.text((w, h),  # (image.width / 2, 15)
                      text=f"Temp: {self.metar.temp.string('C')}",
                      font=font,
                      anchor=p+"m",
                      align=a,
                      fill=self.label_color)

            h = h + il
            draw.text((w, h),  # (image.width / 2, 15)
                      text=f"Press: {self.metar.press.string('mb')}",
                      font=font,
                      anchor=p+"m",
                      align=a,
                      fill=self.label_color)

            if self.metar.wind_dir:
                h = h + il
                draw.multiline_text((w, h),  # (image.width / 2, 15)
                          text=f"Wind: {self.metar.wind_speed.string('MPS')} {self.metar.wind_dir.compass()}",
                          font=font,
                          anchor=p+"m",
                          align=a,
                          fill=self.label_color)

        return image

    def to_icon(self):
        WI = [
            "fog",
            "hail",
            "rain",
            "rain_mix",
            "rain_wind",
            "showers",
            "sleet",
            "snow",
            "sprinkle",
            "snow_wind",
            "smog",
            "smoke",
            "lightning",
            "raindrops",
            "raindrop",
            "dust",
            "snowflake_cold",
            "windy",
            "strong_wind",
            "sandstorm",
            "earthquake",
            "fire",
            "flood",
            "meteor",
            "tsunami",
            "volcano",
            "hurricane",
            "tornado",
            "small_craft_advisory",
            "gale_warning",
            "storm_warning",
            "hurricane_warning",
            "wind_direction",
            "degrees",
            "humidity",
            "na"
        ]

#
# ###############################
# SWITCH BUTTON REPRESENTATION
#
#
class CircularSwitch(DrawBase):

    def __init__(self, config: dict, button: "Button"):

        DrawBase.__init__(self, config=config, button=button)

        self.switch = config.get("circular-switch")

        self.switch_type = self.switch.get("type")
        self.switch_style = self.switch.get("switch-style")

        self.button_size = self.switch.get("button-size", int(2 * ICON_SIZE / 4))
        self.button_fill_color = self.switch.get("button-fill-color", "(150,150,150)")
        self.button_fill_color = convert_color(self.button_fill_color)
        self.button_stroke_color = self.switch.get("button-stroke-color", "white")
        self.button_stroke_color = convert_color(self.button_stroke_color)
        self.button_stroke_width = self.switch.get("button-stroke-width", 4)

        self.handle_fill_color = self.switch.get("handle-fill-color", "(100,100,100)")
        self.handle_fill_color = convert_color(self.handle_fill_color)
        self.handle_stroke_color = self.switch.get("handle-stroke-color", "white")
        self.handle_stroke_color = convert_color(self.handle_stroke_color)
        self.handle_stroke_width = self.switch.get("handle-stroke-width", 4)

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
        self.tick_label_space = self.switch.get("tick-label-space", 10)
        self.tick_labels = self.switch.get("tick-labels")
        self.tick_label_font = self.switch.get("tick-label-font", "DIN")
        self.tick_label_size = self.switch.get("tick-label-size", 50)
        self.tick_label_color = self.switch.get("tick-label-color", "white")
        self.tick_label_color = convert_color(self.tick_label_color)
        # Needle
        self.needle_width = self.switch.get("needle-width", 8)
        self.needle_length = self.switch.get("needle-length", 50)  # % of radius
        self.needle_length = int(self.needle_length * self.button_size / 200)
        self.needle_color = self.switch.get("needle-color", "white")
        self.needle_color = convert_color(self.needle_color)
        # Options
        self.needle_underline_width = self.switch.get("needle-underline-width", 4)
        self.needle_underline_color = self.switch.get("needle-underline-color", "black")
        self.needle_underline_color = convert_color(self.needle_underline_color)

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

        image = Image.new(mode="RGBA", size=(ICON_SIZE*2, ICON_SIZE*2), color=self.cockpit_color)                     # annunciator text and leds , color=(0, 0, 0, 0)
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


        # Thick run mark
        if self.tick_underline_width > 0:
            tl = [center[0]-tick_start, center[1]-tick_start]
            br = [center[0]+tick_start, center[1]+tick_start]
            draw.arc(tl+br, fill=self.tick_underline_color, start=self.tick_from+90, end=self.tick_to+90, width=self.tick_underline_width)

        # Labels
        # print("-<-<", label_anchors)
        fontname = self.get_font(self.tick_label_font)
        font = ImageFont.truetype(fontname, int(self.tick_label_size))
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

        return image.convert("RGB")


class Switch(DrawBase):

    def __init__(self, config: dict, button: "Button"):

        DrawBase.__init__(self, config=config, button=button)

        self.switch = config.get("switch")

        self.switch_style = self.switch.get("switch-style", "round")  # rect, triple
        # Base
        self.base_size = self.switch.get("base-size", 80)
        self.base_color = self.switch.get("base-color", "(200, 200, 200)")
        self.base_color = convert_color(self.base_color)
        self.base_underline_color = self.switch.get("base-underline-color", "orange")
        self.base_underline_width = self.switch.get("base-underline-width", 0)
        # Switch
        self.switch_color = self.switch.get("switch-color", "(128, 128, 128)")
        self.switch_color = convert_color(self.switch_color)
        self.switch_stroke_color = self.switch.get("switch-stroke-color", "white")
        self.switch_stroke_color = convert_color(self.switch_stroke_color)
        self.switch_stroke_width = self.switch.get("switch-stroke-width", 2)
        self.switch_length = self.switch.get("switchs-length", ICON_SIZE/3)
        self.switch_width = self.switch.get("switchs-width", 32)
        self.switch_dot_color = self.switch.get("switch-dot-color", "white")  # 3dot
        self.switch_dot_color = convert_color(self.switch_dot_color)
        # Ticks
        self.tick_space = self.switch.get("tick-space", 10)
        self.tick_length = self.switch.get("tick-length", 20)
        self.tick_width = self.switch.get("tick-length", 6)
        self.tick_color = self.switch.get("switch-color", "(128, 128, 128)")
        self.tick_color = convert_color(self.switch_color)
        self.tick_underline_width = self.switch.get("tick-underline-width", 6)
        # Labels
        self.tick_label_space = self.switch.get("tick-label-space", 10)
        self.tick_label_color = self.switch.get("tick-label-color", "white")
        self.tick_label_color = convert_color(self.tick_label_color)
        self.tick_label_font = self.switch.get("tick-label-font", "DIN")
        self.tick_label_size = self.switch.get("tick-label-size", 50)
        self.tick_labels = self.switch.get("tick-labels")
        self.label_opposite = self.button.has_option("label-opposite")
        # Options
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

        image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=self.cockpit_color)
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


        tl = [center[0]-self.base_size/2, center[1]-self.base_size/2]
        br = [center[0]+self.base_size/2, center[1]+self.base_size/2]
        if self.hexabase:
            draw.regular_polygon((center[0], center[1], self.base_size/2), n_sides=6, rotation=randint(0, 60), fill=self.base_color)
        else:
            draw.ellipse(tl+br, fill=self.base_color)
        if self.base_underline_width > 0:
            tl1 = [center[0]-self.base_size/2-OUT, center[1]-self.base_size/2-OUT]
            br1 = [center[0]+self.base_size/2+OUT, center[1]+self.base_size/2+OUT]
            draw.ellipse(tl1+br1, outline=self.base_underline_color, width=self.base_underline_width)

        # Handle
        value = self.button.get_current_value()  # 0, 1, or 2 if three_way
        if value is None:
            value = 0

        pos = -1
        if value != 0:
            if self.three_way:
                if value == 1:
                    pos = 0
                else:
                    pos = 1

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
                    draw.ellipse(tl+br, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)
                elif self.switch_style == "rect":
                    tl = [center[0]-ew, y1-ew/2]
                    br = [center[0]+ew, y1+ew/2]
                    draw.rectangle(tl+br, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)
                else: # complicate 3 dot rectangle
                    tl = [center[0]-rw, y1-rw/2]
                    br = [center[0]+rw, y1+rw/2]
                    # draw.rectangle(tl+br, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)
                    draw.rounded_rectangle(tl+br, radius=rw/2, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)

                # Tick
                if self.switch_stroke_width > 0:
                    ew = ew + 2*self.switch_stroke_width
                    draw.line([tuple(center), (center[0], y1)],
                              width=ew,
                              fill=self.switch_stroke_color)
                draw.line([tuple(center), (center[0], y1)],
                              width=self.switch_width,
                              fill=self.switch_color)

                if self.switch_style == "3dot": # complicate 3 dot rectangle
                    cx = center[0] - cr - cs
                    tl = [cx-cr/2, y1-cr/2]
                    br = [cx+cr/2, y1+cr/2]
                    draw.ellipse(tl+br, fill=self.switch_dot_color)
                    cx = center[0]
                    tl = [cx-cr/2, y1-cr/2]
                    br = [cx+cr/2, y1+cr/2]
                    cx = center[0] + cr + cs
                    draw.ellipse(tl+br, fill=self.switch_dot_color)
                    tl = [cx-cr/2, y1-cr/2]
                    br = [cx+cr/2, y1+cr/2]
                    draw.ellipse(tl+br, fill=self.switch_dot_color)


                # small base ellipsis
                tl = [center[0]-ew/2, center[1]-ew/4]
                br = [center[0]+ew/2, center[1]+ew/4]
                draw.ellipse(tl+br, fill=self.switch_color)

            else:
                x1 = center[0]+pos*self.switch_length
                ew = self.switch_width

                # top
                tl = [x1-ew/2, center[1]-ew/2]
                br = [x1+ew/2, center[1]+ew/2]
                if self.switch_style == "round":
                    draw.ellipse(tl+br, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)
                elif self.switch_style == "rect":
                    tl = [x1-ew/2, center[1]-ew]
                    br = [x1+ew/2, center[1]+ew]
                    draw.rectangle(tl+br, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)
                else: # complicate 3 dot rectangle
                    tl = [x1-rw/2, center[1]-rw]
                    br = [x1+rw/2, center[1]+rw]
                    # draw.rectangle(tl+br, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)
                    draw.rounded_rectangle(tl+br, radius=rw/2, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)

                # Tick
                if self.switch_stroke_width > 0:
                    ew = ew + 2*self.switch_stroke_width
                    draw.line([tuple(center), (x1, center[1])],
                              width=ew,
                              fill=self.switch_stroke_color)
                draw.line([tuple(center), (x1, center[1])],
                              width=self.switch_width,
                              fill=self.switch_color)

                if self.switch_style == "3dot": # complicate 3 dot rectangle
                    cy = center[1] - cr - cs
                    tl = [x1-cr/2, cy-cr/2]
                    br = [x1+cr/2, cy+cr/2]
                    draw.ellipse(tl+br, fill=self.switch_dot_color)
                    cy = center[1]
                    tl = [x1-cr/2, cy-cr/2]
                    br = [x1+cr/2, cy+cr/2]
                    cy = center[1] + cr + cs
                    draw.ellipse(tl+br, fill=self.switch_dot_color)
                    tl = [x1-cr/2, cy-cr/2]
                    br = [x1+cr/2, cy+cr/2]
                    draw.ellipse(tl+br, fill=self.switch_dot_color)

                # small base ellipsis
                tl = [center[0]-ew/4, center[1]-ew/2]
                br = [center[0]+ew/4, center[1]+ew/2]
                draw.ellipse(tl+br, fill=self.switch_color)
        else:  # middle position
            ew = self.switch_width
            tl = [center[0]-ew/2, center[1]-ew/2]
            br = [center[0]+ew/2, center[1]+ew/2]
            if self.switch_style == "round":
                draw.ellipse(tl+br, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)
            elif self.switch_style == "rect":
                tl = [center[0]-ew, center[1]-ew/2]
                br = [center[0]+ew, center[1]+ew/2]
                draw.rectangle(tl+br, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)
            else: # complicate 3 dot rectangle
                if self.vertical:
                    tl = [center[0]-rw, center[1]-rw/2]
                    br = [center[0]+rw, center[1]+rw/2]
                    # draw.rectangle(tl+br, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)
                    draw.rounded_rectangle(tl+br, radius=rw/2, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)
                    cx = center[0] - cr - cs
                    tl = [cx-cr/2, center[1]-cr/2]
                    br = [cx+cr/2, center[1]+cr/2]
                    draw.ellipse(tl+br, fill=self.switch_dot_color)
                    cx = center[0]
                    tl = [cx-cr/2, center[1]-cr/2]
                    br = [cx+cr/2, center[1]+cr/2]
                    cx = center[0] + cr + cs
                    draw.ellipse(tl+br, fill=self.switch_dot_color)
                    tl = [cx-cr/2, center[1]-cr/2]
                    br = [cx+cr/2, center[1]+cr/2]
                    draw.ellipse(tl+br, fill=self.switch_dot_color)
                else:
                    tl = [center[0]-rw/2, center[1]-rw]
                    br = [center[0]+rw/2, center[1]+rw]
                    # draw.rectangle(tl+br, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)
                    draw.rounded_rectangle(tl+br, radius=rw/2, fill=self.switch_color, outline=self.switch_stroke_color, width=self.switch_stroke_width)
                    cy = center[1] - cr - cs
                    tl = [center[0]-cr/2, cy-cr/2]
                    br = [center[0]+cr/2, cy+cr/2]
                    draw.ellipse(tl+br, fill=self.switch_dot_color)
                    cy = center[1]
                    tl = [center[0]-cr/2, cy-cr/2]
                    br = [center[0]+cr/2, cy+cr/2]
                    cy = center[1] + cr + cs
                    draw.ellipse(tl+br, fill=self.switch_dot_color)
                    tl = [center[0]-cr/2, cy-cr/2]
                    br = [center[0]+cr/2, cy+cr/2]
                    draw.ellipse(tl+br, fill=self.switch_dot_color)

        # Labels
        fontname = self.get_font(self.tick_label_font)
        font = ImageFont.truetype(fontname, int(self.tick_label_size))
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

        return image.convert("RGB")

#
# ###############################
# ANIMATED DRAW REPRESENTATION
#
#
class DrawAnimation(Icon):
    """
    """

    def __init__(self, config: dict, button: "Button"):

        Icon.__init__(self, config=config, button=button)

        self._animation = config.get("animation")

        # Base definition
        self.speed = float(self._animation.get("speed", 1))

        # Working attributes
        self.tween = 0

        self.running = None  # state unknown
        self.thread = None

    def loop(self):
        while self.running:
            self.animate()
            self.button.render()
            time.sleep(self.speed)

    def should_run(self) -> bool:
        """
        Check conditions to animate the icon.
        """
        value = self.get_current_value()
        if type(value) == dict:
            value = value[list(value.keys())[0]]
        return value is not None and value != 0

    def animate(self):
        """
        Where changes between frames occur

        :returns:   { description_of_the_return_value }
        :rtype:     { return_type_description }
        """
        self.tween = self.tween + 1
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
        else:
            logger.warning(f"anim_start: button {self.button.name}: already started")

    def anim_stop(self):
        """
        Stops animation
        """
        if self.running:
            self.running = False
            self.thread.join(timeout=2*self.speed)
            if self.thread.is_alive():
                logger.warning(f"anim_stop: button {self.button.name}: animation did not terminate")
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
        if self.is_valid():
            if self.should_run():
                if not self.running:
                    self.anim_start()
                return super().render()
            else:
                if self.running:
                    self.anim_stop()
                return super().render()
        return None
