List deck buttons and capabilities for each deck model.

## Actions

Interaction is limited to the following:

```python
class DECK_ACTIONS(Enum):
    ENCODER = "encoder"
    ENCODER_PUSH = "encoder-push"
    NONE = "none"
    PUSH = "push"
    SLIDE = "slide"
    SWIPE = "swipe"
```

- Simple press button (1 event)
- Press button (2 event, pushed, released)
- Encoder (2 events, turn clockwise, counter-clockwise)
- Cursor (continuous value between a minimum and a maximum values)
- Touch (a touch surface, complex events between touched, dragged, released, modelled into simpler events.)

## Feedback

Feedback is limited to the following:

```python
class DECK_FEEDBACK(Enum):
    COLORED_LED = "colored-led"
    IMAGE = "image"
    LED = "led"
    MULTI_LEDS = "multi-leds"
    NONE = "none"
```

- Single LED, monochrome or colored,
- Mutliple LED (like a ramp), monochrome,
- LCD, screen display, individual or part (portion) of a larger screen,
- vibrate, according to predefined patterns

## Deck Type

```yaml
---
type: LoupedeckLive
driver: loupedeck
buttons:
  - name: 0
    action: push
    view: image
    image: [90, 90, 0, 0]
    repeat: 12
```

`type` refers to the DECK_TYPE as returned by the driver.

`driver` refers to the Cockpitdecks class that handles events for that deck.

There are currently 3 drivers:
1. streamdeck
2. loupedeck
3. xtouchmini

`action` refers to the above possible actions.

`feedback` refers to the above possible feedbacks.

`ìmage` defines the icon image size on the deck,
and its position on the larger screen if necessary.

When a button is created, it receives the portion of the `buttons` attribute applicable to it.

For example, a Loupedeck button in the center screen receives:

```yaml
  - name: 0
    action: push
    view: image
    image: [90, 90, 0, 0]
    repeat: 12
```

This allows it to check whether its index (name) is valid for example.

