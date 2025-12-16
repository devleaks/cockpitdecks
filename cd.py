"""Load Cockpitdecks normally for operations other than using it
"""
import sys
import platform
import os
import logging
import argparse
import subprocess
import threading

from enum import Enum

from cockpitdecks import __NAME__, __version__, __COPYRIGHT__, __DESCRIPTION__, Config, LOGFILE, FORMAT
from cockpitdecks.constant import CONFIG_FOLDER, ENVIRON_KW, yaml
from cockpitdecks.cockpitdecks_loader import CockpitdecksLoader


logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt="%H:%M:%S")

logger = logging.getLogger(__name__)
if LOGFILE is not None:
    formatter = logging.Formatter(FORMAT)
    handler = logging.FileHandler(LOGFILE, mode="a")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

startup_logger = logging.getLogger("Cockpitdecks startup")


class CD_MODE(Enum):
    NORMAL = 0
    DEMO = 1
    FIXED = 2


def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ.get("PATH", "").split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def xplane_homes(dirlist: str = "x-plane_install_12.txt") -> str:
    """
    retuns a list of X-Plane installation directories
    dir1
    dir2
    """
    opsys = platform.system()
    homes = ""

    if opsys == "Darwin":
        fn = os.path.join(os.environ["HOME"], "Library", "Preferences", dirlist)
        if os.path.exists(fn):
            with open(fn) as fp:
                homes = fp.read()
        else:
            startup_logger.info(f"x-plane installations: {fn} not found")
    elif opsys == "Linux":
        fn = os.path.join(os.environ["HOME"], ".x-plane", dirlist)
        if os.path.exists(fn):
            with open(fn) as fp:
                homes = fp.read()
        else:
            startup_logger.info(f"x-plane installations: {fn} not found")
    elif opsys == "Windows":
        fn = os.path.join(os.environ["HOME"], "AppData", "Local", dirlist)
        if os.path.exists(fn):
            with open(fn) as fp:
                homes = fp.read()
        else:
            startup_logger.info(f"x-plane installations: {fn} not found")

    if homes != "":
        homes = ",".join(homes.split("\n"))

    return homes.strip(",")  # for extra \n in file


def add_env(env, paths):
    return ":".join(set(env.split(":") + paths)).strip(":")


# ######################################################################################################
# COCKPITDECKS STARTS HERE
#
# DESC = "Elgato Stream Decks, Loupedeck decks, Berhinger X-Touch Mini, and web decks to X-Plane 12.1+"
DESC = __DESCRIPTION__

# Default values for demo
DEMO_HOME = os.path.join(os.path.dirname(__file__), "resources", "demo")
AIRCRAFT_HOME = DEMO_HOME
AIRCRAFT_DESC = "Cockpitdecks Demo"

# Used values for startup
SIMULATOR_NAME = None
SIMULATOR_HOME = None

# Command-line arguments
#
parser = argparse.ArgumentParser(description="Load Cockpitdecks extension and files")
parser.add_argument("--version", action="store_true", help="show version information and exit")
parser.add_argument("-v", "--verbose", action="store_true", help="show startup information")
parser.add_argument("-p", "--packages", nargs="+", help="lookup and load additional packages")
parser.add_argument("aircraft_folder", metavar="aircraft_folder", type=str, nargs="?", help="aircraft folder to load")

args = parser.parse_args()

if args.verbose:
    startup_logger.setLevel(logging.DEBUG)
    startup_logger.debug(f"{os.path.basename(sys.argv[0])} {__version__} configuring startup..")
    # startup_logger.debug(args)
else:
    startup_logger.info(f"python {sys.version[0:sys.version.index(' ')]}, {os.path.basename(sys.argv[0])} {__version__}")

