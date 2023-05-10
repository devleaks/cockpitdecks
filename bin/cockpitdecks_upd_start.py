import os
import logging
import sys
import time
import itertools
import threading

sys.path.append(os.path.join(os.path.dirname(__file__), '..')) # we assume we're in subdir "bin/"
from cockpitdecks import Cockpit, __NAME__, __version__, __COPYRIGHT__

# logging.basicConfig(level=logging.DEBUG, filename="streamdecks.log", filemode='a')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ac = sys.argv[1] if len(sys.argv) > 1 else None
ac_desc = os.path.basename(ac) if ac is not None else "(no aircraft folder)"
s = None
try:
    logger.info(f"{__NAME__.title()} {__version__} {__COPYRIGHT__}")
    logger.info(f"Starting for {ac_desc}..")
    logger.info(f"..searching for decks and initializing them (this may take a few seconds)..")
    s = Cockpit()
    s.start_aircraft(ac)
    logger.info(f"..{ac_desc} terminated.")
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
    if s is not None:
        s.terminate_all(2)
    logger.info(f"..{ac_desc} terminated.")
