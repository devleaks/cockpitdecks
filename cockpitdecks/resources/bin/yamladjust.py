from pprint import pprint

import ruamel.yaml

# ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
# yaml = YAML(typ="safe", pure=True)
# yaml.default_flow_style = False

yaml = ruamel.yaml.YAML()  # defaults to round-trip


ifile = "encoders.yaml"

CHANGES = {"set-dataref": "set-variable"}

data = {}
with open(ifile, "r") as fp:
    data = yaml.load(fp)


def chk(ind, kb, ka):
    out = ind.copy()
    for k, v in ind.items():
        # print(k, type(v), v)
        if type(v) is dict:
            temp = chk(v, kb, ka)
            if k == kb:
                out[ka] = temp
                del out[kb]
            else:
                out[k] = temp
        elif type(v) in (ruamel.yaml.comments.CommentedSeq, tuple, list):
            temp = [chk(dict(w), kb, ka) for w in v]
            if k == kb:
                out[ka] = temp
                del out[kb]
            else:
                out[k] = temp
        else:
            if k == kb:
                out[ka] = v
                del out[kb]
            else:
                out[k] = v
    return out


out = data
for k, v in CHANGES.items():
    out = chk(out, k, v)

with open("out.yaml", "w") as fp:
    yaml.dump(out, fp)
