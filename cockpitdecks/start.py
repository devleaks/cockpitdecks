"""Main startup script for Cockpitdecks

Starts up Cockpitdecks. Process command line arguments, load Cockpitdecks with proper simulator.
Starts listening to events from both simulator and decks connected to the computer.
Starts web server to serve web decks, designer, and button editor.
Starts WebSocket listener to collect events from web decks.

Press CTRL-C ** once ** to gracefully stop Cockpitdecks. Be patient.
"""

import sys
import platform
import os
import logging
import time
import itertools
import threading
import json
import urllib.parse
import argparse
import subprocess
import shutil

# import filecmp
import socket
import ipaddress

from enum import Enum

from flask import Flask, render_template, send_from_directory, send_file, request, abort
from simple_websocket import Server, ConnectionClosed

import ruamel
from ruamel.yaml import YAML

from cockpitdecks import Cockpit, __NAME__, __version__, __COPYRIGHT__, __DESCRIPTION__, Config

from cockpitdecks.constant import CONFIG_FOLDER, RESOURCES_FOLDER
from cockpitdecks.constant import ENVIRON_KW, CONFIG_KW, DECK_KW, DECKS_FOLDER, DECK_TYPES, TEMPLATE_FOLDER, ASSET_FOLDER
from cockpitdecks.aircraft import DECK_TYPE_DESCRIPTION


ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
yaml = YAML(typ="safe", pure=True)
yaml.default_flow_style = False


# logging.basicConfig(level=logging.DEBUG, filename="cockpitdecks.log", filemode="a")
LOGFILE = "cockpitdecks.log"
FORMAT = "[%(asctime)s] %(levelname)s %(threadName)s %(filename)s:%(funcName)s:%(lineno)d: %(message)s"

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


#
# Utility functions
def my_ip() -> str | set:
    x = set([address[4][0] for address in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)])
    return list(x)[0] if len(x) == 1 else x


def get_ip(s) -> str:
    c = s[0]
    if c in "0123456789":
        return ipaddress.ip_address(s)
    else:
        return ipaddress.ip_address(socket.gethostbyname(s))


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
SIMULATOR_HOST = None

# Command-line arguments
#
parser = argparse.ArgumentParser(description="Start Cockpitdecks")
parser.add_argument("--version", action="store_true", help="show version information and exit")
parser.add_argument("-d", "--demo", action="store_true", help="start demo mode")
parser.add_argument("-e", "--env", metavar="environ_file", type=str, nargs=1, help="start with alternate environment file")
parser.add_argument(
    "--template", metavar="template_file", type=str, nargs=1, help="create deckconfig and add template files to start in supplied aircraft folder"
)
parser.add_argument("-f", "--fixed", action="store_true", help="does not automatically switch aircraft")
parser.add_argument("-v", "--verbose", action="store_true", help="show startup information")
# parser.add_argument("--install-plugin", action="store_true", help="install Cockpitdecks plugin in X-Plane/XPPython3")
parser.add_argument("aircraft_folder", metavar="aircraft_folder", type=str, nargs="?", help="aircraft folder for non automatic start")

args = parser.parse_args()

if args.verbose:
    startup_logger.setLevel(logging.DEBUG)
    startup_logger.debug(f"{os.path.basename(sys.argv[0])} {__version__} configuring startup..")
else:
    startup_logger.info(f"{os.path.basename(sys.argv[0])} {__version__}")

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
# Copy template files (and exits)
#
if args.template:
    tmpl_dir = args.template[0]
    tmpl_dest = os.path.join(tmpl_dir, CONFIG_FOLDER)
    tmpl_src = DEMO_HOME

    if not os.path.exists(tmpl_src):
        startup_logger.warning(f"could not locate templates in {tmpl_src}")
        sys.exit(1)
    if os.path.exists(tmpl_dest):
        startup_logger.warning(f"{tmpl_dir} already contains a {CONFIG_FOLDER}, cannot install templates")
        sys.exit(1)
    else:
        shutil.copytree(tmpl_src, tmpl_dest, dirs_exist_ok=False)
        startup_logger.info(f"templates installed in {tmpl_dest}")
    sys.exit(0)

