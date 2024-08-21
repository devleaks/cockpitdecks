# ##############################
#
# MAIN SYSTEM CINFIGURATION FILE
#
import os

VERBOSE = True

# #############################@
# 1. NETWORK SETTING
#
# Where X-Plane runs
#
XP_HOST = "127.0.0.1"

XP_HOME = os.path.join(os.sep, "Applications", "X-Plane 12")
# XP_HOME = None  # Uncomment this line if X-Plane runs on a remote machine

API_PORT = "8086"  # API is only available if running on the same host (or use a proxy)
API_PATH = "/api/v1"  # no default, Laminar provides it

# Where Cockpitdecks runs
#
APP_HOST = [os.getenv("APP_HOST", "127.0.0.1"), int(os.getenv("APP_PORT", "7777"))]

# Where to search for aircrafts
COCKPITDECKS_PATH = []
if XP_HOME is not None:
    COCKPITDECKS_PATH = ":".join([os.path.join(XP_HOME, "Aircraft", "Extra Aircraft"), os.path.join(XP_HOME, "Aircraft", "Laminar Research")])

DEMO_HOME = os.path.join(os.path.dirname(__file__), "resources", "demo")