# Run git if available to collect info
#
last_commit = ""
project_url = ""
last_commit_hash = ""
git = which("git")
if os.path.exists(".git") and git is not None:
    process = subprocess.Popen([git, "show", "-s", "--format=%ci"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    last_commit = "." + stdout.decode("utf-8")[:10].replace("-", "")
    process = subprocess.Popen([git, "remote", "get-url", "origin"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    project_url = stdout.decode("utf-8")[:-1]
    process = subprocess.Popen([git, "log", "-n", "1", '--pretty=format:"%H"'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    last_commit_hash = stdout.decode("utf-8")[1:8]

# #########################################@
# Show version (and exits)
#
if args.version:
    if git is not None:
        # copyrights = f"{__NAME__.title()} {__version__}{last_commit} {project_url}\n{__COPYRIGHT__}\n{DESC}\n"
        version = f"{os.path.basename(sys.argv[0])} ({project_url}) version {__version__} ({last_commit_hash})"
        startup_logger.info(version)
    else:
        startup_logger.warning("git not available")
    sys.exit(0)

# #########################################@
# Load Environment File if any, tries default one as well.
# Loads environment to know which flight simulator and where to locate it.
#
environment = Config(filename=None)  # create default env to host values

# Debug
#
debug_mode = environment.get(ENVIRON_KW.DEBUG.value, "info").lower()
if debug_mode == "debug":
    logging.basicConfig(level=logging.DEBUG)
elif debug_mode == "warning":
    logging.basicConfig(level=logging.WARNING)
elif debug_mode != "info":
    debug_mode = "info"
    startup_logger.warning(f"invalid debug mode {debug_mode}, using info")
startup_logger.debug(f"Cockpitdecks debug set to {debug_mode}")

environment.verbose = args.verbose
environment.debug = debug_mode

# #########################################@
# Simulator and software home directory
#
# Simulator name
#
# First try operating system environment:
SIMULATOR_NAME = os.getenv(ENVIRON_KW.SIMULATOR_NAME.value)
if SIMULATOR_NAME is None:
    startup_logger.debug("no simulator in os env")

# Second try environment file:
if SIMULATOR_NAME is None:
    if environment.from_filename():  # we loaded an environment
        SIMULATOR_NAME = environment.get(ENVIRON_KW.SIMULATOR_NAME.value)
        if SIMULATOR_NAME is None:
            startup_logger.debug("no simulator in environment file")

# Third: try x-plane installation file (os dependent):
if SIMULATOR_NAME is None:
    xp_homes = xplane_homes()  # os dependent
    if xp_homes != "":
        xp_homes = xp_homes.split(",")
        if len(xp_homes) == 1:
            SIMULATOR_NAME = "X-Plane"
            SIMULATOR_HOME = xp_homes[0]
            startup_logger.debug(f"found {SIMULATOR_NAME} in {SIMULATOR_HOME} from X-Plane installations file")
        elif len(xp_homes) > 1:
            SIMULATOR_NAME = "X-Plane"
            startup_logger.warning("multiple X-Plane installations found")
        else:
            startup_logger.warning(f"X-Plane simulator installation file contains {xp_homes}, but no SIMULATOR_HOME identified; please specify SIMULATOR_HOME")
    else:
        startup_logger.warning("X-Plane simulator installation file not found or empty")


if SIMULATOR_NAME is None:
    startup_logger.warning("no simulator name")
    sys.exit(1)

# Summary:
if SIMULATOR_NAME is not None:
    environment[ENVIRON_KW.SIMULATOR_NAME.value] = SIMULATOR_NAME
startup_logger.debug(f"Simulator is {SIMULATOR_NAME}")

#
# Simulator software home directory if local:
if SIMULATOR_HOME is None:
    SIMULATOR_HOME = os.getenv(ENVIRON_KW.SIMULATOR_HOME.value)
    # Then environment
    if SIMULATOR_HOME is None:
        startup_logger.debug("no simulator home in os env")

if SIMULATOR_HOME is None:
    SIMULATOR_HOME = environment.get(ENVIRON_KW.SIMULATOR_HOME.value)
    if SIMULATOR_HOME is None:
        startup_logger.debug("no simulator home in environment file")


# Check SIMULATOR_HOME
if SIMULATOR_HOME is not None:
    SIMULATOR_HOME = SIMULATOR_HOME.rstrip(os.sep)
    if not os.path.exists(SIMULATOR_HOME) or not os.path.isdir(SIMULATOR_HOME):  # if defined, must exist.
        startup_logger.warning(f"{SIMULATOR_NAME} not found in {SIMULATOR_HOME}")
        SIMULATOR_HOME = None
        sys.exit(1)
    else:
        environment[ENVIRON_KW.SIMULATOR_HOME.value] = SIMULATOR_HOME
        startup_logger.debug(f"{SIMULATOR_NAME} found in {SIMULATOR_HOME}")
        # while we are at it...
        # plugin_location = os.path.join(SIMULATOR_HOME, "Resources", "plugins", "PythonPlugins", "PI_cockpitdecks.py")
        # if os.path.exists(plugin_location):
        #     startup_logger.debug(f"PI_cockpitdecks plugin found in {plugin_location}")
        # else:
        #     startup_logger.warning(f"PI_cockpitdecks plugin not found in {plugin_location}")


#
if not environment.is_valid():
    startup_logger.error("Cockpitdecks has no environment or environment is not valid")
    sys.exit(1)

# Extension packages
if args.packages is not None:
    if ENVIRON_KW.COCKPITDECKS_EXTENSION_PATH.value not in environment:
        environment[ENVIRON_KW.COCKPITDECKS_EXTENSION_PATH.value] = args.packages
    else:
        environment[ENVIRON_KW.COCKPITDECKS_EXTENSION_PATH.value] = environment[ENVIRON_KW.COCKPITDECKS_EXTENSION_PATH.value] + args.packages
    startup_logger.info(f"added packages {", ".join(args.packages)}")

# COCKPITDECKS_PATH
#
# Strats from environment
COCKPITDECKS_PATH = os.getenv(ENVIRON_KW.COCKPITDECKS_PATH.value, "")

# Append from environment file
ENV_PATH = environment.get(ENVIRON_KW.COCKPITDECKS_PATH.value)
if ENV_PATH is not None:
    COCKPITDECKS_PATH = add_env(COCKPITDECKS_PATH, ENV_PATH)

# Append X-Plane regular aircraft paths
AIRCRAFT_FOLDERS = ["Laminar Research", "Extra Aircraft", "Airbus"]

if SIMULATOR_HOME is not None and SIMULATOR_NAME == "X-Plane":
    COCKPITDECKS_PATH = add_env(COCKPITDECKS_PATH, [os.path.join(SIMULATOR_HOME, "Aircraft", d) for d in AIRCRAFT_FOLDERS])

environment[ENVIRON_KW.COCKPITDECKS_PATH.value] = COCKPITDECKS_PATH

startup_logger.debug(f"{ENVIRON_KW.COCKPITDECKS_PATH.value}={COCKPITDECKS_PATH}")


# Start-up Mode
#
mode = CD_MODE.NORMAL
environment[ENVIRON_KW.MODE.value] = mode

ac = args.aircraft_folder

if ac is not None:
    target_dir = os.path.abspath(os.path.join(os.getcwd(), ac))
    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        startup_logger.error(f"{target_dir} directory not found")
        sys.exit(1)
    test_dir = os.path.join(target_dir, CONFIG_FOLDER)
    if not os.path.exists(test_dir) or not os.path.isdir(test_dir):
        startup_logger.error(f"{target_dir} directory does not contain {CONFIG_FOLDER} directory")
        sys.exit(1)
    AIRCRAFT_HOME = os.path.abspath(os.path.join(os.getcwd(), ac))
    AIRCRAFT_DESC = os.path.basename(ac)
    mode = CD_MODE.NORMAL
    startup_logger.debug(f"starting aircraft folder {AIRCRAFT_HOME}, {'fixed' if mode.value > 0 else 'dynamically adjusted to aircraft'}")
elif ac is None:
    if SIMULATOR_HOME is None and len(COCKPITDECKS_PATH) == 0:
        mode = CD_MODE.DEMO
        startup_logger.debug(f"no aircraft, no {SIMULATOR_NAME} on this host, COCKPITDECKS_PATH not defined: starting in demonstration mode")

startup_logger.debug(f"environment: {environment.store}")
startup_logger.debug(f"cockpitdecks {mode}")
startup_logger.debug(f"..Cockpitdecks configured.\n")
#
# COCKPITDECKS STARTS HERE, REALLY
#
copyrights = f"{__NAME__.title()} {__version__}{last_commit} {__COPYRIGHT__}\n{DESC}\n"
print(copyrights)
logger.info("Initializing CockpitdecksLoader..")
cockpit = CockpitdecksLoader(environ=environment)
logger.info("..initialized\n")


# ##################################
# MAIN
#
# Wrapped in main function to make it accessible
# from builder/installer
#
def main():
    logger.info(f"Loading {AIRCRAFT_DESC}..")
    cockpit.load_aircraft(acpath=args.aircraft_folder)
    logger.info(f"..{AIRCRAFT_DESC} loaded")
    logger.info("stopping decks..")
    cockpit.terminate_devices()
    logger.info("..decks stopped")

    # os._exit(0)

# Run if unwrapped
if __name__ == "__main__":
    main()