# #########################################@
# Load Environment File if any, tries default one as well.
# Loads environment to know which flight simulator and where to locate it.
#
environment = Config(filename=None)  # create default env to host values

if args.env is not None:
    environ_file = args.env[0]
    if os.path.exists(environ_file):
        environment = Config(filename=os.path.abspath(environ_file))
        startup_logger.debug(f"Cockpitdecks loaded environment from file {environ_file}")
    else:
        startup_logger.warning(f"Cockpitdecks could not load environment from file {environ_file}")

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

# Demo
#
if args.demo:
    startup_logger.info("Cockpitdecks starting for demo")
    environment[ENVIRON_KW.SIMULATOR_NAME.value] = "NoSimulator"
    environment[ENVIRON_KW.APP_HOST.value] = ["127.0.0.1", 7777]

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
    if not args.demo:
        startup_logger.warning("no simulator name")
        sys.exit(1)
    else:
        SIMULATOR_NAME = "NoSimulator"
        startup_logger.info("simulator set to default for demo")

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

SIMULATOR_HOST = environment.get(ENVIRON_KW.SIMULATOR_HOST.value)
if SIMULATOR_HOST is not None:
    if SIMULATOR_HOME is None:
        startup_logger.debug(f"no SIMULATOR_HOME, assume remote installation at {ENVIRON_KW.SIMULATOR_HOST.value}={SIMULATOR_HOST}")
    else:
        startup_logger.warning(
            f"both software home directory ({SIMULATOR_HOME}) and remote host ({SIMULATOR_HOST}) provided; please make sure software location is consistent with Cockpitdecks (see manual)"
        )

# Check SIMULATOR_HOME
if SIMULATOR_HOME is not None:
    SIMULATOR_HOME = SIMULATOR_HOME.rstrip(os.sep)
    if not os.path.exists(SIMULATOR_HOME) or not os.path.isdir(SIMULATOR_HOME):  # if defined, must exist.
        startup_logger.warning(f"{SIMULATOR_NAME} not found in {SIMULATOR_HOME}")
        SIMULATOR_HOME = None
        if not args.demo:
            sys.exit(1)
    else:
        environment[ENVIRON_KW.SIMULATOR_HOME.value] = SIMULATOR_HOME
        startup_logger.debug(f"{SIMULATOR_NAME} found in {SIMULATOR_HOME}")
        # while we are at it...
        plugin_location = os.path.join(SIMULATOR_HOME, "Resources", "plugins", "PythonPlugins", "PI_cockpitdecks.py")
        if os.path.exists(plugin_location):
            startup_logger.debug(f"PI_cockpitdecks plugin found in {plugin_location}")
        else:
            startup_logger.warning(f"PI_cockpitdecks plugin not found in {plugin_location}")


