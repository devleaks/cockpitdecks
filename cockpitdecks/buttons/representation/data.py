# ###########################
# Buttons that are drawn on render()
#
import logging

from cockpitdecks.resources.iconfonts import get_special_character

from cockpitdecks.resources.color import convert_color, light_off
from cockpitdecks.strvar import TextWithVariables
from .draw import DrawBase  # explicit Icon from file to avoid circular import

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# DRAWN REPRESENTATION (using Pillow, continued)
#
#
class DataIcon(DrawBase):

    REPRESENTATION_NAME = "data"

    PARAMETERS = {
        "top-line-color": {"type": "string", "prompt": "Top line color"},
        "top-line-width": {"type": "string", "prompt": "Top line width"},
        "icon": {"type": "string", "prompt": "Icon name"},
        "icon-size": {"type": "integer", "prompt": "Icon size"},
        "icon-color": {"type": "string", "prompt": "Icon color"},
        "data": {"type": "string", "prompt": "Data"},
        "data-format": {"type": "string", "prompt": "Data format (python style)"},
        "data-font": {"type": "string", "prompt": "Data font"},
        "data-size": {"type": "integer", "prompt": "Data font size"},
        "data-color": {"type": "string", "prompt": "Data color"},
        "data-unit": {"type": "string", "prompt": "Data unit"},
        "formula": {"type": "string", "prompt": "Formula"},
        "bottomline": {"type": "string", "prompt": "Bottom line"},
        "bottomline-size": {"type": "integer", "prompt": "Bottom line font size"},
        "bottomline-color": {"type": "string", "prompt": "Bottom line color"},
        "mark": {"type": "string", "prompt": "Mark"},
        "mark-size": {"type": "integer", "prompt": "Mark size"},
        "mark-font": {"type": "string", "prompt": "Mark font"},
        "mark-color": {"type": "string", "prompt": "Mark color"},
    }

    def __init__(self, button: "Button"):
        DrawBase.__init__(self, button=button)
        self.data = self._config.get(self.REPRESENTATION_NAME)
        # Text styles
        self.data_style = None
        if self.data is not None:
            self.data_style = TextWithVariables(owner=button, config=self.data, prefix="data")
            self.icon_style = TextWithVariables(owner=button, config=self.data, prefix="icon")
            self.bottomline_style = TextWithVariables(owner=button, config=self.data, prefix="bottomline")
            self.mark_style = TextWithVariables(owner=button, config=self.data, prefix="mark")

    def get_variables(self) -> set:
        if self.datarefs is None:
            if self.data is not None:
                self.datarefs = self.data_style.get_variables()
                # ùay be add those of icon, bottomline and mark?
        return self.datarefs

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image, draw = self.simple_icon()  # annunciator text and leds , color=(0, 0, 0, 0)
        inside = round(0.04 * image.width + 0.5)

        # Data
        if self.data is None:
            logger.warning(f"button {self.button.name}: no data")
            return image

        # Top bar
        topbar = self.data.get("top-line-color")
        if topbar is not None:
            topbarcolor = convert_color(topbar)
            linewidth = self.data.get("top-line-width", 6)
            draw.line(
                [(0, int(linewidth / 2)), (image.width, int(linewidth / 2))],
                fill=topbarcolor,
                width=linewidth,
            )

        # Side icon
        icon = self.icon_style.get_text()
        icon_font, icon_str = get_special_character(icon, "*")
        if icon_font is not None:
            font = self.get_font(icon_font, int(self.icon_style.size))
            inside = round(0.04 * image.width + 0.5)
            w = inside - 4
            h = image.height / 2
            draw.text((w, h), text=icon_str, font=font, anchor="lm", align="left", fill=self.icon_style.color)  # (image.width / 2, 15)

        # Trend
        data_trend = self.data.get("data-trend")
        trend_val = self.button.trend()

        trend_font, trend_str = get_special_character("fa:minus", "=")
        if trend_val > 0:
            trend_font, trend_str = get_special_character("fa:arrow-up", "+")
        elif trend_val < 0:
            trend_font, trend_str = get_special_character("fa:arrow-down", "-")
        if trend_font is not None:
            font = self.get_font(trend_font, int(self.icon_style.size / 2))
            if data_trend:
                draw.text(
                    (w + self.icon_style.size + 4, h),
                    text=trend_str,
                    font=font,
                    anchor="lm",
                    align="center",
                    fill=self.icon_style.color,
                )

        # Value
        DATA_UNIT_SEP = " "
        data_value = self.data_style.get_formula_result()
        data_str = self.data_style.get_text()
        # if data_unit is not None:
        #    data_str = data_str + DATA_UNIT_SEP + data_unit

        font = self.get_font(self.data_style.font, self.data_style.size)
        font_unit = self.get_font(self.data_style.font, int(self.data_style.size * 0.50))
        inside = round(0.04 * image.width + 0.5)
        w = image.width - inside
        h = image.height / 2 + self.data_style.size / 2 - inside
        # if dataprogress is not None:
        #    h = h - DATAPROGRESS_SPACE - DATAPROGRESS / 2
        data_unit = self.data.get("data-unit")
        if data_unit is not None:
            w = w - draw.textlength(DATA_UNIT_SEP + data_unit, font=font_unit)
        draw.text(
            (w, h),
            text=data_str,
            font=font,
            anchor="rs",
            align="right",
            fill=self.data_style.color,
        )  # (image.width / 2, 15)

        # Unit
        if data_unit is not None:
            w = image.width - inside
            draw.text(
                (w, h),
                text=DATA_UNIT_SEP + data_unit,
                font=font_unit,
                anchor="rs",
                align="right",
                fill=self.data_style.color,
            )  # (image.width / 2, 15)

        # Progress bar
        DATA_PROGRESS_SPACE = 8
        DATA_PROGRESS = 6
        data_progress = self.data.get("data-progress")
        progress_color = self.data.get("progress-color")
        if data_progress is not None:
            w = self.icon_style.size + 4 * inside
            h = 3 * image.height / 4 - 2 * DATA_PROGRESS
            pct = float(data_value) / float(data_progress)
            if pct > 1:
                pct = 1
            full_color = light_off(progress_color, 0.30)
            l = w + pct * ((image.width - inside) - w)
            draw.line(
                [(w, h), (image.width - inside, h)],
                fill=full_color,
                width=DATA_PROGRESS,
                joint="curve",
            )  # 100%
            draw.line([(w, h), (l, h)], fill=progress_color, width=DATA_PROGRESS, joint="curve")

        # Bottomline (forced at CENTER BOTTOM line of icon)
        bottom_line = self.bottomline_style.get_text()
        if bottom_line is not None:
            font = self.get_font(self.bottomline_style.font, self.bottomline_style.size)
            w = image.width / 2
            h = image.height / 2
            h = image.height - inside - self.bottomline_style.size / 2  # forces BOTTOM position
            draw.multiline_text(
                (w, h),
                text=bottom_line,
                font=font,
                anchor="md",
                align="center",
                fill=self.bottomline_style.color,
            )  # (image.width / 2, 15)

        # Final mark
        mark = self.mark_style.get_text()
        if mark is not None:
            font = self.get_font(self.mark_style.font, self.mark_style.size)
            w = image.width - 2 * inside
            h = image.height - 2 * inside
            draw.text(
                (w, h),
                text=mark,
                font=font,
                anchor="rb",
                align="right",
                fill=self.mark_style.color,
            )

        # Get background colour or use default value
        # Variables may need normalising as icon-color for data icons is for icon, in other cases its background of button?
        # Overwrite icon-* with data-bg-*
        self.icon_color = self._config.get("data-bg-color", self.cockpit_texture)
        self.icon_texture = self._config.get("data-bg-texture", self.cockpit_color)

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name,
            width=image.width,
            height=image.height,
            texture_in=self.icon_texture,
            color_in=self.icon_color,
            use_texture=True,
            who="Data",
        )
        bg.alpha_composite(image)
        return bg
