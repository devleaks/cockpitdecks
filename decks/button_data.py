# ###########################
# Button with Simple "dashboard-like" data presentation.
#
# Label
# <ICON>  <DATA><DATA-UNIT>
#         <options>
import logging
import threading
import time
import colorsys

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageColor
from mergedeep import merge
from .constant import convert_color

from .button_core import Button
from .rpc import RPC
from .icons import ICONS
from .weathericons import WEATHER_ICONS
from metar import Metar

logger = logging.getLogger("DataButton")
logger.setLevel(logging.DEBUG)

def light_off(color, lightness: float):
    # Darkens (or lighten) a color
    if color.startswith("("):
        color = convert_color(color)
    if type(color) == str:
        color = ImageColor.getrgb(color)
    a = list(colorsys.rgb_to_hls(*[c / 255 for c in color]))
    a[1] = lightness
    return tuple([int(c * 256) for c in colorsys.hls_to_rgb(*a)])


class DataButton(Button):

    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)


    def get_data_value(self, data: dict):
        return data.get("data", "---")

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = self.get_image_for_icon()

        if image is not None:
            draw = None
            # Add label if any
            image = image.copy()  # we will add text over it
            draw = ImageDraw.Draw(image)
            inside = round(0.04 * image.width + 0.5)
            iconsize = 24  # default

            # Label (forced at TOP line of image)
            label = self.get_label()
            if label is not None:
                fontname = self.get_font()
                if fontname is None:
                    logger.warning(f"get_image: label font not found, cannot overlay label")
                else:
                    # logger.debug(f"get_image: font {fontname}")
                    font = ImageFont.truetype(fontname, self.label_size)
                    w = image.width / 2
                    p = "m"
                    a = "center"
                    if self.label_position[0] == "l":
                        w = inside
                        p = "l"
                        a = "left"
                    elif self.label_position[0] == "r":
                        w = image.width - inside
                        p = "r"
                        a = "right"
                    h = image.height / 2
                    h = inside + self.label_size / 2 # forces TOP position
                    # logger.debug(f"get_image: position {(w, h)}")
                    draw.multiline_text((w, h),  # (image.width / 2, 15)
                              text=label,
                              font=font,
                              anchor=p+"m",
                              align=a,
                              fill=self.label_color)

            # Display Data
            data = self._config.get("data")
            if data is None:
                logger.warning(f"get_image: button {self.name}: no data")
                return image

            # Icon
            iconname = data.get("icon-name")
            if iconname is not None:
                iconstr = ICONS.get(iconname, "*")
            else:
                iconstr = "*"
            iconfont = data.get("icon-font", "fontawesome.otf")
            iconsize = data.get("icon-size", iconsize)
            iconcolor = data.get("icon-color", "white")
            fontname = self.get_font(iconfont)
            if fontname is None:
                logger.warning(f"get_image: icon font not found, cannot overlay icon")
            else:
                font = ImageFont.truetype(fontname, iconsize)
                inside = round(0.04 * image.width + 0.5)
                w = inside
                h = image.height / 2
                draw.text((w, h),  # (image.width / 2, 15)
                          text=iconstr,
                          font=font,
                          anchor="lm",
                          align="left",
                          fill=iconcolor)

            # Data
            DATAPROGRESS_SPACE = 8
            DATAPROGRESS = 6
            datavalue = self.get_data_value(data)
            dataformat = data.get("data-format")
            if dataformat is not None:
                datastr = dataformat.format(datavalue)
            else:
                datastr = str(datavalue)
            dataunit = data.get("data-unit")
            if dataunit is not None:
                datastr = datastr + " " + dataunit
            datasize = data.get("data-size", 20)  # @todo: should adapt based on len(data)
            dataprogress = data.get("data-progress")
            datacolor = data.get("data-color", self.label_color)
            datafont = data.get("data-font", self.label_font)
            datafont = self.get_font(datafont)
            if font is None:
                logger.warning(f"get_image: data font not found, cannot overlay label")
            else:
                font = ImageFont.truetype(datafont, datasize)
                inside = round(0.04 * image.width + 0.5)
                w = image.width - inside
                h = image.height / 2
                # if dataprogress is not None:
                #     h = h - DATAPROGRESS_SPACE - DATAPROGRESS / 2
                draw.text((w, h),  # (image.width / 2, 15)
                          text=datastr,
                          font=font,
                          anchor="rm",
                          align="right",
                          fill=datacolor)

            # Progress bar
            if dataprogress is not None:
                w = iconsize + 4 * inside
                h = 3 * image.height / 4 - 2 * DATAPROGRESS
                pct = float(datavalue) / float(dataprogress)
                if pct > 1:
                    pct = 1
                fullcolor = light_off(datacolor, 0.30)
                l = w + pct * ((image.width - inside)-w)
                draw.line([(w, h), (image.width - inside, h)],fill=fullcolor, width=DATAPROGRESS, joint="curve") # 100%
                draw.line([(w, h), (l, h)], fill=datacolor, width=DATAPROGRESS, joint="curve")

            # Bottomline (forced at CENTER BOTTOM line of icon)
            bottomline = data.get("bottomline")
            if bottomline is not None:
                fontname = self.get_font()
                if fontname is None:
                    logger.warning(f"get_image: label font not found, cannot overlay label")
                else:
                    font = ImageFont.truetype(fontname, self.label_size)
                    w = image.width / 2
                    h = image.height / 2
                    h = image.height - inside - self.label_size / 2  # forces BOTTOM position
                    draw.multiline_text((w, h),  # (image.width / 2, 15)
                              text=bottomline,
                              font=font,
                              anchor="md",
                              align="center",
                              fill=self.label_color)

            if not self.is_valid() or self.has_option("placeholder"):
                if draw is None:  # no label
                    image = image.copy()  # we will add text over it
                    draw = ImageDraw.Draw(image)
                c = round(0.97 * image.width)  # % from edge
                s = round(0.1 * image.width)   # size
                pologon = ( (c, c), (c, c-s), (c-s, c) )  # lower right corner
                draw.polygon(pologon, fill="red", outline="white")
            return image
        else:
            logger.warning(f"get_image: button {self.name}: icon {self.key_icon} not found")
            # logger.debug(f"{self.deck.icons.keys()}")
        return None

