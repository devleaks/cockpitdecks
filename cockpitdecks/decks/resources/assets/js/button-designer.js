/* Button generator
 * 
 */
DEFAULT_ICON = "NONE.png"
DEFAULT_FONT = "DIN.ttf"
DEFAULT_SIZE = 32
DEFAULT_POSITION = "tm"

NONE = "none"  // keyword

LABEL_PARAMETERS = {
    "label": {
        "type": "string",
        "prompt": "Text"
    },
    "label-font": {
        "type": "font",
        "prompt": "Font",
        "default-value": DEFAULT_FONT
    },
    "label-size": {
        "type": "integer",
        "prompt": "Size"
    },
    "label-color": {
        "type": "string",
        "prompt": "Color"
    },
    "label-position": {
        "type": "choice",
        "prompt": "Position",  // left, center, right, top, middle, botton
        "choices": ["lt", "ct", "rt", "lm", "cm", "rm", "lb", "cb", "rb"],
        "default-value": "ct"
    },
}

// Form
//
function toTitleCase(str) {
  return str.replace(
    /\w\S*/g,
    text => text.charAt(0).toUpperCase() + text.substring(1).toLowerCase()
  );
}

// document.getElementById("edName").attributes["required"] = "";
function add_elem(name, e, container) {
    switch(e.type) {
    case "string":
        if (e.repeat != undefined) {
            if (e.prompt != undefined) {
                var prompts = Array(e.repeat).fill(e.prompt)
            } else {
                var prompts = e.prompts
            }
            for (let i = 0; i < e.repeat; i++) {
                var el = document.createElement("label");
                el.innerHTML = prompts[i];
                container.appendChild(el);
                var el = document.createElement("input");
                el.name = name+"["+i+"]"
                el.type = "text";
                el.size = 40;
                if (e.mandatory == true) {
                    console.log("required", el.name)
                    el.attributes["required"] = "";
                }
                container.appendChild(el);
                container.appendChild(document.createElement("br"));
            }
        } else {
            var el = document.createElement("label");
            el.innerHTML = e.prompt;
            container.appendChild(el);
            var el = document.createElement("input");
            el.name = name;
            el.type = "text";
            el.size = 40;
            if (e.mandatory == true) {
                console.log("required", el.name)
                el.attributes["required"] = "";
            }
            container.appendChild(el);
            container.appendChild(document.createElement("br"));
        }
        break;
    case "integer":
        var el = document.createElement("label");
        el.innerHTML = e.prompt;
        container.appendChild(el);
        var el = document.createElement("input");
        el.name = name;
        el.type = "text";
        el.size = 10;
        if (e.mandatory == true) {
            console.log("required", el.name)
            el.attributes["required"] = "";
        }
        container.appendChild(el);
        container.appendChild(document.createElement("br"));
        break;
    case "float":
        var el = document.createElement("label");
        el.innerHTML = e.prompt;
        container.appendChild(el);
        var el = document.createElement("input");
        el.name = name;
        el.type = "text";
        el.size = 16;
        if (e.mandatory == true) {
            console.log("required", el.name)
            el.attributes["required"] = "";
        }
        container.appendChild(el);
        container.appendChild(document.createElement("br"));
        break;
    case "boolean":
        var el = document.createElement("label");
        el.innerHTML = e.prompt;
        container.appendChild(el);
        var el = document.createElement("input");
        el.name = name;
        el.type = "checkbox";
        if (e.mandatory == true) {
            console.log("required", el.name)
            el.attributes["required"] = "";
        }
        container.appendChild(el);
        container.appendChild(document.createElement("br"));
        break;
    case "choice":
        var el = document.createElement("label");
        el.innerHTML = e.prompt;
        container.appendChild(el);
        var el = document.createElement("select");
        el.name = name;
        container.appendChild(el);
        e.choices.sort().forEach((c)=>{
            var opt = document.createElement("option");
            opt.value = c;
            opt.innerHTML = c;
            el.appendChild(opt);
        });
        if (e.choices.indexOf(e["default-value"]) > 0) {
            el.value = e["default-value"]
        }
        if (e.mandatory == true) {
            console.log("required", el.name)
            el.attributes["required"] = "";
        }
        container.appendChild(document.createElement("br"));
        break;
    case "font":
        var el = document.createElement("label");
        el.innerHTML = e.prompt;
        container.appendChild(el);
        var el = document.createElement("select");
        el.name = name;
        container.appendChild(el);
        ASSETS.fonts.sort().forEach((c)=>{
            var opt = document.createElement("option");
            opt.value = c;
            opt.innerHTML = c;
            el.appendChild(opt);
        });
        el.value = DEFAULT_FONT
        container.appendChild(document.createElement("br"));
        break;
    case "icon":
        var el = document.createElement("label");
        el.innerHTML = e.prompt;
        container.appendChild(el);
        var el = document.createElement("select");
        el.name = name;
        container.appendChild(el);
        ASSETS.icons.sort().forEach((c)=>{
            var opt = document.createElement("option");
            opt.value = c;
            opt.innerHTML = c;
            el.appendChild(opt);
        });
        el.value = DEFAULT_ICON
        container.appendChild(document.createElement("br"));
        break;
    case "multi":
        var lbl = document.createElement("fieldset");
        var l = document.createElement("legend");
        l.innerHTML = e.prompt;
        lbl.appendChild(l);
        container.appendChild(lbl);
        makeForm(e.multi, lbl, false)
        // create add button to add as many as necessary
        var el = document.createElement("button");
        el.innerHTML = "Add";
        el.onclick = (event) => {
            event.preventDefault();
            makeForm(e.multi, lbl, false)
            lbl.appendChild(document.createElement("br"));
            return false;
        };
        lbl.appendChild(el);
        lbl.appendChild(document.createElement("br"));
        break;
    }
}

