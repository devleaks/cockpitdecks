import logging
import time
from datetime import timedelta

from .activation import Activation
from cockpitdecks import now
from cockpitdecks.simulator import INTERNAL_DATAREF_PREFIX
from cockpitdecks.buttons.representation.xpweatherdrefs import REAL_WEATHER_REGION_DATAREFS, REAL_WEATHER_REGION_CLOUDS_DATAREFS, REAL_WEATHER_REGION_WINDS_DATAREFS
from cockpitdecks.buttons.representation.xpweatherdrefs import REAL_WEATHER_AIRCRAFT_DATAREFS, REAL_WEATHER_AIRCRAFT_CLOUDS_DATAREFS, REAL_WEATHER_AIRCRAFT_WINDS_DATAREFS

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# triggers an call to dataref_changed() at the minute.
# used to force batch roll if batch was not updated for a few seconds
#
TIMEOUT_TICKER = "sim/cockpit2/clock_timer/zulu_time_minutes"
TIMEOUT_TIME   = 10  # seconds
TOO_OLD = 600        # seconds, batches that did not refresh with that time need refreshing.

WEATHER_DATAREFS = REAL_WEATHER_REGION_DATAREFS
CLOUDS_DATAREFS = REAL_WEATHER_REGION_CLOUDS_DATAREFS
CLOUD_LAYERS = 3
WINDS_DATAREFS = REAL_WEATHER_REGION_WINDS_DATAREFS
WIND_LAYERS = 13

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

    def collect(self, threshold = None, force: bool = True):
        if force or self.last_completed is None:
            self.last_loaded = None
        if threshold is not None and self.last_completed < threshold:
            self.last_loaded = None
        if self.last_loaded is None:
            logger.debug(f"batch {self.name} ready to collect")

    def did_not_progress(self, how_old: int = TIMEOUT_TIME) -> bool:
        r = self.last_loaded < now() - timedelta(seconds=how_old)
        if r:
            logger.debug(f"batch {self.name} did not progress for {how_old} seconds")
        return r

    def need_refresh(self, how_old: int = TOO_OLD) -> bool:
        # Batch was last collected more than how_old seconds,
        # it should be refreshed.
        if self.last_completed is None:
            return True
        r = self.last_completed < now() - timedelta(seconds=how_old)
        if r:
            logger.debug(f"batch {self.name} too old, need refresh")
        return r

    def load(self):
        self.last_loaded = now()
        self.loader.button.sim.add_datarefs_to_monitor(self.datarefs)
        time.sleep(1)
        logger.debug(f"batch {self.name} loaded")

    def unload(self):
        self.loader.button.sim.remove_datarefs_to_monitor(self.datarefs)
        self.last_unloaded = now()
        time.sleep(1)
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
        self.last_notified = None

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
            if self.current_batch is not None and self.current_batch.did_not_progress():
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
            elif self.current_batch.did_not_progress():
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
        batches = self._config.get("batches")
        if batches is None:
            logger.warning("no batches")
            return
        for batch in batches:
            name = batch.get("name", self.button.name+"-batch#"+str(len(self.batches)))
            count = batch.get("array")
            drefs = batch.get("datarefs")
            if count is None:
                self.add_batch(Batch(datarefs=drefs, name=name, loader=self))
            else:
                count = int(count)
                # 2. Clouds
                for i in range(count):
                    drefsarr = [f"{d}[{i}]" for d in drefs]
                    self.add_batch(Batch(datarefs=drefsarr, name=f"{name}#{i}", loader=self))
        logger.debug(f"button {self.button.name}: loaded {len(self.batches)} batches, {len(self.dref_collection)} datarefs")

    def make_batch_for_array(self, dataref, size: int, name: str = None):
        drefs = [f"{dataref}[{i}]" for i in range(size)]
        if name is None:
            name = f"{dataref}[{size}]"
        self.add_batch(Batch(datarefs=drefsarr, name=name, loader=self))
