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
import os
import re
import logging
import threading
import time
import random
import colorsys

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageColor
from mergedeep import merge

from .constant import add_ext, has_ext, convert_color
from .constant import CONFIG_DIR, ICONS_FOLDER, FONTS_FOLDER, AIRBUS_DEFAULTS
from .rpc import RPC

logger = logging.getLogger("Button")


class Button:

    def __init__(self, config: dict, page: "Page"):

        # Definition and references
        self._config = config
        self.page = page
        self.deck = page.deck
        self.xp = self.deck.cockpit.xp  # shortcut alias
        self.name = config.get("name", f"{type(self).__name__}-{config['index']}")
        self.index = config.get("index")  # type: button, index: 4 (user friendly) -> _key = B4 (internal, to distinguish from type: push, index: 4).
        self._key = config.get("_key", self.index)  # internal key, mostly equal to index, but not always. Index is for users, _key is for this software.

        # Working variables
        self.pressed_count = 0
        self.pressed = False
        self.bounce_arr = None
        self.bounce_idx = 0
        self.current_value = None
        self.previous_value = None
        self.initial_value = config.get("initial-value")
        self._first_value = None    # first value the button will get


        # Labels
        self.label = config.get("label")
        self.labels = config.get("labels")
        self.label_rpn = config.get("label-rpn")
        self.label_format = config.get("label-format")
        self.label_font = config.get("label-font", self.deck.default_label_font)
        self.label_size = int(config.get("label-size", self.deck.default_label_size))
        self.label_color = config.get("label-color", self.deck.default_label_color)
        self.label_color = convert_color(self.label_color)
        self.label_position = config.get("label-position", "cm")
        self.icon_color = config.get("icon-color")

        if self.label_position[0] not in "lcr" or self.label_position[1] not in "tmb":
            logger.warning(f"__init__: button {self.name}: invalid label position code {self.label_position}, using default")
            self.label_position = "cm"

        # Datarefs
        self.dataref = config.get("dataref")
        self.datarefs = config.get("multi-datarefs")
        self.dataref_rpn = config.get("label-rpn")
        self.all_datarefs = None                # all datarefs used by this button
        self.all_datarefs = self.get_datarefs() # cache them
        if len(self.all_datarefs) > 0:
            self.page.register_datarefs(self)

        # Commands
        self.command = config.get("command")
        self.commands = config.get("commands")
        self.view = config.get("view")

        # Options
        self.options = []
        new = config.get("options")
        if new is not None:  # removes all spaces around = sign and ,. a = b, c, d=e -> a=b,c,d=e -> [a=b, c, d=e]
            old = ""
            while len(old) != len(new):
                old = new
                new = old.strip().replace(" =", "=").replace("= ", "=").replace(" ,", ",").replace(", ", ",")
            self.options = [a.strip() for a in new.split(",")]

        # Icon(s)
        # 1. Collect multi icons
        # Each icon in muti icon lust be an image for now (later could be a (background) color only)
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

    def init(self):
        """
        Install button
        """
        if self.has_option("bounce") and self.multi_icons is not None and len(self.multi_icons) > 0:
            stops = self.option_value(option="stops", default=len(self.multi_icons))
            self.bounce_arr = self.make_bounce_array(stops)

        # test: we try to immediately get a first value
        if self.initial_value is not None:
            self.current_value = self.initial_value
            self._first_value = self.initial_value
        else:
            self.current_value = self.button_value()
        if self._first_value is None and self.dataref is None and self.datarefs is None and self.dataref_rpn is None:  # won't get a value from datarefs
            self._first_value = self.current_value

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

    def is_dotted(self, label: str):
        # check dataref status
        # AirbusFBW/ALTmanaged, AirbusFBW/HDGmanaged,
        # AirbusFBW/SPDmanaged, and AirbusFBW/BaroStdCapt
        hack = "AirbusFBW/BaroStdCapt" if label == "QNH" else f"AirbusFBW/{label}managed"
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

    def get_datarefs(self):
        """
        Returns all datarefs used by this button from label, computed datarefs, and explicitely
        listed dataref and datarefs attributes.
        """
        if self.all_datarefs is not None:  # cached
            return self.all_datarefs

        r = []
        if self.dataref is not None:
            r.append(self.dataref)
            logger.debug(f"get_datarefs: button {self.name}: added single dataref {self.dataref}")
        if self.datarefs is not None:
            r = r + self.datarefs
            logger.debug(f"get_datarefs: button {self.name}: added multiple datarefs {self.datarefs}")
        # logger.debug(f"get_datarefs: button {self.name}: {r}, {self.datarefs}")
        # Use of datarefs in label:
        if self.label is not None:
            datarefs = re.findall("\\${(.+?)}", self.label)
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"get_datarefs: button {self.name}: added label datarefs {datarefs}")
        # Use of datarefs in formulae:
        if self.dataref_rpn is not None:
            datarefs = re.findall("\\${(.+?)}", self.dataref_rpn)
            if len(datarefs) > 0:
                r = r + datarefs
                logger.debug(f"get_datarefs: button {self.name}: added formulae datarefs {datarefs}")

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

    def execute_formula(self, default):
        """
        replace datarefs variables with their (numeric) value and execute formula.
        Returns formula result.
        """
        if self.dataref_rpn is not None:
            expr = self.substitute_dataref_values(self.dataref_rpn)
            r = RPC(expr)
            value = r.calculate()
            # logger.debug(f"execute_formula: button {self.name}: {dataref}: {expr} = {r1}")
            # logger.debug(f"execute_formula: button {self.name}: {self.dataref_rpn} => {expr}:  => {value}")
            return value
        elif len(self.all_datarefs) > 1:
            logger.warning(f"execute_formula: button {self.name}: more than one dataref to get value from and no formula.")
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
                logger.warning(f"get_font: button label font '{fontname}' not found")
        # 2. Tries deck default font
        if self.deck.default_label_font is not None and self.deck.default_label_font in fonts_available:
            logger.info(f"get_font: using deck default font '{self.deck.default_label_font}'")
            return self.deck.cockpit.fonts[self.deck.default_label_font]
        else:
            logger.warning(f"get_font: deck default label font '{fontname}' not found")
        # 3. Tries streamdecks default font
        if self.deck.cockpit.default_label_font is not None and self.deck.cockpit.default_label_font in fonts_available:
            logger.info(f"get_font: using streamdecks default font '{self.deck.cockpit.default_label_font}'")
            return self.deck.cockpit.fonts[self.deck.cockpit.default_label_font]
        logger.error(f"get_font: streamdecks default label font not found, tried {fontname}, {self.deck.default_label_font}, {self.deck.cockpit.default_label_font}")
        return None

    def get_label(self, label = None, label_format = None):
        """
        Returns label, if any, with substitution of datarefs if any
        """
        if label is None:
            if self.label_rpn is not None:
                todo = self.substitute_dataref_values(self.label_rpn)
                rpc = RPC(todo)
                res = rpc.calculate()  # to be formatted
                logger.debug(f"get_label: button {self.name} execute_formula: {self.label_rpn}=>{todo}={res}")
                if label_format is None:
                    label_format = self.label_format
                if label_format is not None:
                    label = label_format.format(res)
                else:
                    label = str(res)
            else:
                label = self.label
        if label_format is None:
            label_format = self.label_format
        if label is not None:
            label = self.substitute_dataref_values(label, formatting=label_format, default="<no-value>")
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
            return self.execute_formula(default=self.get_dataref_value(self.all_datarefs[0]))
            # else:
            #     logger.warning(f"button_value: button {self.name}: {self.all_datarefs[0]} not in {self.page.datarefs.keys()}")
            #     return None
        # 2. Multiple datarefs
        elif len(self.all_datarefs) > 1:
            return self.execute_formula(default=0.0)
        elif "counter" in self.options or "bounce" in self.options:
            # logger.debug(f"button_value: button {self.name} get counter: {self.pressed_count}")pmUageOra-1
            return self.pressed_count
        return None

    # ##################################
    # External API
    #
    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        self.previous_value = self.current_value
        self.current_value = self.button_value()
        if self._first_value is None:  # store first non None value received from datarefs
            self._first_value = self.current_value
        logger.debug(f"{self.name}: {self.previous_value} -> {self.current_value}")
        self.set_key_icon()
        self.render()

    def activate(self, state: bool):
        """
        Function that is executed when a button is pressed (state=True) or released (state=False) on the Stream Deck device.
        Default is to tally number of times this button was pressed. It should have been released as many times :-D.
        **** No command gets executed here **** except if there is an associated view with the button.
        """
        if state:
            self.pressed = True
            self.pressed_count = self.pressed_count + 1
            self.previous_value = self.current_value
            self.current_value = self.button_value()
            if self.view:
                self.xp.commandOnce(self.view)
        else:
            self.pressed = False
        # logger.debug(f"activate: button {self.name} activated ({state}, {self.pressed_count})")

    def render(self):
        """
        Ask deck to set this button's image on the deck.
        set_key_image will call this button get_button function to get the icon to display with label, etc.
        """
        if self.deck is not None:
            self.deck.set_key_image(self)
        # logger.debug(f"render: button {self.name} rendered")

    def clean(self):
        self.previous_value = None  # this will provoke a refresh of the value on data reload


