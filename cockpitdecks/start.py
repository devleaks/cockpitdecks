"""Main startup script for Cockpitdecks

Starts up Cockpitdecks. Process command line arguments, load Cockpitdecks with proper simulator.
Starts listening to events from both X-Plane and decks connected to the computer.
Starts web server to serve web decks, designer, and button editor.
Starts WebSocket listener to collect events from web decks.

Press CTRL-C ** once ** to gracefully stop Cockpitdecks. Be patient.
"""

import sys
import os
import logging
import time
import itertools
import threading
import json
import urllib.parse
import argparse
import subprocess

from enum import Enum

from flask import Flask, render_template, send_from_directory, request
from simple_websocket import Server, ConnectionClosed

import ruamel
from ruamel.yaml import YAML

from cockpitdecks.constant import CONFIG_FILE, CONFIG_FOLDER, RESOURCES_FOLDER
from cockpitdecks.constant import CONFIG_KW, DECKS_FOLDER, DECK_TYPES, TEMPLATE_FOLDER, ASSET_FOLDER
from cockpitdecks import Cockpit, __NAME__, __version__, __COPYRIGHT__, Config
from cockpitdecks.simulators import XPlane  # The simulator we talk to


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
#
# COCKPITDECKS STARTS HERE
#
# COMMAND LINE PARSING
#
# No aircraft supplied starts the demo version.
DESC = "Elgato Stream Decks, Loupedeck decks, Berhinger X-Touch Mini, and web decks to X-Plane 12.1+"
DEMO_HOME = os.path.join(os.path.dirname(__file__), "resources", "demo")
AIRCRAFT_HOME = DEMO_HOME
AIRCRAFT_DESC = "Cockpitdecks Demo"
COCKPITDECKS_FOLDER = "cockpitdecks"


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


# Command-line arguments
#
parser = argparse.ArgumentParser(description="Start Cockpitdecks")
parser.add_argument("aircraft_folder", metavar="aircraft_folder", type=str, nargs="?", help="aircraft folder for non automatic start")
parser.add_argument("-c", "--config", metavar="config_file", type=str, nargs=1, help="alternate configuration file")
parser.add_argument("-d", "--demo", action="store_true", help="start demo mode")
parser.add_argument("-f", "--fixed", action="store_true", help="does not automatically switch aircraft")
parser.add_argument("-v", "--verbose", action="store_true", help="show startup information")

args = parser.parse_args()

VERBOSE = args.verbose

# Environment File
#
default_environment_file = os.path.join(COCKPITDECKS_FOLDER, CONFIG_FILE)
config_file = default_environment_file if args.config is None else args.config[0]

environment = {}
if os.path.exists(config_file):
    environment = Config(filename=os.path.abspath(config_file))
    if VERBOSE:
        print(f"Cockpitdecks loaded environment from file {config_file}")
else:
    print(f"Cockpitdecks environment file {config_file} not found")
    if os.path.exists(default_environment_file):
        environment = Config(filename=default_environment_file)
        print(f"Cockpitdecks loaded default environment file {default_environment_file} instead")
    else:
        print(f"Cockpitdecks defalut environment file {default_environment_file} not found")
        sys.exit(1)

# Debug
#
debug = environment.get("DEBUG", "info").lower()
if debug == "debug":
    logging.basicConfig(level=logging.DEBUG)
elif debug == "warning":
    logging.basicConfig(level=logging.WARNING)
elif debug != "info":
    debug = "info"
    print(f"invalid debug mode {debug}, using info")
if VERBOSE:
    print(f"debug set to {debug}")


# X-Plane
#
# First try env:
XP_HOME = os.getenv("XP_HOME")
# Then environment
if XP_HOME is None:
    XP_HOME = environment.get("XP_HOME")
# if defined, must exist.
if XP_HOME is not None and not (os.path.exists(XP_HOME) and os.path.isdir(XP_HOME)):
    print(f"X-Plane not found in {XP_HOME}")
    sys.exit(1)

if VERBOSE:
    if XP_HOME is not None:
        print(f"X-Plane found in {XP_HOME}")
    else:
        XP_HOST = environment.get("XP_HOST")
        if XP_HOST is None:
            print(f"X-Plane not found. no folder, no remove host")
            sys.exit(1)
        else:
            print(f"no XP_HOME, assume remote installation at XP_HOST={XP_HOST}")

# COCKPITDECKS_PATH
#
def add_env(env, paths):
    return ":".join(set(env.split(":") + paths)).strip(":")


# Strats from environment
COCKPITDECKS_PATH = os.getenv("COCKPITDECKS_PATH", "")

# Append from environment file
ENV_PATH = environment.get("COCKPITDECKS_PATH")
if ENV_PATH is not None:
    COCKPITDECKS_PATH = add_env(COCKPITDECKS_PATH, ENV_PATH)

