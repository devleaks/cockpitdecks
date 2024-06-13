/* Deck class and accessory content (buttons)
 * 
 * Draws button placeholders at their location.
 * Capture interaction in the button and send it to Cockpitdecks.
 */

// A   F E W   C O N S T A N T 2
//
//
const HIGHLIGHT = "#ffffff80"  // white, opacity 80/FF

const FLASH = "#00ffff"  // cyan, opacity 50%
const FLASH_DURATION = 100

const EDITOR_MODE = false

const DECK_TYPE_DESCRIPTION = "deck-type-flat"

const DECK_BACKGROUND_IMAGE_PATH = "/assets/decks/images/"

const DEFAULT_WIDTH = 200
const DEFAULT_HEIGHT = 100
const TITLE_BAR_HEIGHT = 24

// Since no multiple inheritence, and traits are too heavy
// some code needs repeating...

// B U T T O N S
//
// Key
// Simple key to press, square, with optional rounded corners.
//
class Key extends Konva.Rect {
    // Represent a simply rectangular key

    constructor(config, container) {

        let corner_radius = 0
        if (config.options != undefined && config.options != null) {
            corner_radius = parseInt(config.options.corner_radius == undefined ? 0 : config.options.corner_radius)
        }

        super({
            x: config.position[0],
            y: config.position[1],
            width: config.dimension[0],
            height: config.dimension[1],
            cornerRadius: corner_radius,
            stroke: HIGHLIGHT,
            strokeWidth: 1,
            draggable: EDITOR_MODE
        });

        this.config = config
        this.name = config.name
        this.container = container

        this.down = false

        // Hover
        this.on("pointerover", function () {
            if (this.down) {
                this.stroke(FLASH)
            }
            this.container.style.cursor = "pointer"
        });

        this.on("pointerout", function () {
            this.down = false
            this.stroke(HIGHLIGHT)
            this.container.style.cursor = "auto"
        });

        // Clicks
        this.on("pointerdown", function () {
            this.down = true
            this.stroke(FLASH)
            sendEvent(DECK.name, this.name, 1, {x: 0, y: 0})
        });

        this.on("pointerup", function () {
            this.down = false
            this.stroke(HIGHLIGHT)
            sendEvent(DECK.name, this.name, 0, {x: 0, y: 0})
        });

    }

    flash(colorin, colorout) {
        let that = this
        this.stroke(colorin)
        setTimeout(function() {
            that.stroke(colorout)
        }, FLASH_DURATION)
    }

    add_to_layer(layer) {
        this.layer = layer;
        layer.add(this);
    }

    save() {
        const code = {
            type: "key",
            name: this.name,
            x: this.x(),
            y: this.y(),
            width: this.width(),
            height: this.height(),
            corner_radius: this.cornerRadius()
        };
        return code;
    }
}

// KeyRound
// Simple key to press but round.
//
class KeyRound extends Konva.Circle {
    // Represent a simply rectangular key

    constructor(config, container) {
        super({
            x: config.position[0],
            y: config.position[1],
            radius: config.dimension, // only one value
            stroke: HIGHLIGHT,
            strokeWidth: 1,
            draggable: EDITOR_MODE
        });

        this.config = config
        this.name = config.name
        this.container = container

        this.down = false

        // Hover
        this.on("pointerover", function () {
            if (this.down) {
                this.stroke(FLASH)
            }
            this.container.style.cursor = "pointer"
        });

        this.on("pointerout", function () {
            this.down = false
            this.stroke(HIGHLIGHT)
            this.container.style.cursor = "auto"
        });

        // Clicks
        this.on("pointerdown", function () {
            this.down = true
            this.stroke(FLASH)
            sendEvent(DECK.name, this.name, 1, {x: 0, y: 0})
        });

        this.on("pointerup", function () {
            this.down = false
            this.stroke(HIGHLIGHT)
            sendEvent(DECK.name, this.name, 0, {x: 0, y: 0})
        });

    }

    flash(colorin, colorout, time) {
        let that = this
        this.stroke(colorin)
        setTimeout(function() {
            that.stroke(colorout)
        }, time)
    }

    add_to_layer(layer) {
        this.layer = layer;
        layer.add(this);
    }

    save() {
        const code = {
            type: "keyr",
            name: this.name,
            x: this.x(),
            y: this.y(),
        };
        return code;
    }
}

// Encoder
// Round encoder knob.
//
class Encoder extends Konva.Circle {

