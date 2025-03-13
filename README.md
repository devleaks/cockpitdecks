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


WARNING: The latest version of Cockpitdecks, release 15 and above, requires the latest version of X-Plane, 12.1.4 or above.
Read the [documentation](https://devleaks.github.io/cockpitdecks-docs/Installation/).

Create a python environment. Python 3.12 minimum.
In that environment, install the following packages:

```sh
pip install 'cockpitdecks[demoext,weather,streamdeck] @ git+https://github.com/devleaks/cockpitdecks.git'
```

Valid installable extras (between the `[` `]`, comma separated, no space) are:

| Extra              | Content                                                                                                    |
| ------------------ | ---------------------------------------------------------------------------------------------------------- |
| `weather`          | Add special iconic representation for weather. These icons sometimes fetch information outside of X-Plane. |
| `toliss`           | Add special features for ToLiss airbus aircrafts. Useless for other aircrafts.                             |
| `demoext`          | Add a few Loupedeck and Stream Deck+ demo extensions.                                                      |
| `streamdeck`       | For Elgato Stream Deck devices                                                                             |
| `loupedeck`        | For Loupedeck LoupedeckLive, LoupedeckLive.s and Loupedeck CT devices                                      |
| `xtouchmini`       | For Berhinger X-Touch Mini devices                                                                         |
| `development`      | For developer only, add testing packages and python types                                                  |


```sh
cockpitdecks_cli --demo'
```

Fly safely.