class AirbusButton(Button):

    def __init__(self, config: dict, page: "Page"):

        self.lit_display = False
        self.lit_dual = False

        self.multi_icons = config.get("multi-icons")
        self.icon = config.get("icon")

        self.airbus = None                   # working def
        self._airbus = config.get("airbus")  # keep raw
        if self._airbus is not None:
            self.airbus = merge({}, AIRBUS_DEFAULTS, self._airbus)
        else:
            logger.error(f"__init__: button {self.name}: has no airbus property")

        Button.__init__(self, config=config, page=page)

        if self.airbus is not None and (self.icon is not None or self.multi_icons is not None):
            logger.warning(f"__init__: button {self.name}: has airbus property with icon/multi-icons, ignoring icons")
            self.icon = None
            self.multi_icons = None

    def get_datarefs(self):
        """
        Complement button datarefs with airbus special lit datarefs
        """
        if self.all_datarefs is not None:  # cached
            return self.all_datarefs

        r = super().get_datarefs()
        for key in ["display", "dual"]:
            if key in self.airbus:
                c = self.airbus[key]
                if "dataref-rpn" in c:
                    calc = c["dataref-rpn"]
                    datarefs = re.findall("\\${(.+?)}", calc)
                    if len(datarefs) > 0:
                        r = r + datarefs
                        logger.debug(f"get_datarefs: button {self.name}: added {key} datarefs {datarefs}")
        return r

    def button_value(self):
        """
        Same as button value, but exclusively for Airbus-type buttons.
        We basically check with the supplied dataref-rpn that the button is lit or not.
        """
        r = []
        for key in ["display", "dual"]:
            if key in self.airbus:
                c = self.airbus[key]
                if "dataref-rpn" in c:
                    calc = c["dataref-rpn"]
                    todo = self.substitute_dataref_values(calc)
                    rpc = RPC(todo)
                    res = rpc.calculate()
                    r.append(1 if (res is not None and res > 0) else 0)
                    # logger.debug(f"airbus_button_value: button {self.name} execute_formula: {calc}=>{todo}={res}")
                else:
                    r.append(0)
            else:
                r.append(0)
        # logger.debug(f"airbus_button_value: button {self.name} returning: {r}")
        return r

    def set_key_icon(self):
        if self.current_value is not None and type(self.current_value) == list and len(self.current_value) > 1:
            self.lit_display = (self.current_value[0] != 0)
            self.lit_dual = (self.current_value[1] != 0)
        # else: leave untouched

    def get_image(self):
        """
        """
        self.set_key_icon()
        return self.mk_airbus()

    def mk_airbus(self):
        # If the display or dual is not lit, a darker version is printed unless dark option is added to button
        # in which case nothing gets added to the button.

        def light_off(color, lightness: float = 0.10):
            # Darkens (or lighten) a color
            if type(color) == str:
                color = ImageColor.getrgb(color)
            a = list(colorsys.rgb_to_hls(*[c / 255 for c in color]))
            a[1] = lightness
            return tuple([int(c * 256) for c in colorsys.hls_to_rgb(*a)])

        ICON_SIZE = 256  # px
        inside = ICON_SIZE / 32 # 8px

        # Button
        #
        # Overall button size: full, large, medium, small.
        #
        size = self.airbus.get("size", "large")
        if size == "small":  # about 1/2, starts at 128
            button_height = int(ICON_SIZE / 2)
            box = (0, int(ICON_SIZE/4))
        elif size == "medium":  # about 2/3, starts at 96
            button_height = int(10 * ICON_SIZE / 16)
            box = (0, int(3 * ICON_SIZE / 16))
        elif size == "full":  # starts at 0
            button_height = ICON_SIZE
            box = (0, 0)
        else:  # "large", full size, default, starts at 48
            button_height = int(13 * ICON_SIZE / 16)
            box = (0, int(3 * ICON_SIZE / 16))

        led_offset = inside

        # PART 1:
        # Texts that will glow
        glow = Image.new(mode="RGBA", size=(ICON_SIZE, button_height), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)

        # First/top/main item (called "display")
        display = self.airbus.get("display")
        dual    = self.airbus.get("dual")

        if display is not None:
            display_pos = display.get("position", "mm")
            text = display.get("text")
            if text is not None:
                fontname = self.get_font(display.get("font"))
                font = ImageFont.truetype(fontname, display.get("size"))
                w = glow.width / 2
                p = "m"
                a = "center"
                if display_pos[0] == "l":
                    w = inside
                    p = "l"
                    a = "left"
                elif display_pos[0] == "r":
                    w = glow.width - inside
                    p = "r"
                    a = "right"
                h = int(button_height / 2)  # center of button
                if dual is not None and dual.get("text") is not None: # middle of top part
                    h = int(button_height / 4)
                # logger.debug(f"mk_airbus: position {display_pos}: {(w, h)}, {dual}")
                color = display.get("color")
                if not self.lit_display:
                    color = display.get("off-color", light_off(color))
                if not self.has_option("dark"):
                    draw.multiline_text((w, h),  # (glow.width / 2, 15)
                              text=display.get("text"),
                              font=font,
                              anchor=p+"m",
                              align=a,
                              fill=color)
                else:
                    logger.debug("mk_airbus: full dark display")
            else:
                e = ICON_SIZE / 4      # space left and right of LED
                color = display.get("color")
                if not self.lit_display:
                    color = display.get("off-color", light_off(color))
                if size == "small":  # 1 horizontal leds
                    thick = 30             # LED thickness
                    start = button_height / 2 - thick
                    frame = ((e, start), (glow.width - e, start+thick))
                    draw.rectangle(frame, fill=color)
                else:  # 3 horizontal leds
                    thick = 10             # LED thickness
                    start = button_height / 4 - 1.5 * thick - (16 - thick)
                    for i in range(3):
                        s = start + i * 16
                        frame = ((e, s), (glow.width - e, s+thick))
                        draw.rectangle(frame, fill=color)

        # Optional second/bottom item (called "dual")
        if dual is not None:
            dual_pos = dual.get("position", "mm")
            text = dual.get("text")
            if text is not None:
                fontname = self.get_font(dual.get("font"))
                font = ImageFont.truetype(fontname, dual.get("size"))
                w = glow.width / 2
                p = "m"
                a = "center"
                if dual_pos[0] == "l":
                    w = inside
                    p = "l"
                    a = "left"
                elif dual_pos[0] == "r":
                    w = glow.width - inside
                    p = "r"
                    a = "right"
                h = int(3 * button_height / 4)  # middle of bottom part
                # logger.debug(f"mk_airbus: {dual.get('text')}: size {dual.get('size')}, position {dual_pos}: {(w, h)}")

                if not self.has_option("dark"):
                    color = dual.get("color")
                    if not self.lit_dual:
                        color = dual.get("off-color", light_off(color))

                    draw.multiline_text((w, h),  # (glow.width / 2, 15)
                              text=dual.get("text"),
                              font=font,
                              anchor=p+"m",
                              align=a,
                              fill=color)
                    framed = dual.get("framed")
                    if type(framed) == str:
                        framed = framed.lower() in ["true", "on", "yes"]
                    if framed:
                        start = button_height / 2 + inside
                        height = button_height / 2 - 2 * inside
                        thick = 12
                        e = ICON_SIZE / 8
                        frame = ((e, start), (glow.width-e, start + height))
                        draw.rectangle(frame, outline=color, width=thick)
                else:
                    logger.debug("mk_airbus: full dark dual display")

        # Glowing texts, later because not nicely perfect.
        # if not self.has_option("no_blurr") or self.has_option("sharp"):
        #     blurred_image = glow.filter(ImageFilter.GaussianBlur(self.airbus.get("blurr")))
        #     glow.alpha_composite(blurred_image)
        #     # logger.debug("mk_airbus: blurred")

        # We paste the transparent glow into a button:
        button = Image.new(mode="RGB", size=(ICON_SIZE, button_height), color=self.airbus.get("color", "black"))
        button.paste(glow, mask=glow)

        # Background
        image = Image.new(mode="RGB", size=(ICON_SIZE, ICON_SIZE), color=self.airbus.get("background", "lightsteelblue"))
        draw = ImageDraw.Draw(image)

        # Title
        title = self.airbus.get("title")
        if title is not None and title.get("text") is not None:
            title_pos = title.get("position", "mm")
            fontname = self.get_font(title.get("font"))
            font = ImageFont.truetype(fontname, title.get("size"))
            w = image.width / 2
            p = "m"
            a = "center"
            if title_pos[0] == "l":
                w = inside
                p = "l"
                a = "left"
            elif title_pos[0] == "r":
                w = image.width - inside
                p = "r"
                a = "right"
            h = inside + title.get("size") / 2
            # logger.debug(f"mk_airbus: position {title_pos}: {(w, h)}")
            draw.multiline_text((w, h),  # (image.width / 2, 15)
                      text=title.get("text"),
                      font=font,
                      anchor=p+"m",
                      align=a,
                      fill=title.get("color"))

        # Button
        image.paste(button, box=box)

        return image

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
        # We cannot change page validity because target page might not already be loaded.

    def is_valid(self):
        return super().is_valid() and self.name is not None and self.name in self.deck.pages.keys()

    def activate(self, state: bool):
        super().activate(state)
        if state:
            if self.name == "back" or self.name in self.deck.pages.keys():
                logger.debug(f"activate: button {self.name} change page to {self.name}")
                self.deck.change_page(self.name)
                self.previous_value = self.current_value
                self.current_value = self.name
            else:
                logger.warning(f"activate: button {self.name}: page not found {self.name}")


