# PARAMETERS

# ######################
# REPRESENTATIONS
#
# Common blocks

SCHEMA_LABEL = {
    "label": {"type": "string", "meta": {"label": "Label"}},
    "label-size": {"type": "integer", "meta": {"label": "Lbl size"}},
    "label-font": {"type": "font", "meta": {"label": "Lbl font", "default": "DIN.ttf"}},
    "label-position": {"type": "string", "meta": {"label": "Lbl position"}, "allowed": ["lt", "ct", "rt", "lm", "cm", "rm", "lb", "cb", "rb"]},
    "label-color": {"type": "color", "meta": {"label": "Lbl color"}},
}

SCHEMA_TEXT = {
    "text": {"type": "string", "meta": {"label": "Text"}},
    "text-font": {"type": "font", "meta": {"label": "Font"}},
    "text-size": {"type": "integer", "meta": {"label": "Size"}},
    "text-color": {"type": "color", "meta": {"label": "Color"}},
    "text-position": {"type": "choice", "meta": {"label": "Position"}, "choices": ["lt", "ct", "rt", "lm", "cm", "rm", "lb", "cb", "rb"]},
}

SCHEMA_CHART_DATA = {
    "name": {"type": "string", "meta": {"label": "Name"}},
    "type": {
        "type": "string",
        "meta": {"label": "Type"},
        "allowed": [
            "bar",
        ],
    },
    "rate": {"type": "bool", "meta": {"label": "Rate?"}},
    "keep": {"type": "integer", "meta": {"label": "Keep"}},
    "update": {"type": "float", "meta": {"label": "Update rate (secs)"}},
    "value-min": {"type": "integer", "meta": {"label": "Min"}},
    "value-max": {"type": "integer", "meta": {"label": "Max"}},
    "color": {"type": "color", "meta": {"label": "Color"}},
    "marker": {"type": "string", "meta": {"label": "Marker"}, "allowed": ["square"]},
    "marker-color": {"meta": {"label": "Marker Color"}, "type": "color"},
    "dataref": {"type": "string", "meta": {"label": "Data"}},
}

# Button Drawing Parameters, loosely grouped per button type

SCHEMA_BTN_COMMON = {
    "button-fill-color": {"meta": {"label": "Button Fill Color"}, "type": "color"},
    "button-size": {"meta": {"label": "Button Size"}, "type": "integer"},
    "button-stroke-color": {"meta": {"label": "Button Stroke Color"}, "type": "color"},
    "button-stroke-width": {"meta": {"label": "Button Stroke Width"}, "type": "integer"},
    "button-underline-color": {"meta": {"label": "Button Underline Color"}, "type": "color"},
    "button-underline-width": {"meta": {"label": "Button Underline Width"}, "type": "integer"},
    "base-fill-color": {"meta": {"label": "Base Fill Color"}, "type": "color"},
    "base-stroke-color": {"meta": {"label": "Base Stroke Color"}, "type": "color"},
    "base-stroke-width": {"meta": {"label": "Base Stroke Width"}, "type": "integer"},
    "base-underline-color": {"meta": {"label": "Base Underline Color"}, "type": "color"},
    "base-underline-width": {"meta": {"label": "Base Underline Width"}, "type": "integer"},
    "handle-fill-color": {"meta": {"label": "Handle Fill Color"}, "type": "color"},
    "handle-stroke-color": {"meta": {"label": "Handle Stroke Color"}, "type": "color"},
    "handle-stroke-width": {"meta": {"label": "Handle Stroke Width"}, "type": "integer"},
    "top-fill-color": {"meta": {"label": "Top Fill Color"}, "type": "color"},
    "top-stroke-color": {"meta": {"label": "Top Stroke Color"}, "type": "color"},
    "top-stroke-width": {"meta": {"label": "Top Stroke Width"}, "type": "integer"},
    "tick-color": {"meta": {"label": "Tick Color"}, "type": "color"},
    "tick-from": {"meta": {"label": "Tick From"}, "type": "string"},
    "tick-labels": {"type": "sub", "list": {"-label": {"type": "string", "meta": {"label": "Lbl txt"}}}, "min": 1, "max": 0},
    "tick-label-color": {"meta": {"label": "Tick Label Color"}, "type": "color"},
    "tick-label-size": {"meta": {"label": "Tick Label Size"}, "type": "integer"},
    "tick-label-space": {"meta": {"label": "Tick Label Space"}, "type": "string"},
    "tick-length": {"meta": {"label": "Tick Length"}, "type": "integer"},
    "tick-space": {"meta": {"label": "Tick Space"}, "type": "string"},
    "tick-to": {"meta": {"label": "Tick To"}, "type": "string"},
    "tick-underline-color": {"meta": {"label": "Tick Underline Color"}, "type": "color"},
    "tick-underline-width": {"meta": {"label": "Tick Underline Width"}, "type": "integer"},
    "tick-width": {"meta": {"label": "Tick Width"}, "type": "integer"},
    "needle-color": {"meta": {"label": "Needle Color"}, "type": "color"},
    "needle-length": {"meta": {"label": "Needle Length"}, "type": "integer"},
    "needle-start": {"meta": {"label": "Needle Start"}, "type": "string"},
    "needle-tip-size": {"meta": {"label": "Needle Tip Size"}, "type": "integer"},
    "needle-underline-color": {"meta": {"label": "Needle Underline Color"}, "type": "color"},
    "needle-underline-width": {"meta": {"label": "Needle Underline Width"}, "type": "integer"},
    "needle-width": {"meta": {"label": "Needle Width"}, "type": "integer"},
}