# #########################################@
# Install plugin (and exits)
#
# if args.install_plugin:
#     if SIMULATOR_NAME != "X-Plane":
#         startup_logger.error(f"Cockpitdecks plugin is for X-Plane flight simulator only (simulator is {SIMULATOR_NAME})")
#         sys.exit(1)
#     startup_logger.info("installing Cockpitdecks plugin in XPPython3")
#     if SIMULATOR_HOME is None:
#         startup_logger.error("no simulator home directory, cannot install")
#         sys.exit(1)
#     dest = os.path.join(SIMULATOR_HOME, "Resources", "plugins", "PythonPlugins")
#     if not (os.path.exists(dest) and os.path.isdir(dest)):
#         startup_logger.error("no PythonPlugins directory, cannot install")
#         dest = os.path.join(SIMULATOR_HOME, "Resources", "plugins", "XPPython3")
#         if not (os.path.exists(dest) and os.path.isdir(dest)):
#             startup_logger.error("no XPPython3 directory, is XPPython3 installed?")
#             startup_logger.info("it can be downloaded from https://xppython3.readthedocs.io/")
#         sys.exit(1)
#     src = os.path.join(os.path.dirname(__file__), "resources", "xppython3-plugins", "PI_cockpitdecks.py")
#     src = os.path.abspath(src)
#     if not os.path.exists(src):
#         startup_logger.error(f"plugin file not found ({src})")
#         sys.exit(1)
#     dest2 = os.path.join(dest, "PI_cockpitdecks.py")
#     if os.path.exists(dest2):
#         startup_logger.warning(f"plugin file already exists ({dest2})")
#         if filecmp.cmp(src, dest2):
#             startup_logger.info("plugin files are the same")
#         else:
#             startup_logger.info("plugin files are the different")
#             if not args.fixed:
#                 startup_logger.info(f"remove existing file {dest2} first and run installation again to overwrite")
#                 # print(f"use --fixed to overwrite")
#         if not args.fixed:
#             sys.exit(1)
#         else:
#             startup_logger.warning("fixed. overwriting")
#     startup_logger.debug(f"copying {src} to {dest2}..")
#     shutil.copy(src, dest2)
#     startup_logger.debug("..copied")
#     startup_logger.info("plugin installed")
#     sys.exit(0)
#     # We do not do anthing else when installing the plugin, which should only occurs once
#     # or when the plugin is upgraded

#
if not environment.is_valid():
    if not args.demo:
        startup_logger.error("Cockpitdecks has no environment or environment is not valid")
        sys.exit(1)

# COCKPITDECKS_PATH
#
# Strats from environment
COCKPITDECKS_PATH = os.getenv(ENVIRON_KW.COCKPITDECKS_PATH.value, "")

# Append from environment file
ENV_PATH = environment.get(ENVIRON_KW.COCKPITDECKS_PATH.value)
if ENV_PATH is not None:
    COCKPITDECKS_PATH = add_env(COCKPITDECKS_PATH, ENV_PATH)

# Append X-Plane regular aircraft paths
if SIMULATOR_HOME is not None and SIMULATOR_NAME == "X-Plane":
    COCKPITDECKS_PATH = add_env(
        COCKPITDECKS_PATH, [os.path.join(SIMULATOR_HOME, "Aircraft", "Extra Aircraft"), os.path.join(SIMULATOR_HOME, "Aircraft", "Laminar Research")]
    )

environment[ENVIRON_KW.COCKPITDECKS_PATH.value] = COCKPITDECKS_PATH

startup_logger.debug(f"{ENVIRON_KW.COCKPITDECKS_PATH.value}={COCKPITDECKS_PATH}")

# Application environment variables
#
APP_HOST = os.getenv(ENVIRON_KW.APP_HOST.value)  # !! should only return a hostname
APP_PORT = 7777
if APP_HOST is not None:
    APP_PORT = os.getenv(ENVIRON_KW.APP_PORT.value, 7777)
    APP_HOST = [APP_HOST, APP_PORT]
else:  # from now on, APP_HOST = [hostname, port]
    APP_HOST = environment.get(ENVIRON_KW.APP_HOST.value, ["127.0.0.1", 7777])

if APP_HOST is not None:
    environment[ENVIRON_KW.APP_HOST.value] = APP_HOST

startup_logger.debug(f"Cockpitdecks application server at {APP_HOST}")

# X-Plane API guesses (same computer?)
#
# Here API_HOST = IP address, API_PORT = tcp port
API_HOST = os.getenv(ENVIRON_KW.API_HOST.value)
API_PORT = 8086
if API_HOST is not None and API_HOST != "":  # got from OS
    ip_app = get_ip(APP_HOST[0])
    ip_api = get_ip(API_HOST)
    DEFAULT_API_PORT = 8086 if ip_app == ip_api else 8080
    API_PORT = os.getenv(ENVIRON_KW.API_PORT.value, DEFAULT_API_PORT)
    if ip_app == ip_api:
        startup_logger.debug("X-Plane and Cockpidecks on same host computer")
    else:
        startup_logger.debug(f"X-Plane ({ip_api}) and Cockpidecks ({ip_app}) on different host computers")