    constructor(config, container) {
        super({
            x: config.position[0],
            y: config.position[1],
            radius: config.dimension, // only one value
            stroke: HIGHLIGHT,
            strokeWidth: 1,
            draggable: EDITOR_MODE
        });

        this.config = config
        this.name = config.name
        this.container = container

        // Encoder button has optional push/pull behavior like Airbus FCU. Wow.
        this.pushpull = false
        if (config.options != undefined && config.options != null) {
            this.pushpull = config.options.pushpull
        }

        this.down = false

        // Hover
        this.on("pointerout", function () {
            this.down = false
            this.stroke(HIGHLIGHT)
            this.container.style.cursor = "auto"
        });

        this.on("pointermove", function () {
            if (this.down) {
                this.stroke(FLASH)
            }
            switch (this.value()) { // SVG cursor origin is on middle top
            case 1:
                this.container.style.cursor = "url('/assets/images/push.svg') 12 0, pointer";
                break;
            case 4:
                this.container.style.cursor = "url('/assets/images/pull.svg') 12 0, pointer";
                break;
            case 2:
                this.container.style.cursor = "url('/assets/images/clockwise.svg') 12 0, pointer";
                break;
            case 3:
                this.container.style.cursor = "url('/assets/images/counter-clockwise.svg') 12 0, pointer";
                break;
            }
        });

        // Clicks
        this.on("pointerdown", function () {
            this.down = true
            this.stroke(FLASH)
            sendEvent(DECK.name, this.name, this.value(), {x: 0, y: 0})
        });

        this.on("pointerup", function () {
            this.down = false
            this.stroke(HIGHLIGHT)
            sendEvent(DECK.name, this.name, 0, {x: 0, y: 0})
        });

    }

    value() {
        // How encoder was turned, pressed, or optionally pulled. Wow.
        const w = Math.floor(this.width() / 4)
        if ( this.layer.getRelativePointerPosition().x < (this.x()-w)) {
            return 2
        } else if ( this.layer.getRelativePointerPosition().x > (this.x()+w)) {
            return 3
        } else if ( this.pushpull && this.layer.getRelativePointerPosition().y < this.y()) {
            return 4
        } else {
            return 1
        }
    }

    flash(colorin, colorout, time) {
        let that = this
        this.stroke(colorin)
        setTimeout(function() {
            that.stroke(colorout)
        }, time)
    }

    add_to_layer(layer) {
        this.layer = layer;
        layer.add(this);
    }

    save() {
        const code = {
            type: "encoder",
            name: this.name,
            x: this.x(),
            y: this.y(),
            radius: this.radius()
        };
        return code;
    }
}

//
//
//
class Touchscreen extends Konva.Rect {

    constructor(config, container) {

        let corner_radius = 0
        if (config.options != undefined && config.options != null) {
            corner_radius = parseInt(config.options.corner_radius == undefined ? 0 : config.options.corner_radius)
        }

        super({
            x: config.position[0],
            y: config.position[1],
            width: config.dimension[0],
            height: config.dimension[1],
            cornerRadius: corner_radius,
            stroke: HIGHLIGHT,
            strokeWidth: 1,
            draggable: EDITOR_MODE
        });

        this.config = config
        this.name = config.name
        this.container = container

        this.inside = false

        // Inside key
        this.on("pointerover", function () {
            this.container.style.cursor = "pointer"
            this.inside = true
        });

        this.on("pointerout", function () {
            this.container.style.cursor = "auto"
            this.inside = false
        });

        // Clicks
        this.on("pointerdown", function () {
            this.flash(FLASH, HIGHLIGHT, FLASH_DURATION)
            sendEvent(DECK.name, 1, 1, {x: 0, y: 0})
        });

        this.on("pointerup", function () {
            sendEvent(DECK.name, 1, 0, {x: 0, y: 0})
        });

    }

    flash(colorin, colorout, time) {
        let that = this
        this.stroke(colorin)
        setTimeout(function() {
            that.stroke(colorout)
        }, time)
    }

    add_to_layer(layer) {
        this.layer = layer;
        layer.add(this);
    }

    save() {
        const code = {
            type: "touchscreen",
            name: this.name,
            x: this.x(),
            y: this.y(),
            width: this.width(),
            height: this.height(),
            corner_radius: this.cornerRadius()
        };
        return code;
    }
}

//
//
//
class Slider extends Konva.Rect {

    constructor(config, container) {

        let corner_radius = 0
        if (config.options != undefined && config.options != null) {
            corner_radius = parseInt(config.options.corner_radius == undefined ? 0 : config.options.corner_radius)
        }

        super({
            x: config.x,
            y: config.y,
            width: config.width,
            height: config.height,
            cornerRadius: corner_radius,
            stroke: HIGHLIGHT,
            strokeWidth: 1,
            draggable: EDITOR_MODE
        });

        this.config = config
        this.name = config.name
        this.container = container

        this.inside = false
    }

    add_to_layer(layer) {
        this.layer = layer;
        layer.add(this);
    }

