import argparse
from pprint import pprint

import cerberus
import ruamel
from ruamel.yaml import YAML
from ruamel.yaml.compat import StringIO

ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
yaml = YAML(typ="safe", pure=True)
yaml.default_flow_style = False
yaml.sort_base_mapping_type_on_output = False

parser = argparse.ArgumentParser(description="Check Yaml document against Cerberus schema")
parser.add_argument("files", metavar="files", type=str, nargs=2, help="document schema")

args = parser.parse_args()

document = {}
with open(args.files[0], "r") as fp:
    document = yaml.load(fp)

schema = {}
with open(args.files[1], "r") as fp:
    schema = yaml.load(fp)

v = cerberus.Validator(schema)  # , allow_unknown=True
if v.validate(document):
    print(f"{args.files[0]} ok")
else:
    print(f"{args.files[0]}:")
    pprint(v.errors)