class ButtonReload(Button):
    """
    Execute command while the key is pressed.
    Pressing starts the command, releasing stops it.
    """

    def __init__(self, config: dict, page: "Page"):
        Button.__init__(self, config=config, page=page)

    def activate(self, state: bool):
        if state:
            if self.is_valid():
                self.deck.cockpit.reload_decks()


# ###########################
# Normal, standard buttons and switches
#
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

    def get_image(self):
        """
        If button has more icons, select one from button current value
        """
        return super().get_image()

    def activate(self, state: bool):
        # logger.debug(f"ButtonPush::activate: button {self.name}: {state}")
        super().activate(state)
        if state:
            if self.is_valid():
                if self.command is not None:
                    self.xp.commandOnce(self.command)
                self.render()
            else:
                logger.warning(f"activate: button {self.name} is invalid")


class AirbusButtonPush(AirbusButton):
    """
    Execute command once when key pressed. Nothing is done when button is released.
    """
    def __init__(self, config: dict, page: "Page"):
        AirbusButton.__init__(self, config=config, page=page)

    def is_valid(self):
        if self.command is None:
            logger.warning(f"is_valid: button {self.name} has no command")
            if not self.has_option("counter"):
                logger.warning(f"is_valid: button {self.name} has no command or counter option")
                return False
        return super().is_valid()

    def get_image(self):
        """
        If button has more icons, select one from button current value
        """
        return super().get_image()

    def activate(self, state: bool):
        # logger.debug(f"ButtonPush::activate: button {self.name}: {state}")
        super().activate(state)
        if state:
            if self.is_valid():
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
        self.start_value = 0

    def is_valid(self):
        if self.commands is None or len(self.commands) < 2:
            logger.warning(f"is_valid: button {self.name} must have at least 2 commands")
            return False
        return super().is_valid()

    def activate(self, state: bool):
        super().activate(state)
        # We need to do something if button does not start in status 0. @todo
        # if self.start_value is None:
        #     if self.current_value is not None:
        #         self.start_value = int(self.current_value)
        #     else:
        #         self.start_value = 0
        if state:
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


