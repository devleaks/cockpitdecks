import logging
import time
import itertools
from abc import ABC, abstractmethod
from datetime import timedelta
import random

from cockpitdecks import SPAM_LEVEL, now
from cockpitdecks.simulator import Dataref, DatarefListener

loggerDatarefSet = logging.getLogger("DatarefSet")
# loggerDatarefSet.setLevel(SPAM_LEVEL)
# loggerDatarefSet.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)

MAX_COLLECTION_SIZE = 40
DEFAULT_COLLECTION_EXPIRATION = 300  # secs, five minutes
TIMEOUT_TICKER = "sim/cockpit2/clock_timer/zulu_time_minutes"  # zulu_time_seconds
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

    @abstractmethod
    def dataref_collection_completed(self, dataref_collection):
        pass


class DatarefSet(DatarefListener):
    """
    A collection of datarefs that gets monitored by the simulator as a collection.
    When all datarefs in collection have been updated, collection is considered updated
    and stops collecting dataref values.
    """

    def __init__(self, datarefs, name: str, sim, expire: int = 300):
        DatarefListener.__init__(self)
        self.sim = sim
        self.name = name
        self.is_loaded = False

        self.datarefs = datarefs  # { path: Dataref() }
        if len(self.datarefs) > MAX_COLLECTION_SIZE:
            loggerDatarefSet.warning(f"collection larger than {MAX_COLLECTION_SIZE}, *** not all datarefs will be collected ***")
            self.datarefs = dict(itertools.islice(self.datarefs.items(), 0, MAX_COLLECTION_SIZE))
        self.expire = expire  # seconds

        for d in self.datarefs.values():
            d.add_listener(self)

        # Working variables
        self.listeners = []
        self.last_loaded = None
        self.last_unloaded = None
        self.last_completed = None
        self._nice = 1  # I <3 Unix.

    def dataref_changed(self, dataref: "Dataref"):
        # loggerDatarefSet.debug(f"dataref changed {dataref.path}")
        self.notify_changed()
        if self.is_collected():  #  and not self.expired():
            loggerDatarefSet.debug(f"collection {self.name} completed")
            self.last_completed = now()
            self.notify_completed()
        else:
            loggerDatarefSet.debug(f"collection {self.name}")

    def dataref_updated(self, dataref: "Dataref"):
        """Dataref may have been updated with no change"""
        self.dataref_changed(dataref)

    def last_updated(self):
        try:
            return max([d._last_updated for d in self.datarefs if d._last_updated is not None])
        except:
            return None

    def oldest(self):
        try:
            return min([d._last_updated for d in self.datarefs if d._last_updated is not None])
        except:
            return None

    def nice(self):
        return self._nice

    def renice(self, nice: int = 0):
        self._nice = nice

    def upnice(self):
        self._nice = self._nice + 1

    def expired(self) -> bool:
        # Collection was last collected more than expired seconds,
        # it should be refreshed.
        # If collection was never entirely collected, it is expired (~needs collecting)
        # Increases nice value each time found expired
        oldest = self.oldest()
        if oldest is None:
            return True
        expire = self.expire if self.expire is not None else DEFAULT_COLLECTION_EXPIRATION
        r = oldest < now() - timedelta(seconds=expire)
        if r:
            loggerDatarefSet.debug(f"collection {self.name} expired ({self.nice()})")
        return r

    def changed(self) -> bool:
        """Has it changed since the last completion"""
        newest = self.last_updated()
        if newest is None:
            return False
        return newest > self.last_completed

    def did_not_progress(self, how_old: int = TIMEOUT_TIME) -> bool:
        # Collection update is stalled for more than how_old seconds
        r = self.is_loaded and (self.last_loaded < now() - timedelta(seconds=how_old))
        if r:
            loggerDatarefSet.debug(f"collection {self.name} did not progress for at least {how_old} seconds")
        return r

    def is_collected(self) -> bool:
        for d in self.datarefs.values():
            if d.current_value is None:
                loggerDatarefSet.debug(f"collection {self.name} has {d.path} with no value, not fully collected")
                return False
            if d._last_updated is None or d._last_updated < self.last_loaded:
                # loggerDatarefSet.debug(f"{self.name}: {d.path}: {d._last_updated} < {self.last_loaded}")
                loggerDatarefSet.debug(f"collection {self.name} has {d.path} expired, not fully collected")
                return False
            # loggerDatarefSet.debug(f"{self.name}: {d.path}: {d._last_updated}")
        loggerDatarefSet.debug(f"{self.name} fully collected")
        return True

    def acquired(self):
        e = 0
        n = 0
        f = 0
        for d in self.datarefs.values():
            if d._last_updated is None:
                n = n + 1
            elif d._last_updated < self.last_loaded:
                e = e + 1
            if d.current_value is not None:
                f = f + 1
        loggerDatarefSet.debug(f"collection {self.name}: count={len(self.datarefs)}, filled={f}, None={n}, Expired={e}")

    def needs_collecting(self):
        return self.last_loaded is None or self.expired()

    def load(self):
        self.last_loaded = now()
        self.sim.add_datarefs_to_monitor(self.datarefs)
        self.is_loaded = True
        self.renice()
        loggerDatarefSet.info(f"collection {self.name} loaded")  #  {self.datarefs.keys()}
        self.acquired()
        time.sleep(PACE_LOAD)

    def unload(self):
        self.sim.remove_datarefs_to_monitor(self.datarefs)
        self.is_loaded = False
        self.last_unloaded = now()
        loggerDatarefSet.log(SPAM_LEVEL, f"collection {self.name} unloaded")
        self.acquired()
        time.sleep(PACE_UNLOAD)

    def add_listener(self, obj: "DatarefSetListener"):
        if not isinstance(obj, DatarefSetListener):
            loggerDatarefSet.warning(f"{self.name} not a listener {obj}")
        if obj not in self.listeners:
            self.listeners.append(obj)
        loggerDatarefSet.debug(f"{self.name} added listener ({len(self.listeners)})")

    def notify_changed(self):
        for obj in self.listeners:
            obj.dataref_collection_changed(self)
            # loggerDatarefSet.log(SPAM_LEVEL, f"{self.name}: notified {obj.name} of change")
        # loggerDatarefSet.debug(f"{self.name} notified of change")

    def notify_completed(self):
        for obj in self.listeners:
            obj.dataref_collection_completed(self)
            loggerDatarefSet.log(SPAM_LEVEL, f"{self.name}: notified {obj.name} of completion")
        loggerDatarefSet.debug(f"{self.name} notified of completion")

    def get_dataref_value(self, dataref, default=None):
        d = self.datarefs.get(dataref)
        if d is None:
            loggerDatarefSet.warning(f"collection {self.name}: dataref {dataref} not found")
            return None
        return d.current_value if d.current_value is not None else default

    def as_string(self) -> str:
        ret = ""
        for d in self.datarefs.values():
            if d.current_value is not None:
                value = int(d.current_value)
                if value == 0:
                    loggerDatarefSet.debug(f"collection {self.name}: replaced 0 by space")
                    ret = ret + " "
                elif value > 0 and value < 256:
                    ret = ret + chr(value)
                else:
                    loggerDatarefSet.debug(f"collection {self.name}: invalid char value {value}")
        return ret

    def as_list(self) -> list:
        return [d.current_value for d in self.datarefs.values()]


