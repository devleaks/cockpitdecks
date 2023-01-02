# ###########################
# Loupedeck specials buttons
#
import logging
import random

from PIL import ImageDraw, ImageFont

from .constant import convert_color
from .button_core import ButtonPush


logger = logging.getLogger("LoupedeckButton")
# logger.setLevel(logging.DEBUG)


class ColoredButton(ButtonPush):
    """
    A Push button. We can only change the color of the button.
    The color is taken from current_value which defaults to icon_color (which defaults to default_icon_color).
    """

    def __init__(self, config: dict, page: "Page"):
        ButtonPush.__init__(self, config=config, page=page)

    def has_key_image(self):
        return False  # default

    def button_value(self):
        return self.icon_color if self.icon_color is not None else [random.randint(0,255) for _ in range(3)]

    def render(self):
        """
        Ask deck to set this button's image on the deck.
        set_key_image will call this button get_button function to get the icon to display with label, etc.
        """
        self.deck.set_button_color(self)
        # logger.debug(f"render: button {self.name} rendered")

    def get_color(self):
        return self.get_current_value()


class ButtonStop(ColoredButton):
    """
    Execute command while the key is pressed.
    Pressing starts the command, releasing stops it.
    """

    def __init__(self, config: dict, page: "Page"):
        ColoredButton.__init__(self, config=config, page=page)

    def is_valid(self):  # @todo with precision...
        return True

    def activate(self, state: bool):
        if state:
            if self.is_valid():
                self.deck.cockpit.stop()


class ButtonSide(ButtonPush):
    """
    A ButtonPush that has very special size (60x270), end therefore very special button rendering
    """
    def __init__(self, config: dict, page: "Page"):
        ButtonPush.__init__(self, config=config, page=page)

    def is_valid(self):  # @todo with precision...
        return True

    def activate(self, state):
        if type(state) == int:
            super().activate(state)
            return
        # else, swipe event
        logger.debug(f"activate: side bar swipe event unprocessed {state} ")

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it for SIDE keys (60x270).
        Side keys can have 3 labels placed in front of each knob.
        (Currently those labels are static only. Working to make them dynamic.)
        """
        image = None
        # we can't get "button-resized-ready" deck icon, we need to start from original icon stored in decks.
        if self.key_icon in self.deck.cockpit.icons.keys():
            image = self.deck.cockpit.icons[self.key_icon]
            image = self.deck.pil_helper.create_scaled_image(self.index, image)

        if image is not None:
            draw = None
            # Add label if any
            if self.labels is not None:
                image = image.copy()  # we will add text over it
                draw = ImageDraw.Draw(image)
                inside = round(0.04 * image.width + 0.5)
                vcenter = [43, 150, 227]  # this determines the number of acceptable labels, organized vertically
                vposition = "TCB"
                vheight = 38 - inside

                li = 0
                for label in self.labels:
                    cnt = label.get("centers")
                    if cnt is not None:
                        vcenter = [round(270 * i / 100, 0) for i in convert_color(cnt)]  # !
                        continue
                    txt = label.get("label")
                    knob = "knob" + vposition[li] + self.index[0].upper()
                    if knob in self.page.buttons.keys():
                        corrknob = self.page.buttons[knob]
                        if corrknob.has_option("dot"):
                            if corrknob.is_dotted(txt):
                                txt = txt + "•"  # \n•"
                            else:
                                txt = txt + ""   # \n"
                        logger.debug(f"get_image: watching {knob}")
                    else:
                        logger.debug(f"get_image: not watching {knob}")
                    if li >= len(vcenter) or txt is None:
                        continue
                    fontname = self.get_font(label.get("label-font", self.label_font))
                    if fontname is None:
                        logger.warning(f"get_image: no font, cannot overlay label")
                    else:
                        # logger.debug(f"get_image: font {fontname}")
                        lsize = label.get("label-size", self.label_size)
                        font = ImageFont.truetype(fontname, lsize)
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

                        # logger.debug(f"get_image: position {self.label_position}: {(w, h)}, anchor={p+'m'}")
                        draw.multiline_text((w, h),  # (image.width / 2, 15)
                                  text=txt,
                                  font=font,
                                  anchor=p+"m",
                                  align=a,
                                  fill=label.get("label-color", self.label_color))
                    li = li + 1
            elif self.label is not None:
                fontname = self.get_font()
                if fontname is None:
                    logger.warning(f"get_image: no font, cannot overlay label")
                else:
                    # logger.debug(f"get_image: font {fontname}")
                    image = image.copy()  # we will add text over it
                    draw = ImageDraw.Draw(image)
                    font = ImageFont.truetype(fontname, self.label_size)
                    inside = round(0.04 * image.width + 0.5)
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
                    h = image.height / 2 - self.label_size / 2
                    if self.label_position[1] == "t":
                        h = inside + self.label_size / 2
                    elif self.label_position[1] == "r":
                        h = image.height - inside - self.label_size
                    # logger.debug(f"get_image: position {self.label_position}: {(w, h)}")
                    draw.multiline_text((w, h),  # (image.width / 2, 15)
                              text=label,
                              font=font,
                              anchor=p+"m",
                              align=a,
                              fill=self.label_color)



            # Add little check mark if not valid/fake
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