# ###########################
# Loupedeck specials buttons
#
class ColoredButton(ButtonPush):
    """
    A Push button. We can only change the color of the button.
    """

    def __init__(self, config: dict, page: "Page"):
        ButtonPush.__init__(self, config=config, page=page)

    def render(self):
        """
        Ask deck to set this button's image on the deck.
        set_key_image will call this button get_button function to get the icon to display with label, etc.
        """
        self.deck.set_button_color(self)
        # logger.debug(f"render: button {self.name} rendered")

    def get_color(self):
        return self.icon_color if self.icon_color is not None else [random.randint(0,255) for _ in range(3)]


class ButtonKnob(ButtonPush):
    """
    A Push button that can turn left/right.
    """
    def __init__(self, config: dict, page: "Page"):
        ButtonPush.__init__(self, config=config, page=page)

    def is_valid(self):
        if self.has_option("dual") and len(self.commands) != 4:
            logger.warning(f"is_valid: button {self.name} must have 4 commands for dual mode")
            return False
        elif not self.has_option("dual") and len(self.commands) != 2:
            logger.warning(f"is_valid: button {self.name} must have 2 commands")
            return False
        return True  # super().is_valid()

    def activate(self, state):
        if state < 2:
            super().activate(state)
        elif state == 2:  # rotate left
            if self.has_option("dual"):
                if self.is_pushed():
                    self.xp.commandOnce(self.commands[0])
                else:
                    self.xp.commandOnce(self.commands[2])
            else:
                self.xp.commandOnce(self.commands[0])
        elif state == 3:  # rotate right
            if self.has_option("dual"):
                if self.is_pushed():
                    self.xp.commandOnce(self.commands[1])
                else:
                    self.xp.commandOnce(self.commands[3])
            else:
                self.xp.commandOnce(self.commands[1])
        else:
            logger.warning(f"activate: button {self.name} invalid state {state}")

    def render(self):
        """
        No rendering for knobs, but render screen next to it in case it carries status.
        """
        disp = "left" if self.index[-1] == "L" else "right"
        if disp in self.page.buttons.keys():
            logger.debug(f"render: button {self.name} rendering {disp}")
            self.page.buttons[disp].render()