    save() {
        const code = {
            type: "slider",
            name: this.name,
            x: this.x(),
            y: this.y(),
            width: this.width(),
            height: this.height(),
            corner_radius: this.cornerRadius()
        };
        return code;
    }
}

//
//
//
class Overlay {  // later, idea: overlay text or image on top of background (logo, etc.)

    constructor(config, container) {
        this.config = config
        this.container = container
    }

    add_to_layer(layer) {
        this.layer = layer;
        layer.add(this);
    }

}

CONSTRUCTORS = {
    "key": Key,
    "keyr": KeyRound,
    "encoder": Encoder,
    "touchsreen": Touchscreen,
    "slider": Slider
}

// D E C K
//
//
class Deck {

    constructor(config, container) {
        this._config = config;

        this.name = config.name;
        this.container = container;

        this.deck_type = config[DECK_TYPE_DESCRIPTION];
        console.log("config", this.deck_type)

        this.buttons = {};
        this.build(config);
    }

    add(button) {
        this.buttons[button.name] = button
    }

    get_xy(key) {
        const shape = this.buttons[key]
        if (shape != undefined && shape != null) {
            // console.log("get_xy", key, shape.x(), shape.y());
            return {"x": shape.x(), "y": shape.y()}
        }
        console.log("get_xy", key, shape);
        return {"x": 0, "y": 0};
    }

    build(layout) {
        this.deck_type.buttons.forEach((button) => {
            // decide which shape to use
            if (button.actions.indexOf("encoder") > -1) {
                // console.log("encoder", button)
                this.add(new Encoder(button, this.container))
            } else if (button.actions.indexOf("push") > -1 && button.actions.indexOf("encoder") == -1) {
                if (button.dimension.constructor == Array) {
                    // console.log("key", button)
                    this.add(new Key(button, this.container))
                } else {
                    // console.log("keyround", button)
                    this.add(new KeyRound(button, this.container))
                }
            } else if (button.actions.indexOf("swipe") > -1) {
                // console.log("touchscreen", button)
                this.add(new Touchscreen(button, this.container))
            }
        });
        // console.log("build", this.buttons)
    }

    set_background_layer(layer, stage) {
        // Add bacground image and resize deck around it.
        // Resize window as well. Cannot get rid of top bar... (adds 24px)
        const extra_space = EDITOR_MODE ? 2 * TITLE_BAR_HEIGHT : TITLE_BAR_HEIGHT;

        function set_default_size(container, sizes, color) {
            container.style["border"] = "1px solid "+color;
            const width = sizes == undefined ? DEFAULT_WIDTH : sizes[0]
            const height = sizes == undefined ? DEFAULT_HEIGHT : sizes[1]
            stage.width(width);
            stage.height(height);
            window.resizeTo(width,height + extra_space);
        }

        const background = this.deck_type.background
        if (background == undefined || background == null) {
            console.log("no background", this.deck_type)
            set_default_size(this.container, 100, 100, "red")
            return;
        }

        const sizes = background.size

        const bgcolor = background.color
        if (bgcolor != undefined) {
            this.container.style["background-color"] = bgcolor
        }

        const background_image = background.image;
        if (background_image == undefined || background_image == null) {
            console.log("no background image", this.deck_type)
            set_default_size(this.container, sizes, "orange")
            return;
        }

        let deckImage = new Image();
        deckImage.onerror = function() {
            set_default_size(this.container, sizes, "red")
        }
        deckImage.onload = function () {
            let deckbg = new Konva.Image({
                x: 0,
                y: 0,
                image: deckImage
            });
            stage.width(deckImage.naturalWidth);
            stage.height(deckImage.naturalHeight);
            window.resizeTo(deckImage.naturalWidth,deckImage.naturalHeight + extra_space);
            layer.add(deckbg);
        };
        deckImage.src = DECK_BACKGROUND_IMAGE_PATH + background_image;
        // console.log("set_background_layer", this.buttons)
    }

    set_interaction_layer(layer) {
        for (let name in this.buttons) {
            if(this.buttons.hasOwnProperty(name)) {
                this.buttons[name].add_to_layer(layer);
            }
        }
        // console.log("set_interaction_layer", this.buttons)
    }

    save() {
        const buttons = this.buttons.reduce((acc, val) => acc.push(val), Array());
        console.log(buttons);
    }

    set_key_image(key, image, layer) {
        console.log(key, image.length)
        let coords = this.get_xy(key);
        let buttonImage = new Image();
        buttonImage.onload = function () {
            let button = new Konva.Image({
                x: coords.x,
                y: coords.y,
                image: buttonImage
            });
            layer.add(button);
        };
        buttonImage.src = "data:image/jpeg;base64,"+image;
    }

}
