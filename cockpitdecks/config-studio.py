# ##############################
#
# MAIN SYSTEM CINFIGURATION FILE
#
#
# 1. NETWORK SETTING
#
import os

# This is to print configuration information if necessry.
# If false, configuration remains quiet, only showing errors or inconsistancies.
VERBOSE = True
#
# #############################@
# 1. NETWORK SETTING
#
# Where X-Plane runs
#
LOCALHOST = "127.0.0.1"
XP_HOST = LOCALHOST
# XP_HOME = None
XP_HOME = os.path.join(os.sep, "Users", "pierre", "X-Plane 12")

API_HOST = LOCALHOST  # if None, set to self.beacon_data['IP']
API_PORT = 8086  # API is only available if running on the same host (or use a proxy)
API_PATH = "/api/v1"  # no default, Laminar provides it
#
# Where Cockpitdecks runs
#
APP_HOST = [os.getenv("APP_HOST", "mac-studio-de-pierre.local"), int(os.getenv("APP_PORT", 7777))]
DEMO_HOME = os.path.join(os.path.dirname(__file__), "resources", "demo")
#
# #############################@
# 2. COCKPITDECKS SETTING
#
# Where to search for aircrafts
#
COCKPITDECKS_PATH = os.getenv("COCKPITDECKS_PATH", "")
if XP_HOME is not None:
    COCKPITDECKS_PATH = ":".join(
        COCKPITDECKS_PATH.split(":") + [os.path.join(XP_HOME, "Aircraft", "Extra Aircraft"), os.path.join(XP_HOME, "Aircraft", "Laminar Research")]
    )
