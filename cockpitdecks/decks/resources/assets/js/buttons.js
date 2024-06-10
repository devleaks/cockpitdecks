/* Deck class and accessory content (buttons)
 * 
 * Draws button placeholders at their location.
 * Capture interaction in the button and send it to Cockpitdecks.
 */
TRANSLUCENT_WHITE = "#ffffff80"  // white, opacity 80/FF
HIGHLIGHT = "#00ffff"  // cyan, opacity 50%
EDITOR_MODE = false
ROTATE_CLOCKWISE = `data:image/svg+xml;utf8,<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg width="100%" height="100%" viewBox="0 0 24 24" version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xml:space="preserve" xmlns:serif="http://www.serif.com/" style="fill-rule:evenodd;clip-rule:evenodd;stroke-linejoin:round;stroke-miterlimit:2;">
    <g transform="matrix(0.0354795,-0.0867772,0.0867772,0.0354795,-3.16272,18.5397)">
        <g>
            <path d="M192.7,7.7C191.5,10.1 189.2,15 187.6,18.5L184.6,24.8L181.8,23.4C163.9,14.4 144.6,10.2 123.8,10.8C106.1,11.4 93.2,14.5 77.2,22.2C63.5,28.8 53.3,36.2 42.8,47.1C24.2,66.4 12.6,92.4 10.6,118.7L10,124L12.6,124.4C14,124.6 20.9,125.7 27.9,126.8C34.9,127.9 42.1,129 44,129.2L47.3,129.6L47.7,125.6C49.5,103.4 56.9,86.6 70.8,72.5C81.8,61.3 93.6,54.6 109.3,50.5C115.4,49 116.4,48.8 128.2,48.9C140.1,48.9 140.8,49 147.4,50.7C153.9,52.4 163.5,56.2 166.6,58.2L168,59.1L165.5,64.5C164.1,67.5 162,71.9 160.8,74.3C159.6,76.7 158.8,78.6 159.1,78.6C160.6,78.6 214.3,59.3 214.3,58.7C214.3,58.1 204.8,30.8 195.7,5.3L195,3.2L192.7,7.7Z" style="fill-rule:nonzero;stroke:white;stroke-width:10.67px;"/>
        </g>
    </g>
</svg>`
ROTATE_COUNTER_CLOCKWISE = `data:image/svg+xml;utf8,<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg width="100%" height="100%" viewBox="0 0 24 24" version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xml:space="preserve" xmlns:serif="http://www.serif.com/" style="fill-rule:evenodd;clip-rule:evenodd;stroke-linejoin:round;stroke-miterlimit:2;">
    <g transform="matrix(0.0354795,-0.0867772,0.0867772,0.0354795,-3.65214,18.5614)">
        <g transform="matrix(0.713554,-0.7006,-0.7006,-0.713554,125.022,304.424)">
            <path d="M192.7,7.7C191.5,10.1 189.2,15 187.6,18.5L184.6,24.8L181.8,23.4C163.9,14.4 144.6,10.2 123.8,10.8C106.1,11.4 93.2,14.5 77.2,22.2C63.5,28.8 53.3,36.2 42.8,47.1C24.2,66.4 12.6,92.4 10.6,118.7L10,124L12.6,124.4C14,124.6 20.9,125.7 27.9,126.8C34.9,127.9 42.1,129 44,129.2L47.3,129.6L47.7,125.6C49.5,103.4 56.9,86.6 70.8,72.5C81.8,61.3 93.6,54.6 109.3,50.5C115.4,49 116.4,48.8 128.2,48.9C140.1,48.9 140.8,49 147.4,50.7C153.9,52.4 163.5,56.2 166.6,58.2L168,59.1L165.5,64.5C164.1,67.5 162,71.9 160.8,74.3C159.6,76.7 158.8,78.6 159.1,78.6C160.6,78.6 214.3,59.3 214.3,58.7C214.3,58.1 204.8,30.8 195.7,5.3L195,3.2L192.7,7.7Z" style="fill-rule:nonzero;stroke:white;stroke-width:10.67px;"/>
        </g>
    </g>
</svg>`

class Key extends Konva.Rect {
    // Represent a simply rectangular key

