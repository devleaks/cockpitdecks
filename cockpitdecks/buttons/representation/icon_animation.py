# ###########################
# Buttons that are drawn on render()
#
import logging
import threading

from .icon import MultiIcons
from .draw import DrawBase
from cockpitdecks import ICON_SIZE

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

    REPRESENTATION_NAME = "icon-animation"

    PARAMETERS = {"speed": {"type": "integer", "prompt": "Speed (seconds)"}, "icon-off": {"type": "icon", "prompt": "Icon when off"}}

    def __init__(self, button: "Button"):
        MultiIcons.__init__(self, button=button)

        self.speed = float(self._config.get("animation-speed", 1))
        self.icon_off = self._config.get("icon-off")

        if self.icon_off is None and len(self.multi_icons) > 0:
            self.icon_off = self.multi_icons[0]

        # Internal variables
        self.counter = 0
        self.running = False
        self.exit: threading.Event | None = None
        self.thread: threading.Thread | None = None

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
            self.thread = threading.Thread(target=self.loop, name=f"ButtonAnimate::loop({self.button_name()})")
            self.thread.start()
        else:
            logger.warning(f"button {self.button_name()}: already started")

    def anim_stop(self, render: bool = True):
        """
        Stops animation
        """
        if self.running and self.exit is not None and self.thread is not None:
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

    def describe(self) -> str:
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
