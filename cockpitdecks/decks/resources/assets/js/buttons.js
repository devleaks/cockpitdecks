/* Deck class and accessory content (buttons)
 * 
 * Draws button placeholders at their location.
 * Capture interaction in the button and send it to Cockpitdecks.
 */
class Key extends Konva.Rect {
    // Represent a simply rectangular key

    constructor(config, container) {
        super({
            x: config.x,
            y: config.y,
            width: config.width,
            height: config.height,
            cornerRadius: config.corner_radius,
            stroke: 'white',
            strokeWidth: 1,
        });

        this.name = config.name
        this.container = container
        this.inside = false

        // Inside key
        this.on('mouseover', function () {
            this.container.style.cursor = "pointer"
            this.inside = true
        });

        this.on('mouseout', function () {
            this.container.style.cursor = "auto"
            this.inside = false
        });

        // Clicks
        this.on('mousedown', function () {
            sendEvent(DECK.name, 1, 1, {x: 0, y: 0})
        });

        this.on('mouseup', function () {
            sendEvent(DECK.name, 1, 0, {x: 0, y: 0})
        });

    }
}


class KeyRound extends Konva.Circle {
    // Represent a simply rectangular key

    constructor(config, container) {
        super({
            x: config.x,
            y: config.y,
            radius: config.radius,
            stroke: 'white',
            strokeWidth: 1,
        });

        this.name = config.name
        this.container = container
        this.inside = false

        // Inside key
        this.on('mouseover', function () {
            this.container.style.cursor = "pointer"
            this.inside = true
        });

        this.on('mouseout', function () {
            this.container.style.cursor = "auto"
            this.inside = false
        });

        // Clicks
        this.on('mousedown', function () {
            sendEvent(DECK.name, 1, 1, {x: 0, y: 0})
        });

        this.on('mouseup', function () {
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
            stroke: 'white',
            strokeWidth: 1,
        });

        this.name = config.name
        this.container = container
        this.inside = false

        // Inside key
        this.on('mouseover', function () {
            this.inside = true
        });

        this.on('mouseout', function () {
            this.container.style.cursor = "auto"
            this.inside = false
        });

        this.on('pointermove', function () {
            if (this.inside) {
                if (this.clockwise()) {
                    this.container.style.cursor = "url('/assets/images/clockwise.png') 24 24, pointer";
                } else {
                    this.container.style.cursor = "url('/assets/images/counter-clockwise.png') 24 24, pointer";
                }
            }
        });

        // Clicks
        this.on('mousedown', function () {
            let value = this.clockwise() ? 2 : 3
            sendEvent(DECK.name, 1, value, {x: 0, y: 0})
        });

        this.on('mouseup', function () {
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
            stroke: 'white',
            strokeWidth: 1,
        });

        this.name = config.name
        this.container = container
        this.inside = false
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
            stroke: 'white',
            strokeWidth: 1,
        });

        this.name = config.name
        this.container = container
        this.inside = false
    }

}

class Deck {

    constructor(config, container) {
        this.buttons = Array()  // array of Konva shapes to be added to layer

        this.name = config.name
        this.container = container

        const DECK_TYPE = DECK["deck-type-desc"]

        this.icon_width = DECK_TYPE.buttons[0].image[0]
        this.icon_height = DECK_TYPE.buttons[0].image[1]

        this.numkeys_horiz = DECK_TYPE.buttons[0].layout[0]
        this.numkeys_vert = DECK_TYPE.buttons[0].layout[1]

        this.keyspc_horiz = DECK_TYPE.layout.background.spacing[0]
        this.keyspc_vert = DECK_TYPE.layout.background.spacing[1]

        this.offset_horiz = DECK_TYPE.layout.background.offset[0]
        this.offset_vert = DECK_TYPE.layout.background.offset[1]

        this.background_image = DECK_TYPE.layout.background.image

        this.build(config.layout)
    }

    add(button) {
        this.buttons.push(button)
    }

    get_xy(key) {
        let x = this.offset_horiz + (this.icon_width + this.keyspc_horiz) * (key % this.numkeys_horiz)
        let y = this.offset_vert  + (this.icon_height + this.keyspc_vert) * Math.floor(key/this.numkeys_horiz)
        // console.log("get_xy", key, x, y);
        return {"x": x, "y": y}
    }

    build(layout) {
        const max_keys = this.numkeys_horiz * this.numkeys_vert
        for (let i = 0; i < max_keys; i++) {
            let coords = this.get_xy(i)
            let key = new Key({name: i, x: coords.x, y: coords.y, width: this.icon_width, height: this.icon_height, corner_radius: 8}, this.container)
            this.add(key);
        }

        // test for LoupedeckLive
        let r = 27
        for (let i = 0; i < 6; i++) {
            let x = 47+(Math.floor(i/3)*575)
            let y = 120+((i%3)*(this.icon_height+this.keyspc_vert))
            let encoder = new Encoder({name: "e"+i, x: x, y: y, radius: r}, this.container)
            this.add(encoder);
        }

        r = 20
        for (let i = 0; i < 8; i++) {
            let x = 46+i*82
            let y = 398
            let encoder = new KeyRound({name: "e"+i, x: x, y: y, radius: r}, this.container)
            this.add(encoder);
        }
    }

    add_background_image(layer, stage) {
        const TITLE_BAR_HEIGHT = 24
        let deckImage = new Image();
        deckImage.onerror = function() {
            this.container.style["border"] = "1px solid red"

            let width = 2 * this.offset_horiz + this.icon_width  * this.numkeys_horiz + this.keyspc_horiz * (vnumkeys_horiz - 1)
            let height = 2 * this.offset_vert + this.icon_height * this.numkeys_vert  + this.keyspc_vert  * (this.numkeys_vert - 1)

            stage.width(width)
            stage.height(height)
            window.resizeTo(width,height + TITLE_BAR_HEIGHT)
        }
        deckImage.onload = function () {
            let deckbg = new Konva.Image({
                x: 0,
                y: 0,
                image: deckImage
            });
            stage.width(deckImage.naturalWidth)
            stage.height(deckImage.naturalHeight)
            window.resizeTo(deckImage.naturalWidth,deckImage.naturalHeight + TITLE_BAR_HEIGHT)
            layer.add(deckbg);
        };
        deckImage.src = "/assets/decks/images/" + this.background_image;
    }

    add_interaction_to_layer(layer) {
        this.buttons.forEach( (x) => { x.layer = layer; layer.add(x); } )
    }

    set_key_image(key, image, layer) {
        let coords = this.get_xy(key)
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
