from StreamDeck.DeviceManager import DeviceManager

FLIP_DESCRIPTION = {
        (False, False): "not mirrored",
        (True, False): "mirrored horizontally",
        (False, True): "mirrored vertically",
        (True, True): "mirrored horizontally/vertically"
    }

devices = DeviceManager().enumerate()

print(f"found {len(devices)} deck(s):")
for name, device in enumerate(devices):
    device.open()
    device.reset()
    serial = device.get_serial_number()
    print(f"deck {name}")
    print(f"{device.deck_type()} (serial number: {device.get_serial_number()}, fw: {device.get_firmware_version()})")
    print(f"{device.key_count()} keys, layout {device.key_layout()[0]}×{device.key_layout()[1]}")
    if device.is_visual():
        image_format = device.key_image_format()
        print(f"key images: {image_format['size'][0]}x{image_format['size'][1]} pixels, {image_format['format']} format, rotated {image_format['rotation']} degrees, {FLIP_DESCRIPTION[image_format['flip']]}")
    else:
        print(f"no visual")
    if len(devices) > 1:
        print("---")