TIMER = 10  # seconds


class DatarefSetCollector(DatarefListener, DatarefSetListener):
    # Class that collects collection of datarefs one at a time to limit the request pressure on the simulator.
    #
    def __init__(self, simulator):
        DatarefListener.__init__(self)
        DatarefSetListener.__init__(self)
        self.sim = simulator
        self.name = type(self).__name__
        self.collections = {}
        self.current_collection = None
        self.ticker_dataref = self.sim.get_dataref(TIMEOUT_TICKER)
        self.ticker_dataref.add_listener(self)
        self._timer = 0

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
        self.collections[collection.name].add_listener(self)
        logger.debug(f"collection {collection.name} added")
        if start and not self.is_collecting() and collection.needs_collecting():
            self.next_collection()
            logger.debug(f"started")

    def remove_collection(self, collection: DatarefSet, start: bool = True):
        need_next = False
        if collection.name in self.collections.keys():
            if self.current_collection is not None and self.current_collection.name == collection.name:
                logger.debug(f"unloading current collection {collection.name} before removal")
                self.current_collection.unload()
                self.current_collection = None
                need_next = True
            del self.collections[collection.name]
            logger.debug(f"collection {collection.name} removed")
            if start and need_next:
                self.next_collection()

    def remove_all_collections(self):
        self.terminate(False)  # keep ticker
        cl = list(self.collections.keys())
        for c in cl:
            del self.collections[c]
        self.collections = {}

    def get_dataref_value_from_collection(self, dataref, collection, default=None):
        c = self.collections.get(collection)
        if c is None:
            logger.warning(f"collection {collection} not found")
            return None
        return c.get_dataref_value(dataref=dataref, default=default)

    def dataref_collection_changed(self, collection):
        # logger.debug(f"collection {collection.name} changed")
        pass

    def dataref_collection_completed(self, collection):
        logger.debug(f"collection {collection.name} completed")
        self.next_collection()

    def dataref_changed(self, dataref: "Dataref"):
        if dataref.path == TIMEOUT_TICKER:
            self._timer = self._timer + 1
            if TIMEOUT_TICKER.endswith("seconds") and (self._timer % TIMER) != 0:
                return
            logger.debug(f"timeout received")
            if self.is_collecting() and self.current_collection.did_not_progress():
                logger.debug(f"collecting but no progress, next collection..")
                self.next_collection()
            if not self.is_collecting():
                logger.debug(f"not collecting, next collection..")
                self.next_collection()
            return

        # logger.debug(f"dataref changed {dataref.path}")

        if not self.is_collecting():
            logger.debug(f"not collecting")
            return

        if self.current_collection.did_not_progress():
            logger.debug(f"current collection {self.current_collection.name} did not progress, next collection..")
            self.next_collection()
        # else:
        #     logger.debug(f"keep collecting..")

    def is_collecting(self) -> bool:
        if self.current_collection is not None:
            # logger.debug(f"currently collecting {self.current_collection.name} since {self.current_collection.last_loaded.strftime('%H:%M:%S')})")
            return True
        return False

    def needs_collecting(self):
        nc = list(filter(lambda x: x.needs_collecting(), self.collections.values()))
        nc = sorted(nc, key=lambda x: x.nice(), reverse=True)
        logger.debug(f"needs_collecting: {[(c.name, c.nice()) for c in nc]}")
        return nc

    def nice_all(self, cl):
        for c in cl:
            c.upnice()

    def next_collection(self):
        needs_collecting = self.needs_collecting()
        if len(needs_collecting) > 0:
            if self.is_collecting():
                logger.debug(f"unloading {self.current_collection.name}")
                self.current_collection.unload()
                self.current_collection = None
            else:
                logger.debug(f"was not collecting")
            self.current_collection = needs_collecting[0]
            if len(needs_collecting) > 1:
                self.nice_all(needs_collecting[1:])
            # self.current_collection = random.choices(needs_collecting, weights=[x.nice() for x in needs_collecting])[0]  # choices returns a list()
            self.current_collection.load()
            if self.current_collection is not None:  # race condition
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
