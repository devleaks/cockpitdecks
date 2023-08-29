import os
import logging
import sys
import time
import itertools
import threading
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))  # we assume we're in subdir "bin/"

from cockpitdecks import __COPYRIGHT__, FORMAT
from cockpitdecks.simulator import DatarefListener, Dataref
from cockpitdecks import CockpitBase, XPlane

# logging.basicConfig(level=logging.DEBUG, filename="cockpitdecks.log", filemode='a')
LOGFILE = "dataref_fetcher.txt"
__version__ = "0.0.1"
logging.basicConfig(level=logging.INFO, format=FORMAT)


class DatarefFetcher(DatarefListener, CockpitBase):
    """Dummy
    """
    def __init__(self, simulator):
        self.sim = simulator(self)
        CockpitBase.__init__(self)
        DatarefListener.__init__(self)

    def set_logging_level(self, name):
        pass

    def reload_pages(self):
        logger.debug(f"reloading pages..")
        self.sim.clean_datarefs_to_monitor()
        self.fetch_datarefs()
        self.sim.add_all_datarefs_to_monitor()

    def dataref_changed(self, dataref):
        if dataref.previous_value is None and dataref.current_value is not None:
            print(f"{dataref.path} get initial value: {dataref.current_value}")
            return  # got initial value, do not report it...
        print(f"{datetime.now().strftime('%H:%M:%S.%f')} {dataref.path} changed: {dataref.previous_value} -> {dataref.current_value}")

    def fetch_datarefs(self):
        coll = {}
        for d in ["sim/cockpit2/clock_timer/zulu_time_seconds", "sim/cockpit2/clock_timer/zulu_time_minutes"]:
            dref = self.sim.get_dataref(d)
            dref.add_listener(self)
            coll[d] = dref
        self.sim.add_datarefs_to_monitor(coll)

    def run(self):
        # Start reload loop
        logger.info(f"starting..")
        self.sim.connect()
        logger.info(f"{len(threading.enumerate())} threads")
        logger.info(f"{[t.name for t in threading.enumerate()]}")
        logger.info("..started")
        for t in threading.enumerate():
            try:
                t.join()
            except RuntimeError:
                pass
        logger.info("terminated")

    def terminate_all(self):
        if self.sim is not None:
            logger.info("..terminating connection to simulator..")
            self.sim.terminate()
            logger.debug("..deleting connection to simulator..")
            del self.sim
            self.sim = None
            logger.debug("..connection to simulator deleted..")


logger = logging.getLogger(__name__)
if LOGFILE is not None:
    formatter = logging.Formatter(FORMAT)
    handler = logging.FileHandler(
        LOGFILE, mode="a"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

xp = None
try:
    logger.info(f"{'Dataref Fetcher'.title()} {__version__} {__COPYRIGHT__}")
    logger.info("Fetching datarefs until interrupt..")
    df = DatarefFetcher(XPlane)
    df.fetch_datarefs()
    df.run()
    logger.info("..interrupted.")
except KeyboardInterrupt:
    def spin():
        spinners = ["|", "/", "-", "\\"]
        for c in itertools.cycle(spinners):
            print(f"\r{c}", end="")
            time.sleep(0.1)
    logger.warning("terminating (please wait)..")
    thread = threading.Thread(target=spin)
    thread.daemon = True
    thread.name = "spinner"
    thread.start()
    if df is not None:
        df.terminate_all()
    logger.info("..dataref fetcher terminated.")
