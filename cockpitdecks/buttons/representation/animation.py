# ###########################
# Buttons that are drawn on render()
#
import logging
import threading

from .representation import MultiIcons
from .draw import DrawBase

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# ANIMATED  REPRESENTATION
#
# ###############################
# ICON-BASED ANIMATION
# (very much like a GIF image...)
#
class IconAnimation(MultiIcons):
    """
    To start the animation, set the button's current_value to something different from None or 0.
    To stop the anination, set the button's current_value to 0.
    When not running, an optional icon_off can be supplied, otherwise first icon in multi-icons list will be used.
    """

    def __init__(self, config: dict, button: "Button"):
        MultiIcons.__init__(self, config=config, button=button)

        self.speed = float(config.get("animation-speed", 1))
        self.icon_off = config.get("icon-off")

        if self.icon_off is None and len(self.multi_icons) > 0:
            self.icon_off = self.multi_icons[0]

        # Internal variables
        self.counter = 0
        self.exit = None
        self.thread = None
        self.running = False

    def loop(self):
        self.exit = threading.Event()
        while not self.exit.is_set():
            self.button.render()
            self.counter = self.counter + 1
            self.button.set_current_value(self.counter)  # get_current_value() will fetch self.counter value
            self.exit.wait(self.speed)
        logger.debug(f"exited")

    def should_run(self) -> bool:
        """
        Check conditions to animate the icon.
        """
        value = self.get_current_value()
        return value is not None and value != 0

    def anim_start(self):
        """
        Starts animation
        """
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.name = f"ButtonAnimate::loop({self.button_name()})"
            self.thread.start()
        else:
            logger.warning(f"button {self.button_name()}: already started")

    def anim_stop(self, render: bool = True):
        """
        Stops animation
        """
        if self.running:
            self.running = False
            self.exit.set()
            self.thread.join(timeout=2 * self.speed)
            if self.thread.is_alive():
                logger.warning(f"..thread may hang..")
            if render:
                self.render()
        else:
            logger.debug(f"button {self.button_name()}: already stopped")

    def clean(self):
        """
        Stops animation and remove icon from deck
        """
        logger.debug(f"button {self.button_name()}: cleaning requested")
        self.anim_stop(render=False)
        logger.debug(f"button {self.button_name()}: stopped")
        super().clean()

    def render(self):
        """
        Renders icon_off or current icon in list
        """
        if self.should_run():
            self.icon = self.multi_icons[(self.counter % len(self.multi_icons))]
            if not self.running:
                self.anim_start()
            return super().render()
        if self.running:
            self.anim_stop()
        self.icon = self.icon_off
        return super(MultiIcons, self).render()

    def describe(self):
        """
        Describe what the button does in plain English
        """
        a = [
            f"The representation produces an animation by displaying an icon from a list of {len(self.multi_icons)} icons"
            f"and changing it every {self.speed} seconds."
        ]
        if self.icon_off is not None:
            a.append(f"When the animation is not running, it displays an OFF icon {self.icon_off}.")
        return "\n\r".join(a)


#
# ###############################
# ANIMATED DRAW REPRESENTATION
#
#
class DrawAnimation(DrawBase):
    """
    https://stackoverflow.com/questions/5114292/break-interrupt-a-time-sleep-in-python
    """

    def __init__(self, config: dict, button: "Button"):
        DrawBase.__init__(self, config=config, button=button)

        self._animation = config.get("animation", {})

        # Base definition
        self.speed = float(self._animation.get("speed", 1))

        # Working attributes
        self.tween = 0

        self.running = None  # state unknown
        self.exit = None
        self.thread = None

    def loop(self):
        self.exit = threading.Event()
        while not self.exit.is_set():
            self.animate()
            self.button.render()
            self.exit.wait(self.speed)
        logger.debug(f"exited")

    def should_run(self) -> bool:
        """
        Check conditions to animate the icon.
        """
        return False

    def animate(self):
        """
        Where changes between frames occur

        :returns:   { description_of_the_return_value }
        :rtype:     { return_type_description }
        """
        self.tween = self.tween + 1
        # logger.debug(f"tick")
        return super().render()

    def anim_start(self):
        """
        Starts animation
        """
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.name = f"ButtonAnimate::loop({self.button.name})"
            self.thread.start()
            logger.debug(f"started")
        else:
            logger.warning(f"button {self.button.name}: already started")

    def anim_stop(self):
        """
        Stops animation
        """
        if self.running:
            self.running = False
            self.exit.set()
            self.thread.join(timeout=2 * self.speed)
            if self.thread.is_alive():
                logger.warning(f"button {self.button.name}: animation did not terminate")
            logger.debug(f"stopped")
        else:
            logger.debug(f"button {self.button.name}: already stopped")

    def clean(self):
        """
        Stops animation and remove icon from deck
        """
        logger.debug(f"button {self.button.name}: cleaning requested")
        self.anim_stop()
        logger.debug(f"button {self.button.name}: stopped")
        super().clean()

    def render(self):
        """
        Renders icon_off or current icon in list
        """
        logger.debug(f"button {self.button.name}: enter")
        if self.is_valid():
            logger.debug(f"button {self.button.name}: is valid {self.should_run()}, {self.running}")
            if self.should_run():
                if not self.running:
                    self.anim_start()
                return super().render()
            else:
                if self.running:
                    self.anim_stop()
                return super().render()
        return None


