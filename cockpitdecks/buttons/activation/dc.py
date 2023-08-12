import logging
from datetime import datetime, timedelta

from .activation import Activation
from cockpitdecks.simulator import INTERNAL_DATAREF_PREFIX

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# triggers an call to dataref_changed() at the minute.
# used to force batch roll if batch was not updated for a few seconds
#
TIMEOUT_TICKER = "sim/cockpit2/clock_timer/zulu_time_minutes"
TIMEOUT_TIME   = 10 #  seconds

def now():
    return datetime.now().astimezone()

class Batch:
    """
    A collection of datarefs that gets monitored by Cockpitdecks as a batch.
    When all datarefs in batch have been updated, batch is considered updated
    and stops collecting dataref values.
    """
    def __init__(self, datarefs, loader, name: str = None):

        self.batch = datarefs
        self.loader = loader
        self.name = name
        self.datarefs = {}
        self.last_loaded = None
        self.last_unloaded = None
        self.last_completed = None

        self.init()

    def init(self):
        for dref in self.batch:
            self.datarefs[dref] = self.loader.button.sim.get_dataref(dref)  # creates or return already defined dataref
            self.datarefs[dref].add_listener(self.loader.button)

    def get_datarefs(self):
        return self.datarefs

    def is_collected(self) -> bool:
        if self.last_loaded is None:
            return False
        for d in self.datarefs.values():
            if d.path not in self.loader.dref_collection.keys():
                continue
            if d._last_updated is None or d._last_updated < self.last_loaded:
                return False
        return True

    def collected(self):
        # Mark batch as collected
        self.last_completed = now()
        logger.debug(f"batch {self.name} collected")

    def collect(self):
        self.last_loaded = None
        logger.debug(f"batch {self.name} ready to collect")

    def too_old(self, how_old: int = TIMEOUT_TIME) -> bool:
        r = self.last_loaded < now() - timedelta(seconds=how_old)
        if r:
            logger.debug(f"batch {self.name} too old")
        return r

    def load(self):
        self.last_loaded = now()
        self.loader.button.sim.add_datarefs_to_monitor(self.datarefs)
        logger.debug(f"batch {self.name} loaded")

    def unload(self):
        self.loader.button.sim.remove_datarefs_to_monitor(self.datarefs)
        self.last_unloaded = now()
        logger.debug(f"batch {self.name} unloaded")


