import logging
from pprint import pprint
import cerberus

from cockpitdecks.buttons.representation.schemas import SCHEMA_LABEL

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

BUTTON_SCHEMA = {
    "index": {"type": ["string", "integer"], "meta": {"label": "Index"}},
    "name": {"type": "string", "meta": {"label": "Name"}},
    "type": {"type": "string", "meta": {"label": "Activation"}},
} | SCHEMA_LABEL


def cerberus_validate(cockpit, deck_type, button, info) -> bool:
    print(">-"*20)
    print(info)
    cerberus.Validator.types_mapping["color"] = cerberus.TypeDefinition("color", (str, tuple, list), ())
    cerberus.Validator.types_mapping["font"] = cerberus.TypeDefinition("font", (str), ())
    cerberus.Validator.types_mapping["icon"] = cerberus.TypeDefinition("icon", (str), ())
    cerberus.Validator.types_mapping["image"] = cerberus.TypeDefinition("image", (str), ())
    cerberus.Validator.types_mapping["sound"] = cerberus.TypeDefinition("sound", (str), ())
    v1 = cerberus.Validator(schema=BUTTON_SCHEMA, allow_unknown=True)
    try:
        part1 = v1.validate(document=button)
        if not part1:
            logger.warning(f"button config {button['index']} does not validate button common schema")
            pprint(BUTTON_SCHEMA)
            pprint(button)
            logger.warning(v1.errors)
            print("<-"*20)
            return False
        logger.debug(f"button {button['index']} validate button common schema")
    except:
        logger.error(f"button config {button['index']} validate error", exc_info=True)
        pprint(BUTTON_SCHEMA)
        pprint(button)
        return False
    activation = button["type"]
    with_activation = BUTTON_SCHEMA | cockpit.all_activations[activation].SCHEMA
    # self.allow_unknown = False
    try:
        v2 = cerberus.Validator(schema=with_activation, allow_unknown={"type": ["string", "dict"]})
        part2 = v2.validate(document=button)
        if not part2:
            logger.warning(f"button config {button['index']} does not validate button activation schema")
            pprint(with_activation)
            pprint(button)
            logger.warning(v2.errors)
        else:
            logger.debug(f"button {button["index"]} validate activation {activation} schema")
        print("<-"*20)
        return part2
    except:
        logger.error(f"button config {button['index']} validate error", exc_info=True)
        pprint(with_activation)
        pprint(button)

    return False


class ButtonValidator(cerberus.Validator):

    def __init__(self, cockpit, deck_type):

        self.cockpit = cockpit
        self.deck_type = deck_type

        cerberus.Validator.__init__(self)

        cerberus.Validator.types_mapping["color"] = cerberus.TypeDefinition("color", (str, tuple, list), ())
        cerberus.Validator.types_mapping["font"] = cerberus.TypeDefinition("font", (str), ())
        cerberus.Validator.types_mapping["icon"] = cerberus.TypeDefinition("icon", (str), ())
        cerberus.Validator.types_mapping["image"] = cerberus.TypeDefinition("image", (str), ())
        cerberus.Validator.types_mapping["sound"] = cerberus.TypeDefinition("sound", (str), ())

    @staticmethod
    def mk_text(prefix):
        return {
            prefix: {"type": "string"},
            prefix + "-font": {"type": "font", "dependencies": prefix},
            prefix + "-color": {"type": "color", "dependencies": prefix},
            prefix + "-size": {"type": "integer", "dependencies": prefix},
            prefix + "-position": {"type": "string", "allowed": ["lt", "ct", "rt", "lm", "cm", "rm", "lb", "cb", "rb"], "dependencies": prefix},
        }

    def allowed_fonts(self):
        return list(self.cockpit.fonts.keys())

    def check_font(self, field, value, error):
        if value not in self.allowed_fonts():
            error(field, f"Must be list of installed fonts ({value})")

    def allowed_icons(self):
        return list(self.cockpit.icons.keys())

    def allowed_sounds(self):
        return list(self.cockpit.sounds.keys())

    def all_activations(self):
        return list(self.cockpit.all_activations.keys())

    def all_representations(self):
        return list(self.cockpit.all_representations.keys())

    def allowed_indices(self):
        return self.deck_type.valid_indices()

    def allowed_activations_for_button(self, idx):
        return list(self.deck_type.valid_activations(idx, source=self.cockpit))

    def allowed_representations_for_button(self, idx):
        return list(self.deck_type.valid_representations(idx, source=self.cockpit))

    def get_common_schema(self):
        return BUTTON_SCHEMA

    def get_activation_schema(self, activation):
        return self.cockpit.all_activations[activation].SCHEMA

    def get_representation_schema(self, representation):
        return self.cockpit.all_representations[representation].SCHEMA

    def validate_activation(self, button: dict):
        # self.allow_unknown = True
        # part1 = self.validate(document=button, schema=self.get_common_schema())
        # if not part1:
        #     logger.warning(f"button config {button} does not validate button common schema")
        #     return False
        # logger.debug(f"button {button["index"]} validate button common schema")
        activation = button["type"]
        with_activation = self.get_common_schema() | self.get_activation_schema(activation)
        # self.allow_unknown = False
        part2 = self.validate(document=button, schema=with_activation)
        if not part2:
            logger.warning(f"button config {button} does not validate button activation schema")
        else:
            logger.debug(f"button {button["index"]} validate activation {activation} schema")
        return part2

    def validate_representation(self, button, representation):
        if type(representation) is not str:
            logger.warning(f"button config {button} has invalid representation {representation}")
            return False
        part1 = self.validate(document=button[representation], schema=self.get_representation_schema(representation))
        if not part1:
            logger.warning(f"button config {button} does not validate button representation schema")
        return part1
