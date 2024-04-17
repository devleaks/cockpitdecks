# Toliss A321 livery linter
#
# Attempts to check livery folders for inconsistencies.
#
# Inconsistencies are:
#
#   - discrepenscies between livery "strings" and livery configuration files (tlscfg.txt)
#   - invalid values for livery elements
#   - missing texture files in front of their requested variant (ex.: engine_type=LEA requires a LEAP1A.png texture file, etc.)
#
# While we are at it, some aircraft-level insconsistencies are also verified (missing icon files, etc.)
# Most code just check for key words like YES/ON instead of True/False or all their "case" variants (Yes, yes, YES, Y, True, true, TRUE...)
# Config strings are normalized to their case sensitive variant as described in the manuals.
# However, original file may contain case insensitive variants (all lower or upper cased names).
#
# This code can easily be adjusted to other Toliss Airbus products.
# Code uses confiparser standard python library (python 3.11 and up) and deals with its constrains.
#
#
# CHANGELOG
#
# 17-APR-2024: Corrected case sensitivity issues.
# 21-DEC-2023: Initial release.
#
# -------------------------------------------------------------------
import configparser
import logging
import glob
from os import listdir
import re
from os.path import basename, isdir, join, exists

FORMAT = "%(levelname)8s: %(message)s"
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
logger = logging.getLogger("lint")

config = configparser.ConfigParser()
# important note: configparser forces parameter names to lowercase. Example: has_BUSSSwitches -> has_bussswitches

AC_PATH = "/Users/pierre/X-Plane 12/Aircraft/Extra Aircraft/ToLiss A321"
LIVERY_STRING = "^\\[((?P<engine>IAE|CFM){0,1}|(?P<sharklet>S){0,1}|(?P<satcom>T){0,1}|(?P<garbage>.))*\\]"
DEFAULT_SECTION = "top"
NEW_CONFIG = "livery.tlsnew"
NO = "NO"
YES = "YES"


def parsename(m) -> tuple:
    # Should check it has garbage too (i.e. invalid chatracters, stings, etc.)
    # if m.group("garbage") is not None:
    #     logger.warning(f"has garbage")
    return (m.group("engine"), m.group("sharklet") is not None, m.group("satcom") is not None)


def default_config(is_neo: bool = False, original: dict = {}) -> dict:
    # Note: original has all lowercase keys
    cfg = {
        "eng_type": "CFM",  # eng_type=CFM or IAE
        "sharklet": NO,
        "has_SatCom": NO,
        "use_Imperial_Units": NO,
        "num_Extra_Fuel_Tanks": 0,
        "has_DCDUs": NO,
    }
    if is_neo:
        cfg = cfg | {
            "321neo_config": "NEO",
            "eng_type": "PWG",  # eng_type=PWG or LEA
            "exit_Configuration": "CLASSIC",
            "has_eRudder": YES,
            "has_MultiFunRwyLights": YES,
            "has_BUSSSwitches": YES,
        }
    # merge original dict:
    if len(original) > 0:
        for f in cfg.keys():
            val = original.get(f)
            if val is None:  # try no case sensitivity (all lower)
                val = original.get(f.lower())
            if val is None:  # try no case sensitivity (all upper)
                val = original.get(f.upper())
            if val is not None:
                cfg[f] = val
        logger.debug(f"merged default and original ({original})")
    return cfg


def get_config_file(fn: str) -> dict:
    data = {}
    with open(fn) as fp:
        config.read_string(f"[{DEFAULT_SECTION}]\n" + fp.read())
    return dict(config.items(DEFAULT_SECTION))


liveries = join(AC_PATH, "liveries")
ac = basename(AC_PATH)
do_livery_icons = False

# Find aircraft filenames
acfn = sorted([basename(f) for f in glob.glob(join(AC_PATH, "*.acf"))])
logger.info(f"aircraft files: {acfn}")

