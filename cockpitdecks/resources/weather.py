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
from datetime import datetime

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

        self._check_freq = 30  # seconds
        self._station_check_freq = 5 * 60
        self._weather_check_freq = 10 * 60
        self._station_last_checked: datetime
        self._weather_last_checked: datetime
        self._station_last_updated: datetime
        self._weather_last_updated: datetime

        self.listeners: List[WeatherDataListener] = []
        self._exit = threading.Event()
        self._exit.set()
        self._thread: threading.Thread

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

    def check_station(self) -> bool:
        # if self.station is None:
        #     return False
        # if self.weather is None:
        #     return False
        # if (datetime.now() - self._station_last_checked).seconds < self._station_check_freq:
        #     return False
        return False

    @abstractmethod
    def station_changed(self):
        raise NotImplementedError

    @property
    def weather(self) -> Any | None:
        return getattr(self, "_weather", None)

    @abstractmethod
    def check_weather(self) -> bool:
        return False

    def weather_changed(self):
        for listener in self.listeners:
            listener.weather_changed()

    @property
    def last_updated(self) -> datetime | None:
        return self.weather.last_updated if self.weather is not None else None

    @property
    def is_running(self) -> bool:
        return not self._exit.is_set()

    def add_listener(self, listener: WeatherDataListener):
        if isinstance(listener, WeatherDataListener):
            self.listeners.append(listener)
        else:
            logger.warning(f"{listener}, {type(WeatherDataListener)} is not a WeatherDataListener")

    def loop(self):
        while self.is_running:
            if self._last_station_check <= 0 and self.check_station():
                self.station_changed()
                self._last_station_check = self._station_check_freq
            if self._last_weather_check <= 0 and self.check_weather():
                self.weather_changed()
                self._last_weather_check = self._weather_check_freq
            self._last_station_check = self._last_station_check - self._check_freq
            self._last_weather_check = self._last_weather_check - self._check_freq
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
