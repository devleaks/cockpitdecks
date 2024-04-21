# ###########################
# Representation that displays FCU data.
# Horizontal: present the entire FCU.
# Vertical: present half FCU left or right.
# These buttons are *highly* X-Plane and Toliss Airbus specific.
#
import logging

from cockpitdecks import ICON_SIZE
from .draw import DrawBase

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class FCUIcon(DrawBase):
    """Highly customized class to display FCU on Streamdeck Plus touchscreen (whole screen)."""

    def __init__(self, config: dict, button: "Button"):
        DrawBase.__init__(self, config=config, button=button)
        self.fcuconfig = config.get("fcu")
        self.mode: str = self.fcuconfig.get("mode", "horizontal")  # type: ignore # horizontal, vertical-left, vertical-right
        self._cached = None
        self.icon_color = "#101010"
        self.count = 0

    def get_fcu_datarefs(self):
        return {
            "speed": "sim/cockpit2/autopilot/airspeed_dial_kts_mach",
            "altitude": "sim/cockpit2/autopilot/altitude_dial_ft",
            "heading": "sim/cockpit/autopilot/heading_mag",
            "vertspeed": "sim/cockpit/autopilot/vertical_velocity",
            "speed_managed": "AirbusFBW/SPDmanaged",
            "lnav_managed": "AirbusFBW/HDGmanaged",
            "vnav_managed": "AirbusFBW/ALTmanaged",
            "mach": "sim/cockpit/autopilot/airspeed_is_mach",
            "track": "AirbusFBW/HDGTRKmode",
            "vsdashed": "AirbusFBW/VSdashed",
            "spddashed": "AirbusFBW/SPDdashed",
            "hdgdashed": "AirbusFBW/HDGdashed",
            "barostd": "AirbusFBW/BaroStdCapt",
            "barounit": "AirbusFBW/BaroUnitCapt",
            "barohg": "sim/cockpit2/gauges/actuators/barometer_setting_in_hg_pilot",
        }

    def get_image_for_icon(self):
        if self.mode == "vertical-left":
            return self.get_image_for_icon_vertical_left()
        elif self.mode == "vertical-right":
            return self.get_image_for_icon_vertical_right()
        elif self.mode != "horizontal":
            logger.warning(f"invalid mode {self.mode}, using horizontal mode")
        return self.get_image_for_icon_horizontal()

    def get_image_for_icon_horizontal(self):
        """
        FCU display on Streamdeck Plus touchscreen.
        (This is currently more or less hardcoded for Elgato Streamdeck Plus touchscreen.)
        """
        self.count = self.count + 1
        self.count = self.count + 1
        THIS_WIDTH = 8 * ICON_SIZE
        THIS_HEIGHT = ICON_SIZE
        image, draw = self.double_icon(width=THIS_WIDTH, height=THIS_HEIGHT)

        inside = round(0.04 * ICON_SIZE + 0.5)
        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = (
            self.get_text_detail(self.fcuconfig, "text")
        )

        # demo through default values
        #
        mach_mode = (
            self.button.get_dataref_value(
                "sim/cockpit/autopilot/airspeed_is_mach", default=0
            )
            == 1
        )
        heading_mode = (
            self.button.get_dataref_value("AirbusFBW/HDGTRKmode", default=1) == 0
        )

        # print("\n".join(self.button.page.datarefs.keys()))
        # print(
        #     ">>>>>>>",
        #     self.count,
        #     mach_mode,
        #     heading_mode,
        #     self.button.get_dataref_value("sim/cockpit2/autopilot/airspeed_dial_kts_mach"),
        #     self.button.get_dataref_value("sim/cockpit/autopilot/heading_mag"),
        #     self.button.get_dataref_value("sim/cockpit2/autopilot/altitude_dial_ft"),
        #     self.button.get_dataref_value("sim/cockpit/autopilot/vertical_velocity"),
        # )

        # static texts
        font = self.get_font(text_font, text_size)
        h = text_size + inside
        if mach_mode:
            draw.text(
                (150, h),
                text="MACH",
                font=font,
                anchor="ls",
                align="left",
                fill=text_color,
            )
        else:
            draw.text(
                (inside, h),
                text="SPD",
                font=font,
                anchor="ls",
                align="left",
                fill=text_color,
            )

        draw.text(
            (720, h), text="LAT", font=font, anchor="ls", align="left", fill=text_color
        )
        if heading_mode:
            draw.text(
                (460, h),
                text="HDG",
                font=font,
                anchor="ls",
                align="left",
                fill=text_color,
            )
            draw.text(
                (960, 120),
                text="HDG",
                font=font,
                anchor="rs",
                align="right",
                fill=text_color,
            )
        else:
            draw.text(
                (590, h),
                text="TRK",
                font=font,
                anchor="ls",
                align="left",
                fill=text_color,
            )
            draw.text(
                (960, 220),
                text="TRK",
                font=font,
                anchor="rs",
                align="right",
                fill=text_color,
            )

        if heading_mode:
            draw.text(
                (1080, 120),
                text="V/S",
                font=font,
                anchor="ls",
                align="left",
                fill=text_color,
            )
            draw.text(
                (1880, h),
                text="V/S",
                font=font,
                anchor="rs",
                align="right",
                fill=text_color,
            )
        else:
            draw.text(
                (1080, 220),
                text="FPA",
                font=font,
                anchor="ls",
                align="left",
                fill=text_color,
            )
            draw.text(
                (THIS_WIDTH - inside, h),
                text="FPA",
                font=font,
                anchor="rs",
                align="right",
                fill=text_color,
            )

        draw.text(
            (1320, h), text="ALT", font=font, anchor="ls", align="left", fill=text_color
        )
        draw.text(
            (1600, h),
            text="LVL/CH",
            font=font,
            anchor="ms",
            align="center",
            fill=text_color,
        )

        # line
        h = inside + text_size / 2 + 4
        draw.line([(1410, h), (1510, h)], fill=text_color, width=3, joint="curve")
        draw.line(
            [(1410, h), (1410, h + text_size / 3)],
            fill=text_color,
            width=3,
            joint="curve",
        )
        draw.line([(1700, h), (1800, h)], fill=text_color, width=3, joint="curve")
        draw.line(
            [(1800, h), (1800, h + text_size / 3)],
            fill=text_color,
            width=3,
            joint="curve",
        )

        if not self.button.sim.connected:
            logger.debug("not connected")
            bg = self.button.deck.get_icon_background(
                name=self.button_name(),
                width=THIS_WIDTH,
                height=THIS_HEIGHT,
                texture_in=None,
                color_in="black",
                use_texture=False,
                who="FMA",
            )
            bg.alpha_composite(image)
            self._cached = bg.convert("RGB")
            return self._cached

        # values
        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = (
            self.get_text_detail(self.fcuconfig, "value")
        )
        font = self.get_font(text_font, text_size)
        one = " 1" if text_font == "Seven Segment" else "1"
        h = 200
        dot_size = 24
        hdot = 160

        #
        # SPEED
        speed_managed = (
            self.button.get_dataref_value("AirbusFBW/SPDmanaged", default=0) == 1
        )
        speed = "---"
        speed_dashed = (
            self.button.get_dataref_value("AirbusFBW/SPDdashed", default=0) == 1
        )
        if speed_dashed:
            draw.text(
                (20, h),
                text=speed,
                font=font,
                anchor="ls",
                align="left",
                fill=text_color,
            )
        else:
            spdft = 0.56 if mach_mode else 249
            speed_val = self.button.get_dataref_value(
                "sim/cockpit2/autopilot/airspeed_dial_kts_mach", default=spdft
            )
            if speed_val is not None:
                if mach_mode:
                    speed_val = round(speed_val * 100) / 100
                    speed = f"{speed_val:4.2f}"
                else:
                    speed_val = int(round(speed_val, 0))
                    speed = f"{speed_val:3d}"
            draw.text(
                (20, h),
                text=speed.replace("1", one),
                font=font,
                anchor="ls",
                align="left",
                fill=text_color,
            )
        if speed_managed:
            w = 250
            dot = ((w - dot_size, hdot - dot_size), (w + dot_size, hdot + dot_size))
            draw.ellipse(dot, fill=text_color)
        #
        # HEADING
        heading_managed = (
            self.button.get_dataref_value("AirbusFBW/HDGmanaged", default=0) == 1
        )
        heading_dashed = (
            self.button.get_dataref_value("AirbusFBW/HDGdashed", default=0) == 1
        )
        if heading_dashed:
            heading = "---"
            draw.text(
                (500, h),
                text=heading,
                font=font,
                anchor="ls",
                align="left",
                fill=text_color,
            )
        else:
            heading_val = self.button.get_dataref_value(
                "sim/cockpit/autopilot/heading_mag", 0
            )
            heading_val = int(round(heading_val, 0))
            heading = f"{heading_val:03d}"
            draw.text(
                (500, h),
                text=heading.replace("1", one),
                font=font,
                anchor="ls",
                align="left",
                fill=text_color,
            )
        if heading_managed:
            w = 736
            dot = ((w - dot_size, hdot - dot_size), (w + dot_size, hdot + dot_size))
            draw.ellipse(dot, fill=text_color)
        #
        # ALTITUDE (always displayed)
        alt_managed = (
            self.button.get_dataref_value("AirbusFBW/ALTmanaged", default=0) == 1
        )
        vs_dashed = self.button.get_dataref_value("AirbusFBW/VSdashed", False)
        alt_ft_val = self.button.get_dataref_value(
            "sim/cockpit2/autopilot/altitude_dial_ft", 26789
        )
        alt_ft_val = int(round(alt_ft_val, 0))
        alt = f"{alt_ft_val: 5d}"
        draw.text(
            (1240, h),
            text=alt.replace("1", one),
            font=font,
            anchor="ls",
            align="left",
            fill=text_color,
        )  # should always be len=5
        if alt_managed:
            w = 1590
            dot = ((w - dot_size, hdot - dot_size), (w + dot_size, hdot + dot_size))
            draw.ellipse(dot, fill=text_color)

        # Vertical speed/slope is tricky
        vs_val = -1
        if alt_managed or vs_dashed:
            vs = "----" if heading_mode else "-.---"
            draw.text(
                (1700, h),
                text=vs.replace("1", one),
                font=font,
                anchor="ls",
                align="left",
                fill=text_color,
            )  # should always be len=5 or 6
        else:
            vsdft = -1200 if heading_mode else -2.5
            vs_val = self.button.get_dataref_value(
                "sim/cockpit/autopilot/vertical_velocity", default=vsdft
            )
            vs_val_abs = abs(vs_val)
            vs = ""
            if heading_mode:  # V/S
                vs_val_abs = abs(int(vs_val / 100))
                vs = f"{vs_val_abs:02d}" + "oo"  # little zeros
            else:  # FPA
                vs_val_abs = abs(round(vs_val * 10) / 10)
                vs = f"{vs_val_abs:3.1f}"
            # print(">>>", vs_val, heading_mode, alt_managed, vs)
            draw.text(
                (1700, h),
                text=vs.replace("1", one),
                font=font,
                anchor="ls",
                align="left",
                fill=text_color,
            )  # should always be len=5 or 6
        # little + or - in front of vertical speed
        font = self.get_font("Seven Segment", int(0.7 * text_size))
        vs = "-" if vs_val < 0 else "+"
        draw.text(
            (1650, h - 16),
            text=vs,
            font=font,
            anchor="ls",
            align="left",
            fill=text_color,
        )  # should always be len=5 or 6

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=THIS_WIDTH,
            height=THIS_HEIGHT,
            texture_in=None,
            color_in=self.icon_color,
            use_texture=False,
            who="FCU",
        )
        bg.alpha_composite(image)
        self._cached = bg.convert("RGB")
        return self._cached

    def get_image_for_icon_vertical_left(self):
        """Speed, heading, QNH"""
        self.count = self.count + 1
        THIS_WIDTH = int(2 * ICON_SIZE / 3)
        THIS_HEIGHT = 3 * ICON_SIZE
        image, draw = self.double_icon(width=THIS_WIDTH, height=THIS_HEIGHT)

        inside = round(0.04 * ICON_SIZE + 0.5)

        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = (
            self.get_text_detail(self.fcuconfig, "text")
        )

        mach_mode = (
            self.button.get_dataref_value(
                "sim/cockpit/autopilot/airspeed_is_mach", default=0
            )
            == 1
        )
        heading_mode = (
            self.button.get_dataref_value("AirbusFBW/HDGTRKmode", default=1) == 0
        )

        font = self.get_font(text_font, text_size)
        h = inside + text_size
        centerx = image.width / 2
        txt = "MACH" if mach_mode else "SPD"
        draw.text(
            (centerx, h),
            text=txt,
            font=font,
            anchor="ms",
            align="center",
            fill=text_color,
        )

        txt = "HDG" if heading_mode else "TRK"
        draw.text(
            (centerx, h + ICON_SIZE),
            text=txt,
            font=font,
            anchor="ms",
            align="center",
            fill=text_color,
        )

        draw.text(
            (centerx, h + 2 * ICON_SIZE),
            text="QNH",
            font=font,
            anchor="ms",
            align="center",
            fill=text_color,
        )

        if not self.button.sim.connected:
            logger.debug("not connected")
            bg = self.button.deck.get_icon_background(
                name=self.button_name(),
                width=THIS_WIDTH,
                height=THIS_HEIGHT,
                texture_in=None,
                color_in="black",
                use_texture=False,
                who="FMA",
            )
            bg.alpha_composite(image)
            bg = self.button.deck.scale_icon_for_key(self.button.index, bg)
            self._cached = bg.convert("RGB")
            return self._cached

        # values
        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = (
            self.get_text_detail(self.fcuconfig, "value")
        )
        font = self.get_font(text_font, text_size)
        one = " 1" if text_font == "Seven Segment" else "1"
        dot_size = 10
        wdot = image.width - inside - dot_size * 2

        #
        # SPEED
        speed_managed = (
            self.button.get_dataref_value("AirbusFBW/SPDmanaged", default=0) == 1
        )
        speed_dashed = (
            self.button.get_dataref_value("AirbusFBW/SPDdashed", default=0) == 1
        )
        h = ICON_SIZE / 2
        speed = "---"
        if speed_dashed:
            draw.text(
                (centerx, h),
                text=speed,
                font=font,
                anchor="mm",
                align="center",
                fill=text_color,
            )
        else:
            spdft = 0.56 if mach_mode else 249
            speed_val = self.button.get_dataref_value(
                "sim/cockpit2/autopilot/airspeed_dial_kts_mach", default=spdft
            )
            if speed_val is not None:
                if mach_mode:
                    speed_val = round(speed_val * 100) / 100
                    speed = f"{speed_val:4.2f}"
                else:
                    speed_val = int(round(speed_val, 0))
                    speed = f"{speed_val:3d}"
            draw.text(
                (centerx, h),
                text=speed.replace("1", one),
                font=font,
                anchor="mm",
                align="center",
                fill=text_color,
            )
        if speed_managed:
            dot = ((wdot - dot_size, h - dot_size), (wdot + dot_size, h + dot_size))
            draw.ellipse(dot, fill=text_color)
        #
        # HEADING
        heading_managed = (
            self.button.get_dataref_value("AirbusFBW/HDGmanaged", default=0) == 1
        )
        heading_dashed = (
            self.button.get_dataref_value("AirbusFBW/HDGdashed", default=0) == 1
        )
        h = 3 * ICON_SIZE / 2
        if heading_dashed:
            heading = "---"
            draw.text(
                (centerx, h),
                text=heading,
                font=font,
                anchor="mm",
                align="center",
                fill=text_color,
            )
        else:
            heading_val = self.button.get_dataref_value(
                "sim/cockpit/autopilot/heading_mag", 0
            )
            heading_val = int(round(heading_val, 0))
            heading = f"{heading_val:03d}"
            draw.text(
                (centerx, h),
                text=heading.replace("1", one),
                font=font,
                anchor="mm",
                align="center",
                fill=text_color,
            )
        if heading_managed:
            dot = ((wdot - dot_size, h - dot_size), (wdot + dot_size, h + dot_size))
            draw.ellipse(dot, fill=text_color)
        #
        # QNH
        qnh_std = self.button.get_dataref_value("AirbusFBW/BaroStdCapt", 0) == 1
        h = 5 * ICON_SIZE / 2
        qnh = "Std"
        if qnh_std:
            draw.text(
                (centerx, h),
                text=qnh,
                font=font,
                anchor="mm",
                align="center",
                fill=text_color,
            )
        else:
            qnh_val = self.button.get_dataref_value(
                "sim/cockpit2/gauges/actuators/barometer_setting_in_hg_pilot", 0
            )
            qnh_metric = self.button.get_dataref_value("AirbusFBW/BaroUnitCapt", 1) == 1
            if qnh_metric:
                qnh_val = int(round(float(qnh_val) * 33.8639, 0))
                qnh = f"{qnh_val:04d}"
            else:
                qnh_val = round(float(qnh_val), 2)
                qnh = f"{qnh_val:5.2f}"
            draw.text(
                (centerx, h),
                text=qnh.replace("1", one),
                font=font,
                anchor="mm",
                align="center",
                fill=text_color,
            )

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=THIS_WIDTH,
            height=THIS_HEIGHT,
            texture_in=None,
            color_in="black",
            use_texture=False,
            who="FMA",
        )
        bg.alpha_composite(image)
        bg = self.button.deck.scale_icon_for_key(self.button.index, bg)
        self._cached = bg.convert("RGB")
        return self._cached

    def get_image_for_icon_vertical_right(self):
        """Altitude, vs"""
        self.count = self.count + 1
        THIS_WIDTH = int(2 * ICON_SIZE / 3)
        THIS_HEIGHT = 3 * ICON_SIZE
        image, draw = self.double_icon(width=THIS_WIDTH, height=THIS_HEIGHT)

        inside = round(0.04 * ICON_SIZE + 0.5)

        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = (
            self.get_text_detail(self.fcuconfig, "text")
        )

        heading_mode = (
            self.button.get_dataref_value("AirbusFBW/HDGTRKmode", default=1) == 0
        )

        font = self.get_font(text_font, text_size)
        h = inside + text_size
        centerx = int(image.width / 2)
        draw.text(
            (centerx, h),
            text="ALT",
            font=font,
            anchor="ms",
            align="center",
            fill=text_color,
        )

        txt = "V/S" if heading_mode else "FPA"
        draw.text(
            (centerx, h + ICON_SIZE),
            text=txt,
            font=font,
            anchor="ms",
            align="center",
            fill=text_color,
        )

        # Nothing in lower third

        if not self.button.sim.connected:
            logger.debug("not connected")
            bg = self.button.deck.get_icon_background(
                name=self.button_name(),
                width=THIS_WIDTH,
                height=THIS_HEIGHT,
                texture_in=None,
                color_in="black",
                use_texture=False,
                who="FMA",
            )
            bg.alpha_composite(image)
            bg = self.button.deck.scale_icon_for_key(self.button.index, bg)
            self._cached = bg.convert("RGB")
            return self._cached

        # values
        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = (
            self.get_text_detail(self.fcuconfig, "value")
        )
        text_size = int(2 * text_size / 3)
        font = self.get_font(text_font, text_size)
        one = " 1" if text_font == "Seven Segment" else "1"
        dot_size = 10
        wdot = image.width - inside - dot_size * 2

        # ALTITUDE (always displayed)
        alt_ft_val = self.button.get_dataref_value(
            "sim/cockpit2/autopilot/altitude_dial_ft", 26789
        )
        alt_ft_val = int(round(alt_ft_val, 0))
        alt = f"{alt_ft_val: 5d}"
        h = ICON_SIZE / 2
        draw.text(
            (wdot - inside, h),
            text=alt.replace("1", one),
            font=font,
            anchor="rm",
            align="right",
            fill=text_color,
        )

        alt_managed = (
            self.button.get_dataref_value("AirbusFBW/ALTmanaged", default=0) == 1
        )
        if alt_managed:
            dot = ((wdot - dot_size, h - dot_size), (wdot + dot_size, h + dot_size))
            draw.ellipse(dot, fill=text_color)

        # Vertical speed/slope is tricky
        vs_dashed = self.button.get_dataref_value("AirbusFBW/VSdashed", False)
        vs_val = -1
        h = 3 * ICON_SIZE / 2
        if alt_managed or vs_dashed:
            vs = "----" if heading_mode else "-.---"
            draw.text(
                (wdot - dot_size, h),
                text=vs,
                font=font,
                anchor="rm",
                align="right",
                fill=text_color,
            )
        else:
            vsdft = -1200 if heading_mode else -2.5
            vs_val = self.button.get_dataref_value(
                "sim/cockpit/autopilot/vertical_velocity", default=vsdft
            )
            vs_val_abs = abs(vs_val)
            vs = ""
            if heading_mode:  # V/S
                vs_val_abs = abs(int(round(vs_val / 100, 0)))
                vs = f"{vs_val_abs:02d}" + "oo"  # little zeros
            else:  # FPA
                vs_val_abs = abs(round(vs_val * 10) / 10)
                vs = f"{vs_val_abs:3.1f}"
            # print(">>>", vs_val, heading_mode, alt_managed, vs)
            draw.text(
                (wdot - dot_size, h),
                text=vs.replace("1", one),
                font=font,
                anchor="rm",
                align="right",
                fill=text_color,
            )
        # little + or - in front of vertical speed
        font = self.get_font("Seven Segment", int(text_size))
        vs = "-" if vs_val < 0 else "+"
        draw.text(
            (inside, h), text=vs, font=font, anchor="lm", align="left", fill=text_color
        )  # should always be len=5 or 6

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=THIS_WIDTH,
            height=THIS_HEIGHT,
            texture_in=None,
            color_in="black",
            use_texture=False,
            who="FMA",
        )
        bg.alpha_composite(image)
        bg = self.button.deck.scale_icon_for_key(self.button.index, bg)
        self._cached = bg.convert("RGB")
        return self._cached