class DrefCollector(Activation):
    # Activation that collects a limited set of datarefs per (batch)
    # in a sequential way, in order to collect a large set of datarefs.
    # When collection completed, notifies self.local_dataref.
    # Works better with slow changing datarefs.
    # Needs a "ticker" to provoke batch changes when no update occur in current batch. (kind of a timeout)
    # Use minutes ticker to provoke batch changes
    #
    def __init__(self, config: dict, button: "Button"):

        self.local_dataref = config.get("set-dataref", INTERNAL_DATAREF_PREFIX + type(self).__name__ + ":" + config.get("name"))

        self.dref_collection = {}
        self.batches = []
        self.cycle = 0 # to start with 0 after inc
        self.current_batch = None

        Activation.__init__(self, config=config, button=button)

        self.collecting = False
        self.notification_count = 0
        self.last_notified = now()

    def init(self):
        # When button is created,starts collection of datarefs.
        self._local_dataref = self.button.sim.get_dataref(self.local_dataref)  # creates or return already defined dataref
        self.dref_collection[TIMEOUT_TICKER] = self.button.sim.get_dataref(TIMEOUT_TICKER)
        self.dref_collection[TIMEOUT_TICKER].add_listener(self.button)
        self.load_batches()
        self.cycle = -1
        logger.debug(f"{self.button.name} inited")

    def add_batch(self, batch):
        batch.datarefs[TIMEOUT_TICKER] = self.button.sim.get_dataref(TIMEOUT_TICKER)  # creates or return already defined dataref
        self.dref_collection = self.dref_collection | batch.get_datarefs()
        self.batches.append(batch)

    def notify(self):
        self.notification_count = self.notification_count + 1
        self.last_notified = now()
        self._write_dataref(self.local_dataref, self.notification_count)
        logger.debug(f"button {self.button.name}: {self.local_dataref} notified ({self.notification_count})")

    def get_datarefs(self, base:dict = None):
        logger.debug(f"button {self.button.name}: added button datarefs {[TIMEOUT_TICKER]}")
        return [TIMEOUT_TICKER]

    def dataref_changed(self, dataref: "Dataref"):
        # logger.debug(f"button {self.button.name}: dataref changed {dataref.path}")
        if dataref.path == self.local_dataref:
            logger.debug(f"button {self.button.name}: ignore self update")
            return
        if dataref.path == TIMEOUT_TICKER:
            logger.debug(f"button {self.button.name}: timeout received")
            if self.current_batch is not None and self.current_batch.too_old():
                if self.collecting:
                    self.change_batch()
            if not self.collecting:
                logger.debug(f"button {self.button.name}: not collecting, started..")
                self.start_collection()
            return
        if not self.collecting:
            return
        if self.all_batch_collected():
            self.stop_collecting()
            self.notify()
        elif self.collecting and self.current_batch is not None:
            if self.current_batch.is_collected():
                self.current_batch.collected()
                self.change_batch()
            elif self.current_batch.too_old():
                self.change_batch()

    def all_batch_collected(self):
        for batch in self.batches:
            if not batch.is_collected():
                return False
        logger.debug(f"button {self.button.name}: all batches collected")
        return True

    def collect_all_batch(self):
        for batch in self.batches:
            batch.collect()
        logger.debug(f"button {self.button.name}: all batches ready to collect")

    def start_collection(self):
        self.collecting = True
        self.cycle = self.cycle + 1
        self.current_batch = self.batches[self.cycle % len(self.batches)]
        self.current_batch.load()
        logger.debug(f"button {self.button.name}: collection started")
        # logger.debug(f"button {self.button.name}: loaded batch {self.current_batch_id}")
        # logger.debug(f"button {self.button.name}: monitoring {self.batches[self.current_batch_id].keys()}")
        # logger.debug(f"monitoring {self.button.sim.datarefs.values()}")

    def stop_collecting(self):
        self.collecting = False
        if self.current_batch is not None:
            self.current_batch.unload()
        self.current_batch = None
        logger.debug(f"button {self.button.name}: collection stopped")

    def change_batch(self):
        if self.current_batch is not None:
            self.current_batch.unload()
        self.cycle = self.cycle + 1
        self.current_batch = self.batches[self.cycle % len(self.batches)]
        self.current_batch.load()
        logger.debug(f"button {self.button.name}: changed to batch {self.current_batch.name}")
        # logger.debug(f"button {self.button.name}: monitoring {self.batches[self.current_batch_id].keys()}")
        # logger.debug(f"monitoring {self.button.sim.datarefs.values()}")

    def load_again(self):
        self.collect_all_batch()
        self.start_collection()

    def activate(self, state: bool):
        if state:
            self.load_again()

    def load_batches(self):
        # Hardcoded here for now...
        # Later, can simply slice all datarefs into batches of limited size
        # 1. First batch is all weather datarefs
        self.add_batch(Batch(datarefs=[
                "sim/weather/aircraft/altimeter_temperature_error",
                "sim/weather/aircraft/barometer_current_pas",
                "sim/weather/aircraft/gravity_mss",
                "sim/weather/aircraft/precipitation_on_aircraft_ratio",
                "sim/weather/aircraft/qnh_pas",
                "sim/weather/aircraft/relative_humidity_sealevel_percent",
                "sim/weather/aircraft/speed_sound_ms",
                "sim/weather/aircraft/temperature_ambient_deg_c",
                "sim/weather/aircraft/temperature_leadingedge_deg_c",
                "sim/weather/aircraft/thermal_rate_ms",
                "sim/weather/aircraft/visibility_reported_sm",
                "sim/weather/aircraft/wave_amplitude",
                "sim/weather/aircraft/wave_dir",
                "sim/weather/aircraft/wave_length",
                "sim/weather/aircraft/wave_speed",
                "sim/weather/aircraft/wind_now_x_msc",
                "sim/weather/aircraft/wind_now_y_msc",
                "sim/weather/aircraft/wind_now_z_msc",
                "sim/weather/aircraft/wind_speed_msc"], name="weather", loader=self))
        # 2. Clouds
        for i in range(3):
            self.add_batch(Batch(datarefs=[
                    f"sim/weather/aircraft/cloud_base_msl_m[{i}]",
                    f"sim/weather/aircraft/cloud_coverage_percent[{i}]",
                    f"sim/weather/aircraft/cloud_tops_msl_m[{i}]",
                    f"sim/weather/aircraft/cloud_type[{i}]"], name=f"cloud {i}", loader=self))
        # 3. Winds
        for i in range(13):
            self.add_batch(Batch(datarefs=[
                    f"sim/weather/aircraft/dewpoint_deg_c[{i}]",
                    f"sim/weather/aircraft/shear_direction_degt[{i}]",
                    f"sim/weather/aircraft/shear_speed_kts[{i}]",
                    f"sim/weather/aircraft/temperatures_aloft_deg_c[{i}]",
                    f"sim/weather/aircraft/turbulence[{i}]",
                    f"sim/weather/aircraft/wind_altitude_msl_m[{i}]",
                    f"sim/weather/aircraft/wind_direction_degt[{i}]",
                    f"sim/weather/aircraft/wind_speed_kts[{i}]"], name=f"wind {i}", loader=self))
        logger.debug(f"button {self.button.name}: loaded {len(self.batches)} batches, {len(self.dref_collection)} datarefs")