function makeForm(elements, container, add_label, first) {
    if (add_label === false && first == undefined) {
        cleanElement(container);
    }
    if (add_label !== false && first == undefined) { // make labels (always)
        cleanElement(container);
        if (add_label == "none") {
            return;
        }

        // Label, almost always present, framed in fieldset
        var lbl = document.createElement("fieldset");
        var l = document.createElement("legend");
        l.innerHTML = "Label";
        lbl.appendChild(l);
        container.appendChild(lbl);
        makeForm(LABEL_PARAMETERS, lbl, add_label, true)

        // Other elements (framed in fieldset)
        var el = document.createElement("fieldset");
        var l = document.createElement("legend");
        l.innerHTML = toTitleCase(add_label.replace(/-/g, " "))
        el.appendChild(l);
        container.appendChild(el);
        makeForm(elements, el, add_label, true)
        return;
    }

    // Other elements (raw)
    for (var name in elements) {
        if ( ! elements.hasOwnProperty(name) ) {
            continue;
        }
        let e = elements[name];
        // console.log("e", name, e);
        add_elem(name, e, container);
    }
}

// Yaml
//
// Utility functions
//
function has_value(v) {
    return v != undefined && v != ""
}

function add(name, value, indent) {
    if (value != undefined && value !== "") {
        if (name == "font" && value==DEFAULT_FONT) {
            return ""
        }
        if (name.endsWith("-size") && value==DEFAULT_SIZE) {
            return ""
        }
        if (name.endsWith("-position") && value==DEFAULT_POSITION) {
            return ""
        }
        return "\n" + Array(indent).fill("  ").join("") + name + ": " + value
    } else {
        return ""
    }
}

function check_elem(name, elem, data, indent) {
    if(data[name] != undefined) {
        if (elem["default-value"] != undefined) {
            if (data[name] != elem["default-value"] && data[name] != "") {
                return add(name, data[name], indent);
            }
        } else if (data[name] != "") {
            return add(name, data[name], indent);
        }
    }
    return ""
}

function generateYaml(data, act_params, rep_params) {
    function remaining(current, spaces) {
        for (var name in rep_params) {
            if ( ! rep_params.hasOwnProperty(name) || name == current) {
                continue;
            }
            let e = rep_params[name];
            // console.log("r", name, e);
            code += check_elem(name, e, data, spaces);
        }
    }
    var code = ""
    var indent = 0

    code += add("index", data.index, indent);
    code += add("name", data.name, indent);

    // label
    if (has_value(data.view) && data.view != NONE) {
        if (has_value(data.label)) {
            for (var name in LABEL_PARAMETERS) {
                if ( ! LABEL_PARAMETERS.hasOwnProperty(name) ) {
                    continue;
                }
                code += check_elem(name, LABEL_PARAMETERS[name], data, indent); // add(l, data[l], indent);
            }
        }
    }

    // activation parameters
    code += add("type", data.type, indent);
    if (has_value(data.type) && data.type != NONE) {
        for (var name in act_params) {
            if ( ! act_params.hasOwnProperty(name) ) {
                continue;
            }
            let e = act_params[name];
            // console.log("a", name, e);
            code += check_elem(name, e, data, indent);
        }
    }

    // representation parameters
    if (has_value(data.view) && data.view != "" && data.view != NONE) {

        switch(data.view) {
        // icon
        // text
        case "icon":
        case "text":
            code += add(data.view, data[data.view], indent)
            remaining(data.view, indent)
            break;
        // icon-color
        case "icon-color":
            code += add(data.view, data["color"], indent)
            remaining(data.view, indent)
            break;
        // aircraft
        // annunciator
        // annunciator-animate
        // circular-switch
        // colored-led
        // data
        // decor
        // draw-animation
        // draw-base
        // encoder-leds
        // fcu
        // fma
        // ftg
        // hardware-icon
        // icon-animation
        // knob
        // led
        // multi-icons
        // multi-texts
        // none
        // push-switch
        // side
        // switch
        // switch-base
        // virtual-encoder
        // virtual-led
        // virtual-ll-coloredbutton
        // virtual-sd-neoled
        // virtual-xtm-encoderled
        // virtual-xtm-led
        // virtual-xtm-mcled
        // weather-base
        // weather-metar
        // weather-real
        // weather-xp
        default:
            code += add(data.view, data[data.view], indent)
            // code += "\n" + data.view + ":";
            // indent += 1
            // remaining(data.view, indent)
            break;
        }

    } else {
        code += add("representation", false, indent) // that's ok
    }

    return code.slice(1)
}