    constructor(config, container) {
        super({
            x: config.x,
            y: config.y,
            width: config.width,
            height: config.height,
            cornerRadius: config.corner_radius,
            stroke: TRANSLUCENT_WHITE,
            strokeWidth: 1,
            draggable: EDITOR_MODE
        });

        this.config = config
        this.name = config.name
        this.container = container

        this.inside = false

        // Inside key
        this.on('pointerover', function () {
            this.container.style.cursor = "pointer"
            this.inside = true
        });

        this.on('pointerout', function () {
            this.container.style.cursor = "auto"
            this.inside = false
        });

        // Clicks
        this.on('pointerdown', function () {
            this.flash(HIGHLIGHT, TRANSLUCENT_WHITE)
            sendEvent(DECK.name, 1, 1, {x: 0, y: 0})
        });

        this.on('pointerup', function () {
            sendEvent(DECK.name, 1, 0, {x: 0, y: 0})
        });

    }

    flash(colorin, colorout) {
        let that = this
        this.stroke(colorin)
        setTimeout(function() {
            that.stroke(colorout)
        }, 500)
    }
}


class KeyRound extends Konva.Circle {
    // Represent a simply rectangular key

    constructor(config, container) {
        super({
            x: config.x,
            y: config.y,
            radius: config.radius,
            stroke: TRANSLUCENT_WHITE,
            strokeWidth: 1,
            draggable: EDITOR_MODE
        });

        this.config = config
        this.name = config.name
        this.container = container

        this.inside = false

        // Inside key
        this.on('pointerover', function () {
            this.container.style.cursor = "pointer"
            this.inside = true
        });

        this.on('pointerout', function () {
            this.container.style.cursor = "auto"
            this.inside = false
        });

        // Clicks
        this.on('pointerdown', function () {
            sendEvent(DECK.name, 1, 1, {x: 0, y: 0})
        });

        this.on('pointerup', function () {
            sendEvent(DECK.name, 1, 0, {x: 0, y: 0})
        });

    }
}


class Encoder extends Konva.Circle {

    constructor(config, container) {
        super({
            x: config.x,
            y: config.y,
            radius: config.radius,
            stroke: TRANSLUCENT_WHITE,
            strokeWidth: 1,
            draggable: EDITOR_MODE
        });

        this.config = config
        this.name = config.name
        this.container = container

        this.inside = false

        // Inside key
        this.on('pointerover', function () {
            this.inside = true
        });

        this.on('pointerout', function () {
            this.container.style.cursor = "auto"
            this.inside = false
        });

        this.on('pointermove', function () {
            if (this.inside) {
                if (this.clockwise()) {
                    this.container.style.cursor = "url('/assets/images/clockwise.svg') 24 24, pointer";
                } else {
                    this.container.style.cursor = "url('/assets/images/counter-clockwise.svg') 24 24, pointer";
                }
            }
        });

        // Clicks
        this.on('pointerdown', function () {
            let value = this.clockwise() ? 2 : 3
            sendEvent(DECK.name, 1, value, {x: 0, y: 0})
        });

        this.on('pointerup', function () {
            sendEvent(DECK.name, 1, 0, {x: 0, y: 0})
        });

    }

    clockwise() {
        // How encoder was turned
        return (this.layer.getRelativePointerPosition().x - this.x()) < 0
    }

}


class Touchscreen extends Konva.Rect {

    constructor(config, container) {
        super({
            x: config.x,
            y: config.y,
            width: config.width,
            height: config.height,
            cornerRadius: config.corner_radius,
            stroke: TRANSLUCENT_WHITE,
            strokeWidth: 1,
            draggable: EDITOR_MODE
        });

        this.config = config
        this.name = config.name
        this.container = container

        this.inside = false

        // Inside key
        this.on('pointerover', function () {
            this.container.style.cursor = "pointer"
            this.inside = true
        });

        this.on('pointerout', function () {
            this.container.style.cursor = "auto"
            this.inside = false
        });

        // Clicks
        this.on('pointerdown', function () {
            this.flash(HIGHLIGHT, TRANSLUCENT_WHITE)
            sendEvent(DECK.name, 1, 1, {x: 0, y: 0})
        });

        this.on('pointerup', function () {
            sendEvent(DECK.name, 1, 0, {x: 0, y: 0})
        });

    }

    flash(colorin, colorout) {
        let that = this
        this.stroke(colorin)
        setTimeout(function() {
            that.stroke(colorout)
        }, 500)
    }

}

class Slider extends Konva.Rect {

    constructor(config, container) {
        super({
            x: config.x,
            y: config.y,
            width: config.width,
            height: config.height,
            cornerRadius: config.corner_radius,
            stroke: TRANSLUCENT_WHITE,
            strokeWidth: 1,
            draggable: EDITOR_MODE
        });

        this.config = config
        this.name = config.name
        this.container = container

        this.inside = false
    }

}


class Label {
    constructor(config, container) {
        this.config = config
        this.container = container
    }
}

