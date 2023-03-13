import os
import sys

from decks.XTouchMini.DeviceManager import DeviceManager

devices = DeviceManager().enumerate()

print(f"found {len(devices)} XTouch Mini(s):")
for name, device in enumerate(devices):
    serial = device.get_serial_number()
    print(f"deck {name}: {serial}")
    if len(devices) > 1:
        print("---")