SCHEMA_BTN_SWITCH = {
    "switch-handle-dot-color": {"meta": {"label": "Switch Handle Dot Color"}, "type": "color"},
    "switch-length": {"meta": {"label": "Switch Length"}, "type": "integer"},
    "switch-style": {"meta": {"label": "Switch Style"}, "type": "string"},
    "switch-width": {"meta": {"label": "Switch Width"}, "type": "integer"},
}

SCHEMA_BTN_CIRCULAR_SWITCH = {}

SCHEMA_BTN_PUSH = {
    "witness-fill-color": {"meta": {"label": "Witness Fill Color"}, "type": "color"},
    "witness-fill-off-color": {"meta": {"label": "Witness Fill Off Color"}, "type": "color"},
    "witness-size": {"meta": {"label": "Witness Size"}, "type": "integer"},
    "witness-stroke-color": {"meta": {"label": "Witness Stroke Color"}, "type": "color"},
    "witness-stroke-off-color": {"meta": {"label": "Witness Stroke Off Color"}, "type": "color"},
    "witness-stroke-off-width": {"meta": {"label": "Witness Stroke Off Width"}, "type": "integer"},
    "witness-stroke-width": {"meta": {"label": "Witness Stroke Width"}, "type": "integer"},
}

SCHEMA_BTN_KNOB = {
    "button-dent-extension": {"meta": {"label": "Button Dent Extension"}, "type": "string"},
    "button-dent-negative": {"meta": {"label": "Button Dent Negative"}, "type": "string"},
    "button-dent-size": {"meta": {"label": "Button Dent Size"}, "type": "integer"},
    "button-dents": {"meta": {"label": "Button Dents"}, "type": "string"},
    "knob-mark": {"meta": {"label": "Knob Mark"}, "type": "string"},
    "knob-type": {"meta": {"label": "Knob Type"}, "type": "string"},
    "mark-underline-color": {"meta": {"label": "Mark Underline Color"}, "type": "color"},
    "mark-underline-outer": {"meta": {"label": "Mark Underline Outer"}, "type": "string"},
    "mark-underline-width": {"meta": {"label": "Mark Underline Width"}, "type": "integer"},
}

# aircraft
# annunciator
# annunciator-animate
# chart
# colored-led
# data
# decor
# draw-animation
# draw-base
# icon
# icon-animation
# icon-color
# led
# multi-icons
# multi-texts
# none
# text

# special:
# ftg
# solari
# virtual-led
# virtual-encoder
# weather-base
# weather-metar
# weather-real
# weather-xp
# textpage

# TO DO

# knob
# circular-switch
# push-switch
# switch
# switch-base

# special
# encoder-leds
# fcu
# fma
# side