for livery in listdir(liveries):
    d = join(liveries, livery)
    if not isdir(d):
        continue  # not a folder, not a livery
    objects = join(d, "objects")  # A livery folder has a objects sub-folder
    if not isdir(objects):
        logger.debug(f"file {d} does not appear to be a livery")
        continue
    logger.debug(">" * 20 + f" {livery}")
    is_neo = False
    data = {}
    cfg = join(d, "livery.tlscfg")
    m = re.match(LIVERY_STRING, livery)
    if m is not None:
        engine, sharklets, satcom = parsename(m)

        if exists(cfg):  # Search for discrepencies between magic string and livery.tlscfg
            logger.debug(f"livery {livery}: has magic string and config file")
            data = get_config_file(cfg)

            neo = data.get("321neo_config", "")
            is_neo = neo in ["NEO", "LR", "XLR"]

            e = data.get("eng_type")
            if e is not None and engine is not None and e != engine:
                logger.warning(f"livery {livery}: engine differ {engine} (in string) vs {e} (in config file)")

            if not is_neo:
                if e is not None and e not in ["IAE", "CFM"]:
                    logger.warning(f"livery {livery}: engine {e} not valid for CEO")
            else:
                if e is not None and e not in ["PWG", "LEA"]:
                    logger.warning(f"livery {livery}: engine {e} not valid for NEO")

            s = data.get("has_satcom")
            if s is not None:
                s = s.upper() == YES
            if s is not None and satcom is not None and s != satcom:
                logger.warning(f"livery {livery}: SATCOM differ {satcom} (in string) vs {s} (in config file)")

            k = data.get("sharklet")
            if k is not None:
                k = k.upper() == YES
            if k is not None and sharklets is not None and k != sharklets:
                logger.warning(f"livery {livery}: sharkets differ {sharklets} (in string) vs {k} (in config file)")

        else:
            if engine in ["IAE", "CFM"]:
                data["eng_type"] = engine
            if sharklets :
                data["sharklet"] = YES
            if satcom:
                data["has_SatCom"] = YES
            logger.debug(f"livery {livery}: has magic string only {engine, sharklets, satcom}")
            logger.warning(f"livery {livery}: has no config file")

    else:
        logger.debug(f"livery {livery}: has no magic string")
        if exists(cfg):
            logger.debug(f"livery {livery}: has config file")
            data = get_config_file(cfg)

            neo = data.get("321neo_config", "")
            is_neo = neo in ["NEO", "LR", "XLR"]

            # Exit configuration and fuselage texture (Airbus Cabin Flex)
            e = data.get("exit_configuration")
            if e is not None:
                logger.debug(f"livery {livery}: has exit_Configuration={e}")
                v = None
                if e == "CLASSIC":  # 1-sim/rem/0, CLASSIC
                    v = ""
                elif e == "1_OWE":  # 1-sim/rem/1, SINGLE OWE
                    v = "_1"
                elif e == "2_OWE":  # 1-sim/rem/2, DUAL OWE
                    v = "_2"
                elif e == "NO DOOR 3":  # 1-sim/rem/3, NO DOOR 3
                    v = "_3"
                else:
                    logger.warning(f"livery {livery}: invalid exit configuration {e}")
                    continue
                txt = join(objects, f"fuselage321{v}.png")
                if not exists(txt):
                    logger.warning(f"livery {livery}: has exit configuration {e} but no texture file {txt.replace(AC_PATH, '..')}")
            else:
                logger.debug(f"livery {livery}: has no exit configuration")
                txt = join(objects, "fuselage321.png")
                if not exists(txt):
                    logger.warning(f"livery {livery}: has no exit configuration, no texture file {txt.replace(AC_PATH, '..')}")
                else:
                    logger.debug(f"livery {livery}: has no exit configuration, texture file found")

            txtfn = sorted([basename(f) for f in glob.glob(join(objects, "fuselage*.png"))])
            logger.debug(f"livery {livery}: texture files: {txtfn}")

            # Engine type and engine texture
            e = data.get("eng_type")
            if e is not None:
                if is_neo:
                    if e not in ["PWG", "LEA"]:
                        logger.warning(f"livery {livery}: invalid engine type {e} for neo")
                else:
                    if e not in ["CFM", "IAE"]:
                        logger.warning(f"livery {livery}: invalid engine type {e} for ceo")
                logger.debug(f"livery {livery}: has eng_type={e} ({'is neo' if is_neo else ''})")
                v = None
                if e == "CFM":  # anim/CFM=1
                    v = "engines"
                elif e == "IAE":  # anim/IAE=1
                    v = "engines"
                elif e == "LEA":  # anim/NEO=0, anim/NEO/kill=1, anim/LEAP/kill=0
                    v = "LEAP1A"
                elif e == "PWG":  # anim/NEO=1, anim/NEO/kill=0, anim/LEAP/kill=1
                    v = "NEO"
                else:
                    logger.warning(f"livery {livery}: invalid engine type {e}")
                    continue
                txt = join(objects, f"{v}.png")
                if not exists(txt):
                    logger.warning(f"livery {livery}: has engine type {e} but no texture file {txt.replace(AC_PATH, '..')}")
            else:
                logger.warning(f"livery {livery}: has no engine type")

        else:
            logger.info(f"livery {livery}: has no magic string and no config file (and that's ok!)")

    if NEW_CONFIG is not None:
        newcfg = default_config(is_neo=is_neo, original=data)

        # Difference between config and estimated config
        # set1 = set(data.items())
        # set2 = set(newcfg.items())
        # logger.debug(f"CONTROL ^: {set1 ^ set2}")
        # logger.debug(f"CONTROL >: {set1 - set2}")
        # logger.debug(f"CONTROL <: {set2 - set1}")

        logger.debug(f"livery {livery}: suggested config file:")
        logger.debug(f"\n----- livery {livery}\n" + "\n".join([f"{k} = {v}" for k, v in newcfg.items()]) + f":\n-----")
        newfn = join(d, NEW_CONFIG)
        with open(newfn, "w") as fp:
            fp.write("\n".join([f"{k} = {v}" for k, v in newcfg.items()]))
            logger.info(f"livery {livery}: generated {newfn.replace(AC_PATH, '..')}")

    # Report livery-level missing icons
    if do_livery_icons:
        for ac in acfn:
            ac1 = ac.replace(".acf", "_icon11.png")
            thm = join(d, ac1)
            if not exists(thm):
                logger.warning(f"livery {livery}: icon file for {ac} has no icon")
            ac1 = ac.replace(".acf", "_icon11_thumb.png")
            thm = join(d, ac1)
            if not exists(thm):
                logger.warning(f"livery {livery}: icon file for {ac} has no thumb icon")

    logger.debug("<" * 20)


# Aircraft-level icons
for ac in acfn:
    ac1 = ac.replace(".acf", "_icon11.png")
    thm = join(AC_PATH, ac1)
    if not exists(thm):
        logger.warning(f"Aircraft {ac} has no icon")
    ac1 = ac.replace(".acf", "_icon11_thumb.png")
    thm = join(AC_PATH, ac1)
    if not exists(thm):
        logger.warning(f"Aircraft {ac} has no thumb icon")

logger.info("do not forget to set all aircraft parameter values to AUTO in ISCS/AC CONFIG panel")
# import re
# STRING = "^\\[((?P<engine>IAE|CFM){0,1}|(?P<sharklet>S){0,1}|(?P<satcom>T){0,1}|(.))*\\]"
# tests = ["[IAES]", "[S]", "[ST]", "[TS]", "[TSIAE]", "[St]", "[NEOS]", "[ARRDEP]"]
# for t in tests:
#     m = re.match(STRING, t)
#     print(t, [m.group(i) for i in ["engine", "sharklet", "satcom"]])
#     # print(m)
