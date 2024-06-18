/* Deck class and accessory content (buttons)
 * 
 * Draws button placeholders at their location.
 * Capture interaction in the button and send it to Cockpitdecks.
 */

// L O C A L   P A R A M E T E R S
//
// Conventions and codes
//
const HIGHLIGHT = "#ffffff10"  //  white, opacity 40/FF

const FLASH = "#0f80ffb0"  // blue
const FLASH_DURATION = 100

const EDITOR_MODE = false

const DECK_TYPE_DESCRIPTION = "deck-type-flat"

const DECK_BACKGROUND_IMAGE_PATH = "/assets/decks/images/"

const DEFAULT_WIDTH = 200
const DEFAULT_HEIGHT = 100
const TITLE_BAR_HEIGHT = 24

const OPTIONS = "options"
const OPT_CORNER_RADIUS = "corner_radius"
const OPT_PUSHPULL = "pushpull"

// Event codes
// 0 = Push/press RELEASE
// 1 = Push/press PRESS
// 2 = Turned clockwise
// 3 = Turned counter-clockwise
// 4 = Pulled
// 9 = Slider, event data contains value
// 10 = Touch start, event data contains value
// 11 = Touch end, event data contains value
// 12 = Swipe, event data contains value
// 14 = Tap, event data contains value


// Uses:
// function sendCode(deck, code)
// sendEvent(deck, key, event, data)

// https://stackoverflow.com/questions/2631001/test-for-existence-of-nested-javascript-object-key
function checkNested(obj /*, level1, level2, ... levelN*/) {
    var args = Array.prototype.slice.call(arguments, 1);

    for (var i = 0; i < args.length; i++) {
        if (!obj || !obj.hasOwnProperty(args[i])) {
            return false;
        }
        obj = obj[args[i]];
    }
    return true;
}

function getNested(obj, ...args) {
  return args.reduce((obj, level) => obj && obj[level], obj)
}

// B U T T O N S
//
// Key
// Simple key to press, square, with optional rounded corners.
//
class Key extends Konva.Rect {
    // Represent a simply rectangular key

    constructor(config, container) {

        let corner_radius = 0
        if (checkNested(config, OPTIONS, OPT_CORNER_RADIUS)) {
            corner_radius = parseInt(config.options[OPT_CORNER_RADIUS])
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
            const pos = this.getRelativePointerCoordinates();
            sendEvent(DECK.name, this.name, 1, {x: pos.x, y: pos.y, ts: Date.now()})
        });

