/* Deck class and accessory content (buttons)
 * 
 * Draws button placeholders at their location.
 * Capture interaction in the button and send it to Cockpitdecks.
 */

// P A R A M E T E R S
//
// LOCAL GLOBALS (should not be changed)
//
const EDITOR_MODE = false

const PRESENTATION_DEFAULTS = "presentation-default"
const ASSET_IMAGE_PATH = "/assets/images/"

const DEFAULT_WIDTH = 200
const DEFAULT_HEIGHT = 100
const TITLE_BAR_HEIGHT = 24

const OPTIONS = "options"
const OPT_CORNER_RADIUS = "corner_radius"
const OPT_PUSHPULL = "pushpull"

//
// USER SETTABLE GLOBALS
//
const DEFAULT_USER_PREFERENCES = {
    highlight: "#ffffff10",
    flash:  "#0f80ffb0",
    flash_duration: 100 
}

var USER_PREFERENCES = DEFAULT_USER_PREFERENCES

// Event codes
//  0 = Push/press RELEASE
//  1 = Push/press PRESS
//  2 = Turned clockwise
//  3 = Turned counter-clockwise
//  4 = Pulled
//  9 = Slider, event data contains value
// 10 = Touch start, event data contains value
// 11 = Touch end, event data contains value
// 12 = Swipe, event data contains value
// 14 = Tap, event data contains value


// Uses:
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

// Cache small pointers
function toDataUrl(url, callback) {
    var xhr = new XMLHttpRequest();
    xhr.onload = function() {
        var reader = new FileReader();
        reader.onloadend = function() {
            callback(reader.result);
        }
        reader.readAsDataURL(xhr.response);
        // console.log(url, xhr.response)
    };
    xhr.open('GET', url);
    xhr.responseType = 'blob';
    xhr.send();
}

var POINTERS = {};
["push", "pull", "clockwise", "counter-clockwise"].forEach( (url) => {
    toDataUrl(ASSET_IMAGE_PATH+url+".svg", function(base64url) {
        POINTERS[url.replace("-", "")] = base64url;
    });
});