else:
    API_HOST = environment.get(ENVIRON_KW.API_HOST.value, "127.0.0.1")
    API_PORT = environment.get(ENVIRON_KW.API_PORT.value, 8086)
    startup_logger.debug("X-Plane and Cockpidecks on same host computer")

# !! From now on, APP_HOST = [hostname, port]
#
if API_HOST is not None:
    environment[ENVIRON_KW.API_HOST.value] = [API_HOST, API_PORT]

startup_logger.debug(f"X-Plane API reachable at {API_HOST} if X-Plane version > 12.1")

# Start-up Mode
#
mode = CD_MODE.DEMO if args.demo else CD_MODE.NORMAL
environment[ENVIRON_KW.MODE.value] = mode

ac = args.aircraft_folder

if not args.demo:
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
        mode = CD_MODE.FIXED if args.fixed else CD_MODE.NORMAL
        startup_logger.debug(f"starting aircraft folder {AIRCRAFT_HOME}, {'fixed' if mode.value > 0 else 'dynamically adjusted to aircraft'}")
    elif ac is None:
        if args.fixed:
            startup_logger.error("non demo and fixed mode but no aircraft path")
            sys.exit(1)
        elif SIMULATOR_HOME is None and len(COCKPITDECKS_PATH) == 0:
            mode = CD_MODE.DEMO
            startup_logger.debug(f"no aircraft, no {SIMULATOR_NAME} on this host, COCKPITDECKS_PATH not defined: starting in demonstration mode")

startup_logger.debug(f"environment: {environment.store}")
startup_logger.debug(f"cockpitdecks {mode}")
startup_logger.debug(f"..Cockpitdecks configured startup. Let's {'try' if args.fixed else 'fly'}...\n")
#
# COCKPITDECKS STARTS HERE, REALLY
#
copyrights = f"{__NAME__.title()} {__version__}{last_commit} {__COPYRIGHT__}\n{DESC}\n"
print(copyrights)
logger.info("Initializing Cockpitdecks..")
cockpit = Cockpit(environ=environment)
logger.info("..initialized\n")


# ######################################################################################################
# Flask Web Server (& WebSocket Server)
#
# Serves decks and their assets.
# Proxy WebSockets to TCP Sockets
#
# Local key words and defaults
#
AIRCRAFT_ASSET_FOLDER = os.path.join(AIRCRAFT_HOME, CONFIG_FOLDER, RESOURCES_FOLDER)
AIRCRAFT_DECK_TYPES = os.path.join(AIRCRAFT_ASSET_FOLDER, DECKS_FOLDER, DECK_TYPES)
DESIGNER_CONFIG_FILE = "designer.yaml"
DESIGNER = True
CODE = "code"
WEBDECK_DEFAULTS = "presentation-default"
WEBDECK_WSURL = "ws_url"


# Flask Web Server (& WebSocket Server)
#
app = Flask(__NAME__, template_folder=TEMPLATE_FOLDER)

# app.logger.setLevel(logging.DEBUG)
# app.config["EXPLAIN_TEMPLATE_LOADING"] = True


@app.route("/")
def index():
    return render_template("index.j2", virtual_decks=cockpit.virtual_decks, copyrights={"copyrights": copyrights.replace("\n", "<br/>")})


@app.route("/favicon.ico")
def send_favicon():
    return send_from_directory(TEMPLATE_FOLDER, "favicon.ico")


@app.route("/assets/<path:path>")
def send_asset(path):
    return send_from_directory(ASSET_FOLDER, path)


@app.route("/aircraft/<path:path>")
def send_aircraft_asset(path):
    return send_from_directory(AIRCRAFT_ASSET_FOLDER, path)


# Designers
#
@app.route("/designer")
def designer():
    return render_template("designer.j2", image_list=cockpit.get_deck_background_images())


# Button designer
#
@app.route("/button-designer", methods=("GET", "POST"))
def button_designer():
    if request.method == "POST":
        return cockpit.render_button(request.json)
    return render_template("button-designer.j2", assets=cockpit.get_assets())


