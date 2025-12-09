# ###########################
# Buttons that are drawn on render()
#
import logging
import threading

from .draw import DrawBase

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


#
# ###############################
# ANIMATED  REPRESENTATION
#
# ###############################
# ANIMATED DRAW REPRESENTATION
#
#
class DrawAnimation(DrawBase):
    """
    https://stackoverflow.com/questions/5114292/break-interrupt-a-time-sleep-in-python
    """

    REPRESENTATION_NAME = "draw-animation"

    PARAMETERS = DrawBase.PARAMETERS | {"speed": {"type": "integer", "prompt": "Speed (seconds)"}, "icon-off": {"type": "icon", "prompt": "Icon when off"}}

    SCHEMA = DrawBase.SCHEMA | {
        "speed": {"type": "integer", "meta": {"label": "Speed (seconds)"}},
        "icon-off": {"type": "icon", "meta": {"label": "Icon when off"}},
    }

    def __init__(self, button: "Button"):
        DrawBase.__init__(self, button=button)

        self._animation = self._config.get("animation", {})

        # Base definition
        self.speed = float(self._animation.get("speed", 1))

        # Working attributes
        self.tween = 0

        self.running: bool | None = None  # state unknown
        self.exit = None
        self.thread = None

    def loop(self):
        self.exit = threading.Event()
        while not self.exit.is_set():
            self.animate()
            self.button.render()
            self.exit.wait(self.speed)
        logger.debug("exited")

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
        self.inc("tween")
        # logger.debug(f"tick")
        # return super().render()

    def anim_start(self):
        """
        Starts animation
        """
        if not self.running and self.speed is not None:
            self.running = True
            self.thread = threading.Thread(target=self.loop, name=f"ButtonAnimate::loop({self.button.name})")
            self.thread.start()
            logger.debug("started")
        else:
            logger.warning(f"button {self.button.name}: already started")

    def anim_stop(self):
        """
        Stops animation
        """
        if self.running:
            self.running = False
            self.exit.set()
            try:
                wait = 2 * (self.speed if self.speed is not None else 5)
                if wait < 5:
                    wait = 5
                self.thread.join(timeout=wait)
                if self.thread.is_alive():
                    logger.warning(f"button {self.button.name}: animation did not terminate (timetout {wait}secs.)")
            except:
                pass
            logger.debug("stopped")
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


# ###############################
# FOLLOW THE GREEN ICON
#
# (I'm the person who made follow the greens.)
#
class DrawAnimationFTG(DrawAnimation):

    REPRESENTATION_NAME = "ftg"

    PARAMETERS = {"speed": {"type": "integer", "prompt": "Speed (seconds)"}}

    SCHEMA = {"speed": {"type": "integer", "meta": {"label": "Speed (seconds)"}}}

    def __init__(self, button: "Button"):
        DrawAnimation.__init__(self, button=button)

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
        image, draw = self.simple_icon()

        bgrd = self.button.deck.get_icon_background(
            name=self.button_name,
            width=image.width,
            height=image.height,
            texture_in=self.icon_texture,
            color_in=self.icon_color,
            use_texture=True,
            who="Weather",
        )

        icon_size = max(image.size)

        image.paste(bgrd)
        # Button
        cs = 4  # light size, px
        lum = 5  # num flashing green center lines
        nb = 2 * lum  # num side bleu lights, i.e. twice more blue lights than green ones
        h0 = icon_size / 16  # space from left/right sides
        h1 = icon_size / 2 - h0  # space from bottom of upper middle part
        s = (icon_size - (2 * h0)) / (nb - 1)  # spece between blue lights
        # Taxiway borders, blue lights
        for i in range(nb):
            for h in [h0, h1]:
                w = h0 + i * s
                tl = [w - cs, h - cs]
                br = [w + cs, h + cs]
                draw.ellipse(tl + br, fill="blue")
        # Taxiway center yellow line
        h = icon_size / 4
        draw.line([(h0, h), (icon_size - h0, h)], fill="yellow", width=4)

        # Taxiway center lights, lit if animated
        offset = -24
        cs = 2 * cs
        for i in range(lum):
            w = offset + h + i * s * 2 - s / 2
            w = icon_size - w
            tl = [w - cs, h - cs]
            br = [w + cs, h + cs]
            color = "lime" if self.running and (self.tween + i) % lum == 0 else "chocolate"
            draw.ellipse(tl + br, fill=color)

        # Text AVAIL (=off) or framed ON (=on)
        font = self.get_font(self.button.get_attribute("label-font"), 80)
        inside = icon_size / 16
        cx = icon_size / 2
        cy = int(3 * icon_size / 4)
        if self.running:
            draw.multiline_text(
                (cx, cy),
                text="ON",
                font=font,
                anchor="mm",
                align="center",
                fill="deepskyblue",
            )
            txtbb = draw.multiline_textbbox((cx, cy), text="ON", font=font, anchor="mm", align="center")  # min frame, just around the text
            text_margin = 2 * inside  # margin "around" text, line will be that far from text
            framebb = (
                (txtbb[0] - text_margin, txtbb[1] - text_margin / 2),
                (txtbb[2] + text_margin, txtbb[3] + text_margin / 2),
            )
            side_margin = 4 * inside  # margin from side of part of annunciator
            framemax = (
                (cx - icon_size / 2 + side_margin, cy - icon_size / 4 + side_margin),
                (cx + icon_size / 2 - side_margin, cy + icon_size / 4 - side_margin),
            )
            frame = (
                (
                    min(framebb[0][0], framemax[0][0]),
                    min(framebb[0][1], framemax[0][1]),
                ),
                (
                    max(framebb[1][0], framemax[1][0]),
                    max(framebb[1][1], framemax[1][1]),
                ),
            )
            thick = int(icon_size / 32)
            # logger.debug(f"button {self.button.name}: part {partname}: {framebb}, {framemax}, {frame}")
            draw.rectangle(frame, outline="deepskyblue", width=thick)
        else:
            font = self.get_font(self.button.get_attribute("label-font"), 60)
            draw.multiline_text(
                (cx, cy),
                text="AVAIL",
                font=font,
                anchor="mm",
                align="center",
                fill="lime",
            )

        return image
