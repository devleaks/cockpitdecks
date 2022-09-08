from PIL import ImageFilter, Image, ImageDraw, ImageFont

def draw():
    s = 256
    image = Image.new("RGBA", size=(s, s), color="black")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/Volumes/pierre/Developer/streamdecks/A321/esdconfig/fonts/DIN.ttf", 72)

    draw.multiline_text((s/2, s/2),  # (image.width / 2, 15)
              text="DEMO",
              font=font,
              anchor="mm",
              align="center",
              fill=(255, 0, 0))

    # Apply blur
    blurred_image = image.filter(ImageFilter.GaussianBlur(8))
    draw = ImageDraw.Draw(blurred_image)
    draw.multiline_text((s/2, s/2),  # (image.width / 2, 15)
              text="DEMO",
              font=font,
              anchor="mm",
              align="center",
              fill=(220, 0, 0),
              stroke_fill=(255, 0, 0),
              stroke_width=2)

    with open("neon.png", "wb") as fp:
        blurred_image.save(fp, "PNG")

draw()