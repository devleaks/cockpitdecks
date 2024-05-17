import sys
import os
import glob
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))  # we assume we're in subdir "bin/"

from cockpitdecks import __NAME__, __version__, __COPYRIGHT__, FORMAT, COCKPITDECKS_HOST
from cockpitdecks.decks.resources.virtualdeckui import VirtualDeckManagerUI


logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger(__name__)


ac = sys.argv[1] if len(sys.argv) > 1 else None
ac_desc = os.path.basename(ac) if ac is not None else "(no aircraft folder)"
d = None


try:
    logger.info(f"{__NAME__.title()} {__version__} {__COPYRIGHT__}")
    logger.info(f"Starting for {ac_desc}..")
    logger.info(f"..searching for virtual decks and initializing them (this may take a few seconds)..")
    decks = VirtualDeckManagerUI.enumerate(acpath=ac, cdip=COCKPITDECKS_HOST)
    logger.info(f"..running..")
    VirtualDeckManagerUI.run()
    logger.info(f"..virtual decks for {ac_desc} terminated.")
except KeyboardInterrupt:
    logger.warning("terminating virtual decks (please wait)..")
    VirtualDeckManagerUI.terminate()
    logger.info(f"..virtual decks for {ac_desc} terminated.")