class WeatherButton(DataButton):

    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)

        self.metar = Metar.Metar("LFSB 201400Z 33008KT 7000 -SN SCT015 SCT030 01/M00 Q1025")

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = self.get_image_for_icon()

        if image is not None:
            draw = None
            # Add label if any
            image = image.copy()  # we will add text over it
            draw = ImageDraw.Draw(image)
            inside = round(0.04 * image.width + 0.5)
            iconsize = 24  # default

            # Label (forced at TOP line of image)
            label = f"{self.metar.station_id} {self.metar.cycle}"
            if label is not None:
                fontname = self.get_font()
                if fontname is None:
                    logger.warning(f"get_image: label font not found, cannot overlay label")
                else:
                    # logger.debug(f"get_image: font {fontname}")
                    font = ImageFont.truetype(fontname, self.label_size)
                    w = image.width / 2
                    p = "m"
                    a = "center"
                    if self.label_position[0] == "l":
                        w = inside
                        p = "l"
                        a = "left"
                    elif self.label_position[0] == "r":
                        w = image.width - inside
                        p = "r"
                        a = "right"
                    h = image.height / 2
                    h = inside + self.label_size / 2 # forces TOP position
                    # logger.debug(f"get_image: position {(w, h)}")
                    draw.multiline_text((w, h),  # (image.width / 2, 15)
                              text=label,
                              font=font,
                              anchor=p+"m",
                              align=a,
                              fill=self.label_color)

            # Weather Display

            iconname = self.to_icon()
            if iconname is not None:
                iconstr = WEATHER_ICONS.get(iconname, "*")
            else:
                iconstr = "*"
            iconfont = "weathericons.otf"
            iconsize = 40
            iconcolor = "white"
            fontname = self.get_font(iconfont)
            if fontname is None:
                logger.warning(f"get_image: icon font not found, cannot overlay icon")
            else:
                font = ImageFont.truetype(fontname, iconsize)
                inside = round(0.04 * image.width + 0.5)
                w = image.width / 2
                h = image.height / 2
                draw.text((w, h),  # (image.width / 2, 15)
                          text=iconstr,
                          font=font,
                          anchor="mm",
                          align="center",
                          fill=light_off(iconcolor, 0.5))

                fontname = self.get_font()
                if fontname is None:
                    logger.warning(f"get_image: label font not found, cannot overlay label")
                else:
                    # logger.debug(f"get_image: font {fontname}")
                    detailsize = 10
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

            if not self.is_valid() or self.has_option("placeholder"):
                if draw is None:  # no label
                    image = image.copy()  # we will add text over it
                    draw = ImageDraw.Draw(image)
                c = round(0.97 * image.width)  # % from edge
                s = round(0.1 * image.width)   # size
                pologon = ( (c, c), (c, c-s), (c-s, c) )  # lower right corner
                draw.polygon(pologon, fill="red", outline="white")
            return image
        else:
            logger.warning(f"get_image: button {self.name}: icon {self.key_icon} not found")
            # logger.debug(f"{self.deck.icons.keys()}")
        return None


    def to_icon(self):
        WI = [  "fog",
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
                "na"]

        icon = "snow"

        return "wi_" + icon