class DrawAnimationFTG(DrawAnimation):
    def __init__(self, config: dict, button: "Button"):
        DrawAnimation.__init__(self, config=config, button=button)

    def should_run(self):
        """
        I.e. only works with onoff activations.
        """
        return hasattr(self.button._activation, "is_on") and self.button._activation.is_on()

    def get_image_for_icon(self):
        """
        Can use self.running to check whether animated or not.
        Can use self.tween to increase iterations.
        Text, color, sizes are all hardcoded here.
        """
        image, draw = self.double_icon(width=ICON_SIZE, height=ICON_SIZE)

        bgrd = self.get_background(width=image.width, height=image.height)
        image.paste(bgrd)
        # Button
        cs = 4  # light size, px
        lum = 5  # num flashing green center lines
        nb = 2 * lum  # num side bleu lights, i.e. twice more blue lights than green ones
        h0 = ICON_SIZE / 16  # space from left/right sides
        h1 = ICON_SIZE / 2 - h0  # space from bottom of upper middle part
        s = (ICON_SIZE - (2 * h0)) / (nb - 1)  # spece between blue lights
        # Taxiway borders, blue lights
        for i in range(nb):
            for h in [h0, h1]:
                w = h0 + i * s
                tl = [w - cs, h - cs]
                br = [w + cs, h + cs]
                draw.ellipse(tl + br, fill="blue")
        # Taxiway center yellow line
        h = ICON_SIZE / 4
        draw.line([(h0, h), (ICON_SIZE - h0, h)], fill="yellow", width=4)

        # Taxiway center lights, lit if animated
        cs = 2 * cs
        for i in range(lum):
            w = h + i * s * 2 - s / 2
            w = ICON_SIZE - w
            tl = [w - cs, h - cs]
            br = [w + cs, h + cs]
            color = "lime" if self.running and (self.tween + i) % lum == 0 else "chocolate"
            draw.ellipse(tl + br, fill=color)

        # Text AVAIL (=off) or framed ON (=on)
        font = self.get_font(self.button.get_attribute("default-label-font"), 80)
        inside = ICON_SIZE / 16
        cx = ICON_SIZE / 2
        cy = int(3 * ICON_SIZE / 4)
        if self.running:
            draw.multiline_text((cx, cy), text="ON", font=font, anchor="mm", align="center", fill="deepskyblue")
            txtbb = draw.multiline_textbbox((cx, cy), text="ON", font=font, anchor="mm", align="center")  # min frame, just around the text
            text_margin = 2 * inside  # margin "around" text, line will be that far from text
            framebb = ((txtbb[0] - text_margin, txtbb[1] - text_margin / 2), (txtbb[2] + text_margin, txtbb[3] + text_margin / 2))
            side_margin = 4 * inside  # margin from side of part of annunciator
            framemax = (
                (cx - ICON_SIZE / 2 + side_margin, cy - ICON_SIZE / 4 + side_margin),
                (cx + ICON_SIZE / 2 - side_margin, cy + ICON_SIZE / 4 - side_margin),
            )
            frame = (
                (min(framebb[0][0], framemax[0][0]), min(framebb[0][1], framemax[0][1])),
                (max(framebb[1][0], framemax[1][0]), max(framebb[1][1], framemax[1][1])),
            )
            thick = int(ICON_SIZE / 32)
            # logger.debug(f"button {self.button.name}: part {partname}: {framebb}, {framemax}, {frame}")
            draw.rectangle(frame, outline="deepskyblue", width=thick)
        else:
            font = self.get_font(self.button.get_attribute("default-label-font"), 60)
            draw.multiline_text((cx, cy), text="AVAIL", font=font, anchor="mm", align="center", fill="lime")

        return image.convert("RGB")
