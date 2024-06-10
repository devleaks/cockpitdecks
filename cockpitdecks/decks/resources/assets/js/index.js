/* Deck class and accessory content (buttons)
 * 
 * Draws button placeholders at their location.
 * Capture interaction in the button and send it to Cockpitdecks.
 */
class Button {

    constructor(name) {
        this.name = name
        this.shape = null   // Canvas shape graphic container
        this.cursor = null  // On hover, returns cursor to use, default to standard cursor (none specific)
    }


    inside(x, y) {
        return this.shape.contains(x, y)
    }

    cursor() {
        return this.cursor
    }

    value(event) {
        return null        
    }

}

class Key extends Button {

    constructor(name) {
        super(name)
    }

}

class Encoder extends Button {

    constructor(name) {
        super(name)
    }

}

class Touchscreen extends Button {

    constructor(name) {
        super(name)
    }

}

class Slider extends Button {

    constructor(name) {
        super(name)
    }

}

class Deck {

    constructor(name) {
        this.name = name
        this.buttons = array()
    }

    add(button) {
        this.buttons.add(button)
    }

    inside(x, y) {
        hit = this.buttons.filter(b.inside())
        if (hit.length() == 1) {
            return hit[0]
        } else if (hit.length() > 1) {
            console.log("inside returned more than one hit")
        }
        return null
    }

}

deck = new Deck(deck_definition.name)

// Build deck
deck_definition.buttons.forEach(button) {
    var this_button;
    switch (button.type) {
        case "key":
            this_button = Key(button.name, button.position, button.size)
            break;
        case "encoder":
            this_button = Encoder(button.name, button.position, button.size)
            break;
        case "touchscreen":
            this_button = Touchscreen(button.name, button.position, button.size)
            break;
        case "slider":
            this_button = Slider(button.name, button.position, button.size)
            break;
        }
}
