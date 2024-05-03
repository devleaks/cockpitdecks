# List deck buttons and capabilities for each deck model

The `.yaml` files that describe decks must be placed into

`cocpitdecks/decks/resources`

folder.

## Actions

Interaction is limited to the following:

```python
class DECK_ACTIONS(Enum):
    NONE = "none"
    ENCODER = "encoder"
    PRESS = "press"
    LONGPRESS = "longpress"
    PUSH = "push"
    CURSOR = "cursor"
    SLIDE = "cursor"
    SWIPE = "swipe"
    DRAG = "drag"
```

- `none`: No activation, button is display only, like power LED.
- `press`: Simple press button (*1 event*)
- `longpress`: Long press button (*1 event*), Streamdeck specific, which does not provide timing info. See https://github.com/abcminiuser/python-elgato-streamdeck/issues/141.
- `push`: Press button (*2 events*, pushed, released, remain pushed as long as necessary.)
- `encoder`: Encoder (2 events, turn clockwise, counter-clockwise, stepped)
- `cursor`: Continuous value between a minimum and a maximum values, produce a countinuous number within range. Slide, slider is a historical synonnym.
- `swipe`: (a touch surface, complex events between touched, dragged, released, modelled into simpler events.)

(Currently, there is little distinction between `press` and `push` events. The difference being that since press events have only one event, they cannot be used for activation that requires a timing like `long-press`.)

## Feedback

Feedback is limited to the following:

```python
class DECK_FEEDBACK(Enum):
    NONE = "none"
    LED = "led"
    COLORED_LED = "colored-led"
    ENCODER_LEDS = "encoder-leds"
    IMAGE = "image"
    VIBRATE = "vibrate"
```

- `none`: No feedback, like the cursor on the X-Touch Mini, feedback is physical by sliding the cursor on its ramp.
- `led`, `colored-led`: Single LED, monochrome or colored, color provided in RGB, converted appropriately.
- `encoder-led`: Variant of mutliple LED (like a ramp), monochrome, specific to X-Touch Mini encoders.
- `lcd`: screen display, individual or part (portion) of a larger screen,
- `vibrate`: according to predefined patterns


## Deck Type

```yaml
---
type: LoupedeckLive
driver: loupedeck
buttons:
  - name: 0
    action: push
    feedback: image
    image: [90, 90, 0, 0]
    repeat: 12
```

`type` refers to the DECK_TYPE as returned by the driver. That's the string that must be used
in deck enumaration in main Cockpitdecks config.yaml file.

`driver` refers to the Cockpitdecks class that handles events for that deck.

There are currently 3 drivers:
1. streamdeck
2. loupedeck
3. xtouchmini

`action` refers to the above possible actions.

`feedback` refers to the above possible feedbacks.

`ìmage` defines the icon image size on the deck,
and its position on the larger screen if necessary.

```yaml
  - name: slider
    action: cursor
    range: [-8192, 8064]
    feedback: none
```

`range` defines range of values for slider, cursor, pontentiometers, etc. if available.


## Usage

When a button is created, it receives the portion of the `buttons` attribute applicable to it.

For example, a Loupedeck button in the center screen receives:

```yaml
  - name: 0
    action: push
    feedback: image
    image: [90, 90, 0, 0]
    repeat: 12
```

This allows it to check whether its index (name) is valid for example.
