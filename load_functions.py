import os
import yaml

from streamdecks.constant import CONFIG_DIR, CONFIG_FILE, DEFAULT_LAYOUT

# CONFIG_DIR = "esdconfig"
# CONFIG_FILE = "config.yaml"
# DEFAULT_LAYOUT = "default"

def get_beginend_commands(acpath):
    # Constants
    BUTTONS = "buttons"  # keywork in yaml file
    DECKS = "decks"
    LAYOUT = "layout"
    COMMAND = "command"
    MULTI_COMMANDS = "commands"
    NOTICABLE_BUTTON_TYPES = ["dual"]

    commands = []

    config_fn = os.path.join(acpath, CONFIG_DIR, CONFIG_FILE)
    if os.path.exists(config_fn):
        with open(config_fn, "r") as config_fp:
            config = yaml.safe_load(config_fp)
            if DECKS in config:
                for deck in config[DECKS]:
                    layout = DEFAULT_LAYOUT
                    if LAYOUT in deck:
                        layout = deck[LAYOUT]
                    layout_dn = os.path.join(acpath, CONFIG_DIR, layout)
                    if not os.path.exists(layout_dn):
                        print(f"load: stream deck has no layout folder '{layout}'")
                        continue
                    pages = os.listdir(layout_dn)
                    for page in pages:
                        if page.endswith("yaml") or page.endswith("yml"):
                            page_fn = os.path.join(layout_dn, page)
                            if os.path.exists(page_fn):
                                with open(page_fn, "r") as page_fp:
                                    page_def = yaml.safe_load(page_fp)
                                    if not BUTTONS in page_def:
                                        print(f"load: {page_fn} has no action")
                                        continue
                                    for button_def in page_def[BUTTONS]:
                                        bty = None
                                        if "type" in button_def:
                                            bty = button_def["type"]
                                        if bty in NOTICABLE_BUTTON_TYPES:
                                            if COMMAND in button_def:
                                                commands.append(button_def[COMMAND])
                                            if MULTI_COMMANDS in button_def:
                                                for c in button_def[MULTI_COMMANDS]:
                                                    commands.append(c)
                            else:
                                print(f"load: file {page_fn} not found")
                        else:  # not a yaml file
                            print(f"load: ignoring file {page}")
    else:
        print(f"load: no config file {config_fn}")
    return commands

# test
print(get_beginend_commands("A321"))