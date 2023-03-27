# Welcome to Cockpit Deck

Cockpitdecks is a XPPython3 plugin to interface

- Elgato Stream Decks
- Loupedeck LoupedeckLive
- Behringer XTouch Mini

with X-Plane flight simulator.

The project is in active development.

Please head to the [wiki](https://github.com/devleaks/cockpitdecks/wiki) for more information.


# Installation

## Create python environment, LESS THAN 3.11.

## Publicly available
pip install ruamel.yaml pillow avwx-engine scipy pyserial python-rtmidi mido streamdeck

## Private repos
pip install git+https://github.com/devleaks/python-loupedeck-live.git
pip install git+https://github.com/devleaks/python-berhinger-xtouchmini.git

## libhidapi known from python
cd /opt/homebrew/Caskroom/miniforge/base/envs/${ENVNAME}/lib
ln -s /opt/homebrew/lib/libhidapi.dylib .

Must use python < 3.11 because python-rtmidi does not compile on python >= 3.11.


# RELEASE NOTES

If you use xtouchmini, you must use python<3.11 beecause as today (20-MAR-2023) rtmidi does not compile on cython 3.11.