        this.on("pointerup", function () {
            this.down = false
            this.stroke(HIGHLIGHT)
            const pos = this.getRelativePointerCoordinates();
            sendEvent(DECK.name, this.name, 0, {x: pos.x, y: pos.y, ts: Date.now()})
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

    getRelativePointerCoordinates() {
        return {
            x: this.layer.getRelativePointerPosition().x - this.x(), 
            y: this.layer.getRelativePointerPosition().y - this.y()
        }
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
            const pos = this.getRelativePointerCoordinates();
            sendEvent(DECK.name, this.name, 1, {x: pos.x, y: pos.y, ts: Date.now()})
        });

        this.on("pointerup", function () {
            this.down = false
            this.stroke(HIGHLIGHT)
            const pos = this.getRelativePointerCoordinates();
            sendEvent(DECK.name, this.name, 0, {x: pos.x, y: pos.y, ts: Date.now()})
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

    getRelativePointerCoordinates() {
        return {
            x: this.layer.getRelativePointerPosition().x - this.x(), 
            y: this.layer.getRelativePointerPosition().y - this.y()
        }
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
        if (checkNested(config, OPTIONS, OPT_PUSHPULL)) {
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
            const pos = this.getRelativePointerCoordinates();
            // const pos2 = this.layer.getRelativePointerPosition() // , mx: pos2.x, my: pos2.y, cx: this.x(), cy: this.y()
            sendEvent(DECK.name, this.name, this.value(), {x: pos.x, y: pos.y, ts: Date.now()});
        });

        this.on("pointerup", function () {
            this.down = false
            this.stroke(HIGHLIGHT)
            // sendEvent(DECK.name, this.name, 0, {x: 0, y: 0})
        });

    }

    value() {
        // How encoder was turned, pressed, or optionally pulled. Wow.
        const w = Math.floor(this.radius() / 2)
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

    value2(pos) {
        // How encoder was turned, pressed, or optionally pulled. Wow.
        const w = Math.floor(this.radius() / 2)
        if ( pos.x < -w) {
            return 2 // rotate CW
        } else if ( pos.x > w) {
            return 3 // rotate CCW
        } else if ( this.pushpull && pos.y < 0) {
            return 4 // pulled, if capable
        } else {
            return 1 // pushed, pressed
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
        // layer.add(new Konva.Rect({
        //     x: 0,
        //     y: 0,
        //     width: 10,
        //     height: 10,
        //     stroke: "yellow",
        //     strokeWidth: 1,
        // }));
        // layer.add(new Konva.Rect({
        //     x: this.config.position[0],
        //     y: this.config.position[1],
        //     width: 48,
        //     height: 48,
        //     stroke: "red",
        //     strokeWidth: 1,
        // }));
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

    getRelativePointerCoordinates() {
        return {
            x: this.layer.getRelativePointerPosition().x - this.x(),
            y: this.layer.getRelativePointerPosition().y - this.y()
        }
    }
}

// Touchscreen
// Rectangular touch screen
//
class Touchscreen extends Konva.Rect {

    constructor(config, container) {

        let corner_radius = 0
        if (checkNested(config, OPTIONS, OPT_CORNER_RADIUS)) {
            corner_radius = parseInt(config.options[OPT_CORNER_RADIUS])
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

        this.sliding = false
        this.pressed = false

        // Inside key
        this.on("pointerover", function () {
            this.container.style.cursor = "pointer"
        });

        this.on("pointerout", function () {
            this.container.style.cursor = "auto"
        });

        // Pointer events: 
        this.on("pointerdown", function () {
            this.container.style.cursor = "grab"
            this.pressed = true
            const pos = this.getRelativePointerCoordinates();
            // console.log("pointerdown", pos, Date.now());
        });

        this.on("pointermove", function () {
            if (this.pressed && ! this.sliding) { // sliding start
                const pos = this.getRelativePointerCoordinates();
                this.sliding = true
                this.container.style.cursor = "grabbing"
                // console.log("touchstart/pointermove", pos, Date.now());
                sendEvent(DECK.name, this.name, 10, {x: pos.x, y: pos.y, ts: Date.now()});
            }
        });

        this.on("pointerup", function () {
            this.pressed = false
            if (! this.sliding) {
                const pos = this.getRelativePointerCoordinates();
                this.flash(FLASH, HIGHLIGHT, FLASH_DURATION)
                // console.log("tap/pointerup", pos, Date.now());
                sendEvent(DECK.name, this.name, 14, {x: pos.x, y: pos.y, ts: Date.now()});
            } else {
                const pos = this.getRelativePointerCoordinates();
                this.sliding = false
                this.container.style.cursor = "pointer"
                // console.log("touchend/pointerdown", pos, Date.now());
                sendEvent(DECK.name, this.name, 11, {x: pos.x, y: pos.y, ts: Date.now()});
            }
        });

        // Touch events: touchstart, touchmove, touchend, tap
        this.on("tap", function () {
            const pos = this.getRelativePointerCoordinates();
            this.flash(FLASH, HIGHLIGHT, FLASH_DURATION);
            // console.log("tap", pos, Date.now());
            sendEvent(DECK.name, this.name, 1, {x: pos.x, y: pos.y, ts: Date.now()});
        });

        this.on("touchmove", function () {
            this.container.style.cursor = "grabbing";
        });

        this.on("touchstart", function () {
            this.container.style.cursor = "grab";
            const pos = this.getRelativePointerCoordinates();
            // console.log("touchstart", pos, Date.now());
            sendEvent(DECK.name, this.name, 10, {x: pos.x, y: pos.y, ts: Date.now()});
        });

        this.on("touchend", function () {
            this.container.style.cursor = "pointer";
            const pos = this.getRelativePointerCoordinates();
            // console.log("touchend", pos, Date.now());
            sendEvent(DECK.name, this.name, 11, {x: pos.x, y: pos.y, ts: Date.now()});
        });

    }

    flash(colorin, colorout, time) {
        let that = this;
        this.stroke(colorin)
        setTimeout(function() {
            that.stroke(colorout)
        }, time)
    }

    add_to_layer(layer) {
        this.layer = layer;
        layer.add(this);
    }

    getRelativePointerCoordinates() {
        return {
            x: this.layer.getRelativePointerPosition().x - this.x(), 
            y: this.layer.getRelativePointerPosition().y - this.y()
        }
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

// Slider (Cursor)
// Can be horizontal or vertical
// Currently only send value on drag start and end
// to limit the amount of events.
// A Slider consists of a ramp (Slider) and a moving cursor (SliderHandle).
//
class SliderHandle extends Konva.Rect {

    constructor(config, container) {

        const x = config.position[0] + config.dimension[0] / 2 - config.handle[0]/2
        const y = config.position[1] + config.dimension[1] / 2 - config.handle[1]/2
        super({
            x: x,
            y: y,
            width: config.handle[0],
            height: config.handle[1],
            cornerRadius: config.handle[2] != undefined ? config.handle[2] : 4,
            fill: "lightgrey",
            draggable: true
        });

        this.config = config
        this.name = config.name
        this.container = container

        this.horizontal = config.dimension[0] > config.dimension[1]
        this.invert = true

        const c = this.horizontal ? 0 : 1
        const c2 = this.horizontal ? 1 : 0
        this.cmin = config.position[c] + 2  // max pos of mouse
        this.cmax = config.position[c] + config.dimension[c] - 2
        this.pmin = config.position[c] - config.handle[c] / 2 + 1  // pos of handle at min or max
        this.pmax = config.position[c] + config.dimension[c] - config.handle[c] / 2 - 1
        this.crange = config.dimension[c]
        this.range = config.range

        this.middle = x
        this.pressed = false

        // Inside key
        this.on("pointerover", function () {
            this.container.style.cursor = "ns-resize"
        });

        this.on("pointerout", function () {
            this.container.style.cursor = "auto"
        });

        // Slider drag events:
        this.on("dragbegin", function () {
            const pos = this.layer.getRelativePointerPosition();
            this.constraint(pos)
            // console.log("cursor/dragbegin", this.value(pos), Date.now());
            sendEvent(DECK.name, this.name, 9, {x: pos.x, y: pos.y, value: this.value(pos), ts: Date.now()});
        });

        this.on("dragmove", function () {
            const pos = this.layer.getRelativePointerPosition();
            this.constraint(pos)
            // console.log("cursor/dragmove", this.value(pos), Date.now());
            // sendEvent(DECK.name, this.name, 9, {x: pos.x, y: pos.y, value: this.value(pos), ts: Date.now()});
        });

        this.on("dragend", function () {
            this.pressed = false
            this.container.style.cursor = "ns-resize"
            const pos = this.layer.getRelativePointerPosition();
            this.constraint(pos)
            // console.log("cursor/dragend", this.value(pos), Date.now());
            sendEvent(DECK.name, this.name, 9, {x: pos.x, y: pos.y, value: this.value(pos), ts: Date.now()});
        });

    }

    add_to_layer(layer) {
        this.layer = layer;
        layer.add(this);
    }

    value(pos) {
        var value = this.horizontal ? pos.x : pos.y
        value = value - this.cmin
        if (value < 0) {
            value = 0
        } else if (value > this.crange) {
            value = this.crange
        }
        if (this.invert) {
            value = this.crange - value
        }
        const fraction = value / this.crange
        const range = (this.range[1] - this.range[0])
        const result = this.range[0] + Math.round( fraction * range )
        return result
    }

    constraint(pos) {
        if (this.horizontal) {
            ;
        } else {
            this.x(this.middle)
            if (pos.y < this.cmin) {
                this.y(this.pmin)
            }
            if (pos.y > this.cmax) {
                this.y(this.pmax)
            }
        }
    }
}


class Slider extends Konva.Rect {

    constructor(config, container) {

        let corner_radius = 0
        if (checkNested(config, OPTIONS, OPT_CORNER_RADIUS)) {
            corner_radius = parseInt(config.options[OPT_CORNER_RADIUS])
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

        this.handle = new SliderHandle(config, container)
    }

    add_to_layer(layer) {
        this.layer = layer;
        layer.add(this);
        this.handle.add_to_layer(layer)
    }

    save() {
        // to be corrected for handle
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
class LED extends Konva.Rect {
    // Represent a simply rectangular led, no activation, just display

    constructor(config, container) {

        let corner_radius = 0
        if (checkNested(config, OPTIONS, OPT_CORNER_RADIUS)) {
            corner_radius = parseInt(config.options[OPT_CORNER_RADIUS])
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
    }

    add_to_layer(layer) {
        this.layer = layer;
        layer.add(this);
    }

    save() {
        const code = {
            type: "led",
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

// D E C K
//
//
class Deck {

    constructor(config, stage) {
        console.log(config)

        this._config = config;
        this._stage = stage

        this.deck_type = config[DECK_TYPE_DESCRIPTION];

        this.name = config.name;
        this.container = stage.container();

        this.buttons = {};

        this.build();
    }

    //
    // Installation of layers
    //
    set_background_layer(layer) {
        // Add bacground image and resize deck around it.
        // Resize window as well. Cannot get rid of top bar... (adds 24px)
        const extra_space = EDITOR_MODE ? 2 * TITLE_BAR_HEIGHT : TITLE_BAR_HEIGHT;
        var stage = this._stage;

        function set_default_size(container, sizes, color) {
            container.style["border"] = "1px solid "+color;
            const width = sizes == undefined ? DEFAULT_WIDTH : sizes[0]
            const height = sizes == undefined ? DEFAULT_HEIGHT : sizes[1]
            stage.width(width);
            stage.height(height);
            window.resizeTo(width,height + extra_space);
        }

        this.background_layer = layer

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

    set_hardware_image_layer(layer) {
        this.hardware_layer = layer
        // console.log("set_hardware_image_layer", this.buttons)
    }

    set_interaction_layer(layer) {
        this.interaction_layer = layer
        for (let name in this.buttons) {
            if(this.buttons.hasOwnProperty(name)) {
                this.buttons[name].add_to_layer(layer);
            }
        }
        // console.log("set_interaction_layer", this.buttons)
    }

    set_image_layer(layer) {
        this.image_layer = layer
        // console.log("set_image_layer", this.buttons)
    }

    //
    // Building deck from buttons
    //
    build() {
        this.deck_type.buttons.forEach((button) => {
            // decide which shape to use
            // shape selected here will be an interactor only

            if (button.actions.indexOf("encoder") > -1) {
                //console.log("encoder", button)
                this.add(new Encoder(button, this.container))

            } else if (button.actions.indexOf("push") > -1 && button.actions.indexOf("encoder") == -1) {

                if (button.dimension != undefined && button.dimension.constructor == Array) {
                    //console.log("key", button)
                    this.add(new Key(button, this.container))

                } else {
                    //console.log("keyround", button)
                    this.add(new KeyRound(button, this.container))
                }

            } else if (button.actions.indexOf("swipe") > -1) {
                //console.log("touchscreen", button)
                this.add(new Touchscreen(button, this.container))

            } else if (button.actions.indexOf("cursor") > -1) {
                //console.log("slider", button)
                this.add(new Slider(button, this.container))

            } else if (button.actions.length == 0 && button.feedbacks.indexOf("led") > -1) {
                console.log("led", button)
                this.add(new LED(button, this.container))
            }
        });
        // console.log("build", this.buttons)
    }

    add(button) {
        // button.addName(button.name)
        this.buttons[button.name] = button
    }

    get_xy(key) {
        const shape = this.buttons[key]
        if (shape != undefined && shape != null) {
            // console.log("get_xy", key, shape.x(), shape.y());
            return {"x": shape.x(), "y": shape.y()}
        }
        console.log("get_xy no shape", key, shape);
        return {"x": 0, "y": 0};
    }

    get_hardware_image_offset(key) {
        // Empirically try to guess if this is a hardware image.
        // If it is, and if its dimension is a scalar value (= radius)
        // we have to offset the image since it is center.
        const key_def = this.buttons[key];
        if (key_def != undefined) {
            if (checkNested(key_def.config, "layout", "hardware", "type")) {
                if (key_def.config.dimension != undefined && key_def.config.dimension.constructor == Number) {
                    const radius = key_def.radius()
                    return {x: -radius, y: -radius}
                }
            }
        } else {
            console.log("could not find key", key)
        }
        return 
    }

    set_key_image(key, image, layer) {
        var offset = {x: 0, y: 0}
        const shape = this.buttons[key]
        if (shape == undefined || shape == null) {
            console.log("no shape", key);
            return ;
        }
        if (checkNested(shape.config, "layout", "hardware", "type")) {
            if (shape.config.dimension != undefined && shape.config.dimension.constructor == Number) {
                offset = {x: -shape.radius(), y: -shape.radius()}
            }
        }
        let buttonImage = new Image();
        buttonImage.onload = function () {
            let button = new Konva.Image({
                x: shape.x() + offset.x,
                y: shape.y() + offset.y,
                image: buttonImage
            });
            layer.add(button);
        };
        buttonImage.src = "data:image/jpeg;base64," + image;
    }

    save() {
        const buttons = this.buttons.reduce((acc, val) => acc.push(val), Array());
        console.log(buttons);
    }
}
