# Sends events one by one from the event file logged by Cockpitdecks.
# Respect original timing.
# Open perspective of automation, espcially for testing
#
import sys
import os
import time
import json
import argparse
import jsonlines
from datetime import datetime
from simple_websocket import Client, ConnectionClosed



parser = argparse.ArgumentParser(description="Replay Cockpitdecks event log")
parser.add_argument("logfile", type=str, nargs="?", help="file with logged events (jsonlines format)")
parser.add_argument("-f", "--fast", action="store_true", help="does not respect timing, send event every second")
parser.add_argument("-s", "--silent", action="store_true", help="disable logging")
parser.add_argument("-i", "--info", action="store_true", help="disable sending to Cockpitdecks (just print)")

args = parser.parse_args()

if args.logfile is None:
    parser.print_help()
    sys.exit(1)


APP_HOST = [os.getenv("APP_HOST", "mac-studio-de-pierre.local"), int(os.getenv("APP_PORT", 7777))]
ws = None
if not args.info:
    try:
        ws = Client.connect(f"ws://{APP_HOST[0]}:{APP_HOST[1]}/cockpit")
        if not args.silent:
            print("connected")
    except:
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
def get_event(event):
    code = 0
    data = {}

    event_type = event["type"]
    if event_type == "PushEvent":
        if event["pressed"]:
            if event["pulled"] > 0:
                code = 4
            else:
                code = 1
    else:
        print("unhandled event type", event_type)
        return None

    return code, data | {"_replay": True}

tot_time = 0
try:
    data = []
    last = None
    delta = 0
    with jsonlines.open(args.logfile) as reader:
        for obj in reader:
            if last is not None:
                delta = datetime.fromisoformat(obj["ts"]).timestamp() -  datetime.fromisoformat(last["ts"]).timestamp()
            time.sleep(1 if args.fast else delta)
            code, data = get_event(obj["event"])
            if code is None:
                tot_time = tot_time + delta
                continue
            new_event = {
                "code": 99,  # special code for replay
                "deck": obj["event"]["deck"].split("/")[1],
                "key": obj["event"]["button"],
                "event": code,
                "data": data
            }
            if not args.silent or args.info:
                print("replay", round(tot_time, 3), new_event)
            if ws is not None:
                ws.send(json.dumps(new_event))
            last = obj
            tot_time = tot_time + delta
    if ws is not None:
        ws.close()
except (KeyboardInterrupt, EOFError, ConnectionClosed):
    if ws is not None:
        ws.close()