@app.route("/deck-indices", methods=("GET", "POST"))
def deck_indices():
    name = request.args.get("name")
    return cockpit.get_deck_indices(name)


@app.route("/button-details", methods=("GET", "POST"))
def button_details():
    deck = request.args.get("deck")
    index = request.args.get("index")
    return cockpit.get_button_details(deck, index)


@app.route("/activation", methods=("GET", "POST"))
def activation_details():
    name = request.args.get("name")
    return cockpit.get_activation_parameters(name)


@app.route("/representation", methods=("GET", "POST"))
def representation_details():
    name = request.args.get("name")
    return cockpit.get_representation_parameters(name)


@app.route("/load-button", methods=("GET", "POST"))
def button_definition():
    deck = request.args.get("deck")
    layout = request.args.get("layout")
    page = request.args.get("page")
    index = request.args.get("index")
    return cockpit.load_button(deck, layout, page, index)


# Deck designer
#
@app.route("/deck-designer")
def deck_designer():
    background_image = request.args.get("background_image", default="background.png")
    deck_config = {"deck-type-flat": {"background": {"image": background_image}, "aircraft": background_image.startswith("/aircraft")}}

    designer_config = {}
    designer_config_file = os.path.abspath(os.path.join(AIRCRAFT_HOME, CONFIG_FOLDER, RESOURCES_FOLDER, DECKS_FOLDER, DESIGNER_CONFIG_FILE))
    if os.path.exists(designer_config_file):
        with open(designer_config_file, "r") as fp:
            designer_config = yaml.load(fp)

    return render_template("deck-designer.j2", deck=deck_config, designer_config=designer_config)


@app.route("/deck-designer-io", methods=("GET", "POST"))
def button_designer_io():
    if request.method == "POST":

        data = request.json
        if CONFIG_FOLDER not in data:
            return {"status": "no deckconfig"}
        if CODE not in data:
            return {"status": "no code"}
        if CONFIG_KW.NAME.value not in data[CONFIG_FOLDER]:
            return {"status": "no name"}

        if not os.path.exists(AIRCRAFT_DECK_TYPES):
            os.makedirs(AIRCRAFT_DECK_TYPES, exist_ok=True)

        name = data[CONFIG_FOLDER].get(CONFIG_KW.NAME.value)
        fn = os.path.join(AIRCRAFT_DECK_TYPES, name + ".json")
        with open(fn, "w") as fp:
            json.dump(data[CODE], fp, indent=2)
            logger.info(f"Konva saved ({fn})")

        ln = os.path.join(AIRCRAFT_DECK_TYPES, name + ".yaml")
        with open(ln, "w") as fp:
            yaml.dump(data[CONFIG_FOLDER], fp)
            logger.info(f"layout saved ({ln})")

        cockpit.save_deck(name)

        return {"status": "ok"}

    code = {}
    args = request.args
    name = args.get("name")
    if name is not None:
        if "." in name:
            name = os.path.splitext(os.path.basename(name))[0]
        fn = os.path.join(AIRCRAFT_DECK_TYPES, name + ".json")
        logger.info(f"loading Konva ({fn})", args)
        with open(fn, "r") as fp:
            code = json.load(fp)
    else:
        return {"status": "no name"}
    return code


@app.route("/reload-decks")
def reload():
    cockpit.reload_decks()
    return {"status": "ok"}


# Deck runner
#
@app.route("/deck/<name>")
def deck(name: str):
    uname = urllib.parse.unquote(name)
    app.logger.debug(f"Starting deck {uname}")
    deck_desc = cockpit.get_virtual_deck_description(uname)
    # Inject our contact address:
    if type(deck_desc) is dict:
        deck_desc[WEBDECK_WSURL] = f"ws://{APP_HOST[0]}:{APP_HOST[1]}/cockpit"
        deck_desc[WEBDECK_DEFAULTS] = cockpit.get_virtual_deck_defaults()
    else:
        app.logger.debug(f"deck desc is not a dict {deck_desc}")
    return render_template("deck.j2", deck=deck_desc)


