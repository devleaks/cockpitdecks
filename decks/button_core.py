"""
Different button classes for different purpose.
Button base class does not perform any action, it mainly is an ABC.

Buttons do
1. Execute zero or more X-Plane command
2. Optionally update their representation to confirm the action

Button phases:
1. button_value() compute the unique value that will become an index in an array.
   Value is stored in current_value
2. if current_value has changed, provoke render()
3. render: set_key_icon(): get the key icon from the array of available icons and the index (current_value)
   render: get_image(): builds an image from the key icon and text overlay(s)
   render returns the image to the deck for display in the proper key.

"""
import re
import logging
import threading
import time
from datetime import datetime

from PIL import ImageDraw, ImageFont

from .constant import DATAREF_RPN
from .color import convert_color
from .rpc import RPC


logger = logging.getLogger("Button")
logger.setLevel(15)
# logger.setLevel(logging.DEBUG)


def add_ext(name: str, ext: str):
    rext = ext if not ext.startswith(".") else ext[1:]  # remove leading period from extension if any
    narr = name.split(".")
    if len(narr) < 2:  # has no extension
        return name + "." + rext
    nameext = narr[-1]
    if nameext.lower() == rext.lower():
        return ".".join(narr[:-1]) + "." + rext  # force extension to what is should
    else:  # did not finish with extention, so add it
        return name + "." + rext  # force extension to what is should


