import os
import logging
import sys
import time
import itertools
import threading
import json
import urllib.parse
import socket

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))  # we assume we're in subdir "bin/"

from flask import Flask, render_template, send_from_directory, request, jsonify
from simple_websocket import Server, ConnectionClosed

from cockpitdecks import Cockpit, __NAME__, __version__, __COPYRIGHT__
from cockpitdecks.simulators import XPlane  # The simulator we talk to
from cockpitdecks import LOGFILE, FORMAT

# logging.basicConfig(level=logging.DEBUG, filename="cockpitdecks.log", filemode='a')

logging.basicConfig(level=logging.INFO, format=FORMAT)

logger = logging.getLogger(__name__)
if LOGFILE is not None:
    formatter = logging.Formatter(FORMAT)
    handler = logging.FileHandler(LOGFILE, mode="a")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

ac = sys.argv[1] if len(sys.argv) > 1 else None
ac_desc = os.path.basename(ac) if ac is not None else "(no aircraft folder)"


APP_HOST = [
    os.getenv('APP_HOST', '127.0.0.1'),
    int(os.getenv('APP_PORT', '7777'))
]

logger.info(f"{__NAME__.title()} {__version__} {__COPYRIGHT__}")
logger.info(f"Starting for {ac_desc}..")
logger.info(f"..searching for decks and initializing them (this may take a few seconds)..")
cockpit = Cockpit(XPlane)


# ##################################
# Flask Web Server (& WebSocket)
#
# Serves decks and their assets.
# Proxy WebSockets to TCP Sockets
#
TEMPLATE_FOLDER = os.path.join("..", "cockpitdecks", "decks", "resources", "templates")
ASSET_FOLDER = os.path.join("..", "cockpitdecks", "decks", "resources", "assets")

app = Flask(__NAME__, template_folder=TEMPLATE_FOLDER)

app.logger.setLevel(logging.INFO)
# app.config['EXPLAIN_TEMPLATE_LOADING'] = True


@app.route("/")
def index():
    return render_template("index.j2", virtual_decks=cockpit.get_virtual_decks())


@app.route("/favicon.ico")
def send_favicon():
    return send_from_directory(TEMPLATE_FOLDER, "favicon.ico")


@app.route("/assets/<path:path>")
def send_report(path):
    return send_from_directory(ASSET_FOLDER, path)


# Button designer
#
@app.route('/button-designer', methods=("GET", "POST"))
def button_designer():
    if request.method == "POST":
        return cockpit.render_button(request.json)
    return render_template("button-designer.j2", assets=cockpit.get_assets())


@app.route("/deck_indices", methods=("GET", "POST"))
def deck_indices():
    name = request.args.get("name")
    return cockpit.get_deck_indices(name)


@app.route("/button_details", methods=("GET", "POST"))
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


# Deck designer
#
@app.route('/deck-designer')
def deck_designer():
    return render_template("deck-designer.j2")


# Deck runner
#
@app.route("/deck/<name>")
def deck(name: str):
    uname = urllib.parse.unquote(name)
    app.logger.debug(f"Starting deck {uname}")
    deck_desc = cockpit.get_virtual_deck_description(uname)
    # Inject our contact address:
    if type(deck_desc) is dict:
        deck_desc["ws_url"] = f"ws://{APP_HOST[0]}:{APP_HOST[1]}/cockpit"
        deck_desc["presentation-default"] = cockpit.get_virtual_deck_defaults()
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
            code = data.get("code")
            if code == 1:
                deck = data.get("deck")
                cockpit.register_deck(deck, ws)
                app.logger.info(f"registered deck {deck}")
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
        app.logger.debug(f"connection closed")
        cockpit.remove(ws)
        app.logger.debug(f"client removed")
    return ""


# ##################################
# MAIN
#
try:

    cockpit.start_aircraft(ac, release=True)
    if cockpit.has_virtual_decks():
        logger.info(f"Starting application server")  # , press CTRL-C ** twice ** to quit
        app.run(host="0.0.0.0", port=APP_HOST[1])

    # If single CTRL-C pressed, will terminate here
    logger.warning("terminating (please wait)..")
    cockpit.terminate_all(2)
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

    if cockpit is not None:
        cockpit.terminate_all(2)
    logger.info(f"..{ac_desc} terminated.")
