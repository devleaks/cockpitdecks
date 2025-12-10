import logging
from pprint import pprint

import cerberus
import ruamel
from ruamel.yaml import YAML
from ruamel.yaml.compat import StringIO

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
yaml = YAML(typ="safe", pure=True)
yaml.default_flow_style = False
yaml.sort_keys = False


def beatiful(data_in):
    def tr(n):
        v = data_in.get(n)
        if v is not None:
            data[n] = v

    data = {}
    # 1. General, index, name, etc.
    for attr in ["index", "name", "type"]:
        tr(attr)

    # 2. Activation
    # Type copied above...
    activation = data_in["type"]
    activation_schema = ACTIVATION_SCHEMAS[activation]
    for attr in activation_schema.keys():
        tr(attr)

    # 3. Representation
    for attr in ["label", "label-font", "label-color", "label-size", "label-position"]:
        tr(attr)

    # output yaml string
    stream = StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


def check_font(field, value, error):
    if value not in ["DIN", "B612"]:
        error(field, "Must be DIN or B612")


DOCUMENT = """
buttons:
  - index: 0
    type: push
    command:
        command: AirbusFBW/CaptChronoButton
        delay: 2
        condition: formula
    label: CHRONO
    label-size: 10
    sound: sonar-ping.wav
    push-switch:
      button-size: 120
      button-fill-color: black
      button-stroke-width: 0
      button-underline-color: coral
      witness-size: 0
      down: 36
  - index: 1
    name: ND MODE
    type: updown
    stops: 5
    initial-value: 2
    circular-switch:
      button-size: 50
      switch-style: medium
      down: 30
      tick-from: 90
      tick-to: 270
      tick-space: 40
      tick-underline-width: 8
      # tick-color: white
      # tick-underline-color: white
      needle-color: white
      needle-length: 30
      tick-label-size: 28
      tick-labels:
        - LS
        - VOR
        - NAV
        - ARC
        - PLAN
    commands:
      - sim/instruments/EFIS_mode_up
      -
        command: AirbusFBW/CaptChronoButton
        delay: 2
        condition: formula
    dataref: AirbusFBW/NDmodeCapt
  - index: 5
    name: FD 1
    type: push
    annunciator:
      size: medium
      model: B
      parts:
        B0:
          color: lime
          led: bars
          formula: ${AirbusFBW/FD1Engage}
        B1:
          text: FD
          color: white
          text-size: 64
          text-font: DIN Bold
          formula: "1"
    command: toliss_airbus/fd1_push
"""

SCHEMA = """---
index:
  required: true
  type:
  - integer
  - string
name:
  type: string
label:
  type: string
label-color:
  type: color
label-font:
  type: string
label-position:
  allowed:
  - lt
  - ct
  - rt
  - lm
  - cm
  - rm
  - lb
  - cb
  - rb
  type: string
label-size:
  type: integer
sound:
  type: sound
type:
  required: true
  type: string
command:
  oneof:
  - type: string
  - type: dict
    schema:
      command:
        type: string
      condition:
        type: string
      delay:
        type: integer
commands:
  type: list
  schema:
      oneof:
      - type: string
      - type: dict
        schema:
          command:
            type: string
          condition:
            type: string
          delay:
            type: integer
stops:
  type: integer
initial-value:
  type: integer
dataref:
  type: string
"""


annunciator_schema = """---
size:
  type: string
  allowed: [small, medium, large, full]
model:
  type: string
  regex: '[A-F]+'
parts:
  type: dict
  keysrules:
    type: string
    regex: '[A-F]+[0-3]+'
  valuesrules:
    type: dict
    oneof:
      - schema:
            color:
                type: string
            led:
                type: string
            formula:
                type: string
      - schema:
            color:
                type: string
            text:
                type: string
            text-font:
                type: string
            text-size:
                type: integer
            text-color:
                type: string
            framed:
                type: boolean
            formula:
                type: string
"""

document = yaml.load(DOCUMENT)
schema = yaml.load(SCHEMA)

representation_schema = yaml.load(annunciator_schema)
representation = "annunciator"

# pprint(representation_schema)

representation_attributes = [
    "push-switch",
    "circular-switch",
    "button-size",
    "button-fill-color",
    "button-stroke-width",
    "button-underline-color",
    "witness-size",
    "down",
    "switch-style",
    "tick-from",
    "tick-to",
    "tick-space",
    "tick-underline-width",
    "needle-color",
    "needle-length",
    "tick-label-size",
    "tick-labels",
]

valid_unknown = {"type": "dict", "allowed": representation_attributes}

color_type = cerberus.TypeDefinition("color", (str, tuple, list), ())
cerberus.Validator.types_mapping["color"] = color_type
sound_type = cerberus.TypeDefinition("sound", (str,), ())
cerberus.Validator.types_mapping["sound"] = sound_type

v = cerberus.Validator(schema, allow_unknown=valid_unknown)  # , allow_unknown=True
vr = cerberus.Validator(representation_schema)
for b in document["buttons"]:
    if not v.validate(b):
        print("index", b["index"], v.errors)
    else:
        print("index", b["index"], "validate ok")
        print("---")
        print(beatiful(v.normalized(b)))
        print("---")
        # pprint(v.normalized(b))
        # print(v.normalized(document))
    if representation in b:
        if not vr.validate(b[representation]):
            print("index", b["index"], "representation", vr.errors)
        else:
            print("index", b["index"], "representation validate ok")
            # print(v.normalized(document))