# Append X-Plane regular aircraft paths
if XP_HOME is not None:
    COCKPITDECKS_PATH = add_env(COCKPITDECKS_PATH, [os.path.join(XP_HOME, "Aircraft", "Extra Aircraft"), os.path.join(XP_HOME, "Aircraft", "Laminar Research")])

if VERBOSE:
    print(f"COCKPITDECKS_PATH={COCKPITDECKS_PATH}")

# Other environment variables
APP_HOST = os.getenv("APP_HOST")
APP_PORT = 7777
if APP_HOST is not None:
    APP_PORT = os.getenv("APP_PORT", 7777)
else:
    APP_HOST = environment.get("APP_HOST", ["127.0.0.1", 7777])

if VERBOSE:
    print(f"Cockpitdecks server at {APP_HOST}")

# Start-up Mode
#
mode = CD_MODE.DEMO if args.demo else CD_MODE.NORMAL
ac = args.aircraft_folder
if ac is not None:
    target_dir = os.path.abspath(os.path.join(os.getcwd(), ac))
    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        print(f"{target_dir} directory not found")
        sys.exit(1)
    test_dir = os.path.join(target_dir, CONFIG_FOLDER)
    if not os.path.exists(test_dir) or not os.path.isdir(test_dir):
        print(f"{target_dir} directory does not contain {CONFIG_FOLDER} directory")
        sys.exit(1)
    AIRCRAFT_HOME = os.path.abspath(os.path.join(os.getcwd(), ac))
    AIRCRAFT_DESC = os.path.basename(ac)
    mode = CD_MODE.FIXED if args.fixed else CD_MODE.NORMAL
    if VERBOSE:
        print(f"starting aircraft folder {AIRCRAFT_HOME}, {'fixed' if mode.value > 0 else 'dynamically adjusted to aircraft'}\n")
elif ac is None and XP_HOME is None and len(COCKPITDECKS_PATH) == 0:
    mode = CD_MODE.DEMO
    if VERBOSE:
        print("no aircraft, no X-Plane on this host, COCKPITDECKS_PATH not defined: starting in demo mode")


#
# COCKPITDECKS STARTS HERE, REALLY
#
# Run git status
last_commit = ""
git = which("git")
if os.path.exists(".git") and git is not None:
    process = subprocess.Popen([git, "show", "-s", "--format=%ci"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    last_commit = stdout.decode("utf-8")[:10].replace("-", "")

copyrights = f"{__NAME__.title()} {__version__}.{last_commit} {__COPYRIGHT__}\n{DESC}\n"
print(copyrights)
logger.info("Initializing Cockpitdecks..")
cockpit = Cockpit(XPlane, environ=environment)
logger.info("..initialized\n")


# ##################################
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

app.logger.setLevel(logging.INFO)
# app.config["EXPLAIN_TEMPLATE_LOADING"] = True


@app.route("/")
def index():
    return render_template("index.j2", virtual_decks=cockpit.get_web_decks(), copyrights={"copyrights": copyrights.replace("\n", "<br/>")})


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
    config_file = os.path.abspath(os.path.join(AIRCRAFT_HOME, CONFIG_FOLDER, RESOURCES_FOLDER, DECKS_FOLDER, DESIGNER_CONFIG_FILE))
    if os.path.exists(config_file):
        with open(config_file, "r") as fp:
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
                    # app.logger.info(f"dataref event processed, data={data}")
                else:
                    key = data.get("key")
                    event = data.get("event")
                    payload = data.get("data")
                    cockpit.process_event(deck_name=deck, key=key, event=event, data=payload, replay=code == 99)
                # app.logger.info(f"event processed deck={deck}, event={event} data={payload}")
    except ConnectionClosed:
        app.logger.debug("connection closed")
        cockpit.remove(ws)
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
        if ac is None and XP_HOME is not None:
            logger.info(f"(starting in demonstration mode but will load aircraft if X-Plane is running and aircraft with Cockpitdecks {CONFIG_FOLDER} loaded)")
        cockpit.start_aircraft(acpath=AIRCRAFT_HOME, cdpath=COCKPITDECKS_PATH, release=True, mode=mode.value)
        logger.info("..started")
        if cockpit.has_web_decks() or (len(cockpit.get_deck_background_images()) > 0 and DESIGNER):
            if not cockpit.has_web_decks():
                logger.warning("no web deck, start application server for designer")  # , press CTRL-C ** twice ** to quit
            logger.info("Starting application server")  # , press CTRL-C ** twice ** to quit
            app.run(host="0.0.0.0", port=APP_HOST[1])

        # If single CTRL-C pressed, will terminate from here
        logger.warning("terminating (please wait)..")
        cockpit.terminate_all(threads=1)  # [MainThread]
        logger.info(f"..{AIRCRAFT_DESC} terminated.")

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

        if cockpit is not None:
            cockpit.terminate_all(threads=1)
        logger.info(f"..{AIRCRAFT_DESC} terminated.")


# Run if unwrapped
if __name__ == "__main__":
    main()
