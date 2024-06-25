/* Button generator
 * 
 */

// Form
//
function makeForm(elements, container) {
    // make rough form from form_elements details
    cleanElement(container);
    // console.log("makeForm", elements, Object.prototype.toString.call(elements))
    
    for (var name in elements) {
        if (! elements.hasOwnProperty(name)) {
            continue;
        }
        e = elements[name]
        console.log("e", name, e)
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
            e.choices.forEach((c)=>{
                var opt = document.createElement("option");
                opt.value = c;
                opt.innerHTML = c;
                el.appendChild(opt);
            });
            container.appendChild(document.createElement("br"));
        }
    }
}

// Yaml
//
function generateYaml(data, display, act_params, rep_params) {
    var code = "" // YAML.stringify(data)
    code += "index: " + data;
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
