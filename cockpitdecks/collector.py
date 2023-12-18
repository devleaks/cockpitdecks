import logging
from queue import Empty
import psutil
import time
import itertools
import threading
import traceback

from abc import ABC, abstractmethod
from datetime import timedelta
from queue import Queue

from cockpitdecks import SPAM_LEVEL
from cockpitdecks.simulator import Dataref, DatarefListener

loggerDatarefSet = logging.getLogger("DatarefSet")
# loggerDatarefSet.setLevel(SPAM_LEVEL)
# loggerDatarefSet.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
logger.setLevel(logging.DEBUG)

QUEUE_TIMEOUT = 5  # seconds, we check on loop running every that time
LOOP_DELAY = 5.0

MAX_COLLECTION_SIZE = 40  # absolute mark, no more datarefs than that per collection
DEFAULT_COLLECTION_EXPIRATION = 300  # secs, five minutes
DEFAULT_COLLECTION_COLLECT_TIME = 10
PACE_LOAD = 0.5  # secs, little pacing delay after enqueueing numerous drefs
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

    def __init__(self, datarefs, name: str, sim, expire: int = DEFAULT_COLLECTION_EXPIRATION, collect_time: int = DEFAULT_COLLECTION_COLLECT_TIME):
        DatarefListener.__init__(self)
        self.sim = sim
        self.name = name
        self.is_loaded = False

        self.datarefs = datarefs  # { path: Dataref() }
        if len(self.datarefs) > MAX_COLLECTION_SIZE:
            loggerDatarefSet.warning(f"collection larger than {MAX_COLLECTION_SIZE}, *** not all datarefs will be collected ***")
            self.datarefs = dict(itertools.islice(self.datarefs.items(), 0, MAX_COLLECTION_SIZE))
        self.expire = expire  # seconds

        self.collect_time = collect_time  # time a collection will remain on collector before it is declared not progressing
        self._collected = threading.Event()

        for d in self.datarefs.values():
            d.add_listener(self)

        # Working variables
        self.listeners = []
        self.last_loaded = None
        self.last_unloaded = None
        self.last_completed = None
        self.last_completion_status = self.is_completed()
        self._nice = 1  # I <3 Unix.
        self._enqueued = False
        self.instances = 0

    def set_expiration(self, expire):
        if expire is not None:
            self.expire = expire

    def set_collect_time(self, collect_time):
        if collect_time is not None:
            self.collect_time = collect_time

    def set_set_dataref(self, dref):
        if dref is not None:
            self.set_dataref = dref

    # Getting set values
    #
    def get_dataref_value(self, dataref, default=None):
        d = self.datarefs.get(dataref)
        if d is None:
            loggerDatarefSet.warning(f"collection {self.name}: dataref {dataref} not found")
            return None
        return d.current_value if d.current_value is not None else default

    def as_string(self) -> str:
        """returns all datarefs in collection as string (char(dataref float value))"""
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
        """returns all datarefs in collection as list"""
        return [d.current_value for d in self.datarefs.values()]

    # Receiving events
    #
    def dataref_changed(self, dataref: "Dataref"):
        """Called when dataref VALUE has changed"""
        # loggerDatarefSet.debug(f"dataref changed {dataref.path}")
        self.notify_changed()
        if self.is_completed():
            loggerDatarefSet.debug(f"collection {self.name} completed")
            self.last_completed = self.sim.datetime()
            self.notify_completed()
            self.release()
        else:
            loggerDatarefSet.debug(f"collection {self.name}")

    def dataref_updated(self, dataref: "Dataref"):
        """Called when dataref has been updated but may be with no change"""
        last_completed = self.is_completed()
        # loggerDatarefSet.debug(f"status change {last_completed} vs {self.last_completion_status}")
        if last_completed and not self.last_completion_status:  # if was not completed and is now complete
            self.last_completion_status = last_completed
            loggerDatarefSet.debug(f"collection {self.name} completed")
            self.release()
        self.last_completed = self.sim.datetime()

    # Generating events
    # (note: there is no different list for changed/updated)
    #
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

    # Utility functions
    #
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

    def is_completed(self) -> bool:
        if self.last_loaded is None:
            loggerDatarefSet.debug(f"collection {self.name} never loaded")
            return False
        if self.last_completed is not None and self.last_completed + timedelta(seconds=self.expire) < self.sim.datetime():
            loggerDatarefSet.debug(f"collection {self.name} expired")
            return False
        for d in self.datarefs.values():
            if d.current_value is None or d._last_updated is None:
                loggerDatarefSet.debug(f"collection {self.name} has {d.path} with no value, not fully collected")
                return False
            if d._last_updated < self.last_loaded:
                # loggerDatarefSet.debug(f"{self.name}: {d.path}: {d._last_updated} < {self.last_loaded}")
                loggerDatarefSet.debug(f"collection {self.name} has {d.path} expired, not fully collected")
                return False
            # loggerDatarefSet.debug(f"{self.name}: {d.path}: {d._last_updated}")
        # loggerDatarefSet.debug(f"{self.name} fully collected")
        return True

    def show_acquired_status(self):
        """Reports how many datarefs and their statuses"""
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
        return not self.is_completed() and not self._enqueued

    # Collectting...
    #
    def load(self):
        self.sim.add_datarefs_to_monitor(self.datarefs)
        self.is_loaded = True
        self.last_loaded = self.sim.datetime()
        loggerDatarefSet.info(f"collection {self.name} loaded")  #  {self.datarefs.keys()}
        self.show_acquired_status()
        time.sleep(PACE_LOAD)

    def unload(self):
        self.sim.remove_datarefs_to_monitor(self.datarefs)
        self.is_loaded = False
        self.last_unloaded = self.sim.datetime()
        loggerDatarefSet.log(SPAM_LEVEL, f"collection {self.name} unloaded")
        self.show_acquired_status()
        time.sleep(PACE_UNLOAD)

    def enqueue(self, queue):
        if not self._enqueued:  # should not enqueue if event set as well
            self._enqueued = True
            queue.put(self)
            loggerDatarefSet.debug(f"collection {self.name}: enqueued")
        # else:
        #     loggerDatarefSet.debug(f"collection {self.name}: already enqueued")

    def dequeued(self):
        if not self._enqueued:
            loggerDatarefSet.warning(f"collection {self.name}: was not enqueued")
        self._enqueued = False
        loggerDatarefSet.debug(f"collection {self.name}: dequeued")

    def collect(self):
        loggerDatarefSet.debug(f"collection {self.name}: collecting {self.collect_time} secs.")
        self.last_completion_status = False
        self._collected.clear()
        ret = self._collected.wait(self.collect_time)
        loggerDatarefSet.debug(f"collection {self.name}: time up! ({ret})")
        return ret

    def release(self):
        if not self._collected.is_set():
            loggerDatarefSet.debug(f"collection {self.name}: setting event")
            self._collected.set()


