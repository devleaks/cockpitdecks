# Welcome to Cockpit Deck

Cockpitdecks is a XPPython3 plugin to interface

- Elgato Stream Decks
- Loupedeck LoupedeckLive
- Behringer XTouch Mini

with X-Plane flight simulator.

The project is in active development.

Please head to the [wiki](https://github.com/devleaks/cockpitdecks/wiki) for more information.


![Cockpitdecks Icon](relative cockpitdecks/resources/icon.png)

# Installation

## Libhidapi

There must ba a HIDAPI library on your system.

On MacOS, use

```
$ brew install libhidapi
```

### Make libhidapi known from python

Make sure the path where the library is installed into is accessible to dlopen(3)
or whatever call your version of Python uses to locate the library.

```
export DYLD_LIBRARY_PATH=/opt/homebrew/lib
```


## Create python environment, LESS THAN 3.11.

If you use xtouchmini, you must use python<3.11 beecause as today (20-MAR-2023) rtmidi does not compile on cython 3.11.

## Global packages required by Cockpitdecks

```
$ pip install ruamel.yaml pillow
```

If you want to use the Metar representation on a key, add:

```
$ pip install ruamel.yaml 'avwx-engine[scipy]'
```


## Packages required depending on the deck(s) model(s) used

### Elgato Streamdeck

```
$ pip install streamdeck
```

### Loupedeck LoupedeckLive

```
$ pip install git+https://github.com/devleaks/python-loupedeck-live.git
```

### Beringher X Touch Mini

```
$ pip install git+https://github.com/devleaks/python-berhinger-xtouchmini.git
```

## Start

```
$ python bin/cockpitdecks_upd_start.py /path/to/your/aircraft/folder
```

Enjoy.