var Sound = (function () {
    var df = document.createDocumentFragment();
    return function Sound(src) {
        var snd = new Audio(src);
        df.appendChild(snd); // keep in fragment until finished playing
        snd.addEventListener('ended', function () {df.removeChild(snd);});
        snd.play();
        return snd;
    }
}());

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
            stroke: USER_PREFERENCES.highlight,
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
            this.stroke(USER_PREFERENCES.highlight)
            this.container.style.cursor = "auto"
        });

        // Clicks
        this.on("pointerdown", function () {
            this.down = true
            this.stroke(USER_PREFERENCES.flash)
            const pos = this.getRelativePointerCoordinates();
            sendEvent(DECK.name, this.name, 1, {x: pos.x, y: pos.y, ts: Date.now()})
        });

        this.on("pointerup", function () {
            this.down = false
            this.stroke(USER_PREFERENCES.highlight)
            const pos = this.getRelativePointerCoordinates();
            sendEvent(DECK.name, this.name, 0, {x: pos.x, y: pos.y, ts: Date.now()})
        });

    }

    flash(colorin, colorout) {
        let that = this
        this.stroke(colorin)
        setTimeout(function() {
            that.stroke(colorout)
        }, USER_PREFERENCES.flash_duration)
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
            stroke: USER_PREFERENCES.highlight,
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
                this.stroke(USER_PREFERENCES.flash)
            }
            this.container.style.cursor = "pointer"
        });

        this.on("pointerout", function () {
            this.down = false
            this.stroke(USER_PREFERENCES.highlight)
            this.container.style.cursor = "auto"
        });

        // Clicks
        this.on("pointerdown", function () {
            this.down = true
            this.stroke(USER_PREFERENCES.flash)
            const pos = this.getRelativePointerCoordinates();
            sendEvent(DECK.name, this.name, 1, {x: pos.x, y: pos.y, ts: Date.now()})
        });

        this.on("pointerup", function () {
            this.down = false
            this.stroke(USER_PREFERENCES.highlight)
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
            stroke: USER_PREFERENCES.highlight,
            strokeWidth: 1,
            draggable: EDITOR_MODE
        });

        // console.log("user prefs", USER_PREFERENCES)

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
            this.stroke(USER_PREFERENCES.highlight)
            this.container.style.cursor = "auto"
        });

        this.on("pointermove", function () {
            if (this.down) {
                this.stroke(USER_PREFERENCES.flash)
            }
            switch (this.value()) { // SVG cursor origin is on middle top
            case 1:
                this.container.style.cursor = "url('"+POINTERS.push+"') 12 0, pointer";
                break;
            case 4:
                this.container.style.cursor = "url('"+POINTERS.pull+"') 12 0, pointer";
                break;
            case 2:
                this.container.style.cursor = "url('"+POINTERS.clockwise+"') 12 0, pointer";
                break;
            case 3:
                this.container.style.cursor = "url('"+POINTERS.counterclockwise+"') 12 0, pointer";
                break;
            }
        });

        // Clicks
        this.on("pointerdown", function () {
            this.down = true
            this.stroke(USER_PREFERENCES.flash)
            const pos = this.getRelativePointerCoordinates();
            // const pos2 = this.layer.getRelativePointerPosition() // , mx: pos2.x, my: pos2.y, cx: this.x(), cy: this.y()
            sendEvent(DECK.name, this.name, this.value(), {x: pos.x, y: pos.y, ts: Date.now()});
        });

        this.on("pointerup", function () {
            this.down = false
            this.stroke(USER_PREFERENCES.highlight)
            // sendEvent(DECK.name, this.name, 0, {x: 0, y: 0})
        });

        this.on("wheel", function (e) {
            const step = 4
            const pos = this.getRelativePointerCoordinates(); // unused, but supplied...
            // console.log("wheel", e, e.evt.deltaY)
            if (e.evt.deltaY > step) {
                // console.log("up")
                sendEvent(DECK.name, this.name, 2, {x: pos.x, y: pos.y, ts: Date.now()});
            } else if (e.evt.deltaY < (- step)) {
                // console.log("down")
                sendEvent(DECK.name, this.name, 3, {x: pos.x, y: pos.y, ts: Date.now()});
            }
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
            stroke: USER_PREFERENCES.highlight,
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
                this.flash(USER_PREFERENCES.flash, USER_PREFERENCES.highlight, USER_PREFERENCES.flash_duration)
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
            this.flash(USER_PREFERENCES.flash, USER_PREFERENCES.highlight, USER_PREFERENCES.flash_duration);
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
            stroke: USER_PREFERENCES.highlight,
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
            stroke: USER_PREFERENCES.highlight,
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

class Screen extends Konva.Rect {
    // Represent a simply rectangular display area

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
            stroke: USER_PREFERENCES.highlight,
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
            type: "screen",
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
        console.log("deck config", config)

        this._config = config;
        this._stage = stage

        this.deck_type = config[DECK_TYPE_DESCRIPTION];
        USER_PREFERENCES = Object.assign({}, DEFAULT_USER_PREFERENCES, config[PRESENTATION_DEFAULTS]);
        console.log("user preferences", USER_PREFERENCES)

        this.name = config.name;
        this.container = stage.container();

        this.buttons = {};
        this.key_images = {};

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
            const width = sizes == undefined || (sizes.constructor != Array) ? DEFAULT_WIDTH : sizes[0];
            const height = sizes == undefined || (sizes.constructor != Array) ? DEFAULT_HEIGHT : sizes[1];
            stage.width(width);
            stage.height(height);
            window.resizeTo(width,height + extra_space);
            console.log("set_default_size", width,height + extra_space);
        }

        this.background_layer = layer

        const background = this.deck_type.background
        if (background == undefined || background == null) {
            console.log("no background", this.deck_type);
            set_default_size(this.container, 100, 100, "red");
            return;
        }

        const sizes = background.size

        const bgcolor = background.color
        if (bgcolor != undefined) {
            this.container.style["background-color"] = "var(--deck-background-color)";
        }

        const background_image = background.image;
        if (background_image == undefined || background_image == null) {
            console.log("no background image", this.deck_type);
            set_default_size(this.container, sizes, "orange");
            return;
        }

        // this loads the image and sets the size of the window to the size of the image
        // if the image loading fails, the suplied background size is set (if available
        // otherwise a default value is used.)
        let deckImage = new Image();
        deckImage.onerror = function() {
            console.log("deckImage.onerror: backgroud image not found", BACKGROUND_IMAGE_PATH);
            set_default_size(this.container, sizes, "red");
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
            console.log("deckImage.onload", deckImage.naturalWidth,deckImage.naturalHeight + extra_space);
            original_width = deckImage.naturalWidth;
            original_height = deckImage.naturalHeight + extra_space;
            // layer.add(deckbg);
        };
        deckImage.src = BACKGROUND_IMAGE_PATH;
        // console.log("set_background_layer", DECK[DECK_TYPE_DESCRIPTION], image_path)
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
        this.image_layer = layer;
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
                // console.log("encoder", button)
                this.add(new Encoder(button, this.container))

            } else if (button.actions.indexOf("push") > -1 && button.actions.indexOf("encoder") == -1) {

                if (button.dimension != undefined && button.dimension.constructor == Array) {
                    // console.log("key", button)
                    this.add(new Key(button, this.container))

                } else {
                    // console.log("keyround", button)
                    this.add(new KeyRound(button, this.container))
                }

            } else if (button.actions.indexOf("swipe") > -1) {
                // console.log("touchscreen", button)
                this.add(new Touchscreen(button, this.container))

            } else if (button.actions.indexOf("cursor") > -1) {
                // console.log("slider", button)
                this.add(new Slider(button, this.container))

            } else if (button.actions.length == 0 && button.feedbacks.indexOf("led") > -1) {
                // console.log("led", button)
                this.add(new LED(button, this.container))

            } else if (button.actions.length == 0 && button.feedbacks.indexOf("image") > -1) {
                // console.log("screen", button)
                this.add(new Screen(button, this.container))

            } else {
                console.log("not building", button)
            }
        });
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

    set_key_image(key, image) {
        var offset = {x: 0, y: 0}
        const shape = this.buttons[key]
        if (shape == undefined || shape == null) {
            console.log("no shape", key);
            return ;
        }
        // if (checkNested(shape.config, "layout", "hardware", "type")) {
        //     if (shape.config.dimension != undefined && shape.config.dimension.constructor == Number) {
        //         offset = {x: -shape.radius(), y: -shape.radius()}
        //     }
        // } else if (shape.config.dimension != undefined && shape.config.dimension.constructor == Number) {
        //     // THIS MUST BE CHECKED
        //     console.log("offset", shape.name, shape.radius())
        //     offset = {x: -shape.radius(), y: -shape.radius()}
        // }
        if (shape.config.dimension != undefined && shape.config.dimension.constructor == Number) {
            console.log("offset", shape.name, shape.radius())
            offset = {x: -shape.radius(), y: -shape.radius()}
        }
        var that = this
        let buttonImage = new Image();
        buttonImage.onload = function () {
            let button = new Konva.Image({
                x: shape.x() + offset.x,
                y: shape.y() + offset.y,
                image: buttonImage
            });
            if (that.key_images[key] != undefined) { // remove old version
                that.key_images[key].destroy()
            }
            that.image_layer.add(button);
            that.key_images[key] = button
        };
        buttonImage.src = "data:image/jpeg;base64," + image;
    }

    play_sound(sound, type) {
        console.log("sound", "data:audio/"+type+";base64,")
        var snd = Sound("data:audio/"+type+";base64," + sound);
    }

    save() {
        const buttons = this.buttons.reduce((acc, val) => acc.push(val), Array());
        console.log(buttons);
    }
}
