# ###########################
# Representation that displays side icons.
# Vertical: present left or right vertical screens on Loupedeck Live.
# These buttons are Loupedeck Live specific.
#
import logging
from PIL import ImageDraw
from cockpitdecks.resources.color import convert_color
from .icon import Icon
from cockpitdecks import CONFIG_KW, DECK_FEEDBACK

# from cockpitdecks.button import Button


logger = logging.getLogger(__name__)


class IconSide(Icon):  # modified Representation IconSide class

    REPRESENTATION_NAME = "side"

    def __init__(self, config: dict, button: "Button"):
        config["icon-color"] = config["side"].get("icon-color", button.get_attribute("default-icon-color"))
        Icon.__init__(self, config=config, button=button)

        self.side = config.get("side")  # multi-labels
        self.centers = self.side.get("centers", [43, 150, 227])  # type: ignore
        self.labels: str | None = self.side.get("labels")  # type: ignore
        self.label_position = config.get("label-position", "cm")  # "centered" on middle of side image

    def get_datarefs(self):
        datarefs = []
        for label in self.labels:
            drefs = self.button.scan_datarefs(label)
            if len(drefs) > 0:
                datarefs = datarefs + drefs
        return datarefs

    # get_datarefs from old IconSide
    # def get_datarefs(self):
    #     if self.datarefs is None:
    #         self.datarefs = []
    #         if self.labels is not None:
    #             for label in self.labels:
    #                 dref = label.get(CONFIG_KW.MANAGED.value)
    #                 if dref is not None:
    #                     logger.debug(f"button {self.button_name()}: added label dataref {dref}")
    #                     self.datarefs.append(dref)
    #     return self.datarefs

    def is_valid(self):
        if self.button.index not in ["left", "right"]:
            logger.debug(f"button {self.button_name()}: {type(self).__name__}: not a valid index {self.button.index}")
            return False
        return super().is_valid()

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it for SIDE keys (60x270).
        Side keys can have 3 labels placed in front of each knob.
        (Currently those labels are static only. Working to make them dynamic.)
        """
        image = super().get_image_for_icon()

        if image is None:
            return None

        draw = None

        if self.labels is not None:
            image = image.copy()  # we will add text over it
            draw = ImageDraw.Draw(image)
            inside = round(0.04 * image.width + 0.5)
            vheight = 38 - inside

            vcenter = [
                35,
                124,
                213,
            ]  # this determines the number of acceptable labels, organized vertically
            cnt = self.side.get("centers")

            if cnt is not None:
                vcenter = [round(270 * i / 100, 0) for i in convert_color(cnt)]  # !

            li = 0
            for label in self.labels:
                txt = label.get("label")

                get_text = self.button.get_text(label, root="text")

                if li >= len(vcenter) or txt is None:
                    continue

                # Managed block from old IconSide
                # managed = label.get(CONFIG_KW.MANAGED.value)
                # if managed is not None:
                #     value = self.button.get_dataref_value(managed)
                #     txto = txt
                #     if value:
                #         txt = txt + "•"  # \n•"
                #     else:
                #         txt = txt + " "  # \n"
                #     logger.debug(f"watching {managed}: {value}, {txto} -> {txt}")

                txto = get_text

                lfont = label.get("label-font", self.label_font)
                lsize = label.get("label-size", self.label_size)
                font = self.get_font(lfont, lsize)

                # Horizontal centering is not an issue...
                label_position = label.get("label-position", self.label_position)
                w = image.width / 2
                p = "m"
                a = "center"
                if label_position == "l":
                    w = inside
                    p = "l"
                    a = "left"
                elif label_position == "r":
                    w = image.width - inside
                    p = "r"
                    a = "right"
                # Vertical centering is black magic...
                h = vcenter[li] - lsize / 2
                if label_position[1] == "t":
                    h = vcenter[li] - vheight
                elif label_position[1] == "b":
                    h = vcenter[li] + vheight - lsize

                draw.multiline_text(
                    (w, h),
                    text=txt,
                    font=font,
                    anchor=p + "m",
                    align=a,
                    fill=label.get("label-color", self.label_color),  # (image.width / 2, 15)
                )

                # Text below LABEL
                tfont = label.get("text-font")
                tsize = label.get("text-size")
                tfont = self.get_font(tfont, tsize)

                text_position = h + lsize + 5  # Adjust based on your needs, adding lsize for simplicity
                draw.text(
                    (w, text_position),
                    text=txto,
                    font=tfont,
                    anchor=p + "m",
                    align=a,
                    fill=label.get("text-color"),
                )

                li = li + 1
        return image

    def describe(self) -> str:
        return "The representation produces an icon with optional label overlay for larger side buttons on LoupedeckLive."
