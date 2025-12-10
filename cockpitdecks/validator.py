import logging
from pprint import pprint

import cerberus

from cockpitdecks.buttons.representation.schemas import SCHEMA_LABEL, REPRESENTATION_NAMES, REPRESENTATION_ATTRIBUTES

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BUTTON_SCHEMA = {
    "index": {"type": ["string", "integer"], "meta": {"label": "Index"}},
    "name": {"type": "string", "meta": {"label": "Name"}},
    "type": {"type": "string", "meta": {"label": "Activation"}},
    "options": {"type": "string", "meta": {"label": "Options (coded string)"}},
} | SCHEMA_LABEL


class ButtonValidator(cerberus.Validator):

    def __init__(self, cockpit, deck, page):

        self.cockpit = cockpit
        self.deck = deck
        self.page = page

        cerberus.Validator.types_mapping["color"] = cerberus.TypeDefinition("color", (str, tuple, list), ())
        cerberus.Validator.types_mapping["font"] = cerberus.TypeDefinition("font", (str), ())
        cerberus.Validator.types_mapping["icon"] = cerberus.TypeDefinition("icon", (str), ())
        cerberus.Validator.types_mapping["image"] = cerberus.TypeDefinition("image", (str), ())
        cerberus.Validator.types_mapping["sound"] = cerberus.TypeDefinition("sound", (str), ())

    def validate(self, button_config: dict, activation: str, representation: str) -> bool:
        button = button_config.copy()
        button_full_name = (
            "::".join([self.deck.name, self.deck.layout, self.page.name, str(button.get("index", "-no index-"))]) + f" ({activation}, {representation})"
        )

        logger.debug(f">>>>> validating {button_full_name}...")

        # 1. Very basic check on essentials
        v1 = cerberus.Validator(schema=BUTTON_SCHEMA, allow_unknown=True)
        try:
            part1 = v1.validate(document=button)
            if not part1:
                logger.warning(f"button config {button_full_name} does not validate button common schema")
                pprint("common schema", BUTTON_SCHEMA)
                pprint("button", button)
                logger.warning(v1.errors)
                logger.warning("<<<<< common schema validated with errors")
                return False
            # logger.debug(f"button {button_full_name} validate button common schema")
        except:
            logger.error(f"button config {button_full_name} common validate error", exc_info=True)
            pprint("common schema", BUTTON_SCHEMA)
            pprint("button", button)
            logger.warning("<<<<< common schema validated with errors")
            return False

        # 2. Button common schema with activation specific
        # drop representation part
        allow_unknown = {"type": ["string", "dict"], "allowed": REPRESENTATION_NAMES + REPRESENTATION_ATTRIBUTES}
        if representation in button:
            del button[representation]
            allow_unknown = False

        if activation is not None and activation != "none":
            with_activation = BUTTON_SCHEMA | self.cockpit.all_activations[activation].SCHEMA
            # self.allow_unknown = False
            part2 = False
            try:
                v2 = cerberus.Validator(schema=with_activation, allow_unknown=allow_unknown)
                part2 = v2.validate(document=button)
                if not part2:
                    logger.warning(f"button config {button_full_name} does not validate button activation schema {activation}")
                    pprint(with_activation)
                    pprint(button)
                    logger.warning(v2.errors)
                    logger.warning(f"<<<<< activation {activation} validated with errors")
                    return False
                logger.debug(f"button {button_full_name} validate activation {activation} schema")
            except:
                logger.error(f"button config {button_full_name} activation {activation} validate error", exc_info=True)
                pprint(with_activation)
                pprint(button)
                logger.warning(f"<<<<< activation {activation} validated with errors")
                return False

        # 3. Button representation
        if representation == "none":
            logger.debug("<<<<< representation is none")
            logger.debug("<<<<< validated ok")
            return True

        representation_schema = self.cockpit.all_representations[representation].SCHEMA
        button_representation = button_config[representation]
        if button_representation is None:
            logger.debug(f"<<<<< representation {representation} not found")
            logger.debug(f"<<<<< representation {representation} validated with errors")
            return False
        try:
            v3 = cerberus.Validator(schema=representation_schema)
            part3 = v3.validate(document=button_representation)
            if not part3:
                logger.warning(f"button config {button_full_name} does not validate button representation schema {representation}")
                pprint(representation_schema)
                pprint(button_representation)
                logger.warning(v3.errors)
                logger.warning(f"<<<<< representation {representation} validated with errors")
                return False
            logger.debug(f"button {button_full_name} validate representation {representation} schema")
            logger.debug("<<<<< validated ok")
            return True
        except:
            logger.error(f"button config {button_full_name} representation {representation} validate error", exc_info=True)
            pprint(button_representation)
            pprint(button_representation)
            logger.warning(f"<<<<< representation {representation} validated with errors")

        return False
