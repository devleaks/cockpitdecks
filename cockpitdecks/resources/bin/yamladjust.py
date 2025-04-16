from pprint import pprint

import ruamel.yaml

# ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
# yaml = YAML(typ="safe", pure=True)
# yaml.default_flow_style = False

yaml = ruamel.yaml.YAML()  # defaults to round-trip


ifile = "encoders.yaml"

data = {}
with open(ifile, "r") as fp:
    data = yaml.load(fp)

pprint(type(data))

def chk(ind, kb, ka):
    out = ind
    for k, v in ind.items():
        print(k, type(v), v)
        if type(v) is dict:
            temp = chk(v, kb, ka)
            if k == kb:
                out[ka] = temp
            else:
                out[k] = temp
        elif type(v) is (ruamel.yaml.comments.CommentedSeq, tuple, list):
            temp = [chk(dict(w), kb, ka) for w in v]
            print("temp", temp)
            if k == kb:
                out[ka] = temp
            else:
                out[k] = temp
        else:
            if k == kb:
                out[ka] = v
            else:
                out[k] = v
    print("<<<", out)
    return out

out = chk(data, "set-dataref", "set-variable")

with open("out.yaml", "w") as fp:
    yaml.dump(out, fp)
