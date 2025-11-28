data = []
with open("attributes.txt", "r") as fp:
    data = fp.readlines()


def mkparam(s):
    s = s.strip("\n")
    p = {}
    p["label"] = s.replace("-", " ").title()
    if "color" in s:
        p["type"] = "color"

    if "width" in s or "size" in s or "length" in s:
        p["type"] = "int"

    if "texture" in s or "icon" in s:
        p["type"] = "icon"  # image

    if "font" in s:
        p["type"] = "font"  # image

    if not "type" in p:
        p["type"] = "string"

    return {s: p}


for v in data:
    print(mkparam(v))
