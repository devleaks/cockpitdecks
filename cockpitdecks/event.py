from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from math import sqrt
import logging

from cockpitdecks import DECK_ACTIONS

# from cockpitdecks.deck import Deck

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class Event(ABC):
    """Event base class.

    Defines required capability to handle event.
    """

    def __init__(self, autorun: bool = True):
        """Deck event

        Args:
            action (DECK_ACTIONS): Action produced by this event (~ DeckEvent type)
            deck (Deck): Deck that produced the event
        """
        self._ts = datetime.now().timestamp()
        if autorun:
            self.run()

    def __str__(self):
        return f"{self.event}:{self.timestamp}"

    @property
    def event(self) -> str:
        """Event type"""
        return type(self).__name__

    @property
    def timestamp(self) -> float:
        """Event creation timestamp"""
        return self._ts

    def handling(self):
        """Called before event is processed"""
        self.started = datetime.now().timestamp()

    def handled(self):
        """Called when event has been processed"""
        self.completed = datetime.now().timestamp()

    def is_processed(self) -> bool:
        """Returns whether event has been processed and marked as such"""
        return hasattr(self, "completed") and self.completed is not None

    @property
    def duration(self) -> float:
        """Returns event handling duration in seconds"""
        if hasattr(self, "started") and self.started is not None and self.is_processed():
            return self.completed - self.started
        return -1.0

    @abstractmethod
    def run(self, just_do_it: bool = False) -> bool:
        return False


class DeckEvent(Event):
    """Deck event base class.

    Defines required capability to handle event.
    Keeps a timestamp when event was created

    [description]
    """

    REQUIRED_DECK_ACTIONS = DECK_ACTIONS.NONE

    def __init__(self, deck: "Deck", button: str, autorun: bool = True):
        """Deck event

        Args:
            action (DECK_ACTIONS): Action produced by this event (~ DeckEvent type)
            deck (Deck): Deck that produced the event
        """
        self.deck = deck
        self.button = button
        self._ts = datetime.now().timestamp()
        if autorun:
            self.run()

    def __str__(self):
        return f"{self.deck.name}:{self.button}:{self.REQUIRED_DECK_ACTIONS}:{self.timestamp}"

    @property
    def action(self) -> DECK_ACTIONS:
        """Event deck action type"""
        return self.REQUIRED_DECK_ACTIONS

    @property
    def event(self) -> str:
        """Event type"""
        return type(self).__name__

    @property
    def timestamp(self) -> float:
        """Event creation timestamp"""
        return self._ts

    def handling(self):
        """Called before event is processed"""
        self.started = datetime.now().timestamp()

    def handled(self):
        """Called when event has been processed"""
        self.completed = datetime.now().timestamp()

    def is_processed(self) -> bool:
        """Returns whether event has been processed and marked as such"""
        return hasattr(self, "completed") and self.completed is not None

    @property
    def duration(self) -> float:
        """Returns event handling duration in seconds"""
        if hasattr(self, "started") and self.started is not None and self.is_processed():
            return self.completed - self.started
        return -1.0

    def run(self, just_do_it: bool = False) -> bool:
        if self.deck is None:
            logger.warning(f"no deck")
            return False

        if just_do_it:
            page = self.deck.current_page
            if page is None:
                logger.warning(f"no current page on deck {self.deck.name}")
                return False

            idx = str(self.button)
            if idx not in self.deck.current_page.buttons.keys():
                logger.warning(f"no button {idx} on page {page.name} on deck {self.deck.name}")
                return False

            try:
                logger.debug(f"doing {idx} on page {page.name} on deck {self.deck.name}..")
                if not self.is_processed():
                    self.handling()
                    self.deck.current_page.buttons[idx].activate(self)
                    self.handled()
                    logger.debug(f"..done {round(self.duration, 3)}ms")
            except:
                logger.warning(
                    f"..done with error: deck {self.deck.name},  page {page.name}, button {idx}",
                    exc_info=True,
                )
                return False
        else:
            self.enqueue()
            logger.debug(f"enqueued")
        return True

    def enqueue(self):
        if self.deck is not None:
            self.deck.cockpit.event_queue.put(self)
        else:
            logger.warning("no deck")


class PushEvent(DeckEvent):
    """Event for key press"""

    REQUIRED_DECK_ACTIONS = DECK_ACTIONS.PUSH

    def __init__(self, deck: "Deck", button: str, pressed: bool, autorun: bool = True):
        """Event for key press.

        Args:
            pressed (bool): Whether the key was pressed (true) or released (false)
        """
        self.pressed = pressed
        DeckEvent.__init__(self, deck=deck, button=button, autorun=autorun)

    def __str__(self):
        return f"{self.deck.name}:{self.button}:{self.REQUIRED_DECK_ACTIONS}:{self.timestamp}:{self.is_pressed}"

    @property
    def is_pressed(self) -> bool:
        return self.pressed

    @property
    def is_released(self) -> bool:
        return not self.is_pressed


