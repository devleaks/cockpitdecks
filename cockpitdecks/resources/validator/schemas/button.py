from .representations import SCHEMA_LABEL

SCHEMA_BUTTON = {
    "index": {"type": ["string", "integer"], "meta": {"label": "Index"}},
    "name": {"type": "string", "meta": {"label": "Name"}},
    "type": {"type": "string", "meta": {"label": "Activation"}},
    "options": {"type": "string", "meta": {"label": "Options (coded string)"}},
} | SCHEMA_LABEL
# Formal:
# historically, LABEL is used to describe the button (all buttons)
# LABEL attributes should be restricted to representation with an image or text display ability