class ButtonKnobPushPull(ButtonDual):
    """
    A Push button that can turn left/right.
    """
    def __init__(self, config: dict, page: "Page"):
        ButtonDual.__init__(self, config=config, page=page)

    def is_valid(self):
        if self.has_option("dual") and len(self.commands) != 6:
            logger.warning(f"is_valid: button {self.name} must have 6 commands for dual mode")
            return False
        elif len(self.commands) != 4:
            logger.warning(f"is_valid: button {self.name} must have 4 commands")
            return False
        return True  # super().is_valid()

    def activate(self, state):
        if state < 2:
            super().activate(state)
        elif state == 2:  # rotate left
            if self.has_option("dual"):
                if self.is_pushed():
                    self.xp.commandOnce(self.commands[2])
                else:
                    self.xp.commandOnce(self.commands[4])
            else:
                self.xp.commandOnce(self.commands[2])
        elif state == 3:  # rotate right
            if self.has_option("dual"):
                if self.is_pushed():
                    self.xp.commandOnce(self.commands[3])
                else:
                    self.xp.commandOnce(self.commands[5])
            else:
                self.xp.commandOnce(self.commands[3])
        else:
            logger.warning(f"activate: button {self.name} invalid state {state}")

    def render(self):
        """
        No rendering for knobs, but render screen next to it in case it carries status.
        """
        disp = "left" if self.index[-1] == "L" else "right"
        if disp in self.page.buttons.keys():
            logger.debug(f"render: button {self.name} rendering {disp}")
            self.page.buttons[disp].render()