class EncoderEvent(DeckEvent):
    REQUIRED_DECK_ACTIONS = DECK_ACTIONS.ENCODER

    def __init__(self, deck: "Deck", button: str, clockwise: bool, autorun: bool = True):
        """Event for encoder stepped click.

        Args:
            clockwise (bool): Whether the encoder was turned clockwise (true) or counter-clockwise (false)
        """
        self.clockwise = clockwise
        DeckEvent.__init__(self, deck=deck, button=button, autorun=autorun)

    def __str__(self):
        return f"{self.deck.name}:{self.button}:{self.REQUIRED_DECK_ACTIONS}:{self.timestamp}:{self.turned_clockwise}"

    @property
    def turned_clockwise(self) -> bool:
        return self.clockwise

    @property
    def turned_counter_clockwise(self) -> bool:
        return not self.turned_clockwise


class SlideEvent(DeckEvent):
    REQUIRED_DECK_ACTIONS = DECK_ACTIONS.CURSOR

    def __init__(self, deck: "Deck", button: str, value: int, autorun: bool = True):
        """Event when sliding or rotation cursor value has changed..

        Args:
            value (int): new slider value
        """
        self.value = value
        DeckEvent.__init__(self, deck=deck, button=button, autorun=autorun)

    def __str__(self):
        return f"{self.deck.name}:{self.button}:{self.REQUIRED_DECK_ACTIONS}:{self.timestamp}:{self.value}"


class SwipeEvent(DeckEvent):
    REQUIRED_DECK_ACTIONS = DECK_ACTIONS.SWIPE

    def __init__(
        self,
        deck: "Deck",
        button: str,
        start_pos_x: int,
        start_pos_y: int,
        start_ts: float,
        end_pos_x: int,
        end_pos_y: int,
        end_ts: float,
        autorun: bool = True,
    ):
        """Event when a touch screen has been touched or swiped.

        For swipe events, only start and end positions are returned.
        Path of swipe is currently not tracked. (To be enhanced.)

        Args:
            start_pos_x (int): Start x position of swipe
            start_pos_y (int): Start y position of swipe
            start_ts (int): Timestamp of start of swipe
            end_pos_x (int): End x position of swipe
            end_pos_y (int): End y position of swipe
            end_ts (int): Timestamp of end of swipe
        """
        self.start_pos_x = start_pos_x
        self.start_pos_y = start_pos_y
        self.start_ts = start_ts
        self.end_pos_x = end_pos_x
        self.end_pos_y = end_pos_y
        self.end_ts = end_ts
        DeckEvent.__init__(self, deck=deck, button=button, autorun=autorun)

    def __str__(self):
        return f"{self.deck.name}:{self.button}:{self.REQUIRED_DECK_ACTIONS}:{self.timestamp}:swipe"

    @property
    def swipe_distance(self) -> float:
        """Distance covered by finger.

        Returns:
            float: Distance covered by finger in pixels
        """
        return sqrt(
            (self.end_pos_x - self.start_pos_x) * (self.end_pos_x - self.start_pos_x)
            + (self.end_pos_y - self.start_pos_y) * (self.end_pos_y - self.start_pos_y)
        )

    @property
    def swipe_duration(self) -> float:
        """Duration of the contact of the finger with the surface.

        Returns:
            float: duration of swipe or touch, in seconds
        """
        return self.end_ts - self.start_ts

    def touched_only(self, tolerance: float = 10.0) -> bool:
        """Returns whether the swipe was just a touch, a very small movement swipe

        Args:
            tolerance (float): Minimum distance to cover to have a real swipe (default: `10.0` pixels)

        Returns:
            bool: Whether the touch screen was touched or swiped.
        """
        return self.swipe_distance < tolerance

    def long_press(self, minimum_duration: float = 3.0, tolerance: float = 10.0) -> bool:
        """Returns whether the swipe was just a touch but for a long time

        Args:
            minimum_duration (float): Minimum time to remain _pressed_ before considered a _long press_ (default: `3.0` seconds)
            tolerance (float): Minimum distance to cover to have a real swipe (default: `10.0` pixels)

        Returns:
            bool: Whether the touch screen was touched (not swiped) for a longer time than `minimum_duration`.
        """
        return self.touched_only(tolerance=tolerance) and self.swipe_duration > minimum_duration


class TouchEvent(DeckEvent):
    REQUIRED_DECK_ACTIONS = DECK_ACTIONS.SWIPE

    def __init__(
        self,
        deck: "Deck",
        button: str,
        pos_x: int,
        pos_y: int,
        start: TouchEvent | None = None,
        autorun: bool = True,
    ):
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.start = start
        DeckEvent.__init__(self, deck=deck, button=button, autorun=autorun)

    def __str__(self):
        return f"{self.deck.name}:{self.button}:{self.REQUIRED_DECK_ACTIONS}:{self.timestamp}:touch"

    def swipe(self) -> SwipeEvent | None:
        if self.start is not None:
            return SwipeEvent(
                deck=self.deck,
                button=self.button,
                start_pos_x=self.start.pos_x,
                start_pos_y=self.start.pos_y,
                start_ts=self.start.timestamp,
                end_pos_x=self.pos_x,
                end_pos_y=self.pos_y,
                end_ts=self.timestamp,
                autorun=autorun,
            )
        return None