CONSTRUCTORS = {
    "key": Key,
    "keyr": KeyRound,
    "encoder": Encoder,
    "touchsreen": Touchscreen,
    "slider": Slider,
    "label": Label
}

class Deck {

    constructor(config, container) {
        this.config = config;
        this.buttons = Array();  // array of Konva shapes to be added to layer

        this.name = config.name;
        this.container = container;

        const deck_type = config["deck-type-desc"];

        this.icon_width = deck_type.buttons[0].image[0];
        this.icon_height = deck_type.buttons[0].image[1];

        this.numkeys_horiz = deck_type.buttons[0].layout[0];
        this.numkeys_vert = deck_type.buttons[0].layout[1];

        this.keyspc_horiz = deck_type.layout.background.spacing[0];
        this.keyspc_vert = deck_type.layout.background.spacing[1];

        this.offset_horiz = deck_type.layout.background.offset[0];
        this.offset_vert = deck_type.layout.background.offset[1];

        this.background_image = deck_type.layout.background.image;

        this.build(config.layout);
    }

    add(button) {
        this.buttons.push(button);
    }

    get_xy(key) {
        let x = this.offset_horiz + (this.icon_width + this.keyspc_horiz) * (key % this.numkeys_horiz);
        let y = this.offset_vert  + (this.icon_height + this.keyspc_vert) * Math.floor(key/this.numkeys_horiz);
        // console.log("get_xy", key, x, y);
        return {"x": x, "y": y};
    }

    build(layout) {
        const max_keys = this.numkeys_horiz * this.numkeys_vert
        for (let i = 0; i < max_keys; i++) {
            let coords = this.get_xy(i);
            let key = new Key({name: i, x: coords.x, y: coords.y, width: this.icon_width, height: this.icon_height, corner_radius: 8}, this.container);
            this.add(key);
        }

        // test for LoupedeckLive
        // Encoders
        let r = 27
        for (let i = 0; i < 6; i++) {
            let x = 47+(Math.floor(i/3)*575);
            let y = 120+((i%3)*(this.icon_height+this.keyspc_vert));
            let encoder = new Encoder({name: "e"+i, x: x, y: y, radius: r}, this.container);
            this.add(encoder);
        }

        // Colored buttons
        r = 20
        for (let i = 0; i < 8; i++) {
            let x = 46+i*82;
            let y = 398;
            let encoder = new KeyRound({name: "e"+i, x: x, y: y, radius: r}, this.container);
            this.add(encoder);
        }

        // Side screens
        let key = new Key({name: "left", x: 104, y: 74, width: 45, height: 270, corner_radius: 4}, this.container);
        this.add(key);
        key = new Key({name: "right", x: 521, y: 74, width: 46, height: 270, corner_radius: 4}, this.container);
        this.add(key);

    }

    build_new(layout) {
        const deck_type = this.config["deck-type-desc"]
        let allbuttons = deck_type.buttons
        allbuttons.forEach( (button_type) => {
            buttons = allbuttons[button_type]
            buttons.forEach( (button) => {
                buttons = allbuttons[button_type]
                this.add(shape);
            })
        })

    }

    add_background_image(layer, stage) {
        const TITLE_BAR_HEIGHT = 24
        const deck_type = this.config["deck-type-desc"]
        let bgcolor = deck_type.layout.background.color
        if (bgcolor != undefined) {
            this.container.style["background-color"] = bgcolor
        }
        let deckImage = new Image();
        deckImage.onerror = function() {
            this.container.style["border"] = "1px solid red";

            let width = 2 * this.offset_horiz + this.icon_width  * this.numkeys_horiz + this.keyspc_horiz * (vnumkeys_horiz - 1);
            let height = 2 * this.offset_vert + this.icon_height * this.numkeys_vert  + this.keyspc_vert  * (this.numkeys_vert - 1);

            stage.width(width);
            stage.height(height);
            window.resizeTo(width,height + TITLE_BAR_HEIGHT);
        }
        deckImage.onload = function () {
            let deckbg = new Konva.Image({
                x: 0,
                y: 0,
                image: deckImage
            });
            stage.width(deckImage.naturalWidth);
            stage.height(deckImage.naturalHeight);
            window.resizeTo(deckImage.naturalWidth,deckImage.naturalHeight + TITLE_BAR_HEIGHT);
            layer.add(deckbg);
        };
        deckImage.src = "/assets/decks/images/" + this.background_image;
    }

    add_interaction_to_layer(layer) {
        this.buttons.forEach( (x) => { x.layer = layer; layer.add(x); } );
    }

    set_key_image(key, image, layer) {
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