@app.route("/deck-bg/<name>")
def deck_bg(name: str):
    if name is None or name == "":
        app.logger.debug(f"no deck name")
        abort(404)
    uname = urllib.parse.unquote(name)
    deck_desc = cockpit.get_virtual_deck_description(uname)
    if deck_desc is None:
        app.logger.debug(f"no description")
        abort(404)
    deck_flat = deck_desc.get(DECK_TYPE_DESCRIPTION)
    if deck_flat is None:
        app.logger.debug(f"no {DECK_TYPE_DESCRIPTION} in description")
        abort(404)
    deck_img = deck_flat.get(DECK_KW.BACKGROUND_IMAGE_PATH.value)  # can be "background-image": None
    if deck_img is None:
        app.logger.debug(f"no {DECK_KW.BACKGROUND_IMAGE_PATH.value} in {DECK_TYPE_DESCRIPTION}")
        abort(404)
    if deck_img == "":
        app.logger.debug(f"no background image for {uname}")
        abort(404)
    return send_file(deck_img, mimetype="image/png")


@app.route("/cockpit", websocket=True)  # How convenient...
def cockpit_wshandler():
    ws = Server.accept(request.environ)
    try:
        while True:
            data = ws.receive()
            app.logger.debug(f"received {data}")
            data = json.loads(data)
            code = data.get(CODE)
            if code == 1:
                deck = data.get("deck")
                cockpit.register_deck(deck, ws)
                # app.logger.info(f"registered deck {deck}")
                cockpit.handle_code(code, deck)
                app.logger.debug(f"handled deck={deck}, code={code}")
            elif code == 0 or code == 99:  # 99 is replay
                deck = data.get("deck")
                if deck is None:  # sim event
                    cockpit.replay_sim_event(data=data)
                    # app.logger.info(f"event processed, data={data}")
                else:
                    key = data.get("key")
                    event = data.get("event")
                    payload = data.get("data")
                    cockpit.process_event(deck_name=deck, key=key, event=event, data=payload, replay=code == 99)
                # app.logger.info(f"event processed deck={deck}, event={event} data={payload}")
    except ConnectionClosed:
        app.logger.debug("connection closed")
        cockpit.remove_client(ws)
        app.logger.debug("client removed")
    return ""


# ##################################
# MAIN
#
# Wrapped in main function to make it accessible
# from builder/installer
#
def main():
    try:

        logger.info(f"Starting {AIRCRAFT_DESC}..")
        if ac is None and SIMULATOR_HOME is not None:
            logger.info(
                f"(starting in demonstration mode but will load aircraft if {SIMULATOR_NAME} is running and aircraft with Cockpitdecks {CONFIG_FOLDER} loaded)"
            )
        cockpit.start_aircraft(acpath=AIRCRAFT_HOME, release=True, mode=mode.value)
        logger.info(f"..{AIRCRAFT_DESC} running..")
        if cockpit.has_web_decks() or (len(cockpit.get_deck_background_images()) > 0 and DESIGNER):
            if not cockpit.has_web_decks():
                logger.warning("no web deck, start application server for designer")
            logger.info("starting application server..")
            app.run(host="0.0.0.0", port=APP_HOST[1])

        # If single CTRL-C pressed, will terminate from here
        # logger.info("terminating (please wait)..")
        print("")  # to highlight CTRL-C in log window
        logger.info("..application server terminated")
        cockpit.terminate_all(threads=1)  # [MainThread]
        logger.info(f"..{cockpit.get_aircraft_name()} terminated.")

    except KeyboardInterrupt:

        def spin():
            spinners = ["|", "/", "-", "\\"]
            for c in itertools.cycle(spinners):
                print(f"\r{c}", end="")
                time.sleep(0.1)

        logger.info("terminating (please wait)..")
        thread = threading.Thread(target=spin)
        thread.daemon = True
        thread.name = "spinner"
        thread.start()

        if cockpit is not None:
            cockpit.terminate_all(threads=1)
        logger.info(f"..{AIRCRAFT_DESC} terminated.")


# Run if unwrapped
if __name__ == "__main__":
    main()
