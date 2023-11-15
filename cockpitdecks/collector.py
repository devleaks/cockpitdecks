import logging
import time
import itertools
from abc import ABC, abstractmethod
from datetime import timedelta
import random

from cockpitdecks import SPAM_LEVEL, now
from cockpitdecks.simulator import DatarefListener

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

MAX_COLLECTION_SIZE = 40
DEFAULT_COLLECTION_EXPIRATION = 300  # secs, five minutes
TIMEOUT_TICKER = "sim/cockpit2/clock_timer/zulu_time_minutes"
TIMEOUT_TIME = 10  # seconds
TOO_OLD = 600  # seconds, collections that did not refresh within that default time need refreshing.

PACE_LOAD = 0.5  # secs
PACE_UNLOAD = 0.5


class DatarefSetListener(ABC):
    # To get notified when a dataref has changed.

    def __init__(self):
        self.name = "unnamed"

    @abstractmethod
    def dataref_collection_changed(self, dataref_collection):
        pass


class DatarefSet:
    """
    A collection of datarefs that gets monitored by the simulator as a collection.
    When all datarefs in collection have been updated, collection is considered updated
    and stops collecting dataref values.
    """

    def __init__(self, datarefs, name: str, sim, expire: int = 300):
        self.sim = sim
        self.name = name
        self.set_dataref = None
        self.is_loaded = False

        self.datarefs = datarefs  # { path: Dataref() }
        if len(self.datarefs) > MAX_COLLECTION_SIZE:
            logger.warning(f"collection larger than {MAX_COLLECTION_SIZE}, not all datarefs collected")
            self.datarefs = dict(itertools.islice(self.datarefs.items(), 0, MAX_COLLECTION_SIZE))
        self.expire = expire  # seconds

        # Working variables
        self.listeners = []
        self.last_loaded = None
        self.last_unloaded = None
        self.last_completed = None
        self.nice = 1  # I <3 Unix.

    def expired(self) -> bool:
        # Collection was last collected more than expired seconds,
        # it should be refreshed.
        # If collection was never entirely collected, it is expired (~needs collecting)
        # Increases nice value each time found expired
        if self.last_completed is None:
            self.nice = self.nice + 1
            return True
        expire = self.expire if self.expire is not None else DEFAULT_COLLECTION_EXPIRATION
        r = self.last_completed < now() - timedelta(seconds=expire)
        if r:
            self.nice = self.nice + 1
            logger.debug(f"collection {self.name} expired ({self.nice})")
        return r

    def did_not_progress(self, how_old: int = TIMEOUT_TIME) -> bool:
        # Collection update is stalled for more than how_old seconds
        r = self.is_loaded and (self.last_loaded < now() - timedelta(seconds=how_old))
        if r:
            logger.debug(f"collection {self.name} did not progress for at least {how_old} seconds")
        return r

    def is_collected(self) -> bool:
        if self.last_loaded is None:
            return False
        for d in self.datarefs.values():
            if d._last_updated is None or d._last_updated < self.last_loaded:
                # logger.debug(f"{self.name}: {d.path}: {d._last_updated} < {self.last_loaded}")
                return False
            # logger.debug(f"{self.name}: {d.path}: {d._last_updated}")
        logger.debug(f"{self.name} collected")
        return True

    def mark_collected(self):
        # Mark collection as collected
        self.last_completed = now()
        self.nice = 1
        logger.debug(f"{self.name} collected")
        self.notify()

    def mark_needs_collecting(self, threshold=None, force: bool = True):
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
        self.sim.add_datarefs_to_monitor(self.datarefs)
        self.is_loaded = True
        logger.debug(f"collection {self.name} loaded")  #  {self.datarefs.keys()}
        time.sleep(PACE_LOAD)

    def unload(self):
        self.sim.remove_datarefs_to_monitor(self.datarefs)
        self.is_loaded = False
        self.last_unloaded = now()
        logger.debug(f"collection {self.name} unloaded")
        time.sleep(PACE_UNLOAD)

    def add_listener(self, obj: "DatarefSetListener"):
        if not isinstance(obj, DatarefSetListener):
            logger.warning(f"{self.name} not a listener {obj}")
        if obj not in self.listeners:
            self.listeners.append(obj)
        logger.debug(f"{self.name} added listener ({len(self.listeners)})")

    def notify(self):
        for obj in self.listeners:
            obj.dataref_collection_changed(self)
            logger.log(SPAM_LEVEL, f"{self.name}: notified {obj.name}")
        logger.debug(f"{self.name} notified {'<'*20}")


