from datetime import datetime, timedelta

from avwx import Station

from cockpitdecks.observable import Observable
from cockpitdecks.variable import Variable

WEATHER_STATION_VARIABLE = "weather-station-icao"


class StationObservable(Observable):
    """Special observable that monitor the aircraft position
    and update the closest weather/airport station every check_time seconds
    if necessary.
    """

    def __init__(self, config: dict, simulator: Simulator):
        super().__init__(config, simulator)
        self.check_time = 30  # seconds
        self._last_checked = datetime.now() - timedelta(seconds=self.check_time)
        self._last_updated = datetime.now()
        self.station: Station = Station.from_icao(icao=self.DEUFAULT_STATION)
        self.station_variable = simulator.get_variable(name=Variable.internal_variable_name(name=WEATHER_STATION_VARIABLE), is_string=True)

    def get_variables(self) -> set:
        return {"sim/flightmodel/position/latitude", "sim/flightmodel/position/longitude"}

    def simulator_variable_changed(self, data: "SimulatorVariable"):
        if (datetime.now() - self._last_checked).seconds < self.check_time:
            return

        self._last_checked = datetime.now()

        lat = self.simulator.get_simulator_variable_value("sim/flightmodel/position/latitude")
        lon = self.simulator.get_simulator_variable_value("sim/flightmodel/position/longitude")

        if lat is None or lon is None:
            if (self._no_coord_warn % 10) == 0:
                logger.warning("no coordinates")
            self._no_coord_warn = self._no_coord_warn + 1

        (nearest, coords) = Station.nearest(lat=lat, lon=lon, max_coord_distance=150000)
        if nearest.icao != self.station.icao:
            self.station = nearest
            self.station_variable.update_value(new_value=nearest.icao)
            self._last_updated = datetime.now()
