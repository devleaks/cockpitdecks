### Icon Naming for Airbus Aicrafts

There is an attempt at logically naming textual Airbus display switches.

(Alternatively, there is a flexible [Airbus Button Generator](https://github.com/devleaks/cockpitdecks/wiki/Button-Airbus)
for some textual buttons.)

If the button has a single display line (fire, etc.) its name is

`TEXT_COLOR[_ON|_OFF]`

If the button has two lines of text, the name is made of the text, followed by `_`, followed by the color of the text.
This is repeated for each of the two lines, with an additional `_` in between.

`TEXT1_COLOR1_TEXT2_COLOR2`

If the second text (bottom text) if surrounded by a frame, we add `_FR` to the name of the icon.

Valid Airbus colors are: `RED`, `DARK_ORANGE`, `GREEN`, `BLUE`, `WHITE`, `AMBER`, `LIGHT_AMBER`
(note: `LIGHT_AMBER` is really `WHITE` with some reflections added to it...)

##### Examples

`FAULT_AMBER_ALIGN_LIGHT_AMBER`

![FAULT_AMBER_ALIGN_LIGHT_AMBER](https://github.com/devleaks/streamdecks/blob/main/docs/images/FAULT_ALIGN.png?raw=true)


If the (bottom) text is framed in a highlight box, it is suffixed with _FR like so:

`NONE_ON_BLUE_FR`

![NONE_ON_BLUE_FR](https://github.com/devleaks/streamdecks/blob/main/docs/images/NONE_ON_BLUE.png?raw=true)

##### Cycles

When there is a succession of displayed states, they are named

`F.GREENS_{integer counter}`

![F.GREEN_SEQ](https://github.com/devleaks/streamdecks/blob/main/docs/images/F.GREEN_SEQ.png?raw=true)