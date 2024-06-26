import json
import ruamel
from ruamel.yaml import YAML

ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
yaml = YAML(typ="safe", pure=True)
yaml.default_flow_style = False

  # - name: 0
  #   prefix: b
  #   action: push
  #   dimension: [50, 10]
  #   feedback: led
  #   repeat: [2, 1]
  #   layout:
  #     offset: [99, 324]
  #     spacing: [324, 0]
  #     hardware:
  #       type: virtual-sd-neoled
  #   options: corner_radius=5
FILENAME = "decklayout.json"

def decklayout_convert(konva):
    r = []
    for layer in konva["children"]:
        for item in layer["children"]:
            if item["className"] == "Group":
                name = None
                for shape in item["children"]:
                    if shape["className"] == "Text":
                        name = shape["attrs"]["text"]
                print(name)
                if name is not None:
                    for shape in item["children"]:
                        if shape["className"] == "Rect":
                            button = {
                                "name": name,
                                "dimension": (int(shape["attrs"]["width"]), int(shape["attrs"]["height"])),
                                "layout": {
                                    "offset": (int(shape["attrs"]["x"]), int(shape["attrs"]["y"]))
                                }
                            }
                            if shape["attrs"]["name"] == "hardware":
                                button["layout"]["hardware"] = "hardware"
                            r.append(button)
                        elif shape["className"] == "Circle":
                            radius = shape["attrs"]["radius"]
                            button = {
                                "name": name,
                                "dimension": radius,
                                "layout": {
                                    "offset": (int(shape["attrs"]["x"]), int(shape["attrs"]["y"]))
                                }
                            }
                            r.append(button)
    return r

lines = None
with open(FILENAME) as fp:
    konva = json.load(fp)

r = decklayout_convert(konva)

fn = FILENAME.replace(".json", ".yaml")

with open(fn, "w") as fp:
    yaml.dump(r, fp)