# ##########################################
# BUTTONS
#
class Button:

    def __init__(self, config: dict, page: "Page"):

        # Definition and references
        self._activation = None
        self._representation = None
        self._activations = {}
        self._last_activate = None
        self._config = config
        self.page = page
        self.deck = page.deck
        self.xp = self.deck.cockpit.xp  # shortcut alias
        self.name = config.get("name", f"{type(self).__name__}-{config['index']}")
        self.index = config.get("index")  # type: button, index: 4 (user friendly) -> _key = B4 (internal, to distinguish from type: push, index: 4).
        self._key = config.get("_key", self.index)  # internal key, mostly equal to index, but not always. Index is for users, _key is for this software.
        self.num_index = None
        if type(self.index) == str:
            idxnum = re.findall("\\d+(?:\\.\\d+)?$", self.index)  # just the numbers of a button index name knob3 -> 3.
            if len(idxnum) > 0:
                self.num_index = idxnum[0]

        # Working variables
        self.pressed_count = 0
        self.pressed = False
        self.bounce_arr = None
        self.bounce_idx = 0
        self.current_value = None
        self.previous_value = None
        self.initial_value = config.get("initial-value")
        self._first_value = None    # first value the button will get

        self.guarded = None          # None: No guard, True: Guarded, closed. False: Guarded, open, ready to be used.

        # Labels
        self.label = config.get("label")
        self.labels = config.get("labels")
        self.label_format = config.get("label-format")
        self.label_font = config.get("label-font", self.deck.default_label_font)
        self.label_size = int(config.get("label-size", self.deck.default_label_size))
        self.label_color = config.get("label-color", self.deck.default_label_color)
        self.label_color = convert_color(self.label_color)
        self.label_position = config.get("label-position", "cm")
        self.icon_color = config.get("icon-color", page.default_icon_color)

        if self.label_position[0] not in "lcr" or self.label_position[1] not in "tmb":
            logger.warning(f"__init__: button {self.name}: invalid label position code {self.label_position}, using default")
            self.label_position = "cm"

        # Datarefs
        self.dataref = config.get("dataref")
        self.datarefs = config.get("multi-datarefs")
        self.dataref_rpn = config.get(DATAREF_RPN)

        self.all_datarefs = None                # all datarefs used by this button
        self.all_datarefs = self.get_datarefs() # cache them
        if len(self.all_datarefs) > 0:
            self.page.register_datarefs(self)   # when the button's page is loaded, we monitor these datarefs

        # Commands
        self.command = config.get("command")
        self.commands = config.get("commands")
        self.view = config.get("view")

        # Options
        self.options = []
        new = config.get("options")
        if new is not None:  # removes all spaces around = sign and ,. a = b, c, d=e -> a=b,c,d=e -> [a=b, c, d=e]
            old = ""         # a, c, d are options, b, e are option values. c option value is boolean True.
            while len(old) != len(new):
                old = new
                new = old.strip().replace(" =", "=").replace("= ", "=").replace(" ,", ",").replace(", ", ",")
            self.options = [a.strip() for a in new.split(",")]

        # Icon(s)
        # 1. Collect multi icons
        # Each icon in multi-icons must be an image for now (later could be a (background) color only)
        self.multi_icons = config.get("multi-icons")
        if self.multi_icons is not None:
            for i in range(len(self.multi_icons)):
                self.multi_icons[i] = add_ext(self.multi_icons[i], ".png")
                if self.multi_icons[i] not in self.deck.icons.keys():
                    logger.warning(f"__init__: button {self.name}: icon not found {self.multi_icons[i]}")

        # 2. Find the main icon for button
        self.icon = config.get("icon")
        if self.icon is not None:  # 2.1 if supplied, use it
            self.icon = add_ext(self.icon, ".png")
            if self.icon not in self.deck.icons.keys():
                logger.warning(f"__init__: button {self.name}: icon not found {self.icon}")
        elif self.icon_color is not None:  # 2.2 if no icon, but an icon-color, create one
            self.icon_color = convert_color(self.icon_color)
            # the icon size varies for center "buttons" and left and right side "buttons".
            if type(self.deck.device).__name__.startswith("StreamDeck"):
                imgtype = self.deck.device
            else:
                imgtype = "button" if self.index not in ["left", "right"] else self.index
            # self.default_icon_image = self.deck.pil_helper.create_image(deck=imgtype, background=self.icon_color)
            if self.deck.pil_helper is not None:
                self.default_icon_image = self.deck.pil_helper.create_image(deck=imgtype, background=self.icon_color)
                self.default_icon = f"_default_{self.page.name}_{self.name}_icon.png"
            # self.default_icon = add_ext(self.default_icon, ".png")
            # logger.debug(f"__init__: button {self.name}: creating icon '{self.default_icon}' with color {self.icon_color}")
            # register it globally
                self.deck.cockpit.icons[self.default_icon] = self.default_icon_image
            # add it to icon for this deck too since it was created at proper size
                self.deck.icons[self.default_icon] = self.default_icon_image
                self.icon = self.default_icon
        elif self.multi_icons is not None and len(self.multi_icons) > 0:  # 2.3 multiicons, take the first one
            self.icon = self.multi_icons[0]
            logger.debug(f"__init__: button {self.name}: icon not found but has multi-icons. Using {self.icon}.")
        else:  # 2.4 lastly, use the default deck icon (later, could be a default icon per page?)
            self.icon = add_ext(self.deck.default_icon_name, ".png")
            logger.warning(f"__init__: button {self.name}: no icon, no icon-color, using deck default icon {self.icon}")
            if self.icon not in self.deck.icons.keys():
                logger.warning(f"__init__: button {self.name}: icon not found in deck {self.icon}")

        # 3. The key icon is the one that is displayed when render() called.
        self.key_icon = self.icon  # Working icon that will be displayed, default to self.icon
                                   # If key icon should come from icons, will be selected later
        # logger.debug(f"__init__: button {self.name}: key icon {self.key_icon}, icon {self.icon}")

        self.all_icons = self.get_icons()  # simplification for later refactoring

        self.init()

    @classmethod
    def new(cls, config: dict, page: "Page"):
        return cls(config=config, page=page)

    def id(self):
        return ":".join([self.deck.name, self.page.name, self.name])

    def inspect(self):
        """
        Return information aout button status
        """
        logger.info(f"Button {self.name} -- Statistics")
        logger.info("Datarefs:")
        for d in self.get_datarefs():
            v = self.get_dataref_value(d)
            logger.info(f"    {d} = {v}")

    def register_activation(self, activation):
        self._activation = activation

    def register_representation(self, representation):
        self._representation = representation

    def on_current_page(self):
        """
        Returns whether button is on current page
        """
        return self.deck.current_page == self.page

    def init(self):
        """
        Install button
        """
        if self.has_option("bounce") and self.multi_icons is not None and len(self.multi_icons) > 0:
            stops = self.option_value(option="stops", default=len(self.multi_icons))
            self.bounce_arr = self.make_bounce_array(stops)

        # test: we try to immediately get a first value
        logger.debug(f"init: button {self.name} setting initial value..")
        if self.initial_value is not None:
            self.set_current_value(self.initial_value)
            self._first_value = self.initial_value
        else:
            self.set_current_value(self.button_value())
        if self._first_value is None and self.dataref is None and self.datarefs is None and self.dataref_rpn is None:  # won't get a value from datarefs
            self._first_value = self.current_value
        logger.debug(f"init: button {self.name}: ..has value {self.current_value}.")

        if self.has_option("guarded"):
            self.guarded = True   # guard type is option value: guarded=cover or grid.

        self.set_key_icon()

    def has_key_image(self):
        return True  # default

    def guard(self):
        return self.guarded if self.guarded is not None else False

    def set_current_value(self, value):
        self.previous_value = self.current_value
        self.current_value = value
        self.set_key_icon()

    def get_current_value(self):
        return self.current_value

    def value_has_changed(self) -> bool:
        if self.previous_value is None and self.current_value is None:
            return False
        elif self.previous_value is None and self.current_value is not None:
            return True
        elif self.previous_value is not None and self.current_value is None:
            return True
        return self.current_value != self.previous_value

    def is_valid(self) -> bool:
        """
        Validate button data once and for all
        """
        if self.deck is None:
            logger.warning(f"is_valid: button {self.name} has no deck")
            return False
        if self.index is None:
            logger.warning(f"is_valid: button {self.name} has no index")
            return False
        return True

    def has_option(self, option):
        # Check whether a button has an option.
        for opt in self.options:
            if opt.split("=")[0].strip() == option:
                return True
        return False

    def option_value(self, option, default = None):
        # Return the value of an option or the supplied default value.
        for opt in self.options:
            opt = opt.split("=")
            name = opt[0]
            if name == option:
                if len(opt) > 1:
                    return opt[1]
                else:  # found just the name, so it may be a boolean, True if present
                    return True
        return default

    def is_pushed(self):
        # Starts raised, True is pushed an odd number of times.
        return (self.pressed_count % 2) == 1

    def is_on(self):
        v = self.get_current_value()
        return v is not None and v != 0

    def is_dotted(self, label: str):
        # check dataref status
        # AirbusFBW/ALTmanaged, AirbusFBW/HDGmanaged,
        # AirbusFBW/SPDmanaged, and AirbusFBW/BaroStdCapt
        hack = "AirbusFBW/BaroStdCapt" if label.upper() == "QNH" else f"AirbusFBW/{label}managed"
        status = self.is_pushed()
        if hack in self.xp.all_datarefs.keys():
            # logger.debug(f"is_dotted: {hack} = {self.xp.all_datarefs[hack].value()}")
            status = self.xp.all_datarefs[hack].value() == 1
        else:
            logger.warning(f"is_dotted: button {self.name} dataref {hack} not found")
        return status

    def make_bounce_array(self, stops: int):
        # Builds an array like 0-1-2-3-2-1-0 for a 4 stops button.
        if stops > 1:
            af = list(range(stops - 1))
            ab = af.copy()
            ab.reverse()
            return af + [stops-1] + ab[:-1]
        return [0]

    def get_icons(self):
        # temporary, will return appropriate image immediately of course...
        icons = {}
        if self.icon is not None:
            icons[self.icon] = self.icon
        if self.multi_icons is not None:
            for i in self.multi_icons:
                icons[i] = i
        return icons

    def get_datarefs(self, base:dict = None):
        """
        Returns all datarefs used by this button from label, computed datarefs, and explicitely
        listed dataref and datarefs attributes.
        This can be applied to the entire button or to a subset (for annunciator parts)
        """
        if base is None:  # local, button-level ones
            if self.all_datarefs is not None:  # cached
                return self.all_datarefs
            base = self._config                # else, runs through config

        r = []
        # Use of datarefs in button:
        # 1. RAW datarefs
        # 1.1 Single
        dataref = base.get("dataref")
        if dataref is not None:
            r.append(dataref)
            logger.debug(f"get_datarefs: button {self.name}: added single dataref {dataref}")
        # 1.2 Multiple
        datarefs = base.get("multi-datarefs")  # base.get("datarefs")
        if datarefs is not None:
            r = r + datarefs
            logger.debug(f"get_datarefs: button {self.name}: added multiple datarefs {datarefs}")
        # logger.debug(f"get_datarefs: button {base.name}: {r}, {base.datarefs}")

        # Use of datarefs in formula:
        # 2. Formulae datarefs
        dataref_rpn = base.get(DATAREF_RPN)
        if dataref_rpn is not None and type(dataref_rpn) == str:
            datarefs = re.findall("\\${(.+?)}", dataref_rpn)
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"get_datarefs: button {self.name}: added formula datarefs {datarefs}")

        # Use of datarefs in label:
        # 3. LABEL datarefs
        # 3.1 Label
        label = base.get("label")
        if label is not None and type(label) == str:
            datarefs = re.findall("\\${(.+?)}", label)
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"get_datarefs: button {self.name}: added label datarefs {datarefs}")

        if DATAREF_RPN in r:  # label: ${dataref-rpn}, "dataref-rpn" is not a dataref.
            r.remove(DATAREF_RPN)

        return list(set(r))  # removes duplicates

    # ##################################
    # Dataref processing
    #
    def get_dataref_value(self, dataref, default = None):
        d = self.page.datarefs.get(dataref)
        return d.current_value if d is not None else default

    def substitute_dataref_values(self, message: str, formatting = None, default: str = "0.0"):
        """
        Replaces ${dataref} with value of dataref in labels and execution formula.
        """
        if type(message) == int or type(message) == float:  # probably dataref-rpn is a contant value
            logger.debug(f"substitute_dataref_values: button {self.name}: received int or float, returning as is.")
            return str(message)

        dataref_names = re.findall("\\${(.+?)}", message)
        if len(dataref_names) == 0:
            return message
        if formatting is not None:
            if type(formatting) == list:
                if len(dataref_names) != len(formatting):
                    logger.warning(f"substitute_dataref_values: button {self.name}: number of datarefs {len(dataref_names)} not equal to the number of format {len(formatting)}, cannot proceed.")
                    return message
            elif type(formatting) != str:
                logger.warning(f"substitute_dataref_values: button {self.name}: single format is not a string, cannot proceed.")
                return message
        retmsg = message
        cnt = 0
        for dataref_name in dataref_names:
            value = self.get_dataref_value(dataref_name)
            value_str = ""
            if formatting is not None and value is not None:
                if type(formatting) == list:
                    value_str = formatting[cnt].format(value)
                elif formatting is not None:
                    value_str = formatting.format(value)
            else:
                value_str = str(value) if value is not None else default
            retmsg = retmsg.replace(f"${{{dataref_name}}}", value_str)
            cnt = cnt + 1
        return retmsg

    def execute_formula(self, default, formula: str = None):
        """
        replace datarefs variables with their (numeric) value and execute formula.
        Returns formula result.
        """
        if formula is None:
            formula = self.dataref_rpn
        if formula is not None:
            expr = self.substitute_dataref_values(formula)
            r = RPC(expr)
            value = r.calculate()
            # logger.debug(f"execute_formula: button {self.name}: {formula} => {expr}:  => {value}")
            logger.log(15, f"execute_formula: button {self.name}: {formula} => {expr} => {value}")
            return value
        else:
            logger.warning(f"execute_formula: button {self.name}: no formula ({len(self.all_datarefs)} datarefs).")
        return default

    # ##################################
    # Icon image and label(s)
    #
    def get_font(self, fontname = None):
        """
        Helper function to get valid font, depending on button or global preferences
        """
        if fontname is None:
            fontname = self.label_font
        fonts_available = self.deck.cockpit.fonts.keys()
        # 1. Tries button specific font
        if fontname is not None:
            narr = fontname.split(".")
            if len(narr) < 2:  # has no extension
                fontname = add_ext(fontname, ".ttf")  # should also try .otf

            if fontname in fonts_available:
                return self.deck.cockpit.fonts[fontname]
            else:
                logger.warning(f"get_font: button {self.name}: button label font '{fontname}' not found")
        # 2. Tries deck default font
        if self.deck.default_label_font is not None and self.deck.default_label_font in fonts_available:
            logger.info(f"get_font: button {self.name}: using deck default font '{self.deck.default_label_font}'")
            return self.deck.cockpit.fonts[self.deck.default_label_font]
        else:
            logger.warning(f"get_font: button {self.name}: deck default label font '{fontname}' not found")
        # 3. Tries streamdecks default font
        if self.deck.cockpit.default_label_font is not None and self.deck.cockpit.default_label_font in fonts_available:
            logger.info(f"get_font: button {self.name}: using cockpit default font '{self.deck.cockpit.default_label_font}'")
            return self.deck.cockpit.fonts[self.deck.cockpit.default_label_font]
        logger.error(f"get_font: button {self.name}: cockpit default label font not found, tried {fontname}, {self.deck.default_label_font}, {self.deck.cockpit.default_label_font}")
        return None

    def get_label(self, base: dict = None, label_format: str = None):
        """
        Returns label, if any, with substitution of datarefs if any
        """
        DATAREF_RPN_STR = f"${{{DATAREF_RPN}}}"

        if base is None:
            base = self._config

        label = base.get("label")

        # If label contains ${dataref-rpn}, it is replaced by the value of the dataref-rpn calculation.
        # So we do it.
        if label is not None:
            if DATAREF_RPN in label:
                dataref_rpn = base.get(DATAREF_RPN)
                if dataref_rpn is not None:
                    expr = self.substitute_dataref_values(dataref_rpn)
                    rpc = RPC(expr)
                    res = rpc.calculate()  # to be formatted
                    if label_format is None:
                        label_format = base.get("label-format")
                    if label_format is not None:
                        logger.debug(f"get_label: button {self.name}: label_format {label_format} res {res} => {label_format.format(res)}")
                        res = label_format.format(res)
                    else:
                        res = str(res)
                    label = label.replace(DATAREF_RPN_STR, res)
                else:
                    logger.warning(f"get_label: button {self.name}: label contains {DATAREF_RPN_STR} but no {DATAREF_RPN} attribute found")
            else:
                label = self.substitute_dataref_values(label, formatting=label_format, default="---")

        return label

    def get_image_for_icon(self):
        image = None
        if self.key_icon in self.deck.icons.keys():  # look for properly sized image first...
            image = self.deck.icons[self.key_icon]
        elif self.key_icon in self.deck.cockpit.icons.keys(): # then icon, but need to resize it if necessary
            image = self.deck.cockpit.icons[self.key_icon]
            image = self.deck.pil_helper.create_scaled_image("button", image)
        return image

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """
        image = self.get_image_for_icon()

        if image is not None:
            draw = None
            # Add label if any
            label = self.get_label()
            if label is not None:
                fontname = self.get_font()
                if fontname is None:
                    logger.warning(f"get_image: no font, cannot overlay label")
                else:
                    # logger.debug(f"get_image: font {fontname}")
                    image = image.copy()  # we will add text over it
                    draw = ImageDraw.Draw(image)
                    font = ImageFont.truetype(fontname, self.label_size)
                    inside = round(0.04 * image.width + 0.5)
                    w = image.width / 2
                    p = "m"
                    a = "center"
                    if self.label_position[0] == "l":
                        w = inside
                        p = "l"
                        a = "left"
                    elif self.label_position[0] == "r":
                        w = image.width - inside
                        p = "r"
                        a = "right"
                    h = image.height / 2
                    if self.label_position[1] == "t":
                        h = inside + self.label_size / 2
                    elif self.label_position[1] == "r":
                        h = image.height - inside - self.label_size / 2
                    # logger.debug(f"get_image: position {(w, h)}")
                    draw.multiline_text((w, h),  # (image.width / 2, 15)
                              text=label,
                              font=font,
                              anchor=p+"m",
                              align=a,
                              fill=self.label_color)
            # Add little check mark if not valid/fake
            if not self.is_valid() or self.has_option("placeholder"):
                if draw is None:  # no label
                    image = image.copy()  # we will add text over it
                    draw = ImageDraw.Draw(image)
                c = round(0.97 * image.width)  # % from edge
                s = round(0.1 * image.width)   # size
                pologon = ( (c, c), (c, c-s), (c-s, c) )  # lower right corner
                draw.polygon(pologon, fill="red", outline="white")
            return image
        else:
            logger.warning(f"get_image: button {self.name}: icon {self.key_icon} not found")
            # logger.debug(f"{self.deck.icons.keys()}")
        return None

    # ##################################
    # Value and icon
    #
    def set_key_icon(self):
        if self.multi_icons is not None and len(self.multi_icons) > 1:
            num_icons = len(self.multi_icons)
            value = self.current_value
            if value is None:
                logger.debug(f"set_key_icon: button {self.name}: current value is null, default to 0")
                value = 0
            else:
                value = int(value)
            # logger.debug(f"get_image: button {self.name}: value={value}")
            if "counter" in self.options and num_icons > 0:  # modulo: 0-1-2-0-1-2...
                value = value % num_icons

            elif "bounce" in self.options and num_icons > 0:  # "bounce": 0-1-2-1-0-1-2-1-0-1-2-1-0
                value = self.bounce_arr[value % len(self.bounce_arr)]

            if value < 0 or value >= num_icons:
                logger.debug(f"set_key_icon: button {self.name} invalid icon key {value} not in [0,{len(self.multi_icons)}], default to 0")
                value = 0

            self.key_icon = self.multi_icons[value]
        else:
            self.key_icon = self.icon

    def button_value(self):
        """
        Button ultimately returns one value that is either directly extracted from a single dataref,
        or computed from several dataref values (later).
        """
        # 1. Unique dataref
        if len(self.all_datarefs) == 1:
            # if self.all_datarefs[0] in self.page.datarefs.keys():  # unnecessary check
            logger.debug(f"button_value: button {self.name} get single dataref {self.all_datarefs[0]}")
            return self.execute_formula(default=self.get_dataref_value(self.all_datarefs[0]))
            # else:
            #     logger.warning(f"button_value: button {self.name}: {self.all_datarefs[0]} not in {self.page.datarefs.keys()}")
            #     return None
        # 2. Multiple datarefs
        elif len(self.all_datarefs) > 1:
            logger.debug(f"button_value: button {self.name} getting formula since more than one dataref")
            return self.execute_formula(default=0.0)
        # 3. A Dataref formula without dataref in it...
        elif self.dataref_rpn is not None:
            logger.debug(f"button_value: button {self.name} getting formula without dataref")
            return self.execute_formula(default=0.0)
        # 4. Special cases
        elif "counter" in self.options or "bounce" in self.options:
            logger.debug(f"button_value: button {self.name} has counter or bounce: {self.pressed_count}")
            return self.pressed_count
        if type(self).__name__ not in ["ColoredButton"] and not self.has_option("nostate"):  # command-only buttons without real "display"
            logger.debug(f"button_value: button {self.name}, datarefs: {len(self.all_datarefs)}, rpn: {self.dataref_rpn}, options: {self.options}")
            logger.warning(f"button_value: button {self.name}, no dataref, no formula, no counter, returning None (add options nostate to suppress this warning)")
        return None

    # ##################################
    # External API
    #
    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        self.set_current_value(self.button_value())
        if self._first_value is None:  # store first non None value received from datarefs
            self._first_value = self.current_value
        logger.debug(f"{self.name}: {self.previous_value} -> {self.current_value}")
        self.render()

    def activate(self, state: bool):
        """
        Function that is executed when a button is pressed (state=True) or released (state=False) on the Stream Deck device.
        Default is to tally number of times this button was pressed. It should have been released as many times :-D.
        **** No command gets executed here **** except if there is an associated view with the button.
        Also, removes guard if it was present. @todo: close guard
        """
        if state:
            self.pressed = True
            self.pressed_count = self.pressed_count + 1
            if self.guarded is not None:    # if guarded
                if self.guarded:            # just open it
                    self.guarded = False
                    return
            # not guarded, or guard open
            self.set_current_value(self.button_value())
            if self.view:
                self.xp.commandOnce(self.view)
        else:
            self.pressed = False

        s = str(state)
        if s in self._activations:
            self._activations[s] = self._activations[s] + 1
        else:
            self._activations[s] = 1
        self._last_activate = datetime.now().timestamp()
        # logger.debug(f"activate: button {self.name} activated ({state}, {self.pressed_count})")

    def render(self):
        """
        Ask deck to set this button's image on the deck.
        set_key_image will call this button get_button function to get the icon to display with label, etc.
        """
        if self.deck is not None:
            if self.on_current_page():
                self.deck.set_key_image(self)
                # logger.debug(f"render: button {self.name} rendered")
            else:
                logger.debug(f"render: button {self.name} not on current page")
        else:
            logger.debug(f"render: button {self.name} has no deck")

    def clean(self):
        self.previous_value = None  # this will provoke a refresh of the value on data reload




# ###########################
# Deck manipulation functions
#
class ButtonPage(Button):
    """
    When pressed, activation change to selected page.
    If new page is not found, issues a warning and remain on current page.
    """
    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)
        if self.name is None:
            logger.error(f"__init__: page button has no name")
        self.remote_deck = self._config.get("deck")

        # We cannot change page validity because target page might not already be loaded.

    def button_value(self):
        return None

    def is_valid(self):
        return super().is_valid() and self.name is not None and self.name in self.deck.pages.keys()

    def activate(self, state: bool):
        super().activate(state)
        if self.remote_deck is not None and self.remote_deck not in self.deck.cockpit.cockpit.keys():
            logger.warning(f"activate: button {self.name}: deck not found {self.remote_deck}")
            self.remote_deck = None
        if state:
            deck = self.deck
            if self.remote_deck is not None and self.remote_deck in self.deck.cockpit.cockpit.keys():
                deck = self.deck.cockpit.cockpit[self.remote_deck]

            if self.name == "back" or self.name in deck.pages.keys():
                logger.debug(f"activate: button {self.name} change page to {self.name}")
                new_name = deck.change_page(self.name)
                if new_name is not None and self.name != "back":
                    self.set_current_value(new_name)
            else:
                logger.warning(f"activate: button {self.name}: page not found {self.name}")


class ButtonReload(Button):
    """
    Execute command while the key is pressed.
    Pressing starts the command, releasing stops it.
    """

    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)

    def button_value(self):
        return None

    def activate(self, state: bool):
        if state:
            if self.is_valid():
                self.deck.cockpit.reload_decks()


class ButtonInspect(Button):
    """
    Execute command while the key is pressed.
    Pressing starts the command, releasing stops it.
    """

    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)

    def button_value(self):
        return None

    def activate(self, state: bool):
        if state:
            # what = self.option_value("what")
            self.deck.cockpit.inspect()


# ###########################
# Normal, standard buttons and switches
#
class ButtonNone(Button):
    """
    Execute command once when key pressed. Nothing is done when button is released.
    """
    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)

    def get_image(self):
        return None


class ButtonPush(Button):
    """
    Execute command once when key pressed. Nothing is done when button is released.
    """
    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)

    def is_valid(self):
        if self.command is None:
            logger.warning(f"is_valid: button {self.name} has no command")
            if not self.has_option("counter"):
                logger.warning(f"is_valid: button {self.name} has no command or counter option")
                return False
        return super().is_valid()

    def activate(self, state: bool):
        # logger.debug(f"ButtonPush::activate: button {self.name}: {state}")
        super().activate(state)
        if state:
            if self.is_valid() and not self.guard():
                if self.command is not None:
                    self.xp.commandOnce(self.command)
                self.render()
            else:
                logger.warning(f"activate: button {self.name} is invalid")


class ButtonLongpress(Button):
    """
    Execute beginCommand while the key is pressed and endCommand when the key is released.
    """
    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)

    def is_valid(self):
        if self.command is None:
            logger.warning(f"is_valid: button {self.name} has no command")
            return False
        return super().is_valid()

    def activate(self, state: bool):
        if state:
            if self.is_valid():
                self.xp.commandBegin(self.command)
        else:
            if self.is_valid():
                self.xp.commandEnd(self.command)
        self.render()


class ButtonDual(Button):
    """
    Execute two commands in alternance.
    """
    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)

    def is_valid(self):
        if self.commands is None:
            logger.warning(f"is_valid: button {self.name} has no command")
            return False
        if len(self.commands) < 2:
            logger.warning(f"is_valid: button {self.name} has not enough commands (at least two needed)")
            return False
        return super().is_valid()

    def activate(self, state: bool):
        super().activate(state)
        if state:
            if self.is_valid():
                if self.is_pushed():
                    self.xp.commandOnce(self.commands[0])
                else:
                    self.xp.commandOnce(self.commands[1])
        self.render()


class ButtonUpDown(ButtonPush):
    # Execute a first command when button value increases, execute a second command when button value decreases.
    # Button value runs between 2 values.
    # It can either always increase: 0-1-2-3-0-1-2-3-0-1...
    # or increase and decrease: 0-1-2-3-2-1-0-1-2-3-2-1-0...
    def __init__(self, config: dict, page: "Page"):
        ButtonPush.__init__(self, config=config, page=page)
        self.stops = self.option_value("stops", len(self.multi_icons))
        self.bounce_arr = self.make_bounce_array(self.stops)
        self.start_value = None

    def is_valid(self):
        if self.commands is None or len(self.commands) < 2:
            logger.warning(f"is_valid: button {self.name} must have at least 2 commands")
            return False
        return True

    def activate(self, state: bool):
        super().activate(state)
        # We need to do something if button does not start in status 0. @todo
        # if self.start_value is None:
        #     if self.current_value is not None:
        #         self.start_value = int(self.current_value)
        #     else:
        #         self.start_value = 0
        if state:
            if self.start_value is None:
                self.start_value = int(self.current_value) if self.current_value is not None else 0
                self.bounce_idx = self.start_value
            value = self.bounce_arr[(self.start_value + self.pressed_count) % len(self.bounce_arr)]
            # logger.debug(f"activate: counter={self.start_value + self.pressed_count} = start={self.start_value} + press={self.pressed_count} curr={self.current_value} last={self.bounce_idx} value={value} arr={self.bounce_arr} dir={value > self.bounce_idx}")
            if self.is_valid():
                if value > self.bounce_idx:
                    self.xp.commandOnce(self.commands[0])  # up
                else:
                    self.xp.commandOnce(self.commands[1])  # down
                self.bounce_idx = value
            else:
                logger.warning(f"activate: button {self.name}: invalid {self.commands}")
        self.render()


# #################################
# Special button rendering
#
class ButtonAnimate(Button):
    """
    """
    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)
        self.thread = None
        self.running = False
        self.finished = None
        self.speed = float(self.option_value("animation_speed", 1))
        self.counter = 0

    def loop(self):
        self.finished = threading.Event()
        while self.running:
            self.render()
            self.counter = self.counter + 1
            time.sleep(self.speed)
        self.finished.set()

    def should_run(self) -> bool:
        """
        Check conditions to animate the icon.
        """
        return self.current_value is not None and self.current_value == 1

    def anim_start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.name = f"ButtonAnimate::loop({self.name})"
            self.thread.start()
        else:
            logger.warning(f"anim_start: button {self.name}: already started")

    def anim_stop(self):
        if self.running:
            self.running = False
            if not self.finished.wait(timeout=2*self.speed):
                logger.warning(f"anim_stop: button {self.name}: did not get finished signal")
            self.render()
        else:
            logger.debug(f"anim_stop: button {self.name}: already stopped")

    def get_image(self):
        """
        If button has more icons, select one from button current value
        """
        if self.running:
            self.key_icon = self.multi_icons[self.counter % len(self.multi_icons)]
        else:
            self.key_icon = self.icon  # off
        return super().get_image()

    # Works with activation on/off
    def activate(self, state: bool):
        super().activate(state)
        if state:
            if self.is_valid():
                # self.label = f"pressed {self.current_value}"
                self.xp.commandOnce(self.command)
                if self.should_run():
                    self.anim_start()
                else:
                    self.anim_stop()
                    self.render()  # renders default "off" icon

    # Works if underlying dataref changed
    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        self.set_current_value(self.button_value())
        logger.debug(f"{self.name}: {self.previous_value} -> {self.current_value}")
        if self.should_run():
            self.anim_start()
        else:
            self.anim_stop()
            self.render()  # renders default "off" icon

    def clean(self):
        self.anim_stop()