class DatarefSetCollector(DatarefListener):
    # Class that collects collection of datarefs one at a time to limit the request pressure on the simulator.
    #
    def __init__(self, simulator):
        self.sim = simulator
        self.name = type(self).__name__
        self.collections = {}
        self.current_collection = None
        self.ticker_dataref = self.sim.get_dataref(TIMEOUT_TICKER)
        self.ticker_dataref.add_listener(self)

        self.init()

    def init(self):
        self.add_ticker()
        logger.debug(f"inited")

    def add_ticker(self):
        # this class' dataref_changed() will be called every minute
        self.sim.add_datarefs_to_monitor({self.ticker_dataref.path: self.ticker_dataref})
        logger.debug(f"ticker started")

    def add_collection(self, collection: DatarefSet, start: bool = True):
        for dref in collection.datarefs.values():
            dref.add_listener(self)  # the collector dataref_changed() will be called each time the dataref changes
        self.collections[collection.name] = collection
        logger.debug(f"collection {collection.name} added")
        if start and not self.is_collecting() and collection.needs_collecting():
            self.next_collection()
            logger.debug(f"started")

    def remove_collection(self, collection: DatarefSet):
        need_next = False
        if collection.name in self.collections.keys():
            if self.current_collection.name == collection.name:
                logger.debug(f"unloading current collection {collection.name} before removal")
                self.current_collection.unload()
                self.current_collection = None
                need_next = True
            del self.collections[collection.name]
            logger.debug(f"collection {collection.name} removed")
            if need_next:
                self.next_collection()

    def remove_all_collections(self):
        self.terminate(False)  # keep ticker
        cl = list(self.collections.keys())
        for c in cl:
            del self.collections[c]
        self.collections = {}

    def dataref_changed(self, dataref: "Dataref"):
        logger.debug(f"dataref changed {dataref.path}")

        if dataref.path == TIMEOUT_TICKER:
            logger.debug(f"timeout received")
            if self.is_collecting() and self.current_collection.did_not_progress():
                self.next_collection()
            if not self.is_collecting():
                logger.debug(f"not collecting, checking..")
                self.next_collection()
            return

        if not self.is_collecting():
            logger.debug(f"not collecting")
            return

        # we are collecting...
        if self.current_collection.is_collected():
            logger.debug(f"current collection last_completed")
            self.current_collection.mark_collected()
            self.next_collection()
        elif self.current_collection.did_not_progress():
            logger.debug(f"current collection did not progress")
            self.next_collection()
        else:
            logger.debug(f"keep collecting..")

    def is_collecting(self) -> bool:
        if self.current_collection is not None:
            logger.debug(f"currently collecting {self.current_collection.name} since {self.current_collection.last_loaded.strftime('%H:%M:%S')})")
            return True
        return False

    def needs_collecting(self):
        return list(filter(lambda x: x.needs_collecting(), self.collections.values()))

    def next_collection(self):
        needs_collecting = self.needs_collecting()
        logger.debug(f"needs_collecting: {needs_collecting}")
        if len(needs_collecting) > 0:
            if self.is_collecting():
                logger.debug(f"unloading {self.current_collection.name}")
                self.current_collection.unload()
                self.current_collection = None
            else:
                logger.debug(f"was not collecting")
            self.current_collection = random.choices(needs_collecting, weights=[x.nice for x in needs_collecting])[0]  # choices returns a list()
            self.current_collection.load()
            logger.debug(f"changed to collection {self.current_collection.name} at {now().strftime('%H:%M:%S')}")  # causes issue
            logger.debug(f"collecting..")
        else:
            logger.debug(f"no collection to update")
            if self.is_collecting():
                logger.debug(f"collection {self.current_collection.name} keep collecting")
            else:
                logger.debug(f"not collecting")

    def terminate(self, notify=True):
        if self.is_collecting():
            self.current_collection.unload()
            self.current_collection = None
        if notify:
            self.sim.remove_datarefs_to_monitor({self.ticker_dataref.path: self.ticker_dataref})
            logger.debug(f"terminated")
