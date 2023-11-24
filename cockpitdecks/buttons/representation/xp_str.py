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
        self._update_count = 0
        self._cached = None
        self._last_updated = None
        self._strconfig = config.get("strings")

        self.text = {}
        self.text_default = config.get("no-text", "no text")

        DrawBase.__init__(self, config=config, button=button)

    def init(self):
        if self._inited:
            return
        self.notify_strings_updated()
        self._inited = True
        logger.debug(f"inited")

    def notify_strings_updated(self):
        if len(self.text) > 0:
            self._update_count = self._update_count + 1
            # self.button._activation.write_dataref(float(self._update_count)) # this cause infinite recursion
            self._last_updated = now()
            logger.info(f"button {self.button.name}: notified of new strings ({self._update_count})")
            # logger.debug("\n".join(["", "0a:1234567890123456789012345678901234567890"] + [f"{k}:{v}" for k, v in self.text.items()]))

    def is_updated(self) -> bool:
        # def updated_recently(how_long_ago: int = 10):  # secs
        #     # prevents multiple notification on startup or during string
        #     if self._last_updated is not None:
        #         delta = now().timestamp() - self._last_updated.timestamp()
        #         logger.debug(f"button {self.button.name}: updated recently: {delta < how_long_ago} ({delta}<{how_long_ago})")
        #         return delta < how_long_ago  # seconds
        #     logger.debug(f"button {self.button.name}: not updated yet")
        #     return False

        upd_cnt = 0
        for name, collection in self.button.dataref_collections.items():
            if name not in self.button.sim.collector.collections.keys():  # not collecting now
                continue
            if name == "boxes":  # no string
                continue

            this_coll = self.button.sim.collector.collections[name]
            this_string = this_coll.as_string()

            if len(this_string) < len(this_coll.datarefs):  # we did not fetch all chars yet
                logger.debug(f"button {self.button.name}: collection {name}: received {len(this_string)} out of {len(this_coll.datarefs)}")
                continue

            logger.debug(f"button {self.button.name}: collection {name}: completed ({len(this_coll.datarefs)})")
            # 2. Has the string changed?
            curr_text = self.text.get(name)
            if curr_text is None or curr_text != this_string:
                self.text[name] = this_string
                upd_cnt = upd_cnt + 1
                logger.debug(f"button {self.button.name}: collection {name}: old text='{curr_text}', new text='{this_string}'")
                # notify local handler of collcetion, if any
                # set_dref = collection.get("set-dataref")
                # if set_dref is not None:
                #     self.button._activation._write_dataref(set_dref, float(self._update_count))
                #     logger.debug(f"button {self.button.name}: collection {name}: notified {set_dref}")
            else:
                logger.debug(f"button {self.button.name}: collection {name}: text unchanged '{this_string}'")

        if upd_cnt > 0:
            self.notify_strings_updated()

        return upd_cnt > 0

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

        text = "\n".join(self.text.values()) if len(self.text) > 0 else self.text_default

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
        elif text_position[1] == "b":
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