class ButtonKnobPushTurnRelease(ButtonPush):
    """
    A know button that can turn left/right either when pressed or released.
    """
    def __init__(self, config: dict, page: "Page"):
        ButtonPush.__init__(self, config=config, page=page)

    def is_valid(self):
        if len(self.commands) != 4:
            logger.warning(f"is_valid: button {self.name} must have 4 commands for dual mode")
            return False
        return True  # super().is_valid()

    def activate(self, state):
        if state < 2:
            super().activate(state)
        elif state == 2:  # rotate left
            if self.pressed:
                self.xp.commandOnce(self.commands[2])
            else:
                self.xp.commandOnce(self.commands[0])
        elif state == 3:  # rotate right
            if self.pressed:
                self.xp.commandOnce(self.commands[3])
            else:
                self.xp.commandOnce(self.commands[1])
        else:
            logger.warning(f"activate: button {self.name} invalid state {state}")

    def render(self):
        """
        No rendering for knobs, but render screen next to it in case it carries status.
        """
        disp = "left" if self.index[-1] == "L" else "right"
        if disp in self.page.buttons.keys():
            logger.debug(f"render: button {self.name} rendering {disp}")
            self.page.buttons[disp].render()


class ButtonKnobDataref(ButtonPush):
    """
    A knob button that writes directly to a dataref.
    """
    def __init__(self, config: dict, page: "Page"):
        ButtonPush.__init__(self, config=config, page=page)
        self.step = config.get("step")
        self.stepxl = config.get("stepxl")
        self.value = config.get("value")
        self.value_min = config.get("value-min")
        self.value_max = config.get("value-max")

    def is_valid(self):
        return True  # super().is_valid()

    def activate(self, state):
        if state < 2:
            super().activate(state)
        elif state == 2:  # rotate left
            step = self.step
            if self.has_option("dual") and self.is_pushed():
                step = self.stepxl
            self.value = self.value - step
            if self.value < self.value_min:
                self.value = self.value_min
            if self.dataref in self.xp.all_datarefs:
                self.xp.all_datarefs[self.dataref].save(self)
            else:
                logger.warning(f"activate: button {self.name} dataref {self.dataref} not found")
        elif state == 3:  # rotate right
            step = self.step
            if self.has_option("dual") and self.is_pushed():
                step = self.stepxl
            self.value = self.value + step
            if self.value > self.value_max:
                self.value = self.value_max
            if self.dataref in self.xp.all_datarefs:
                self.xp.all_datarefs[self.dataref].save(self)
            else:
                logger.warning(f"activate: button {self.name} dataref {self.dataref} not found")
        else:
            logger.warning(f"activate: button {self.name} invalid state {state}")

    def render(self):
        """
        No rendering for knobs, but render screen next to it in case it carries status.
        """
        disp = "left" if self.index[-1] == "L" else "right"
        if disp in self.page.buttons.keys():
            logger.debug(f"render: button {self.name} rendering {disp}")
            self.page.buttons[disp].render()


