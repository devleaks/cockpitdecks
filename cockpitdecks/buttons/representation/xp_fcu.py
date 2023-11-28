# ###########################
# Representation that displays the content of sim/aircraft/view/acf_ICAO on an icon.
# These buttons are *highly* X-Plane and Toliss Airbus specific.
#
import logging

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR
from .draw import DrawBase

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

FCU_DATAREFS = {
    "speed": "sim/cockpit2/autopilot/airspeed_dial_kts_mach",
    "heading": "sim/cockpit/autopilot/heading_mag",
    "altitude": "sim/cockpit2/autopilot/altitude_dial_ft",
    "vertspeed": "sim/cockpit/autopilot/vertical_velocity",
    "speed_managed": "AirbusFBW/SPDmanaged",
    "lnav_managed": "AirbusFBW/HDGmanaged",
    "vnav_managed": "AirbusFBW/ALTmanaged",
    "mach": "sim/cockpit/autopilot/airspeed_is_mach",
    "track": "AirbusFBW/HDGTRKmode",
    "vsdashed": "AirbusFBW/VSdashed",
}


class FCUIcon(DrawBase):
    """Highly customized class to display FCU on Streamdeck Plus touchscreen (whole screen)."""

    def __init__(self, config: dict, button: "Button"):
        DrawBase.__init__(self, config=config, button=button)
        self.fcuconfig = config.get("fcu")
        self._cached = None
        self.icon_color = "#101010"
        self.count = 0

    def get_fcu_datarefs(self):
        return FCU_DATAREFS.values()

    def get_image_for_icon(self):
        """
        FCU display on Streamdeck Plus touchscreen.
        (This is currently more or less hardcoded for Elgato Streamdeck Plus touchscreen.)
        """
        image = Image.new(mode="RGBA", size=(8 * ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)
        FCU_COLLECTION = "fcu"
        self.count = self.count + 1
        draw = ImageDraw.Draw(image)

        inside = round(0.04 * image.height + 0.5)

        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self.fcuconfig, "text")

        # demo through default values
        #
        mach_mode = self.button.get_dataref_value_from_collection("sim/cockpit/autopilot/airspeed_is_mach", FCU_COLLECTION, default=0) == 1
        heading_mode = self.button.get_dataref_value_from_collection("AirbusFBW/HDGTRKmode", FCU_COLLECTION, default=1) == 0

        speed_managed = self.button.get_dataref_value_from_collection("AirbusFBW/SPDmanaged", FCU_COLLECTION, default=0) == 1
        heading_managed = self.button.get_dataref_value_from_collection("AirbusFBW/HDGmanaged", FCU_COLLECTION, default=0) == 1
        alt_managed = self.button.get_dataref_value_from_collection("AirbusFBW/ALTmanaged", FCU_COLLECTION, default=0) == 1

        # print("\n".join(self.button.page.datarefs.keys()))
        # print(
        #     ">>>>>>>",
        #     self.count,
        #     metric_alt,
        #     mach_mode,
        #     heading_mode,
        #     speed_managed,
        #     heading_managed,
        #     alt_managed,
        #     self.button.get_dataref_value_from_collection("sim/cockpit2/autopilot/airspeed_dial_kts_mach", FCU_COLLECTION),
        #     self.button.get_dataref_value_from_collection("sim/cockpit/autopilot/heading_mag", FCU_COLLECTION),
        #     self.button.get_dataref_value_from_collection("sim/cockpit2/autopilot/altitude_dial_ft", FCU_COLLECTION),
        #     self.button.get_dataref_value_from_collection("sim/cockpit/autopilot/vertical_velocity", FCU_COLLECTION),
        # )

        # static texts
        font = self.get_font(text_font, text_size)
        h = text_size + inside
        if mach_mode:
            draw.text((150, h), text="MACH", font=font, anchor="ls", align="left", fill=text_color)
        else:
            draw.text((inside, h), text="SPD", font=font, anchor="ls", align="left", fill=text_color)

        draw.text((720, h), text="LAT", font=font, anchor="ls", align="left", fill=text_color)
        if heading_mode:
            draw.text((460, h), text="HDG", font=font, anchor="ls", align="left", fill=text_color)
            draw.text((960, 120), text="HDG", font=font, anchor="rs", align="right", fill=text_color)
        else:
            draw.text((590, h), text="TRK", font=font, anchor="ls", align="left", fill=text_color)
            draw.text((960, 220), text="TRK", font=font, anchor="rs", align="right", fill=text_color)

        if heading_mode:
            draw.text((1080, 120), text="V/S", font=font, anchor="ls", align="left", fill=text_color)
            draw.text((1880, h), text="V/S", font=font, anchor="rs", align="right", fill=text_color)
        else:
            draw.text((1080, 220), text="FPA", font=font, anchor="ls", align="left", fill=text_color)
            draw.text((8 * ICON_SIZE - inside, h), text="FPA", font=font, anchor="rs", align="right", fill=text_color)

        draw.text((1320, h), text="ALT", font=font, anchor="ls", align="left", fill=text_color)
        draw.text((1600, h), text="LVL/CH", font=font, anchor="ms", align="center", fill=text_color)

        # line
        h = inside + text_size / 2 + 4
        draw.line([(1410, h), (1510, h)], fill=text_color, width=3, joint="curve")
        draw.line([(1410, h), (1410, h + text_size / 3)], fill=text_color, width=3, joint="curve")
        draw.line([(1700, h), (1800, h)], fill=text_color, width=3, joint="curve")
        draw.line([(1800, h), (1800, h + text_size / 3)], fill=text_color, width=3, joint="curve")

        # values
        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self.fcuconfig, "value")
        font = self.get_font(text_font, text_size)
        one = " 1" if text_font == "Seven Segment" else "1"
        h = 200
        dot_size = 24
        hdot = 160

        #
        # SPEED
        if speed_managed:
            speed = "---"
            draw.text((20, h), text=speed, font=font, anchor="ls", align="left", fill=text_color)
            w = 250
            dot = ((w - dot_size, hdot - dot_size), (w + dot_size, hdot + dot_size))
            draw.ellipse(dot, fill=text_color)
        else:
            spdft = 0.56 if mach_mode else 249
            speed_val = self.button.get_dataref_value_from_collection("sim/cockpit2/autopilot/airspeed_dial_kts_mach", FCU_COLLECTION, default=spdft)
            speed = ""
            if mach_mode:
                speed_val = round(speed_val * 100) / 100
                speed = f"{speed_val:4.2f}"
            else:
                speed_val = int(speed_val)
                speed = f"{speed_val:3d}"
            draw.text((20, h), text=speed.replace("1", one), font=font, anchor="ls", align="left", fill=text_color)
        #
        # HEADING
        if heading_managed:
            heading = "---"
            draw.text((500, h), text=heading, font=font, anchor="ls", align="left", fill=text_color)
            w = 736
            dot = ((w - dot_size, hdot - dot_size), (w + dot_size, hdot + dot_size))
            draw.ellipse(dot, fill=text_color)
        else:
            heading_val = self.button.get_dataref_value_from_collection("sim/cockpit/autopilot/heading_mag", FCU_COLLECTION, 0)
            heading_val = int(heading_val)
            heading = f"{heading_val:3d}"
            draw.text((500, h), text=heading.replace("1", one), font=font, anchor="ls", align="left", fill=text_color)
        #
        # ALTITUDE (always displayed)
        vs_dashed = self.button.get_dataref_value_from_collection("AirbusFBW/VSdashed", FCU_COLLECTION, False)
        alt_ft_val = self.button.get_dataref_value_from_collection("sim/cockpit2/autopilot/altitude_dial_ft", FCU_COLLECTION, 26789)
        alt_ft_val = int(alt_ft_val)
        alt = f"{alt_ft_val: 5d}"
        draw.text((1240, h), text=alt.replace("1", one), font=font, anchor="ls", align="left", fill=text_color)  # should always be len=5
        if alt_managed:
            w = 1590
            dot = ((w - dot_size, hdot - dot_size), (w + dot_size, hdot + dot_size))
            draw.ellipse(dot, fill=text_color)

        # Vertical speed/slope is tricky
        vs_val = -1
        if alt_managed or vs_dashed:
            vs = "----" if heading_mode else "-.---"
            draw.text((1700, h), text=vs.replace("1", one), font=font, anchor="ls", align="left", fill=text_color)  # should always be len=5 or 6
        else:
            vsdft = -1200 if heading_mode else -2.5
            vs_val = self.button.get_dataref_value_from_collection("sim/cockpit/autopilot/vertical_velocity", FCU_COLLECTION, default=vsdft)
            vs_val_abs = abs(vs_val)
            vs = ""
            if heading_mode:  # V/S
                vs_val_abs = abs(int(vs_val / 100))
                vs = f"{vs_val_abs:02d}" + "oo"  # little zeros
            else:  # FPA
                vs_val_abs = abs(round(vs_val * 10) / 10)
                vs = f"{vs_val_abs:3.1f}"
            # print(">>>", vs_val, heading_mode, alt_managed, vs)
            draw.text((1700, h), text=vs.replace("1", one), font=font, anchor="ls", align="left", fill=text_color)  # should always be len=5 or 6
        # little + or - in front of vertical speed
        font = self.get_font("Seven Segment", int(0.7 * text_size))
        vs = "-" if vs_val < 0 else "+"
        draw.text((1650, h - 16), text=vs, font=font, anchor="ls", align="left", fill=text_color)  # should always be len=5 or 6

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(), width=8 * ICON_SIZE, height=ICON_SIZE, texture_in=None, color_in=self.icon_color, use_texture=False, who="FCU"
        )
        bg.alpha_composite(image)
        self._cached = bg.convert("RGB")
        return self._cached
