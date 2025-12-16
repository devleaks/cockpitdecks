import logging
from pprint import pprint

from ruamel.yaml.compat import StringIO
import cerberus

from cockpitdecks.resources.validator.schemas.button import SCHEMA_BUTTON
from cockpitdecks.resources.validator.schemas.activations import ACTIVATION_ATTRIBUTES
from cockpitdecks.resources.validator.schemas.representations import REPRESENTATION_NAMES, REPRESENTATION_ATTRIBUTES
from cockpitdecks.constant import yaml


yaml.sort_base_mapping_type_on_output = False

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def dict_schema(schema: dict | str) -> dict:
    return yaml.load(schema) if type(schema) is str else schema


def yaml_schema(schema: dict) -> str:
    stream = StringIO()
    yaml.dump(schema, stream)
    return stream.getvalue()


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

        # Experimental:
        cerberus.schema_registry.add("button", SCHEMA_BUTTON)

        # self.do_once()

    def guess_activation_type(self, config):
        a = config.get("type")
        if a is None or a == "none":
            logger.debug("no type attribute, assuming type is none")
            return "none"
        return a

    def guess_representation_type(self, config):
        all_representations = self.cockpit.all_representations
        all_hardware_representations = self.cockpit.all_hardware_representations
        a = [r for r in all_representations.keys() if r in config and r not in all_hardware_representations.keys()]
        if len(a) == 1:
            return a[0]
        elif len(a) == 0:
            logger.debug(f"no representation in \n{config},\n assuming none, add representation: none to suppress warning message")
        else:
            logger.warning(f"multiple representations {a} found in {config}")
        return "none"

    def validate(self, button_config) -> bool:
        button = button_config.copy()

        activation = button_config.get("type", "none")
        representation = self.guess_representation_type(button_config)
        button_full_name = (
            "::".join([self.deck.name, self.deck.layout, self.page.name, str(button.get("index", "-no index-"))]) + f" ({activation}, {representation})"
        )

        logger.debug(f">>>>> validating {button_full_name}...")

        # 1. Very basic check on essentials
        v1 = cerberus.Validator(schema=SCHEMA_BUTTON, allow_unknown=True)
        try:
            part1 = v1.validate(document=button)
            if not part1:
                logger.warning(f"button config {button_full_name} does not validate button schema")
                logger.warning(v1.errors)
                pprint({"schema": SCHEMA_BUTTON})
                pprint({"button": button})
                logger.warning("<<<<< common schema validated with errors")
                return False
            # logger.debug(f"button {button_full_name} validate button common schema")
        except:
            logger.error(f"button config {button_full_name} common validate error", exc_info=True)
            pprint({"schema": SCHEMA_BUTTON})
            pprint({"button": button})
            logger.warning("<<<<< common schema validated with errors")
            return False

        # 2. Button common schema with activation specific
        # drop representation part
        allow_unknown = {"type": ["string", "dict"], "allowed": REPRESENTATION_NAMES + REPRESENTATION_ATTRIBUTES}
        if representation in button:
            del button[representation]
            allow_unknown = False

        if activation != "none":
            with_activation = dict_schema(SCHEMA_BUTTON | self.cockpit.all_activations[activation].SCHEMA)
            # self.allow_unknown = False
            part2 = False
            try:
                v2 = cerberus.Validator(schema=with_activation, allow_unknown=allow_unknown)
                part2 = v2.validate(document=button)
                if not part2:
                    logger.warning(f"button config {button_full_name}: ACTIVATION does not validate schema {activation}")
                    logger.warning(v2.errors)
                    pprint({activation: with_activation})
                    pprint({"button": button})
                    logger.warning(f"<<<<< activation {activation} validated with errors")
                    return False
                logger.debug(f"button {button_full_name} validate activation {activation} schema")
            except:
                logger.error(f"button config {button_full_name} ACTIVATION {activation} validate error", exc_info=True)
                pprint({activation: with_activation})
                pprint({"button": button})
                logger.warning(f"<<<<< activation {activation} validated with errors")
                return False

        # 3. Button representation
        if representation == "none":
            logger.debug("<<<<< representation is none")
            logger.debug("<<<<< validated ok")
            return True

        representation_schema = dict_schema(self.cockpit.all_representations[representation].SCHEMA)
        button_representation = button_config[representation]

        if button_representation is None:
            logger.debug(f"<<<<< representation {representation} not found")
            logger.debug(f"<<<<< representation {representation} validated with errors")
            return False

        if type(button_representation) is not dict:
            button_representation = {representation: button_config[representation]}
        else:
            if representation in ["icon"]:
                button_representation = {representation: button_config[representation]}
                # print(">>>", button_representation)
                # At one point, rewrite all representation schema like representayion_name: dict

        try:
            v3 = cerberus.Validator(schema=representation_schema)
            part3 = v3.validate(document=button_representation)
            if not part3:
                logger.warning(f"button config {button_full_name} REPRESENTATION does not validate schema {representation}")
                logger.warning(v3.errors)
                pprint({representation: representation_schema})
                pprint({representation: button_representation})
                logger.warning(f"button:\n{self.beautify({representation: button_representation}, representation)}")
                logger.warning(f"<<<<< representation {representation} validated with errors")
                return False
            logger.debug(f"button {button_full_name} validate representation {representation} schema")
            logger.debug("<<<<< validated ok")
            # logger.debug(f"button:\n{self.beautify(button_config, representation)}")
            return True
        except:
            logger.error(f"button config {button_full_name} REPRESENTATION {representation} validate error", exc_info=True)
            pprint({representation: representation_schema})
            pprint({representation: button_representation})
            logger.warning(f"<<<<< representation {representation} validated with errors")

        return False

    def do_once(self):
        keys = set()
        for a in self.cockpit.all_activations.values():
            for k in a.SCHEMA.keys():
                keys.add(k)
        print("Keys", sorted(keys))

    def beautify(self, document: dict, representation: str | None = None) -> str:
        """Idea is to feed beautifier with a "normalized"
           dictionary for a button.
           Buttons are almost manually composed into a Page

        Args:
            document (dict): Dictionary of a button definition

        Returns:
            dict: Beautified input
        """

        def sort_dict(d: dict):
            if type(d) is not dict:
                return d
            for k, v in d.items():
                if type(v) is dict:
                    d[k] = sort_dict(v)
            return dict(sorted(d.items()))

        def tr(n):
            v = document.get(n)
            if v is not None:
                data[n] = v

        data = {}
        # 1. General, index, name, etc.
        for attr in ["index", "name"]:
            tr(attr)

        # 1b. Label (= doc)
        for attr in ["label", "label-font", "label-color", "label-size", "label-position"]:
            tr(attr)

        # 2. Activation
        tr("type")
        for attr in sorted(ACTIVATION_ATTRIBUTES):
            if attr not in data:
                tr(attr)

        # 3. Representation
        if representation is not None:
            data[representation] = sort_dict(document[representation])

        # output yaml string
        stream = StringIO()
        yaml.dump(data, stream)
        return stream.getvalue()
