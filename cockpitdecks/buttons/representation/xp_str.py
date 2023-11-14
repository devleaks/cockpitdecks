# ###########################
# Representation that displays the content of a dataref string on an icon.
# These buttons are highly XP specific.
# (This is an attempt to generalize xp_ac button to any string.)
#
import logging

from cockpitdecks import ICON_SIZE, now
from .draw import DrawBase

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class StringIcon(DrawBase):
    def __init__(self, config: dict, button: "Button"):
        self._inited = False
        self.fetched_string = None
        self.text = None
        self._update_count = 0
        self._cached = None
        self._last_updated = None
        self._strconfig = config.get("dref-string")
        self._drefcoll = config.get("dataref-collections")
        self._dataref = None
        self._array = 0
        self._notify = None

        DrawBase.__init__(self, config=config, button=button)

    def init(self):
        if self._inited:
            return
        if self._drefcoll is not None:
            self._collname = self._drefcoll[0].get("name")  # string
            self._dataref = self._drefcoll[0].get("datarefs")[0]
            self._array = self._drefcoll[0].get("array")
            self._notify = self._drefcoll[0].get("set-dataref")
        else:
            logger.info(f"no dataref")
        self.notify_string_updated()
        self._inited = True
        logger.debug(f"inited")

    def notify_string_updated(self):
        if self.text is not None:
            self._update_count = self._update_count + 1
            self.button._activation._write_dataref(self._notify, float(self._update_count))
            self._last_updated = now()
            logger.info(f"notified of new string {self._update_count} ({self.text})")

    def get_string(self):
        return self.fetched_string if self.fetched_string != "" else None

    def is_updated(self):
        def updated_recently(how_long_ago: int = 10):  # secs
            # prevents multiple notification on startup or during string
            if self._last_updated is not None:
                delta = now().timestamp() - self._last_updated.timestamp()
                return delta < how_long_ago  # seconds
            return False

        drefs = self.button.sim.collector.collections[self._collname].datarefs
        # 1. Collect string character per character :-D
        new_string = ""
        updated = False
        cnt = 0
        for d in drefs.values():
            if d.current_value is not None:
                cnt = cnt + 1
                c = chr(int(d.current_value))
                new_string = new_string + c
        self.fetched_string = new_string

        if cnt < self._array:  # we did not fetch all chars yet
            logger.debug(f"received {cnt}/{self._array}")
            return False

        logger.debug(f"received {cnt}/{self._array} (completed)")
        # 2. Has the string changed?
        text = self.get_string()
        if text is not None:
            updated = self.text != text
            if updated:
                self.text = text
                if not updated_recently():
                    self.notify_string_updated()  # notifies writable dataref
                else:
                    # self._last_updated should not be None as we reach here
                    logger.debug(f"new string {self.text} but no notification, collection in progress, notified at {self._last_updated}")
        return updated

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        if not self.is_updated() and self._cached is not None:
            return self._cached

        image, draw = self.double_icon(width=ICON_SIZE, height=ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)
        inside = round(0.04 * image.width + 0.5)

        text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self._strconfig, "text")
        text = self.text
        if text is None:
            text = "no text"
        else:
            substr = self._strconfig.get("substring")
            if substr is not None:
                sa = [int(s) for s in substr.split(",")]
                text = text[sa[0] : sa[1]]

        font = self.get_font(text_font, text_size)
        w = image.width / 2
        p = "m"
        a = "center"
        if text_position[0] == "l":
            w = inside
            p = "l"
            a = "left"
        elif text_position[0] == "r":
            w = image.width - inside
            p = "r"
            a = "right"
        h = image.height / 2
        if text_position[1] == "t":
            h = inside + text_size / 2
        elif text_position[1] == "r":
            h = image.height - inside - text_size / 2
        # logger.debug(f"position {(w, h)}")
        draw.multiline_text((w, h), text=text, font=font, anchor=p + "m", align=a, fill=text_color)  # (image.width / 2, 15)

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(), width=ICON_SIZE, height=ICON_SIZE, texture_in=self.icon_texture, color_in=self.icon_color, use_texture=True, who="Data"
        )
        bg.alpha_composite(image)
        self._cached = bg.convert("RGB")
        return self._cached
