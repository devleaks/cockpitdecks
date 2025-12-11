    SCHEMA = {
        "icon": {"type": "icon", "meta": {"label": "Icon"}},
        "model": {"type": "string", "meta": {"label": "Type"}, "allowed": ["A", "B", "C", "D", "E", "F"]},
        "size": {"type": "string", "allowed": ["small", "medium", "large", "full"], "meta": {"label": "Size"}},
        # "style": {"type": "string", "meta": {"label": "Style"}, "lov": ["Korry", "Vivisun"]},
        # "color": {"type": "color", "meta": {"label": "Background color"}},
        # "texture": {"type": "icon", "meta": {"label": "Background texture"}},
        "annunciator-color": {"meta": {"label": "Annunciator Color"}, "type": "color"},
        "annunciator-style": {"meta": {"label": "Annunciator Style"}, "type": "string", "allowed": ["Korry", "K", "Vivisun", "V"]},
        "annunciator-texture": {"meta": {"label": "Annunciator Texture"}, "type": "icon"},
        "light-off-intensity": {"meta": {"label": "Light Off Intensity"}, "type": "string"},
        "oneof": [
            {
                "text": {"type": "string", "meta": {"label": "Text"}},
                "text-font": {"type": "font", "meta": {"label": "Font"}},
                "text-size": {"type": "integer", "meta": {"label": "Size"}},
                "text-color": {"type": "color", "meta": {"label": "Color"}},
                "text-bg-color": {"type": "color", "meta": {"label": "Background color"}},
                "text-position": {"type": "string", "meta": {"label": "Position"}, "allowed": ["lt", "ct", "rt", "lm", "cm", "rm", "lb", "cb", "rb"]},
            },{
                "parts": {
                    "meta": {"label": "Parts"},
                    "type": "dict",
                    "keysrules": {"type": "string", "regex": "[A-F]+[0-3]+"},
                    "valuesrules": {
                        "type": "dict",
                        "oneof": [
                            {  # schema for LED part: Bar, block, landing gear triangle...
                                "schema": {
                                    "formula": {"type": "string"},
                                    "dataref": {"type": "string"},
                                    "color": {"type": "color"},
                                    "led": {"type": "string", "allowed": [l.value for l in ANNUNCIATOR_LED]},
                                }
                            },
                            {  # schema for TEXT part, like ON, OFF, DISCH...
                                "schema": {
                                    "formula": {"type": "string"},
                                    "dataref": {"type": "string"},
                                    "text": {"type": "string", "meta": {"label": "Text"}},
                                    "text-font": {"type": "font", "meta": {"label": "Font"}},
                                    "text-size": {"type": "integer", "meta": {"label": "Size"}},
                                    "text-bg-color": {"type": "color", "meta": {"label": "Background color"}},
                                    "text-color": {"type": "color", "meta": {"label": "Color"}},
                                    "text-position": {
                                        "type": "string",
                                        "meta": {"label": "Position"},
                                        "allowed": ["lt", "ct", "rt", "lm", "cm", "rm", "lb", "cb", "rb"],
                                    },
                                    "framed": {"type": "boolean", "meta": {"label": "Framed"}},
                                }
                            },
                        ],
                    },  # parts (value)
                },  # parts
            }
        ],
    }

