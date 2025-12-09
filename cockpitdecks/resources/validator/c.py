import logging
from typing import Tuple, List

import ruamel
from ruamel.yaml import YAML

import cerberus

ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True

yaml = YAML(typ="safe", pure=True)
yaml.default_flow_style = False

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


# List to have
# Globals:
#  Fonts
#  Icons
# Per button:
#  Activations
#  Representations

# Activation -> Activation schema
# Representation -> Representation schema

color_type = cerberus.TypeDefinition("color", (str, tuple, list), ())
cerberus.Validator.types_mapping["color"] = color_type


def mk_text(prefix):
    return {
        prefix: {"type": "string"},
        prefix + "-font": {"type": "string", "check_with": check_font},
        prefix + "-color": {"type": "color"},
        prefix + "-size": {"type": "integer"},
        prefix + "-position": {"type": "string", "allowed": ["lt", "ct", "rt", "lm", "cm", "rm", "lb", "cb", "rb"]},
    }


def check_font(field, value, error):
    if value not in ["DIN", "B612"]:
        error(field, "Must be DIN or B612")


BUTTON_SCHEMA = {
    "index": {"required": True, "type": ["integer", "string"]},
    "name": {"type": "string"},
    "type": {"required": True, "type": "string"},
    # "commands": {"type": "list", "anyof": [
    #     {"schema": {"type": "string"}},
    #     {"schema": {
    #         "command": {"type": "string"},
    #         "delay": {"type": "string"},
    #         "condition": {"type": "string"},
    #     }},
    # ]}
}

CMD1 = {
    "commands": {"type": "list", "schema": {"type": "string"}}
}

CMD2 = {
    "commands": {"type": "list", "schema": {
        "command": {"type": "string"},
        "delay": {"type": "string"},
        "condition": {"type": "string"},
    }}
}

BUTTON_SCHEMA = BUTTON_SCHEMA | mk_text("label") | CMD1

# PAGE_SCHEMA = {
#     "aircraft": {"type": "string"},
#     "version": {"type": "string"},
#     "last-updated": {"type": "string"},
#     "buttons": {"required": True, "type": "list", "schema": {"type": "dict", "schema": BUTTON_SCHEMA}},
# }


document = {}
with open("index.yaml", "r") as fp:
    document = yaml.load(fp)

# print(document)

# # type Font = str
# # type Color = str | Tuple[int] | List[int]
# # color_type = cerberus.TypeDefinition('color', (Color,), ())
# # Validator.types_mapping['color'] = color_type

# v = cerberus.Validator(PAGE_SCHEMA, allow_unknown=True)

# if not v.validate(document):
#     print(v.errors)
# else:
#     print("validate ok")
#     # print(v.normalized(document))


v = cerberus.Validator(BUTTON_SCHEMA, allow_unknown=True)
for b in document["buttons"]:
    if not v.validate(b):
        print(b["index"], v.errors)
    else:
        print(b["index"], "validate ok")
        # print(v.normalized(document))

        # b[type] -> Activation schema
        # va = cerberus.Validator(Activation schema, allow_unknown=True)
        # if not va.validate(b):
        #     print(va.errors)

        # b[representation] -> Representation schema
        # vr = cerberus.Validator(Representation schema, allow_unknown=True)
        # if not vr.validate(b[representation]):
        #     print(vr.errors)
