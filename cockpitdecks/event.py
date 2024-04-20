from __future__ import annotations
from abc import ABC
from datetime import datetime
from math import sqrt
from cockpitdecks import DECK_ACTIONS
# from cockpitdecks.deck import Deck


class DeckEvent(ABC):
    """Deck event base class.

    Defines required capability to handle event.
    Keeps a timestamp when event was created

    [description]
    """
    _required_deck_capability = DECK_ACTIONS.NONE


    def __init__(self, deck: "Deck", button: str):
        """Deck event

        Args:
            action (DECK_ACTIONS): Action produced by this event (~ DeckEvent type)
            deck (Deck): Deck that produced the event
        """
        self.deck = deck
        self.button = button
        self._ts = datetime.now().timestamp()

    @property
    def action(self) -> float:
        """Event deck action type"""
        return self._required_deck_capability

    @property
    def event(self) -> float:
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


class PushEvent(DeckEvent):
    """Event for key press"""
    _required_deck_capability = DECK_ACTIONS.PUSH

    def __init__(self, deck: "Deck", button: str, pressed: bool):
        """Event for key press.

        Args:
            pressed (bool): Whether the key was pressed (true) or released (false)
        """
        DeckEvent.__init__(self, deck=deck, button=button)
        self.pressed = pressed

    @property
    def is_pressed(self) -> bool:
        return self.pressed


    @property
    def is_released(self) -> bool:
        return not self.is_pressed


class EncoderEvent(DeckEvent):
    _required_deck_capability = DECK_ACTIONS.ENCODER

    def __init__(self, deck: "Deck", button: str, clockwise: bool):
        """Event for encoder stepped click.

        Args:
            clockwise (bool): Whether the encoder was turned clockwise (true) or counter-clockwise (false)
        """
        DeckEvent.__init__(self, deck=deck, button=button)
        self.clockwise = clockwise

    @property
    def turned_clockwise(self) -> bool:
        return self.clockwise

    @property
    def turned_counter_clockwise(self) -> bool:
        return not self.turned_clockwise


# class EncoderPushEvent(DeckEvent):
#     _required_deck_capability = DECK_ACTIONS.ENCODER_PUSH

#     def __init__(self, deck: "Deck", button: str, pressed: bool, clockwise: bool):
#         """Event for encoder stepped click.

#         Args:
#             clockwise (bool): Whether the encoder was turned clockwise (true) or counter-clockwise (false)
#         """
#         DeckEvent.__init__(self, deck=deck, button=button)
#         self.pressed = pressed
#         self.clockwise = clockwise

#     @property
#     def turned_clockwise(self) -> bool:
#         return self.clockwise

#     @property
#     def turned_counter_clockwise(self) -> bool:
#         return not self.turned_clockwise


class SlideEvent(DeckEvent):
    _required_deck_capability = DECK_ACTIONS.SLIDE

    def __init__(self, deck: "Deck", button: str, value: int):
        """Event when sliding or rotation cursor value has changed..

        Args:
            value (int): new slider value
        """
        DeckEvent.__init__(self, deck=deck, button=button)
        self.value = value


class SwipeEvent(DeckEvent):
    _required_deck_capability = DECK_ACTIONS.SWIPE

    def __init__(self, deck: "Deck", button: str, start_pos_x: int, start_pos_y: int, start_ts: float, end_pos_x: int, end_pos_y: int, end_ts: float):
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
        DeckEvent.__init__(self, deck=deck, button=button)
        self.start_pos_x = start_pos_x
        self.start_pos_y = start_pos_y
        self.start_ts = start_ts
        self.end_pos_x = end_pos_x
        self.end_pos_y = end_pos_y
        self.end_ts = end_ts

    @property
    def swipe_distance(self) -> float:
        """Distance covered by finger.

        Returns:
            float: Distance covered by finger in pixels
        """
        return sqrt((self.end_pos_x - self.start_pos_x)*(self.end_pos_x - self.start_pos_x) + (self.end_pos_y - self.start_pos_y)*(self.end_pos_y - self.start_pos_y))

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
    _required_deck_capability = DECK_ACTIONS.SWIPE

    def __init__(self, deck: "Deck", button: str, pos_x: int, pos_y: int, start: TouchEvent|None = None):
        DeckEvent.__init__(self, deck=deck, button=button)
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.start = start

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
                end_ts=self.timestamp)
        return None