class DatarefSetCollector:
    # Class that collects collection of datarefs one at a time to limit the request pressure on the simulator.
    #
    def __init__(self, simulator):
        self.sim = simulator
        self.name = type(self).__name__
        self.collections = {}
        self.current_collection = None
        self.last_changed = self.sim.datetime()
        self.candidates = Queue()
        self.collector_must_stop = None
        self.thread = None

        self.init()

    def init(self):
        self.start()

    def add_collection(self, collection: DatarefSet, start: bool = True):
        if collection.name in self.collections.keys():
            collection.instances = collection.instances + 1
            logger.debug(f"collection {collection.name} additional registered")
        else:
            self.collections[collection.name] = collection
            logger.debug(f"collection {collection.name} added")
        if start and collection.needs_collecting():
            collection.enqueue(self.candidates)

    def remove_collection(self, collection: DatarefSet, start: bool = True):
        if collection.name not in self.collections.keys():
            return
        need_next = False
        if self.is_collecting(specific_collection=collection):
            self.stop_collecting()
        if collection.instances <= 0:
            collection._enqueued = False  # silently prevent it from enqueuing again
            del self.collections[collection.name]
            logger.debug(f"collection {collection.name} removed")
        else:
            logger.debug(f"collection {collection.name} still used ({collection.instances})")
        if start and need_next:
            self.enqueue_collections()

    def remove_all_collections(self):
        self.stop_collecting()
        cl = list(self.collections.keys())
        for c in cl:
            del self.collections[c]
        self.collections = {}

    def get_dataref_value_from_collection(self, dataref, collection, default=None):
        c = self.collections.get(collection)
        if c is None:
            logger.warning(f"collection {collection} not found for dataref {dataref}")
            return default  # changed, we do never return None
        return c.get_dataref_value(dataref=dataref, default=default)

    # Utilities
    #
    def is_collecting(self, specific_collection=None) -> bool:
        if specific_collection is None:
            return self.current_collection is not None
        if self.current_collection is None:
            return False
        return self.current_collection.name == specific_collection.name

    def run(self):
        if len(self.collections) == 0:
            if self.collector_must_stop is not None:
                logger.debug(f"no collection, stopping")
                self.stop()
        else:
            if self.collector_must_stop is None:
                logger.debug(f"collections to collect, starting")
                self.start()

    # Action
    #
    def collect(self, collection):
        if not self.sim.connected:
            logger.debug(f"not connected")
            return
        if self.current_collection is None:
            self.current_collection = collection
            self.current_collection.load()
            return True
        if self.current_collection != collection:
            if not self.current_collection.is_completed():  # enqueue it for later completion
                self.current_collection.enqueue(self.candidates)
            self.current_collection.unload()
            self.current_collection = collection
            self.current_collection.load()
            return True
        logger.debug(f"..collecting..")
        return False  # no new collection loaded

    def stop_collecting(self, release: bool = True):
        if not self.sim.connected:
            logger.debug(f"not connected")
            return
        if self.is_collecting():
            currcoll = self.current_collection
            self.current_collection.unload()
            self.current_collection = None
            if release:
                currcoll.release()

    def enqueue_collections(self):
        if not self.sim.connected:
            logger.debug(f"not connected")
            return
        nc = list(filter(lambda x: x.needs_collecting(), self.collections.values()))
        nc = sorted(nc, key=lambda x: x.nice(), reverse=True)
        logger.debug(f"needs_collecting: {[(c.name, c.nice()) for c in nc]}")
        for collection in nc:
            collection.enqueue(self.candidates)
            self.last_changed = self.sim.datetime()
        # important note: enqueue_collection is called after adding or removing dataref sets
        self.run()  # just check it has to run, or stop

    def clear_queue(self):
        while not self.candidates.empty():
            try:
                self.candidates.get(block=False)
            except Empty:
                continue

    def loop(self):
        loop_count = 0
        change_count = 0
        logger.debug("Collector loop started..")
        while not self.collector_must_stop.is_set():
            loop_count = loop_count + 1
            self.enqueue_collections()
            try:
                next_collection = self.candidates.get(timeout=QUEUE_TIMEOUT)
                next_collection.dequeued()
                if next_collection.name in self.collections.keys():
                    if self.collect(next_collection):
                        change_count = change_count + 1
                    if not next_collection.collect():
                        if not next_collection.is_completed():
                            if next_collection.name in self.collections.keys():
                                logger.debug(f"collection {next_collection.name} did not complete, rescheduling")
                                next_collection.enqueue(self.candidates)
                            else:
                                logger.debug(f"collection {next_collection.name} did not complete, no longer need collecting")
                        else:
                            self.stop_collecting(release=False)
                            logger.debug(f"collection {next_collection.name} is complete, no longer collecting")
                    else:
                        logger.debug(f"collection {next_collection.name} completed")
                        self.stop_collecting(release=False)
                else:
                    logger.debug(f"collection {next_collection.name} no longer collectable")
            except Empty:
                logger.debug(f"queue is empty")
            logger.info(
                f"uptime: {psutil.cpu_percent()}, {', '.join([f'{l:4.1f}' for l in psutil.getloadavg()])} ({self.candidates.qsize()} in queue), {self.collector_must_stop.is_set()}"
            )
            time.sleep(LOOP_DELAY)  # this is to give a chance to other thread to run...
        self.collector_must_stop = None
        logger.debug(f"..Collector loop terminated")

    def start(self):
        if not self.sim.connected:
            logger.warning(f"not connected, not starting")
            return
        if self.thread is not None:
            logger.debug("Collector already running.")
            return
        logger.debug("starting..")
        self.collector_must_stop = threading.Event()
        self.thread = threading.Thread(target=self.loop)
        self.thread.name = "Collector::loop"
        self.thread.start()
        logger.info("Collector started")

    def stop(self, clear_queue: bool = False):
        if self.thread is None:
            logger.debug("Collector not running")
            return
        logger.debug("stopping..")
        self.collector_must_stop.set()
        logger.debug(f"..asked Collector to stop (this may take {QUEUE_TIMEOUT} secs.)..")
        self.stop_collecting()
        logger.debug("..joining..")
        self.thread.join(timeout=QUEUE_TIMEOUT)  # this never blocks... why? may be it is called from itself ("sucide")??
        if self.thread.is_alive():
            logger.warning("..thread may hang..")
        else:
            logger.debug("..joined..")
        time.sleep(QUEUE_TIMEOUT * 2)  # this allow for the thread to terminate safely.
        self.thread = None
        logger.debug("..no more thread..")
        if clear_queue:
            logger.debug("..clearing queue..")
            self.clear_queue()
        logger.debug("..stopped")
        logger.info("Collector stopped")

    def terminate(self):
        traceback.print_stack()
        logger.debug("terminating Collector..")
        logger.debug("..clearing queue..")
        self.clear_queue()
        logger.debug("..removing all collections..")
        self.remove_all_collections()
        logger.debug("..stopping..")
        self.stop()
        logger.debug("..terminated")
