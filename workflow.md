# Workflow for Web Deck Design

Get a background image. PNG or JPEG only.

Place it in

```
<Aircraft>/deckconfig/resources/decks/images/<image-name>.png
```

Start cockpitdecks for that aircraft:

```sh
$ python bon/cockpitdecks_start.py <Aircraft>
```

If there are no deck available to the aircraft, Cockpitdecks will terminate.

To prevent that, and use the Deck Designer, set the constant DESIGNER to True in cockpitdecks_start.py.
Cockpitdecks will start the application server and Deck Designer will be available
if there are images in the above folder.


# Deck Designer

In a browser, head to the designer:

```
http://host:7777/designer
```

Your image name should appear.

Select it to start a designer for that image.

Place a single first button.

Change de label to RELOAD. (Doubble click on label to change it, press enter when text is entered.)

Resize and move the button to your liking. 
Doubble click inside the button to resize it,
click outside the button to deselect it.
Press Delete key when selected to remove it.


Save the deck layout. The deck layout is now saved in 

```
<Aircraft>/deckconfig/resources/decks/types
```

There should be two files

```
<image-name>.json     <-- Never touch this one, you would loose your layout
<image-name>.yaml
```

The new deck type is named after the image:

```
name: a321-xp
driver: virtualdeck
background:
  image: a321-xp.png
buttons:
- action:
  - push
  dimension:
  - 40
  - 40
  feedback: image
  layout:
    offset:
    - 581
    - 869
  name: RELOAD
```

The first save should also have created a new deck in deckconfig/config.yaml:

```
  - name: <image-name>
    type: <image-name>
    layout: <image-name>
```

and added it in serial.yaml:

```
<image-name>: <image-name>
```

Cockpitdecks configuration needs reloading to take into account this new deck.
If there are deck running, Cockpitdecks will reload all decks.
If not, Cockpitdecks will start and serve the new deck.

If you head to the Web Deck home page, the deck will now appear with a thin white frame
around the added load button, however, the button will remain inactive.


# Button Designer

Go back to the Designer home page and select Button Designer to start it.

Fill in the form:

Select the deck, give a name to a layout (default would be default if none provided).

The button name is "RELOAD", the label we gave it.

Give a name to a page (default would be index).

Select reload as Activation.

Select icon as Representation. Select icon named "reload-page-icon.png".

Press render to preview rendering.

Press save to save the layout/page/button.

# Testing

Head to Cockpitdecks Web Deck home page:

```
http://host:7777/
```

Select your deck in the list.

Test the reload button to test it.

## Automation

USing nodemon (nodejs), it is possible to reload the decks automatically when a deck type or layout file has changed. 

```
$ nodemon -w aircrafts/*/deckconfig/resources/decks/types -e yaml --exec curl "http://127.0.0.1:7777/reload-decks"
```

# Moving on from there

From there one can:

- Add more buttons, encoders, hardware button.
- Adjust the layout, resize buttons, move them.
- Save the new layout.
- Define and save more button definitions.
- Reload the deck to preview.


When the deck is completed, it is advisable to rename it.

Change name and cross references to name in config, secret, and layout pages.

