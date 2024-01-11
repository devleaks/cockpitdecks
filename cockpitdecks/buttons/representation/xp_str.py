# ###########################
# Representation that displays the content of a dataref string on an icon.
# These buttons are highly XP specific.
# (This is an attempt to generalize xp_ac button to any string.)
#
import logging

from cockpitdecks import ICON_SIZE
from cockpitdecks.simulator import DatarefSetListener
from .draw import DrawBase

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
logger.setLevel(logging.DEBUG)


class StringIcon(DrawBase, DatarefSetListener):
    def __init__(self, config: dict, button: "Button"):
        self.name = type(self).__name__
        self._inited = False
        self._cached = None
        self._updated = False
        self._last_updated = None
        self._strconfig = config.get("strings")

        self.text = {}
        self.text_default = config.get("no-text", "no text")

        DrawBase.__init__(self, config=config, button=button)

    def dataref_collection_changed(self, dataref_collection):
        # logger.debug(f"button {self.button.name}: dataref collection {dataref_collection.name} changed")
        if dataref_collection.is_completed():
            logger.debug(f"button {self.button.name}: dataref collection {dataref_collection.name} changed")
            currstr = dataref_collection.as_string()
            if currstr != self.text.get(dataref_collection.name):
                self.text[dataref_collection.name] = currstr
                self._updated = True

    def is_updated(self):
        if self._inited:
            return self._updated
        c = []
        for collection in self.button.dataref_collections.keys():
            if collection in self.button.page.dataref_collections.keys():
                self.button.page.dataref_collections[collection].add_listener(self)
                c.append(collection)
        self._inited = True
        logger.debug(f"inited ({c})")
        return False

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
        self._updated = False
        return self._cached
