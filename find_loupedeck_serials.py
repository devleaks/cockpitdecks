import os
import sys

# p = os.path.join("/Users", "pierre", "X-Plane 11", "Resources", "plugins", "XPPython3")
p = os.path.join("/Users", "pierre", "Developer", "xppythonstubs")
print(p)
sys.path.append(p)

from decks.Loupedeck.DeviceManager import DeviceManager

devices = DeviceManager().enumerate()

print(f"found {len(devices)} loupedeck(s):")
for name, device in enumerate(devices):
    serial = device.get_serial_number()
    print(f"deck {name}: {serial}")
    if len(devices) > 1:
        print("---")
