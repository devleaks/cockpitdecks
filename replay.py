# Experimental script to replay actions
# Currently only works for all events except DatarefEvents
#
# Sends events one by one from the event file logged by Cockpitdecks.
# Respect original timing.
# Open perspective of automation, espcially for testing
#
# Pip install jsonlines before using.
#
import sys
import os
import time
import json
import argparse
import jsonlines
from datetime import datetime
from typing import Tuple
from simple_websocket import Client, ConnectionClosed



parser = argparse.ArgumentParser(description="Replay Cockpitdecks event log")
parser.add_argument("logfile", type=str, nargs="?", help="file with logged events (jsonlines format)")
parser.add_argument("-f", "--fast", action="store_true", help="does not respect timing")
parser.add_argument("-s", "--silent", action="store_true", help="disable logging")
parser.add_argument("-i", "--info", action="store_true", help="disable sending to Cockpitdecks (just print)")
parser.add_argument("-x", "--xplane", action="store_true", help="send X-Plane dataref updates")
parser.add_argument("-I", "--internal", action="store_true", help="send internal dataref updates")

args = parser.parse_args()

if args.logfile is None:
    parser.print_help()
    sys.exit(1)

need_flush = False
def flush():
    global need_flush
    if need_flush:
        print(".", flush=True)
    need_flush = False


COCKPITDECKS_DATA_PREFIX = "data:"
APP_HOST = [os.getenv("APP_HOST", "mac-studio-de-pierre.local"), int(os.getenv("APP_PORT", 7777))]

ws = None
if not args.info:
    try:
        ws = Client.connect(f"ws://{APP_HOST[0]}:{APP_HOST[1]}/cockpit")
        if not args.silent:
            print("connected")
    except ConnectionRefusedError:
        print("no connection")
elif not args.silent:
    print("no connection")

# Event codes:
#  0 = Push/press RELEASE
#  1 = Push/press PRESS
#  2 = Turned clockwise
#  3 = Turned counter-clockwise
#  4 = Pulled
#  9 = Slider, event data contains value
# 10 = Touch start, event data contains value
# 11 = Touch end, event data contains value
# 12 = Swipe, event data contains value
# 14 = Tap, event data contains value
# Event data varies with the code...
def get_event(event) -> Tuple[int | None, dict]:
    global need_flush
    code = 0
    data = {}

    event_type = event["type"]
    # Event types:
    # PushEvent
    # EncoderEvent
    # SlideEvent
    # SwipeEvent
    # TouchEvent

    event_code = event.get("rawcode", -1)
    if event_code == -1: # need to recontruct it
        if event_type == "PushEvent":
            if event["pressed"]:
                if event["pulled"] > 0:
                    code = 4
                else:
                    code = 1
        elif event_type == "EncoderEvent":
            if event["clockwise"]:
                code = 2
            else:
                code = 3
        elif event_type == "TouchEvent":
            if event["start"] is None:
                code = 10
            else:
                code = 11
            data = {
                "x": event["pos_x"],
                "y": event["pos_y"],
                "ts": event["cli_ts"]
            }
        elif event_type == "SlideEvent":
            code = 9
            data = {
                "value": event["value"]
            }
        elif event_type == "DatarefEvent":
            if args.xplane:
                path = event["path"]
                if path is not None and (args.internal or not path.startswith(COCKPITDECKS_DATA_PREFIX)):
                    data = {
                        "code": 99,
                        "path": path,
                        "value": event["value"]
                    }
                    return -1, data
            if not args.silent:
                print(".", end="", flush=True)
                need_flush = True
            return None, data
        else:
            if not args.silent:
                flush()
                print("unhandled event type", event_type)
            return None, data

    return code, data | {"_replay": True}

MIN_TIME = 0.01  # secs between 2 send
tot_time = 0
try:
    data = []
    last = None
    delta = 0
    with jsonlines.open(args.logfile) as reader:
        for obj in reader:
            if last is not None:
                delta = datetime.fromisoformat(obj["ts"]).timestamp() -  datetime.fromisoformat(last["ts"]).timestamp()
            tot_time = tot_time + delta
            time.sleep(MIN_TIME if args.fast else max(MIN_TIME, delta))
            code, data = get_event(obj["event"])
            last = obj
            if code is None:
                tot_time = tot_time + delta
                continue
            new_event = data if code == -1 else {
                    "code": 99,  # special code for replay
                    "deck": obj["event"]["deck"].split("/")[1],
                    "key": obj["event"]["button"],
                    "event": code,
                    "data": data
            }
            if not args.silent or args.info:
                flush()
                print("replay", f"{tot_time:5.3f}", new_event)
            if ws is not None:
                try:
                    ws.send(json.dumps(new_event))
                except:
                    flush()
                    print(f"failed to send {new_event}")
    if ws is not None:
        ws.close()
except (KeyboardInterrupt, EOFError, ConnectionClosed):
    if ws is not None:
        ws.close()
if not args.silent:
    flush()
    print("done")
flush()