# Welcome to Cockpit Deck

Cockpitdecks is a XPPython3 plugin to interface

- Elgato Stream Decks
- Loupedeck LoupedeckLive
- Behringer XTouch Mini

with X-Plane flight simulator.

The project is in active development.

Please head to the [wiki](https://github.com/devleaks/cockpitdecks/wiki) for more information.


# Installation

## Libhidapi

There must ba a HIDAPI library on your system.

On MacOS, use

```
$ brew install libhidapi
```

### Make libhidapi known from python

Then make sure the path where the library is installed into is accessible to dlopen(3)
or whatever call your version of Python uses to locate the library.

Either add

```
export DYLD_LIBRARY_PATH=/opt/homebrew/lib
```

Or create a symbolic link to it in your Python environment library path:

```
cd /opt/homebrew/Caskroom/miniforge/base/envs/${ENVNAME}/lib
ln -s /opt/homebrew/lib/libhidapi.dylib .
```


## Create python environment, LESS THAN 3.11.

If you use xtouchmini, you must use python<3.11 beecause as today (20-MAR-2023) rtmidi does not compile on cython 3.11.

## Publicly available

```
$ pip install ruamel.yaml pillow avwx-engine scipy pyserial python-rtmidi mido streamdeck
```

## Private repos (not in pip repository)

```
$ pip install git+https://github.com/devleaks/python-loupedeck-live.git
$ pip install git+https://github.com/devleaks/python-berhinger-xtouchmini.git
```

## Start

```
$ python python cockpitdecks_upd_start.py /path/to/your/aircraft/folder
```

Enjoy.