class ButtonSide(ButtonPush):
    """
    A ButtonPush that has very special size (60x270), end therefore very special button rendering
    """
    def __init__(self, config: dict, page: "Page"):
        ButtonPush.__init__(self, config=config, page=page)

    def is_valid(self):  # @todo with precision...
        return True

    def activate(self, state):
        if type(state) == int:
            super().activate(state)
            return
        # else, swipe event
        logger.debug(f"activate: side bar swipe event unprocessed {state} ")

    def get_image(self):
        """
        Helper function to get button image and overlay label on top of it for SIDE keys (60x270).
        """
        image = None
        # we can't get "button-resized-ready" deck icon, we need to start from original icon stored in decks.
        if self.key_icon in self.deck.cockpit.icons.keys():
            image = self.deck.cockpit.icons[self.key_icon]
            image = self.deck.pil_helper.create_scaled_image(self.index, image)

        if image is not None:
            draw = None
            # Add label if any
            if self.labels is not None:
                image = image.copy()  # we will add text over it
                draw = ImageDraw.Draw(image)
                inside = round(0.04 * image.width + 0.5)
                vcenter = [43, 150, 227]  # this determines the number of acceptable labels, organized vertically
                vposition = "TCB"
                vheight = 38 - inside

                li = 0
                for label in self.labels:
                    cnt = label.get("centers")
                    if cnt is not None:
                        vcenter = [round(270 * i / 100, 0) for i in convert_color(cnt)]  # !
                        continue
                    txt = label.get("label")
                    knob = "knob" + vposition[li] + self.index[0].upper()
                    logger.debug(f"get_image: watching {knob}")
                    if knob in self.page.buttons.keys():
                        corrknob = self.page.buttons[knob]
                        if corrknob.has_option("dot"):
                            if corrknob.is_dotted(txt):
                                txt = txt + "•"  # \n•"
                            else:
                                txt = txt + ""   # \n"
                    if li >= len(vcenter) or txt is None:
                        continue
                    fontname = self.get_font(label.get("label-font", self.label_font))
                    if fontname is None:
                        logger.warning(f"get_image: no font, cannot overlay label")
                    else:
                        # logger.debug(f"get_image: font {fontname}")
                        lsize = label.get("label-size", self.label_size)
                        font = ImageFont.truetype(fontname, lsize)
                        # Horizontal centering is not an issue...
                        label_position = label.get("label-position", self.label_position)
                        w = image.width / 2
                        p = "m"
                        a = "center"
                        if label_position == "l":
                            w = inside
                            p = "l"
                            a = "left"
                        elif label_position == "r":
                            w = image.width - inside
                            p = "r"
                            a = "right"
                        # Vertical centering is black magic...
                        h = vcenter[li] - lsize / 2
                        if label_position[1] == "t":
                            h = vcenter[li] - vheight
                        elif label_position[1] == "b":
                            h = vcenter[li] + vheight - lsize

                        # logger.debug(f"get_image: position {self.label_position}: {(w, h)}, anchor={p+'m'}")
                        draw.multiline_text((w, h),  # (image.width / 2, 15)
                                  text=txt,
                                  font=font,
                                  anchor=p+"m",
                                  align=a,
                                  fill=label.get("label-color", self.label_color))
                    li = li + 1
            elif self.label is not None:
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
                    h = image.height / 2 - self.label_size / 2
                    if self.label_position[1] == "t":
                        h = inside + self.label_size / 2
                    elif self.label_position[1] == "r":
                        h = image.height - inside - self.label_size
                    # logger.debug(f"get_image: position {self.label_position}: {(w, h)}")
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

    def anim_start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.name = f"button {self.name} animation"
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
                if self.pressed_count % 2 == 0:
                    self.anim_stop()
                    self.render()
                else:
                    self.anim_start()

    # Works if underlying dataref changed
    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        self.previous_value = self.current_value
        self.current_value = self.button_value()
        logger.debug(f"{self.name}: {self.previous_value} -> {self.current_value}")
        if self.current_value is not None and self.current_value == 1:
            self.anim_start()
        else:
            if self.running:
                self.anim_stop()
            self.render()

    def clean(self):
        self.anim_stop()


