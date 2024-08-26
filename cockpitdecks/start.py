import sys
import os
import logging
import time
import itertools
import threading
import json
import urllib.parse
from enum import Enum

from flask import Flask, render_template, send_from_directory, request
from simple_websocket import Server, ConnectionClosed

import ruamel
from ruamel.yaml import YAML

from cockpitdecks.config import XP_HOME, APP_HOST, DEMO_HOME, VERBOSE
from cockpitdecks.constant import CONFIG_FOLDER, RESOURCES_FOLDER

from cockpitdecks.constant import CONFIG_KW, DECKS_FOLDER, DECK_TYPES, COCKPITDECKS_ASSET_PATH, AIRCRAFT_ASSET_PATH, TEMPLATE_FOLDER, ASSET_FOLDER
from cockpitdecks import Cockpit, __NAME__, __version__, __COPYRIGHT__
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
DESC = "Elgato Stream Decks, LoupedeckLive, Berhinger X-Touch, and web decks to X-Plane 12"
AIRCRAFT_HOME = DEMO_HOME
AIRCRAFT_DESC = "Cockpitdecks Demo"


def print_help():
    print(
        """usage: cockpitdecks-cli [ { --help | --demo | directory [fixed] } ]

--help, -h, -?: displays command line help and exits
--demo        : starts demo mode, X-plane not needed but used if available, aircraft will not change
directory     : start from directory if directory contains deckconfig directory (ignored otherwise)
       fixed  : if 'fixed' added after the directory, aircraft will not change in Cockpitdecks

without any argument:
- if X-Plane runs on same computer as Cockpitdecks, starts in full automatic mode.
- if X-Plane does not run on same computer as Cockpitdecks, start demo mode.
"""
    )


class CD_MODE(Enum):
    NORMAL = 0
    DEMO = 1
    FIXED = 2


ac = sys.argv[1] if len(sys.argv) > 1 else None
fixed = sys.argv[2] if len(sys.argv) > 2 else None

if ac in ["--help", "-h", "-?"]:  # command line help
    print_help()
    sys.exit(0)

if XP_HOME is not None and not (os.path.exists(XP_HOME) and os.path.isdir(XP_HOME)):
    print(f"X-Plane not found in {XP_HOME}")
    sys.exit(1)

mode = CD_MODE.DEMO if ac == "--demo" else CD_MODE.NORMAL
if ac is not None and ac != "--demo":
    if ac.startswith("-"):
        print(f"invalid {ac} command line switch")
        print_help()
        sys.exit(1)
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
    mode = CD_MODE.FIXED if fixed in ["--fixed", "fixed", "fix", "f"] else CD_MODE.NORMAL
elif ac is None and XP_HOME is None:
    mode = CD_MODE.DEMO
    if VERBOSE:
        print("no aircraft, no X-Plane on this host, starting in demo mode")

if VERBOSE:
    print(f"{AIRCRAFT_HOME}, {'fixed' if mode.value > 0 else 'can change'}")

#
# COCKPITDECKS STARTS HERE, REALLY
#
print(f"\n\n{__NAME__.title()} {__version__} {__COPYRIGHT__}\n{DESC}\n")
logger.info(f"Initializing Cockpitdecks..")
cockpit = Cockpit(XPlane)
logger.info("..initialized")


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
    return render_template("index.j2", virtual_decks=cockpit.get_web_decks())


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
            elif code == 0:
                deck = data.get("deck")
                key = data.get("key")
                event = data.get("event")
                payload = data.get("data")
                cockpit.process_event(deck_name=deck, key=key, event=event, data=payload)
                app.logger.debug(f"event processed deck={deck}, event={event} data={payload}")
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
        cockpit.start_aircraft(AIRCRAFT_HOME, release=True, mode=mode.value)
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
