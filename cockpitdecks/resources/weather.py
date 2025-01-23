"""Weather Data Abstraction

Abstraction has two component: The location of the weather information, and the weather itself.
This abstract class provides the hook to monitor both component independently.
Location is provided by the avwx.Station type which allows for all existing weather station worldwide.
If no station exists at the location, the closest station is used.

In this abstract class, the station (location) is a string that represent the ICAO code of the weather station.
(This way, this bastract class does not depend on a specific "Station" class.)
"""

import logging
import threading
from typing import Any, List
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from cockpitdecks.resources.weathericon import WeatherIcon

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class WeatherDataListener(ABC):

    @abstractmethod
    def weather_changed(self):
        raise NotImplementedError


class WeatherData(ABC):

    def __init__(self, name: str, config: dict) -> None:
        super().__init__()
        self.name = name
        self._config = config

        self._station: Any
        self._weather: Any

        self._check_freq = 60  # seconds

        self._station_check_freq = 2 * 60  # seconds
        self._weather_check_freq = 10 * 60  # seconds

        self._station_last_checked = datetime.now().astimezone() - timedelta(seconds=self._station_check_freq)
        self._weather_last_checked = datetime.now().astimezone() - timedelta(seconds=self._weather_check_freq)
        self._station_last_updated: datetime
        self._weather_last_updated: datetime

        self.listeners: List[WeatherDataListener] = []
        self._exit = threading.Event()
        self._exit.set()
        self._thread: threading.Thread

        self.weather_icon_factory = WeatherIcon()  # decorating weather icon image

    @property
    def station(self) -> Any:
        return getattr(self, "_station", None)

    @station.setter
    def station(self, station: Any):
        if self.station is None:
            self._station = station
            self.station_changed()
        elif self._station != station:
            self._station = station
            self.station_changed()

    @abstractmethod
    def set_station(self, station: Any):
        """Set weather station.

        Since station can be any type, it is "overloaded" in each class
        to accommodate for the weather data requested type.
        In its simplest form, the station is a string.

        Args:
            station (Any): [description]
        """
        self.station = station

    @abstractmethod
    def check_station(self) -> bool:
        """Check if requested station is the same as the weather station.
        If not, request a weather data for the new station.
        """
        # if self.station is None:
        #     return False
        # if self.weather is None:
        #     return False
        # if (datetime.now() - self._station_last_checked).seconds > self._station_check_freq:
        #     return True
        return False

    @abstractmethod
    def station_changed(self):
        """Called when a new station is installed"""
        raise NotImplementedError

    @property
    def weather(self) -> Any | None:
        return getattr(self, "_weather", None)

    def metar(self) -> str | None:
        """Returns raw METAR if available"""
        return None

    def has_weather(self):
        return self.weather is not None

    @abstractmethod
    def check_weather(self) -> bool:
        """Attempt to update weather data. Returns True if data is valid and has changed."""
        return False

    def add_listener(self, listener: WeatherDataListener):
        if isinstance(listener, WeatherDataListener):
            self.listeners.append(listener)
        else:
            logger.warning(f"{listener}, {type(WeatherDataListener)} is not a WeatherDataListener")

    def weather_changed(self):
        """Called when weather data has changed"""
        for listener in self.listeners:
            listener.weather_changed()

    @property
    def last_updated(self) -> datetime | None:
        return getattr(self, "_weather_last_updated", None)

    @property
    def label(self):
        """Returns the weather station name or label"""
        return self.name

    @property
    def is_running(self) -> bool:
        return not self._exit.is_set()

    def loop(self):
        logger.debug("started")
        now = datetime.now().astimezone()
        while self.is_running:
            logger.debug(f"checking for {self.name}")
            if self.check_station():
                self.station_changed()
            if self.check_weather():
                self.weather_changed()
            self._exit.wait(self._check_freq)
        logger.debug("exited")

    def start(self):
        if not self.is_running:
            self._exit.clear()
            self._thread = threading.Thread(target=self.loop, name=f"WeatherData::loop({self.name})")
            self._thread.start()
            logger.debug("started")
        else:
            logger.warning("already started")

    def stop(self):
        if self.is_running:
            self._exit.set()
            try:
                self._thread.join(timeout=self._check_freq)
                if self._thread.is_alive():
                    logger.warning("weather data check did not terminate")
                # self._thread = None
            except:
                logger.warning("weather data check did not terminate gracefully", exc_info=True)
            logger.debug("stopped")
        else:
            logger.debug("already stopped")

    def get_icon(self) -> tuple:
        if hasattr(self.weather, "metar"):
            name = self.weather_icon_factory.select_weather_icon(metar=self.weather.metar, station=self.station)
            icon = self.weather_icon_factory.get_icon(name=name)
            logger.info(f"metar weather icon {name} ({self.metar})")
            return name, icon
        name = self.weather_icon_factory.select_weather_icon(metar=self.weather, station=self.station, at_random=True)
        logger.debug(f"no metar, using random icon {name}")
        icon = self.weather_icon_factory.get_icon(name=name)
        return name, icon


class NoWeatherData(WeatherData):
    def __init__(self, name: str, config: dict) -> None:
        super().__init__(name, config)

    def check_station(self) -> bool:
        return False

    def check_weather(self) -> bool:
        return False

    def station_changed(self):
        pass

    def weather_changed(self):
        pass


if __name__ == "__main__":
    w = NoWeatherData(name="no-weather", config={})
    print(w.station, w.last_updated)
