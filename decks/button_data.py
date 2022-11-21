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

logger = logging.getLogger("DataButton")
logger.setLevel(logging.DEBUG)


class DataButton(Button):

    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        def light_off(color, lightness: float):
            # Darkens (or lighten) a color
            if color.startswith("("):
                color = convert_color(color)
            if type(color) == str:
                color = ImageColor.getrgb(color)
            a = list(colorsys.rgb_to_hls(*[c / 255 for c in color]))
            a[1] = lightness
            return tuple([int(c * 256) for c in colorsys.hls_to_rgb(*a)])

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
            iconname = data.get("icon-name", u"\uf5af")
            iconfont = data.get("icon-font")
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
                          text=iconname,
                          font=font,
                          anchor="lm",
                          align="left",
                          fill=iconcolor)

            # Data
            DATAPROGRESS_SPACE = 8
            DATAPROGRESS = 6
            datavalue = data.get("data", 0)
            dataformat = data.get("data-format", "")
            if dataformat is not None:
                datastr = dataformat.format(datavalue)
            else:
                datastr = str(datavalue)
            dataunit = data.get("data-unit", "")
            datastr = datastr + " " + dataunit
            datasize = data.get("data-size", 12)  # should adapt based on len(data)
            dataprogress = data.get("data-progress")
            datafont = data.get("data-font", "DIN")
            datacolor = data.get("data-color", "white")
            font = self.get_font(datafont)
            if font is None:
                logger.warning(f"get_image: data font not found, cannot overlay label")
            else:
                font = ImageFont.truetype(fontname, datasize)
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
                fullcolor = light_off(datacolor, 0.40)
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

