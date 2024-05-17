import io


def get_dimensions(display):
    width = 128  # dimension of "button"
    height = 128
    return (width, height)


def create_image(deck, background="black", display="button"):
    """
    Creates a new PIL Image with the correct image dimensions for the given
    StreamDeck device's keys.

    .. seealso:: See :func:`~PILHelper.to_native_format` method for converting a
                 PIL image instance to the native image format of a given
                 StreamDeck device.

    :param Loupedeck deck: Loupedeck device.
    :param str background: Background color to use, compatible with `PIL.Image.new()`.
    :param str display: button name to generate a compatible image for.

    :rtype: PIL.Image
    :return: Created PIL image
    """
    from PIL import Image

    return Image.new("RGB", get_dimensions(display=display), background)


def create_scaled_image(deck, image, margins=[0, 0, 0, 0], background="black", display="button"):
    """
    Creates a new key image that contains a scaled version of a given image,
    resized to best fit the given StreamDeck device's keys with the given
    margins around each side.

    The scaled image is centered within the new key image, offset by the given
    margins. The aspect ratio of the image is preserved.

    .. seealso:: See :func:`~PILHelper.to_native_format` method for converting a
                 PIL image instance to the native image format of a given
                 StreamDeck device.

    :param Loupedeck deck: Loupedeck device.
    :param Image image: PIL Image object to scale
    :param str background: Background color to use, compatible with `PIL.Image.new()`.
    :param str display: button name to generate a compatible image for.

    :rtrype: PIL.Image
    :return: Loaded PIL image scaled and centered
    """
    from PIL import Image

    if len(margins) != 4:
        raise ValueError("Margins should be given as an array of four integers.")

    final_image = create_image(deck, background=background, display=display)

    thumbnail_max_width = final_image.width - (margins[1] + margins[3])
    thumbnail_max_height = final_image.height - (margins[0] + margins[2])

    thumbnail = image.convert("RGBA")
    thumbnail.thumbnail((thumbnail_max_width, thumbnail_max_height), Image.LANCZOS)

    thumbnail_x = margins[3] + (thumbnail_max_width - thumbnail.width) // 2
    thumbnail_y = margins[0] + (thumbnail_max_height - thumbnail.height) // 2

    final_image.paste(thumbnail, (thumbnail_x, thumbnail_y), thumbnail)

    return final_image
