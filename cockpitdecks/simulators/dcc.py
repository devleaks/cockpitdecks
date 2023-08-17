import logging
import time
from abc import ABC, abstractmethod
from datetime import timedelta
import random

from cockpitdecks import SPAM_LEVEL, now
from cockpitdecks.simulator import DatarefListener, INTERNAL_DATAREF_PREFIX

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


TIMEOUT_TICKER = "sim/cockpit2/clock_timer/zulu_time_minutes"
TIMEOUT_TIME   = 10 # seconds
TOO_OLD = 600       # seconds, collections that did not refresh within that default time need refreshing.

PACE_LOAD   = 0.5   # secs
PACE_UNLOAD = 0.5


class DatarefCollection:
    """
    A collection of datarefs that gets monitored by the simulator as a collection.
    When all datarefs in collection have been updated, collection is considered updated
    and stops collecting dataref values.
    """
    def __init__(self, datarefs, name: str, collector, expire: int = 300):

        self.collector = collector
        self.name = name
        self.datarefs = datarefs
        self.expire = expire    # seconds

        # Working variables
        self.listeners = []
        self.last_loaded = None
        self.last_unloaded = None
        self.last_completed = None
        self.nice = 0  # I <3 Unix.

    def expired(self, how_old: int = TOO_OLD) -> bool:
        # Collection was last collected more than how_old seconds,
        # it should be refreshed.
        # If collection was never entirely collected, it is expired (~needs collecting)
        # Increases nice value each time found expired
        if self.last_completed is None:
            self.nice = self.nice + 1
            return True
        r = self.last_completed < now() - timedelta(seconds=how_old)
        if r:
            self.nice = self.nice + 1
            logger.debug(f"collection {self.name} expired ({self.nice})")
        return r

    def did_not_progress(self, how_old: int = TIMEOUT_TIME) -> bool:
        # Collection update is stalled for more than how_old seconds
        r = self.is_loaded and (self.last_loaded < now() - timedelta(seconds=how_old))
        if r:
            logger.debug(f"collection {self.name} did not progress for {how_old} seconds")
        return r

    def is_collected(self) -> bool:
        if self.last_loaded is None:
            return False
        for d in self.datarefs.values():
            if d.path not in self.loader.dref_collection.keys():
                continue
            if d._last_updated is None or d._last_updated < self.last_loaded:
                return False
        return True

    def mark_collected(self):
        # Mark collection as collected
        self.last_completed = now()
        self.nice = 0
        logger.debug(f"collection {self.name} collected")
        self.notify()

    def mark_needs_collecting(self, threshold = None, force: bool = True):
        if force or self.last_completed is None:
            self.last_loaded = None
        if threshold is not None and self.last_completed < threshold:
            self.last_loaded = None
        if self.last_loaded is None:
            logger.debug(f"collection {self.name} ready to collect")

    def needs_collecting(self):
        return self.last_loaded is None or self.expired()

    def load(self):
        self.last_loaded = now()
        self.collector.sim.add_datarefs_to_monitor(self.datarefs)
        self.is_loaded = True
        # logger.debug(f"collection {self.name} loaded")
        time.sleep(PACE_LOAD)

    def unload(self):
        self.collector.sim.remove_datarefs_to_monitor(self.datarefs)
        self.is_loaded = False
        self.last_unloaded = now()
        # logger.debug(f"collection {self.name} unloaded")
        time.sleep(PACE_UNLOAD)

    def add_listener(self, obj: "DatarefCollectionListener"):
        # if not isinstance(obj, DatarefCollectionListener):
        #   logger.warning(f"{self.dataref} not a listener {obj}")
        if obj not in self.listeners:
            self.listeners.append(obj)
        logger.debug(f"{self.dataref} added listener ({len(self.listeners)})")

    def notify(self):
        for obj in self.listeners:
            obj.dataref_collection_changed(self)
            logger.log(SPAM_LEVEL, f"{self.name}: notified {obj.name}")


class DatarefCollectionListener(ABC):
    # To get notified when a dataref has changed.

    def __init__(self):
        self.name = "unnamed"

    @abstractmethod
    def dataref_collection_changed(self, dataref_collection):
        pass


class DatarefCollectionCollector(DatarefListener):
    # Class that collects collection of datarefs one at a time to limit the request pressure on the simulator.
    #
    def __init__(self, simulator):

        self.sim = simulator
        self.name = type(self).__name__
        self.collections = {}
        self.current_collection = None
        self.collecting = False

        self.init()

    def init(self):
        # this class' dataref_changed() will be called every minute
        dref = self.sim.get_dataref(TIMEOUT_TICKER)
        dref.add_listener(self)
        logger.debug(f"inited")

    def add_collection(self, collection: DatarefCollection):
        for dref in collection:
            dref.add_listener(self)  # the collector will be called each time the dataref changes
        self.collections[collection.name] = collection

    def remove_collection(self, collection: DatarefCollection):
        if collection.name in self.collections.keys():
            del self.collections[collection.name]

    def dataref_changed(self, dataref: "Dataref"):
        # logger.debug(f"dataref changed {dataref.path}")
        if dataref.path == TIMEOUT_TICKER:
            logger.debug(f"timeout received")
            if self.current_collection is not None and self.current_collection.did_not_progress():
                self.next_collection()
            if not self.collecting:
                logger.debug(f"not collecting, checking..")
                self.next_collection()
            return
        if not self.collecting:
            return
        if self.current_collection is not None:
            if self.current_collection.is_collected():
                self.current_collection.mark_collected()
                self.next_collection()
            elif self.current_collection.did_not_progress():
                self.next_collection()

    def needs_collecting(self):
        return list(filter(self.collections.values(), lambda x: x.needs_collecting()))

    def next_collection(self):
        if self.current_collection is not None:
            self.current_collection.unload()
            self.current_collection = None
        needs_collecting = self.needs_collecting()
        if len(needs_collecting) > 0:
            self.collecting = True
            self.current_collection = random.choice(needs_collecting, weights=[x.nice for x in needs_collecting])
            self.current_collection.load()
            logger.debug(f"changed to collection {self.current_collection.name} at {now().strftime('%H:%M:%S')}")
        else:
            self.collecting = False
            logger.debug(f"no collection to update")

