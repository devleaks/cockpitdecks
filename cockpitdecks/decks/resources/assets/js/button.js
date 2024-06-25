/* Button generator
 * 
 */
LABEL_PARAMETERS = {
    "label": {
        "type": "string",
        "prompt": "Text"
    },
    "label-font": {
        "type": "font",
        "prompt": "Font"
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
        "prompt": "Position",
        "choices": ["tl", "tm", "tr", "ml", "mm", "mr", "bl", "bm", "br"]
    },
}

var annunciator_parts;

// Form
//
function toTitleCase(str) {
  return str.replace(
    /\w\S*/g,
    text => text.charAt(0).toUpperCase() + text.substring(1).toLowerCase()
  );
}

function add_elem(e, container) {
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
        el.value = "DIN.ttf"
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
        el.value = "NONE.png"
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
    if (add_label !== false && first == undefined) { // make labels (always)
        cleanElement(container);

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
        console.log("e", name, e);
        add_elem(e, container);
    }
}

// Yaml
//
function generateYaml(data, display, act_params, rep_params) {
    var code = "" // YAML.stringify(data)
    code += "index: " + data.index;
    if (data.name != undefined) {
        code += "\nname: " + data.name;
    }
    code += "\ntype: " + data.type;
    // activation parameters
    code += "\n" + data.view + ":";
    // representation parameters
    code += "\n\t" + data.view + ": true";
    display.innerHTML = code;
}
