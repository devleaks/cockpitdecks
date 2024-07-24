# Welcome to Cockpit Deck

<div float="right">
<img src="https://github.com/devleaks/cockpitdecks/raw/main/cockpitdecks/resources/icon.png" width="200" alt="Cockpitdecks icon"/>
</div>
Cockpitdecks is a python software to interface

- Elgato Stream Decks
- Loupedeck LoupedeckLive
- Behringer XTouch Mini

with X-Plane flight simulator.

Cockpitdecks also allows you to create and use [Web decks](https://devleaks.github.io/cockpitdecks-docs/Extending/Web%20Decks/) in a browser window.

The project is in active development, and will remain perpetual beta software.

Please head to the [documentation](https://devleaks.github.io/cockpitdecks-docs/) for more information.

You can find [numerous configurations for different aircrafts here](https://github.com/dlicudi/cockpitdecks-configs).

Fly safely.


## Installation

Read the [documentation](https://devleaks.github.io/cockpitdecks-docs/Installation/).

Create a python environment. Python 3.10 minimum (it is a requirement of an underlying package).
(Tested in 3.11 and 3.12.)

In that environement, install the following packages:

```sh
$ pip install git+https://github.com/devleaks/cockpitdecks.git
```

If you plan to use weather icons, optionally install the following complements:
```sh
$ pip install avwx-engine scipy suntime timezonefinder metar tabulate
```

If you plan to use Elgato Stream Deck decks, install the following package:
```sh
$ pip install streamdeck
```

If you plan to use Loupedeck LoupedeckLive decks, install the following package:
```sh
$ pip install git+https://github.com/devleaks/python-loupedeck-live.git
```

If you plan to use X-Touch Mini decks, install the following package:
```sh
$ pip install git+https://github.com/devleaks/python-berhinger-xtouchmini.git
```

Fly safely.
