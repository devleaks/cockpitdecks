# PARAMETERS

# ######################
# REPRESENTATIONS
#
# Common blocks

PARAM_TEXT = {
    "text": {"type": "string", "prompt": "Text"},
    "text-font": {"type": "font", "prompt": "Font"},
    "text-size": {"type": "integer", "prompt": "Size"},
    "text-color": {"type": "color", "prompt": "Color"},
    "text-position": {"type": "choice", "prompt": "Position", "choices": ["lt", "ct", "rt", "lm", "cm", "rm", "lb", "cb", "rb"]},
}

PARAM_CHART_DATA = {
    "name": {"type": "string", "prompt": "Name"},
    "type": {
        "type": "string",
        "prompt": "Type",
        "lov": [
            "bar",
        ],
    },
    "rate": {"type": "bool", "prompt": "Rate?"},
    "keep": {"type": "integer", "prompt": "Keep"},
    "update": {"type": "float", "prompt": "Update rate (secs)"},
    "value-min": {"type": "integer", "prompt": "Min"},
    "value-max": {"type": "integer", "prompt": "Max"},
    "color": {"type": "color", "prompt": "Color"},
    "marker": {"type": "string", "prompt": "Marker", "lov": ["square"]},
    "marker-color": {"label": "Marker Color", "type": "color"},
    "dataref": {"type": "string", "prompt": "Data"},
}

# Button Drawing Parameters, loosely grouped per button type

PARAM_BTN_COMMON = {
    "button-fill-color": {"label": "Button Fill Color", "type": "color"},
    "button-size": {"label": "Button Size", "type": "int"},
    "button-stroke-color": {"label": "Button Stroke Color", "type": "color"},
    "button-stroke-width": {"label": "Button Stroke Width", "type": "int"},
    "button-underline-color": {"label": "Button Underline Color", "type": "color"},
    "button-underline-width": {"label": "Button Underline Width", "type": "int"},
    "base-fill-color": {"label": "Base Fill Color", "type": "color"},
    "base-stroke-color": {"label": "Base Stroke Color", "type": "color"},
    "base-stroke-width": {"label": "Base Stroke Width", "type": "int"},
    "base-underline-color": {"label": "Base Underline Color", "type": "color"},
    "base-underline-width": {"label": "Base Underline Width", "type": "int"},
    "handle-fill-color": {"label": "Handle Fill Color", "type": "color"},
    "handle-stroke-color": {"label": "Handle Stroke Color", "type": "color"},
    "handle-stroke-width": {"label": "Handle Stroke Width", "type": "int"},
    "top-fill-color": {"label": "Top Fill Color", "type": "color"},
    "top-stroke-color": {"label": "Top Stroke Color", "type": "color"},
    "top-stroke-width": {"label": "Top Stroke Width", "type": "int"},
    "tick-color": {"label": "Tick Color", "type": "color"},
    "tick-from": {"label": "Tick From", "type": "string"},
    "tick-labels": {"type": "sub", "list": {"-label": {"type": "string", "label": "Lbl txt"}}, "min": 1, "max": 0},
    "tick-label-color": {"label": "Tick Label Color", "type": "color"},
    "tick-label-size": {"label": "Tick Label Size", "type": "int"},
    "tick-label-space": {"label": "Tick Label Space", "type": "string"},
    "tick-length": {"label": "Tick Length", "type": "int"},
    "tick-space": {"label": "Tick Space", "type": "string"},
    "tick-to": {"label": "Tick To", "type": "string"},
    "tick-underline-color": {"label": "Tick Underline Color", "type": "color"},
    "tick-underline-width": {"label": "Tick Underline Width", "type": "int"},
    "tick-width": {"label": "Tick Width", "type": "int"},
    "needle-color": {"label": "Needle Color", "type": "color"},
    "needle-length": {"label": "Needle Length", "type": "int"},
    "needle-start": {"label": "Needle Start", "type": "string"},
    "needle-tip-size": {"label": "Needle Tip Size", "type": "int"},
    "needle-underline-color": {"label": "Needle Underline Color", "type": "color"},
    "needle-underline-width": {"label": "Needle Underline Width", "type": "int"},
    "needle-width": {"label": "Needle Width", "type": "int"},
}

PARAM_BTN_SWITCH = {
    "switch-handle-dot-color": {"label": "Switch Handle Dot Color", "type": "color"},
    "switch-length": {"label": "Switch Length", "type": "int"},
    "switch-style": {"label": "Switch Style", "type": "string"},
    "switch-width": {"label": "Switch Width", "type": "int"},
}

PARAM_BTN_CIRCULAR_SWITCH = {}

PARAM_BTN_PUSH = {
    "witness-fill-color": {"label": "Witness Fill Color", "type": "color"},
    "witness-fill-off-color": {"label": "Witness Fill Off Color", "type": "color"},
    "witness-size": {"label": "Witness Size", "type": "int"},
    "witness-stroke-color": {"label": "Witness Stroke Color", "type": "color"},
    "witness-stroke-off-color": {"label": "Witness Stroke Off Color", "type": "color"},
    "witness-stroke-off-width": {"label": "Witness Stroke Off Width", "type": "int"},
    "witness-stroke-width": {"label": "Witness Stroke Width", "type": "int"},
}

PARAM_BTN_KNOB = {
    "button-dent-extension": {"label": "Button Dent Extension", "type": "string"},
    "button-dent-negative": {"label": "Button Dent Negative", "type": "string"},
    "button-dent-size": {"label": "Button Dent Size", "type": "int"},
    "button-dents": {"label": "Button Dents", "type": "string"},
    "knob-mark": {"label": "Knob Mark", "type": "string"},
    "knob-type": {"label": "Knob Type", "type": "string"},
    "mark-underline-color": {"label": "Mark Underline Color", "type": "color"},
    "mark-underline-outer": {"label": "Mark Underline Outer", "type": "string"},
    "mark-underline-width": {"label": "Mark Underline Width", "type": "int"},
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