class AirbusButtonAnimate(AirbusButton):
    """
    """
    def __init__(self, config: dict, page: "Page"):
        AirbusButton.__init__(self, config=config, page=page)
        self.thread = None
        self.running = False
        self.finished = None
        self.speed = float(self.option_value("animation_speed", 0.5))
        self.counter = 0

    def loop(self):
        self.finished = threading.Event()
        while self.running:
            self.render()
            self.counter = self.counter + 1
            time.sleep(self.speed)
        self.finished.set()

    def anim_start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.name = f"button {self.name} animation"
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

    def set_key_icon(self):
        """
        If button has more icons, select one from button current value
        """
        if self.running:
            self.lit_display = not self.lit_display
            self.lit_dual = not self.lit_dual
        else:
            super().set_key_icon()  # off

    # Works with activation on/off
    def activate(self, state: bool):
        super().activate(state)
        if state:
            if self.is_valid():
                # self.label = f"pressed {self.current_value}"
                self.xp.commandOnce(self.command)
                if self.pressed_count % 2 == 0:
                    self.anim_stop()
                    self.render()
                else:
                    self.anim_start()

    # Works if underlying dataref changed
    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        self.previous_value = self.current_value
        self.current_value = self.button_value()
        logger.debug(f"{self.name}: {self.previous_value} -> {self.current_value}")
        if self.current_value is not None and self.current_value == 1:
            self.anim_start()
        else:
            if self.running:
                self.anim_stop()
            self.render()

    def clean(self):
        self.anim_stop()


# ###########################
# Mapping between button types and classes
#
STREAM_DECK_BUTTON_TYPES = {
    "none": Button,
    "page": ButtonPage,
    "push": ButtonPush,
    "dual": ButtonDual,
    "long-press": ButtonLongpress,
    "updown": ButtonUpDown,
    "animate": ButtonAnimate,
    "airbus": AirbusButton,
    "airbus-push": AirbusButtonPush,
    "airbus-animate": AirbusButtonAnimate,
    "reload": ButtonReload
}

LOUPEDECK_BUTTON_TYPES = {
    "none": Button,
    "page": ButtonPage,
    "push": ButtonPush,
    "dual": ButtonDual,
    "long-press": ButtonLongpress,
    "updown": ButtonUpDown,
    "animate": ButtonAnimate,  # loaded from xplaneudp/xplanesdk depending on integration
    "knob": ButtonKnob,
    "knob-push-pull": ButtonKnobPushPull,
    "knob-push-turn-release": ButtonKnobPushTurnRelease,
    "knob-dataref": ButtonKnobDataref,
    "button": ColoredButton,
    "side": ButtonSide,
    "airbus": AirbusButton,
    "airbus-push": AirbusButtonPush,
    "airbus-animate": AirbusButtonAnimate,
    "reload": ButtonReload
}

XTOUCH_MINI_BUTTON_TYPES = {
    "none": Button,
    "push": ButtonPush,
    "dual": ButtonDual,
    "long-press": ButtonLongpress,
    "knob": ButtonKnob,
    "knob-push-pull": ButtonKnobPushPull
}
