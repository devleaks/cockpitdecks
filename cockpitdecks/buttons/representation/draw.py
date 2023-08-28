# ###########################
# Buttons that are drawn on render()
#
import logging
import threading
import time
import math
from random import randint
from enum import Enum

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE, DEFAULT_LABEL_FONT
from cockpitdecks.resources.iconfonts import ICON_FONTS

from cockpitdecks.resources.color import TRANSPARENT_PNG_COLOR, convert_color, light_off
from .representation import Icon  # explicit Icon from file to avoid circular import

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

#
# ###############################
# DRAWN REPRESENTATION (using Pillow)
#
#
class DrawBase(Icon):

	def __init__(self, config: dict, button: "Button"):

		Icon.__init__(self, config=config, button=button)

		self.texture = None
		self.bgcolor   = None
		self.cockpit_texture = config.get("cockpit-texture", self.button.page.cockpit_texture)
		self.cockpit_color = config.get("cockpit-color", self.button.page.cockpit_color)

		# Reposition for move_and_send()
		self.draw_scale = float(config.get("scale", 1))
		if self.draw_scale < 0.5 or self.draw_scale > 2:
			logger.warning(f"button {self.button.name}: invalid scale {self.draw_scale}, must be in interval [0.5, 2]")
			self.draw_scale = 1
		self.draw_left = config.get("left", 0) - config.get("right", 0)
		self.draw_up = config.get("up", 0) - config.get("down", 0)


	def double_icon(self, width: int = ICON_SIZE*2, height: int = ICON_SIZE*2):
		image = Image.new(mode="RGBA", size=(width, height), color=TRANSPARENT_PNG_COLOR)
		draw = ImageDraw.Draw(image)
		return image, draw

	def get_background(self, width: int, height: int, use_texture: bool = True):
		"""
		Returns a **Pillow Image** of size width x height with either the file specified by texture or a uniform color
		"""
		image = None
		# Try local texture
		if use_texture and self.texture is not None and self.texture in self.button.deck.cockpit.icons.keys():
			image = self.button.deck.cockpit.icons[self.texture]
			if image is not None:  # found a texture as requested
				image = image.resize((width, height))
				logger.debug(f"using texture {self.texture}")
				return image

		# Try deck cockpit_texture
		if use_texture and self.cockpit_texture is not None and self.cockpit_texture in self.button.deck.cockpit.icons.keys():
			image = self.button.deck.cockpit.icons[self.cockpit_texture]
			if image is not None:  # found cockpit texture
				image = image.resize((width, height))
				logger.debug(f"using cockpit texture {self.cockpit_texture}")
				return image

		if use_texture and self.texture is None:
			logger.debug(f"should use texture but no texture found, using uniform color")

		if self.bgcolor is not None:
			image = Image.new(mode="RGBA", size=(width, height), color=self.bgcolor)
			logger.debug(f"using uniform color {self.bgcolor}")
			return image

		image = Image.new(mode="RGBA", size=(width, height), color=self.cockpit_color)
		logger.debug(f"using uniform cockpit color {self.cockpit_color}")
		return image

	def move_and_send(self, image):
		# 1. Scale whole drawing if requested
		if self.draw_scale != 1:
			l = int(image.width*self.draw_scale)
			image = image.resize((l, l))
		# 2a. Move whole drawing around
		a = 1
		b = 0
		c = self.draw_left
		d = 0
		e = 1
		f = self.draw_up
		if c != 0 or f != 0:
			image = image.transform(image.size, Image.AFFINE, (a, b, c, d, e, f))
		# 2b. Crop center to ICON_SIZExICON_SIZE
		cl = image.width/2 - ICON_SIZE/2
		ct = image.height/2 - ICON_SIZE/2
		image = image.crop((cl, ct, cl+ICON_SIZE, ct+ICON_SIZE))

		# 3. Paste image on cockpit background and return it.
		bg = self.button.deck.get_icon_background(name=self.button_name(), width=ICON_SIZE, height=ICON_SIZE, texture_in=self.icon_texture, color_in=self.icon_color, use_texture=True, who="Annunciator")
		bg.alpha_composite(image)
		return bg.convert("RGB")


class DataIcon(DrawBase):

	def __init__(self, config: dict, button: "Button"):
		DrawBase.__init__(self, config=config, button=button)

	def get_datarefs(self):
		if self.datarefs is None:
			data = self._config["data"]
			if data is not None:
				self.datarefs = self.button.scan_datarefs(base=data)
		return self.datarefs

	def get_image_for_icon(self):
		"""
		Helper function to get button image and overlay label on top of it.
		Label may be updated at each activation since it can contain datarefs.
		Also add a little marker on placeholder/invalid buttons that will do nothing.
		"""
		image, draw = self.double_icon(width=ICON_SIZE, height=ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)
		inside = round(0.04 * image.width + 0.5)

		# Display Data
		data = self._config.get("data")
		if data is None:
			logger.warning(f"button {self.button.name}: no data")
			return image

		topbar = data.get("top-line-color")
		if topbar is not None:
			topbarcolor = convert_color(topbar)
			linewidth = data.get("top-line-width", 6)
			draw.line([(0, int(linewidth/2)), (image.width, int(linewidth/2))],fill=topbarcolor, width=linewidth)

		# Icon
		icon, icon_format, icon_font, icon_color, icon_size, icon_position = self.get_text_detail(data, "icon")

		icon_str = "*"
		icon_arr = icon.split(":")
		if len(icon_arr) == 0 or icon_arr[0] not in ICON_FONTS.keys():
			logger.warning(f"button {self.button.name}: invalid icon {icon}")
		else:
			icon_name = ":".join(icon_arr[1:])
			icon_str = ICON_FONTS[icon_arr[0]][1].get(icon_name, "*")

		icon_font = data.get("icon-font", ICON_FONTS[icon_arr[0]][0])
		font = self.get_font(icon_font, int(icon_size))
		inside = round(0.04 * image.width + 0.5)
		w = inside
		h = image.height / 2
		draw.text((w, h),  # (image.width / 2, 15)
				  text=icon_str,
				  font=font,
				  anchor="lm",
				  align="left",
				  fill=icon_color)

		# Data
		DATA_UNIT_SEP = " "
		data_value, data_format, data_font, data_color, data_size, data_position = self.get_text_detail(data, "data")
		#print(">"*10, "DATA", data_value, data_format, data_font, data_color, data_size, data_position)

		if data_format is not None:
			data_str = data_format.format(float(data_value))
		else:
			data_str = str(data_value)

		data_unit = data.get("data-unit")
		# if data_unit is not None:
		#	 data_str = data_str + DATA_UNIT_SEP + data_unit

		data_progress = data.get("data-progress")

		font = self.get_font(data_font, data_size)
		font_unit = self.get_font(data_font, int(data_size * 0.50))
		inside = round(0.04 * image.width + 0.5)
		w = image.width - inside
		h = image.height / 2 + data_size / 2 - inside
		# if dataprogress is not None:
		#	 h = h - DATAPROGRESS_SPACE - DATAPROGRESS / 2
		if data_unit is not None:
			w = w - draw.textlength(DATA_UNIT_SEP + data_unit, font=font_unit)
		draw.text((w, h),  # (image.width / 2, 15)
				  text=data_str,
				  font=font,
				  anchor="rs",
				  align="right",
				  fill=data_color)

		if data_unit is not None:
			w = image.width - inside
			draw.text((w, h),  # (image.width / 2, 15)
					  text=DATA_UNIT_SEP + data_unit,
					  font=font_unit,
					  anchor="rs",
					  align="right",
					  fill=data_color)

		# Progress bar
		DATA_PROGRESS_SPACE = 8
		DATA_PROGRESS = 6

		if data_progress is not None:
			w = icon_size + 4 * inside
			h = 3 * image.height / 4 - 2 * DATA_PROGRESS
			pct = float(data_value) / float(data_progress)
			if pct > 1:
				pct = 1
			full_color = light_off(data_color, 0.30)
			l = w + pct * ((image.width - inside) - w)
			draw.line([(w, h), (image.width - inside, h)],fill=full_color, width=DATA_PROGRESS, joint="curve") # 100%
			draw.line([(w, h), (l, h)], fill=data_color, width=DATA_PROGRESS, joint="curve")

		# Bottomline (forced at CENTER BOTTOM line of icon)
		bottom_line, botl_format, botl_font, botl_color, botl_size, botl_position = self.get_text_detail(data, "bottomline")
		#print(">"*10, "BOTL", bottom_line, botl_format, botl_font, botl_color, botl_size, botl_position)

		if bottom_line is not None:
			font = self.get_font(botl_font, botl_size)
			w = image.width / 2
			h = image.height / 2
			h = image.height - inside - botl_size / 2  # forces BOTTOM position
			draw.multiline_text((w, h),  # (image.width / 2, 15)
					  text=bottom_line,
					  font=font,
					  anchor="md",
					  align="center",
					  fill=botl_color)

		# Final mark
		mark, mark_format, mark_font, mark_color, mark_size, mark_position = self.get_text_detail(data, "mark")
		if mark is not None:
			font = self.get_font(mark_font, mark_size)
			w = image.width - 2 * inside
			h = image.height - 2 * inside
			draw.text((w, h),
					  text=mark,
					  font=font,
					  anchor="rb",
					  align="right",
					  fill=mark_color)

		# Paste image on cockpit background and return it.
		bg = self.button.deck.get_icon_background(name=self.button_name(), width=ICON_SIZE, height=ICON_SIZE, texture_in=self.icon_texture, color_in=self.icon_color, use_texture=True, who="Data")
		bg.alpha_composite(image)
		return bg.convert("RGB")

#
# ###############################
# SWITCH BUTTON REPRESENTATION
#
#
def grey(i: int):
	return (i, i, i)

class SWITCH_STYLE(Enum):
	ROUND = "round"
	FLAT  = "rect"
	DOT3  = "3dot"

SWITCH_BASE_FILL_COLOR = grey(40)
SWITCH_BASE_STROKE_COLOR = grey(240)
SWITCH_BASE_UNDERLINE_COLOR = "orange"

SCREW_HOLE_COLOR = grey(80)
SCREW_HOLE_UNDERLINE = grey(40)
SCREW_HOLE_UWIDTH = 1

SWITCH_HANDLE_BASE_COLOR = grey(200)

SWITCH_HANDLE_FILL_COLOR = grey(140)
SWITCH_HANDLE_STROKE_COLOR = grey(230)

SWITCH_HANDLE_TOP_FILL_COLOR = grey(100)
SWITCH_HANDLE_TOP_STROKE_COLOR = grey(150)

HANDLE_TIP_COLOR = grey(255)

NEEDLE_COLOR = grey(255)
NEEDLE_UNDERLINE_COLOR = grey(0)
MARKER_COLOR = "lime"

TICK_COLOR = grey(255)
LABEL_COLOR = grey(255)

class SwitchBase(DrawBase):

	def __init__(self, config: dict, button: "Button", switch_type: str):

		DrawBase.__init__(self, config=config, button=button)

		self.switch = config.get(switch_type)

		self.switch_type = self.switch.get("type")
		self.switch_style = self.switch.get("switch-style")

		# Base and handle
		self.button_size = self.switch.get("button-size", int(2 * ICON_SIZE / 4))
		self.button_fill_color = self.switch.get("button-fill-color", SWITCH_BASE_FILL_COLOR)
		self.button_fill_color = convert_color(self.button_fill_color)
		self.button_stroke_color = self.switch.get("button-stroke-color", SWITCH_BASE_STROKE_COLOR)
		self.button_stroke_color = convert_color(self.button_stroke_color)
		self.button_stroke_width = self.switch.get("button-stroke-width", 2)
		self.button_underline_color = self.switch.get("button-underline-color", SWITCH_BASE_UNDERLINE_COLOR)
		self.button_underline_color = convert_color(self.button_underline_color)
		self.button_underline_width = self.switch.get("button-underline-width", 0)

		self.handle_base_fill_color = self.switch.get("handle-fill-color", SWITCH_HANDLE_BASE_COLOR)
		self.handle_base_fill_color = convert_color(self.handle_base_fill_color)

		self.handle_fill_color = self.switch.get("handle-fill-color", SWITCH_HANDLE_FILL_COLOR)
		self.handle_fill_color = convert_color(self.handle_fill_color)
		self.handle_stroke_color = self.switch.get("handle-stroke-color", SWITCH_HANDLE_STROKE_COLOR)
		self.handle_stroke_color = convert_color(self.handle_stroke_color)
		self.handle_stroke_width = self.switch.get("handle-stroke-width", 0)

		self.top_fill_color = self.switch.get("top-fill-color", SWITCH_HANDLE_TOP_FILL_COLOR)
		self.top_fill_color = convert_color(self.top_fill_color)
		self.top_stroke_color = self.switch.get("top-stroke-color", SWITCH_HANDLE_TOP_STROKE_COLOR)
		self.top_stroke_color = convert_color(self.top_stroke_color)
		self.top_stroke_width = self.switch.get("top-stroke-width", 2)

		self.handle_tip_fill_color = self.switch.get("handle-fill-color", HANDLE_TIP_COLOR)
		self.handle_tip_fill_color = convert_color(self.handle_tip_fill_color)

		# Ticks
		self.tick_space = self.switch.get("tick-space", 10)
		self.tick_length = self.switch.get("tick-length", 16)
		self.tick_width = self.switch.get("tick-width", 4)
		self.tick_color = self.switch.get("tick-color", TICK_COLOR)
		self.tick_color = convert_color(self.tick_color)
		self.tick_underline_color = self.switch.get("tick-underline-color", TICK_COLOR)
		self.tick_underline_color = convert_color(self.tick_underline_color)
		self.tick_underline_width = self.switch.get("tick-underline-width", 4)

		# Labels
		self.tick_labels = self.switch.get("tick-labels")
		self.tick_label_space = self.switch.get("tick-label-space", 10)
		self.tick_label_font = self.switch.get("tick-label-font", "DIN")
		self.tick_label_size = self.switch.get("tick-label-size", 50)
		self.tick_label_color = self.switch.get("tick-label-color", LABEL_COLOR)
		self.tick_label_color = convert_color(self.tick_label_color)

		# Handle needle
		self.needle_width = self.switch.get("needle-width", 8)
		self.needle_start = self.switch.get("needle-start", 10)  	# from center of button
		self.needle_length = self.switch.get("needle-length", 50)  	# end = start + length
		self.needle_tip = self.switch.get("needle-tip")				# arro, arri, ball
		self.needle_tip_size = self.switch.get("needle-tip-size", 5)
		# self.needle_length = int(self.needle_length * self.button_size / 200)
		self.needle_color = self.switch.get("needle-color", NEEDLE_COLOR)
		self.needle_color = convert_color(self.needle_color)
		# Options
		self.needle_underline_width = self.switch.get("needle-underline-width", 4)
		self.needle_underline_color = self.switch.get("needle-underline-color", NEEDLE_UNDERLINE_COLOR)
		self.needle_underline_color = convert_color(self.needle_underline_color)

		self.marker_color = self.switch.get("marker-color", MARKER_COLOR)

		# Reposition for move_and_send(), found locally in switch config
		self.draw_scale = float(self.switch.get("scale", 1))
		if self.draw_scale < 0.5 or self.draw_scale > 2:
			logger.warning(f"button {self.button.name}: invalid scale {self.draw_scale}, must be in interval [0.5, 2]")
			self.draw_scale = 1
		self.draw_left = self.switch.get("left", 0) - self.switch.get("right", 0)
		self.draw_up = self.switch.get("up", 0) - self.switch.get("down", 0)



class CircularSwitch(SwitchBase):

	def __init__(self, config: dict, button: "Button"):

		SwitchBase.__init__(self, config=config, button=button, switch_type="circular-switch")

		self.button_fill_color = grey(190)

		self.tick_from = self.switch.get("tick-from", 90)
		self.tick_to = self.switch.get("tick-to", 270)
		if hasattr(self.button._activation, "stops"):
			self.tick_steps = self.button._activation.stops
			logger.debug(f"button {self.button.name}: button has {self.tick_steps} steps")
		else:
			self.tick_steps = self.switch.get("tick-steps", 2)
		if self.tick_steps < 2:
			logger.warning(f"button {self.button.name}: insuficient number of steps: {self.tick_steps}, forcing 2")
			self.tick_steps = 2
		logger.debug(f"button {self.button.name}: {self.tick_steps} steps")
		self.angular_step = (self.tick_to - self.tick_from) / (self.tick_steps - 1)
		if len(self.tick_labels) < self.tick_steps:
			logger.warning(f"button {self.button.name}: not enough label ({len(self.tick_labels)}/{self.tick_steps})")

	def get_image_for_icon(self):
		"""
		Helper function to get button image and overlay label on top of it.
		Label may be updated at each activation since it can contain datarefs.
		Also add a little marker on placeholder/invalid buttons that will do nothing.
		"""
		def red(a):
			# reduce a to [0, 360[
			if a >= 360:
				return red(a - 360)
			elif a < 0:
				return red(a + 360)
			return a

		image, draw = self.double_icon()

		# Button
		center = [ICON_SIZE, ICON_SIZE]

		tl = [center[0]-self.button_size/2, center[1]-self.button_size/2]
		br = [center[0]+self.button_size/2, center[1]+self.button_size/2]
		draw.ellipse(tl+br, fill=self.button_fill_color, outline=self.button_stroke_color, width=self.button_stroke_width)

		# Ticks
		tick_start = self.button_size/2 + self.tick_space
		tick_end   = tick_start + self.tick_length
		tick_lbl   = tick_end + self.tick_label_space

		label_anchors = []
		for i in range(self.tick_steps):
			a = red(self.tick_from + i * self.angular_step)
			x0 = center[0] - tick_start * math.sin(math.radians(a))
			y0 = center[1] + tick_start * math.cos(math.radians(a))
			x1 = center[0] - tick_end * math.sin(math.radians(a))
			y1 = center[1] + tick_end * math.cos(math.radians(a))
			x2 = center[0] - tick_lbl * math.sin(math.radians(a))
			y2 = center[1] + tick_lbl * math.cos(math.radians(a))
			# print(f"===> ({x0},{y0}) ({x1},{y1}) a=({x2},{y2})")
			label_anchors.append([a, x2, y2])
			draw.line([(x0,y0), (x1, y1)], width=self.tick_width, fill=self.tick_color)


		# Tick run mark
		if self.tick_underline_width > 0:
			tl = [center[0]-tick_start, center[1]-tick_start]
			br = [center[0]+tick_start, center[1]+tick_start]
			draw.arc(tl+br, fill=self.tick_underline_color, start=self.tick_from+90, end=self.tick_to+90, width=self.tick_underline_width)

		# Labels
		# print("-<-<", label_anchors)
		font = self.get_font(self.tick_label_font, int(self.tick_label_size))
		for i in range(self.tick_steps):
			angle = int(label_anchors[i][0])
			tolerence = 30
			if angle > tolerence and angle < 180-tolerence:
				anchor="rs"
				align="right"
			elif angle > 180+tolerence and angle < 360-tolerence:
				anchor="ls"
				align="left"
			else:  # 0, 180, 360
				anchor="ms"
				align="center"
			# print(self.tick_labels[i], label_anchors[i], label_anchors[i][1:3], anchor, align)
			draw.text(label_anchors[i][1:3],
					  text=self.tick_labels[i],
					  font=font,
					  anchor=anchor,
					  align=align,
					  fill=self.tick_label_color)

		# Needle
		value = self.button.get_current_value()
		if value is None:
			value = 0
		if value >= self.tick_steps:
			logger.warning(f"button {self.button.name} invalid initial value {value}. Set to {self.tick_steps - 1}")
			value = self.tick_steps - 1
		angle = red(self.tick_from + value * self.angular_step)

		if self.switch_style in ["medium", "large", "xlarge"]:   # handle style
			overlay, overlay_draw = self.double_icon()
			inner = self.button_size

			# Base circle
			tl = [center[0]-inner, center[1]-inner]
			br = [center[0]+inner, center[1]+inner]
			overlay_draw.ellipse(tl+br, fill=self.button_fill_color, outline=self.button_stroke_color, width=self.button_stroke_width)

			# Button handle needle
			home, home_drawing = self.double_icon()
			handle_width = int(2*inner/3)
			handle_height = int(2*inner/3)

			if self.switch_style == "large":   # big handle style
				handle_width = int(inner)
			elif self.switch_style == "xlarge":   # big handle style
				handle_width = int(4*inner/3)

			r = 10
			side = handle_width / math.sqrt(2) + r / 2
			tl = [center[0]-side/2, center[1]-side/2]
			br = [center[0]+side/2, center[1]+side/2]
			home_drawing.rounded_rectangle(tl+br, radius=r, fill=self.handle_fill_color)
			home = home.rotate(45)
			a = 1
			b = 0
			c = 0  # left/right (i.e. 5/-5)
			d = 0
			e = 1
			f = - handle_height + r/2  # up/down (i.e. 5/-5)
			home = home.transform(overlay.size, Image.AFFINE, (a, b, c, d, e, f))

			# # Button handle
			home_drawing = ImageDraw.Draw(home)
			tl = [center[0]-handle_width/2, center[1]-handle_height]
			br = [center[0]+handle_width/2, center[1]+handle_height]
			home_drawing.rounded_rectangle(tl+br, radius=r, fill=self.handle_fill_color)

			overlay.alpha_composite(home)
			overlay = overlay.rotate(red(-angle))  # ;-)
			image.alpha_composite(overlay)
			# Overlay tick/line/needle mark on top of button
			start = self.needle_start
			# end = handle_height + side / 2 - r / 2
			length = self.needle_length
			end = start + length
			xr = center[0] - start * math.sin(math.radians(angle))
			yr = center[1] + start * math.cos(math.radians(angle))
			xc = center[0] - end * math.sin(math.radians(angle))
			yc = center[1] + end * math.cos(math.radians(angle))
			if self.needle_underline_width > 0:
				draw.line([(xc, yc), (xr, yr)],
						  width=self.needle_width+2*self.needle_underline_width,
						  fill=self.needle_underline_color)
			draw.line([(xc, yc), (xr, yr)], width=self.needle_width, fill=self.needle_color)
			# needle tip
			if self.needle_tip is not None:
				# print("tip1", self.switch_style, self.button_size, self.needle_start, self.needle_length, self.needle_tip, self.needle_tip_size)
				tip_image, tip_draw = self.double_icon()
				if self.needle_tip.startswith("arr"):
					orient = -1 if self.needle_tip == "arri" else 1
					tip = ((3*self.needle_tip_size, 0), (0, 4*self.needle_tip_size*orient), (-3*self.needle_tip_size, 0), (3*self.needle_tip_size, 0))
					tip = list(((center[0]+x[0], center[1]+x[1]) for x in tip))
					tip_draw.polygon(tip, fill=self.needle_color)  # , outline="red", width=3
				else:
					tl = [center[0]-self.needle_tip_size/2, center[1]-self.needle_tip_size/2]
					br = [center[0]+self.needle_tip_size/2, center[1]+self.needle_tip_size/2]
					tip_draw.ellipse(tl+br, fill=self.needle_color, outline="red", width=3)
				tip_image = tip_image.rotate(red(-angle), translate=(-end*math.sin(math.radians(angle)), end*math.cos(math.radians(angle))))  # ;-)
				image.alpha_composite(tip_image)

		else:  # Just a needle
			xr = center[0] - self.button_size/2 * math.sin(math.radians(angle))
			yr = center[1] + self.button_size/2 * math.cos(math.radians(angle))
			length = self.button_size/2 - self.needle_length
			xc = center[0] - length * math.sin(math.radians(angle))
			yc = center[1] + length * math.cos(math.radians(angle))
			# print(f"***> {value} => {angle}")
			if self.needle_underline_width > 0:
				draw.line([(xc, yc), (xr, yr)],
						  width=self.needle_width+2*self.needle_underline_width,
						  fill=self.needle_underline_color)
			draw.line([(xc, yc), (xr, yr)], width=self.needle_width, fill=self.needle_color)
			# needle tip
			if self.needle_tip is not None:
				# print("tip2", self.switch_style, self.button_size, self.needle_start, self.needle_length, self.needle_tip, self.needle_tip_size)
				tip_image, tip_draw = self.double_icon()
				if self.needle_tip.startswith("arr"):
					orient = -1 if self.needle_tip == "arri" else 1
					tip = ((3*self.needle_tip_size, 0), (0, 4*self.needle_tip_size*orient), (-3*self.needle_tip_size, 0), (3*self.needle_tip_size, 0))
					tip = list(((center[0]+x[0], center[1]+x[1]) for x in tip))
					tip_draw.polygon(tip, fill=self.needle_color)  # , outline="red", width=3
				else:
					tl = [center[0]-self.needle_tip_size/2, center[1]-self.needle_tip_size/2]
					br = [center[0]+self.needle_tip_size/2, center[1]+self.needle_tip_size/2]
					tip_draw.ellipse(tl+br, fill=self.needle_color, outline="red", width=3)
			tip_image = tip_image.rotate(red(-angle), translate=(-end*math.sin(math.radians(angle)), end*math.cos(math.radians(angle))))  # ;-)
			image.alpha_composite(tip_image)

		return self.move_and_send(image)


class Switch(SwitchBase):

	def __init__(self, config: dict, button: "Button"):

		SwitchBase.__init__(self, config=config, button=button, switch_type="switch")

		# Alternate defaults
		self.switch_style = self.switch.get("switch-style", "round")
		self.button_size = self.switch.get("button-size", int(ICON_SIZE/5))

		# Handle
		self.handle_dot_color = self.switch.get("switch-length", "white")

		# Switch
		self.switch_length = self.switch.get("switch-length", ICON_SIZE / 2.75)
		self.switch_width = self.switch.get("switch-width", 32)

		self.tick_label_size = self.switch.get("tick-label-size", 40)

		# Options
		self.three_way = self.button.has_option("3way")
		self.label_opposite = self.button.has_option("label-opposite")
		self.invert = self.button.has_option("invert")
		self.vertical = not self.button.has_option("horizontal")
		self.hexabase = self.button.has_option("hexa")
		self.screw_rot = randint(0, 60) # remembers it so that it does not "turn" between updates

		# Magic default resizing
		# Resizes default value switches to nice looking Airbus switches
		self.draw_scale = float(self.switch.get("scale", 0.8))
		if self.draw_scale < 0.5 or self.draw_scale > 2:
			logger.warning(f"button {self.button.name}: invalid scale {self.draw_scale}, must be in interval [0.5, 2]")
			self.draw_scale = 1
		if self.switch.get("left") is None and self.switch.get("right") is None:
			if self.vertical:
				if self.label_opposite:
					self.draw_left = 40
				else:
					self.draw_left = -40
		if self.switch.get("up") is None and self.switch.get("down") is None:
			if self.vertical:
				self.draw_up = -20
			else:
				self.draw_up = -40

	# The following functions draw switches centered on 0, 0 on a a canvas of ICON_SIZE x ICON_SIZE
	def draw_base(self, draw, radius: int = ICON_SIZE/4):
		# Base is either hexagonal or round
		if self.hexabase:
			draw.regular_polygon((ICON_SIZE, ICON_SIZE, radius), n_sides=6, rotation=self.screw_rot,
								 fill=self.button_fill_color, outline=self.button_stroke_color)
			# screw hole is circular
			SCREW_HOLE_FRACT = 3
			tl = [ICON_SIZE-radius/SCREW_HOLE_FRACT, ICON_SIZE-radius/SCREW_HOLE_FRACT]
			br = [ICON_SIZE+radius/SCREW_HOLE_FRACT, ICON_SIZE+radius/SCREW_HOLE_FRACT]
			# print("H>", tl, br)
			draw.ellipse(tl+br, fill=SCREW_HOLE_COLOR, outline=SCREW_HOLE_UNDERLINE, width=SCREW_HOLE_UWIDTH)
		else:
			if self.button.has_option("no-ublack"):
				tl = [ICON_SIZE-radius, ICON_SIZE-radius]
				br = [ICON_SIZE+radius, ICON_SIZE+radius]
				draw.ellipse(tl+br, fill=self.button_fill_color, outline=self.button_stroke_color, width=self.button_stroke_width)
			else:
				# Add underline back
				tl = [ICON_SIZE-radius, ICON_SIZE-radius]
				br = [ICON_SIZE+radius, ICON_SIZE+radius]
				draw.ellipse(tl+br, fill="black", outline=self.button_stroke_color, width=self.button_stroke_width)

				w = 12
				r = radius - w
				tl = [ICON_SIZE-r, ICON_SIZE-r]
				br = [ICON_SIZE+r, ICON_SIZE+r]
				draw.ellipse(tl+br, fill=self.button_fill_color)
			# print("B>", tl, br)
			# screw hole is oval (not elliptic)
			w = int(3*radius/8)
			l = int(radius/2)
			tl = [ICON_SIZE-w, ICON_SIZE-l]
			br = [ICON_SIZE+w, ICON_SIZE+l]
			# print("rr>", tl, br)
			draw.rounded_rectangle(tl+br, radius=w, fill=SCREW_HOLE_COLOR, outline=SCREW_HOLE_UNDERLINE, width=SCREW_HOLE_UWIDTH)

		if self.button_underline_width > 0:
			tl1 = [ICON_SIZE-radius-self.tick_space, ICON_SIZE-radius-self.tick_space]
			br1 = [ICON_SIZE+radius+self.tick_space, ICON_SIZE+radius+self.tick_space]
			# print("U>", tl1, br1)
			draw.ellipse(tl1+br1, outline=self.button_underline_color, width=self.button_underline_width)

	def draw_round_switch_from_top(self, draw, radius: int = ICON_SIZE / 16):
		#### TOP
		tl = [ICON_SIZE-2*radius, ICON_SIZE-2*radius]
		br = [ICON_SIZE+2*radius, ICON_SIZE+2*radius]
		# print(">R", tl, br)
		draw.ellipse(tl+br, fill=self.top_fill_color, outline=self.top_stroke_color, width=self.top_stroke_width)

		# (white) tip
		tl = [ICON_SIZE-radius, ICON_SIZE-radius]
		br = [ICON_SIZE+radius, ICON_SIZE+radius]
		# print(">tip", tl, br)
		draw.ellipse(tl+br, fill=self.handle_tip_fill_color)

	def draw_round_switch(self, draw, radius: int = ICON_SIZE / 16):
		# A Handle is visible if not in "middle" position,
		# in which case the button, as seen from top, has not handle.
		# Base
		# Little ellipsis at base
		lr = radius - 4
		tl = [ICON_SIZE-lr, ICON_SIZE-lr/2]
		br = [ICON_SIZE+lr, ICON_SIZE+lr/2]
		# print("|b", tl, br)
		draw.ellipse(tl+br, fill=self.handle_base_fill_color)
		# Little start of handle (height of little part = lph)
		lph = radius
		tl = [ICON_SIZE-lr, ICON_SIZE-lph]
		br = [ICON_SIZE+lr, ICON_SIZE]
		# print("|B", tl, br)
		draw.rectangle(tl+br, fill=self.handle_base_fill_color)

		# # larger part of handle (high of larger part = hheight, width of larger part at top = hwidth)
		hheight = 5 * radius
		hwidth  = 3 * radius
		swtop = ICON_SIZE - lph
		p1 = (ICON_SIZE-hwidth/2, swtop - hheight)
		p2 = (ICON_SIZE+hwidth/2, swtop - hheight)
		p3 = (ICON_SIZE+radius, swtop)
		p4 = (ICON_SIZE-radius, swtop)
		# print("|M", [p1, p2, p3, p4, p1])
		draw.polygon([p1, p2, p3, p4, p1],
					  fill=self.handle_fill_color,
					  outline=self.handle_stroke_color,
					  width=self.handle_stroke_width)
		# #### TOP
		tl = [ICON_SIZE-hwidth/2, swtop-hheight-hwidth/4]
		br = [ICON_SIZE+hwidth/2, swtop-hheight+hwidth/4]
		# print("|T", tl, br)
		draw.ellipse(tl+br, fill=self.top_fill_color, outline=self.top_stroke_color, width=self.top_stroke_width)

		# # (white) tip
		hwidth = int(hwidth/2)
		tl = [ICON_SIZE-hwidth/2, swtop-hheight-hwidth/4]
		br = [ICON_SIZE+hwidth/2, swtop-hheight+hwidth/4]
		# print("|tip", tl, br)
		draw.ellipse(tl+br, fill=self.handle_tip_fill_color)

	def draw_flat_switch_from_top(self, draw, radius: int = ICON_SIZE / 16):
		# Then the flat part
		w = 2 * radius
		h = radius
		tl = [ICON_SIZE-w, ICON_SIZE-h]
		br = [ICON_SIZE+w, ICON_SIZE+h]
		# print(">F", tl, br)
		# draw.rectangle(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)
		draw.rounded_rectangle(tl+br, radius=4, fill=self.top_fill_color, outline=self.top_stroke_color, width=int(self.top_stroke_width * 1.5))

		#### (white) tip
		# rrect in top 1/3 of flat part
		nlines = 4
		avail = int(8 * radius / 3)
		separ  = int(avail / (nlines+1))
		start = separ / 4
		w = int((2 * radius - 2 * start))
		h = (radius - 2 * start) / 2
		tl = [ICON_SIZE-w, ICON_SIZE-h]
		br = [ICON_SIZE+w, ICON_SIZE+h]
		# print(">tip", tl, br, "wxh", w, h, "separ", separ, "start", start)
		draw.rounded_rectangle(tl+br, radius=w/2, fill=self.handle_tip_fill_color)

	def draw_flat_switch(self, draw, radius: int = ICON_SIZE / 16):
		# Little ellipsis at base
		lr = radius - 4
		tl = [ICON_SIZE-lr, ICON_SIZE-lr/2]
		br = [ICON_SIZE+lr, ICON_SIZE+lr/2]
		# print("|b", tl, br)
		draw.ellipse(tl+br, fill=self.handle_base_fill_color)

		# Little start of handle (height of little part = lph)
		lph = radius
		tl = [ICON_SIZE-lr, ICON_SIZE-lph]
		br = [ICON_SIZE+lr, ICON_SIZE]
		# print("|B", tl, br)
		draw.rectangle(tl+br, fill=self.handle_base_fill_color)

		# First an enlargement of the little start of handle
		hheight = 2 * radius
		hwidth  = 4 * radius
		swtop = ICON_SIZE - lph
		p1 = (ICON_SIZE-hwidth/2, swtop - hheight)
		p2 = (ICON_SIZE+hwidth/2, swtop - hheight)
		p3 = (ICON_SIZE+radius, swtop)
		p4 = (ICON_SIZE-radius, swtop)
		# print("|m", [p1, p2, p3, p4, p1])
		draw.polygon([p1, p2, p3, p4, p1],
					  fill=self.handle_fill_color,
					  outline=self.handle_stroke_color,
					  width=self.handle_stroke_width)

		# # Then the flat part
		toph = 4 * radius
		tl = [ICON_SIZE-hwidth/2, swtop - hheight - toph]
		br = [ICON_SIZE+hwidth/2, swtop - hheight]
		# print("|M", [p1, p2, p3, p4, p1], "h", toph)
		draw.rectangle(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)

		# Decoration of the flat part
		# small lines in bottom 2/3 of flat part
		nlines = 4
		avail = int(2 * toph / 4)
		separ  = int(avail / nlines)
		start = int(separ / 2)
		for i in range(nlines):
			h = swtop - hheight - start - i * separ
			l = ICON_SIZE-hwidth/2 + separ
			e = ICON_SIZE+hwidth/2 - separ
			# print("|-", [(l, h),(e, h)], "avail", avail, "separ", separ, "bot", swtop - hheight, "2/3", swtop - hheight - avail)
			draw.line([(l, h),(e, h)], width=2, fill=grey(210))

		# #### (white) tip
		# # rrect in top 1/3 of flat part
		mid  = swtop - hheight - int(5 * toph / 6)
		# topw = int(hwidth / 4)
		# tl = [ICON_SIZE-hwidth/2 + separ, mid-topw/2]
		# br = [ICON_SIZE+hwidth/2 - separ, mid+topw/2]
		# # print("|=", [tl+br], "2/3=bot", swtop - avail, "top", swtop - hheight - toph, '5/6', swtop - hheight - int(5 * toph / 6))
		# draw.rounded_rectangle(tl+br, radius=topw/4, fill=self.handle_tip_fill_color)


		w = int((2 * radius - 2 * start))
		h = (radius - 2 * start) / 2
		tl = [ICON_SIZE-w, mid-h]
		br = [ICON_SIZE+w, mid+h]
		# print(">tip", tl, br, "wxh", w, h, "separ", separ, "start", start)
		draw.rounded_rectangle(tl+br, radius=w/2, fill=self.handle_tip_fill_color)

	def draw_3dot_switch_from_top(self, draw, radius: int = ICON_SIZE / 16):
		# Big rounded rect
		width = 10 * radius
		height = 4 * radius
		tl = [ICON_SIZE-width/2, ICON_SIZE-height/2]
		br = [ICON_SIZE+width/2, ICON_SIZE+height/2]
		# print(">3", tl, br)
		draw.rounded_rectangle(tl+br, radius=height/2, fill=self.top_fill_color, outline=self.top_stroke_color, width=int(self.top_stroke_width * 1.5))

		# Dots
		ndots = 3
		sep = width / (ndots + 1)
		start = sep
		dotr = 2 * radius
		left = ICON_SIZE - (width/2) + start
		for i in range(ndots):
			x = left + i * sep
			tl = [x-dotr/2, ICON_SIZE-dotr/2]
			br = [x+dotr/2, ICON_SIZE+dotr/2]
			# print(">•", tl, br, "x", x, width, left, sep, start)
			draw.ellipse(tl+br, fill=self.handle_tip_fill_color)

	def draw_3dot_switch(self, draw, radius: int = ICON_SIZE / 16):
		# Little ellipsis at base
		lr = radius - 4
		tl = [ICON_SIZE-lr, ICON_SIZE-lr/2]
		br = [ICON_SIZE+lr, ICON_SIZE+lr/2]
		# print("|b", tl, br)
		draw.ellipse(tl+br, fill=self.handle_base_fill_color)

		# Little start of handle (height of little part = lph)
		lph = radius
		tl = [ICON_SIZE-lr, ICON_SIZE-lph]
		br = [ICON_SIZE+lr, ICON_SIZE]
		# print("|B", tl, br)
		draw.rectangle(tl+br, fill=self.handle_base_fill_color)

		# Then the handle
		hh = 2 * radius
		hw = radius
		top0 = ICON_SIZE-lr
		tl = [ICON_SIZE-hw, top0 - hh]
		br = [ICON_SIZE+hw, top0]
		# print("|M", tl+br)
		draw.rectangle(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)

		# Big rounded rect
		radius = radius * 2
		width = 5 * radius
		height = 2 * radius
		top = top0 - hh - height/2
		tl = [ICON_SIZE-width/2, top-height/2+2]
		br = [ICON_SIZE+width/2, top+height/2-2]
		# print(">3", tl, br)
		draw.rounded_rectangle(tl+br, radius=height/2, fill=self.top_fill_color, outline=self.top_stroke_color, width=int(self.top_stroke_width * 1.5))

		# Dots
		ndots = 3
		sep = width / (ndots + 1)
		start = sep
		dotr = int(radius)
		left = ICON_SIZE - (width/2) + start
		for i in range(ndots):
			x = left + i * sep
			tl = [x-dotr/2, top-dotr/2+2]
			br = [x+dotr/2, top+dotr/2-2]
			# print(">•", tl, br, "x", x, width, left, sep, start)
			draw.ellipse(tl+br, fill=self.handle_tip_fill_color)

	def draw_ticks(self, draw):
		underline = ICON_SIZE - self.tick_space
		tick_end  = underline + self.tick_length
		# top mark
		draw.line([(underline, ICON_SIZE - self.switch_length),(tick_end, ICON_SIZE - self.switch_length)], width=self.tick_width, fill=self.tick_color)
		# middle mark
		if self.three_way:
			draw.line([(underline, ICON_SIZE),(tick_end, ICON_SIZE)], width=self.tick_width, fill=self.tick_color)
		# bottom mark
		draw.line([(underline, ICON_SIZE + self.switch_length),(tick_end, ICON_SIZE + self.switch_length)], width=self.tick_width, fill=self.tick_color)
		# underline
		if self.tick_underline_width > 0:
			draw.line([(underline, ICON_SIZE - self.switch_length),(underline, ICON_SIZE + self.switch_length)], width=self.tick_underline_width, fill=self.tick_color)

	def draw_labels(self, draw):
		inside = ICON_SIZE / 32
		font = self.get_font(self.tick_label_font, int(self.tick_label_size))
		if self.vertical:
			# Vertical
			# Distribute labels between [-switch_length and +switch_length]
			align="right"
			anchor="rm"
			if self.label_opposite:
				align="left"
				anchor="lm"
			hloc = ICON_SIZE + self.tick_label_space
			draw.text((hloc, ICON_SIZE - self.switch_length),
					  text=self.tick_labels[0],
					  font=font,
					  anchor=anchor,
					  align=align,
					  fill=self.tick_label_color)
			n = 1
			if self.three_way:
				draw.text((hloc, ICON_SIZE),
						  text=self.tick_labels[1],
						  font=font,
						  anchor=anchor,
						  align=align,
						  fill=self.tick_label_color)
				n = 2
			draw.text((hloc, ICON_SIZE + self.switch_length),
					  text=self.tick_labels[n],
					  font=font,
					  anchor=anchor,
					  align=align,
					  fill=self.tick_label_color)
			return

		# Horizontal
		# Equally space labels (centers) inside button width - 2*inside (for borders)
		vloc = ICON_SIZE + self.tick_label_space
		draw.text((ICON_SIZE - ICON_SIZE/2 + inside, vloc),
				  text=self.tick_labels[0],
				  font=font,
				  anchor="lm",
				  align="center",
				  fill=self.tick_label_color)
		n = 1
		if self.three_way:
			draw.text((ICON_SIZE, vloc),
					  text=self.tick_labels[1],
					  font=font,
					  anchor="mm",
					  align="center",
					  fill=self.tick_label_color)
			n = 2
		draw.text((ICON_SIZE + ICON_SIZE/2 - inside, vloc),
				  text=self.tick_labels[n],
				  font=font,
				  anchor="rm",
				  align="center",
				  fill=self.tick_label_color)

	def get_image_for_icon(self):
		"""
		Helper function to get button image and overlay label on top of it.
		Label may be updated at each activation since it can contain datarefs.
		Also add a little marker on placeholder/invalid buttons that will do nothing.
		"""
		# Value
		value = self.button.get_current_value()  # 0, 1, or 2 if three_way
		if value is None:
			value = 0
		pos = -1  # 1 or -1, or 0 if 3way
		if value != 0:
			if self.three_way:
				if value == 1:
					pos = 0
				else:
					pos = 1
			else:
				pos = 1  # force to 1 in case value > 1
		if self.invert:
			pos = pos * -1

		# Canvas
		image, draw = self.double_icon()

		# Switch
		self.draw_base(draw, radius=self.button_size)
		switch, switch_draw = self.double_icon()
		if pos == 0:  # middle position
			if self.switch_style == SWITCH_STYLE.ROUND.value:
				self.draw_round_switch_from_top(switch_draw)
			elif self.switch_style == SWITCH_STYLE.FLAT.value:
				self.draw_flat_switch_from_top(switch_draw)
			else:
				self.draw_3dot_switch_from_top(switch_draw)
		else:
			if self.switch_style == SWITCH_STYLE.ROUND.value:
				self.draw_round_switch(switch_draw)
			elif self.switch_style == SWITCH_STYLE.FLAT.value:
				self.draw_flat_switch(switch_draw)
			else:
				self.draw_3dot_switch(switch_draw)
		if pos < 0:
			switch = switch.transpose(method=Image.Transpose.FLIP_TOP_BOTTOM)
		if not self.vertical:
			switch = switch.transpose(method=Image.Transpose.ROTATE_90)
			image = image.transpose(method=Image.Transpose.ROTATE_90)
		# Tick marks
		if self.tick_length > 0:
			ticks, ticks_draw = self.double_icon()
			self.draw_ticks(ticks_draw)
			if not self.vertical:
				ticks = ticks.transpose(method=Image.Transpose.ROTATE_270)
			# Shift ticks
			space = self.button_size + self.tick_space
			if self.button_underline_width > 0:
				space = space + 2 * self.tick_space
			c = space if self.vertical else 0
			f = space if not self.vertical else 0
			ticks = ticks.transform(ticks.size, Image.AFFINE, (1, 0, c, 0, 1, f))
			if self.label_opposite:
				ticks = ticks.transpose(method=Image.Transpose.ROTATE_180)
			image.alpha_composite(ticks)
		# # Tick labels
		if len(self.tick_labels) > 0:
			tick_labels, tick_labels_draw = self.double_icon()
			self.draw_labels(tick_labels_draw)
			space = self.button_size + self.tick_length
			if self.button_underline_width > 0:
				space = space + self.tick_space
			c = (space + 2 * self.tick_space) if self.vertical else 0
			f = (space + 4 * self.tick_space) if not self.vertical else 0
			if self.label_opposite:
				c = -c
				f = -f
			tick_labels = tick_labels.transform(tick_labels.size, Image.AFFINE, (1, 0, c, 0, 1, f))
			image.alpha_composite(tick_labels)
		image.alpha_composite(switch)

		return self.move_and_send(image)


class PushSwitch(SwitchBase):

	def __init__(self, config: dict, button: "Button"):

		SwitchBase.__init__(self, config=config, button=button, switch_type="push-switch")

		# Alternate defaults
		self.button_size = self.switch.get("button-size", 80)

		self.handle_size = self.switch.get("witness-size", min(self.button_size/2, 40))

		self.handle_fill_color = self.switch.get("witness-fill-color", (0,0,0,0))
		self.handle_fill_color = convert_color(self.handle_fill_color)
		self.handle_stroke_color = self.switch.get("witness-stroke-color", (255,255,255))
		self.handle_stroke_color = convert_color(self.handle_stroke_color)
		self.handle_stroke_width = self.switch.get("witness-stroke-width", 4)

		self.handle_off_fill_color = self.switch.get("witness-fill-off-color", (0,0,0,0))
		self.handle_off_fill_color = convert_color(self.handle_off_fill_color)
		self.handle_off_stroke_color = self.switch.get("witness-stroke-off-color", (255,255,255, 0))
		self.handle_off_stroke_color = convert_color(self.handle_off_stroke_color)
		self.handle_off_stroke_width = self.switch.get("witness-stroke-off-width", 4)


	def get_image_for_icon(self):
		"""
		Helper function to get button image and overlay label on top of it.
		Label may be updated at each activation since it can contain datarefs.
		Also add a little marker on placeholder/invalid buttons that will do nothing.
		"""
		image, draw = self.double_icon()

		# Button
		center = [ICON_SIZE, ICON_SIZE]
		tl = [center[0]-self.button_size/2, center[1]-self.button_size/2]
		br = [center[0]+self.button_size/2, center[1]+self.button_size/2]
		draw.ellipse(tl+br, fill=self.button_fill_color, outline=self.button_stroke_color, width=self.button_stroke_width)

		if self.handle_size > 0:
			tl = [center[0]-self.handle_size/2, center[1]-self.handle_size/2]
			br = [center[0]+self.handle_size/2, center[1]+self.handle_size/2]
			if hasattr(self.button._activation, "is_off") and self.button._activation.is_off():
				logger.debug(f"button {self.button.name}: has on/off state and IS OFF")
				draw.ellipse(tl+br, fill=self.handle_off_fill_color, outline=self.handle_off_stroke_color, width=self.handle_off_stroke_width)
			else:
				if not hasattr(self.button._activation, "is_on"):
					logger.debug(f"button {self.button.name}: has no on/off state")
				draw.ellipse(tl+br, fill=self.handle_fill_color, outline=self.handle_stroke_color, width=self.handle_stroke_width)

		return self.move_and_send(image)


class Knob(SwitchBase):

	def __init__(self, config: dict, button: "Button"):

		SwitchBase.__init__(self, config=config, button=button, switch_type="knob")

		self.knob_type = self.switch.get("knob-type", "dent")
		self.knob_mark = self.switch.get("knob-mark", "triangle")  # needle, triangle, bar (diameter)

		# Alternate defaults
		# self.button_size = self.switch.get("button-size", 80)
		self.base_size = self.switch.get("base-size", int(ICON_SIZE / 1.25))
		self.base_fill_color = self.switch.get("base-fill-color", grey(128))
		self.base_stroke_color = self.switch.get("base-stroke-color", grey(20))
		self.base_stroke_width = self.switch.get("base-stroke-width", 16)

		self.base_underline_color = self.switch.get("base-underline-color", grey(240))
		self.base_underline_width = self.switch.get("base-underline-width", int(self.base_stroke_width/2))

		self.button_fill_color = self.switch.get("button-fill-color", grey(220))
		self.button_stroke_color = self.switch.get("button-stroke-color", grey(0))
		self.button_stroke_width = self.switch.get("button-stroke-width", 2)
		self.button_dents = self.switch.get("button-dents", 36)
		self.button_dent_size = self.switch.get("button-dent-size", 4)
		self.button_dent_extension = self.switch.get("button-dent-extension", 4)
		self.button_dent = self.switch.get("button-dent-negative", False)

		if self.button_dent_size < self.button_dent_extension:
			self.button_dent_size = self.button_dent_extension

		self.mark_underline_outer = self.switch.get("mark-underline-outer", 12)
		self.mark_underline_color = self.switch.get("mark-underline-color", "coral")
		self.mark_underline_width = self.switch.get("mark-underline-width", 4)
		self.mark_size = self.switch.get("witness-size", min(self.button_size/2, 40))
		self.mark_fill_color = self.switch.get("witness-fill-color", None)
		self.mark_fill_color = convert_color(self.mark_fill_color)
		self.mark_stroke_color = self.switch.get("witness-stroke-color", "blue")
		self.mark_stroke_color = convert_color(self.mark_stroke_color)
		self.mark_stroke_width = self.switch.get("witness-stroke-width", 8)

		self.mark_off_fill_color = self.switch.get("witness-fill-off-color", (0,0,0,0))
		self.mark_off_fill_color = convert_color(self.mark_off_fill_color)
		self.mark_off_stroke_color = self.switch.get("witness-stroke-off-color", (255,255,255, 0))
		self.mark_off_stroke_color = convert_color(self.mark_off_stroke_color)
		self.mark_off_stroke_width = self.switch.get("witness-stroke-off-width", 4)

		self.rotation = randint(0, 359)

	def set_rotation(self, rotation):
		"""Rotates a button's drawing

		May be an animation later?

		Args:
			rotation (float): Rotation of button in degrees
		"""
		self.rotation = rotation

	def get_image_for_icon(self):
		"""
		Helper function to get button image and overlay label on top of it.
		Label may be updated at each activation since it can contain datarefs.
		Also add a little marker on placeholder/invalid buttons that will do nothing.
		"""
		def mk_dent(count, center):
			dents_image, dents_draw = self.double_icon()

			bsize = self.button_dent_size	   # radius of little bubble added
			bover = self.button_dent_extension  # size of button extention

			radius = self.button_size/2 + bover - bsize
			if 360 % count != 0: # must be a multiple of 360
				count = 12
			step = int(360 / count)
			for i in range(count):
				angle = math.radians(i * step)
				lc = [center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)]
				tl = [lc[0]-bsize, lc[1]-bsize]
				br = [lc[0]+bsize, lc[1]+bsize]
				dents_draw.ellipse(tl+br, fill=self.button_fill_color, outline=self.button_stroke_color, width=self.button_stroke_width)
			return dents_image, dents_draw

		center = [ICON_SIZE, ICON_SIZE]
		#
		# Base
		base_image, base_draw = self.double_icon()
		base = self.base_size/2
		tl = [center[0]-base, center[1]-base]
		br = [center[0]+base, center[1]+base]
		base_draw.ellipse(tl+br, fill=self.base_fill_color, outline=self.base_stroke_color, width=self.base_stroke_width)

		# Base "underline", around it
		if self.base_underline_width > 0:
			base = self.base_size/2+self.base_underline_width/2
			tl = [center[0]-base, center[1]-base]
			br = [center[0]+base, center[1]+base]
			base_draw.ellipse(tl+br, outline=self.base_underline_color, width=self.base_underline_width)

		#
		# Button
		image, draw = self.double_icon()

		base = self.button_size/2
		tl = [center[0]-base, center[1]-base]
		br = [center[0]+base, center[1]+base]

		if self.button_dents:
			# button with outline
			draw.ellipse(tl+br, fill=self.button_fill_color, outline=self.button_stroke_color, width=self.button_stroke_width)
			# add dents over
			border_image, border = mk_dent(self.button_dents, center)
			image.alpha_composite(border_image)
			# button without outline
			image2, draw2 = self.double_icon()
			draw2.ellipse(tl+br, fill=self.button_fill_color)
			image.alpha_composite(image2)
		else:
			draw.ellipse(tl+br, fill=self.button_fill_color, outline=self.button_stroke_color, width=self.button_stroke_width)

		# Button-top mark underline
		if self.mark_underline_width > 0:
			base = self.button_size/2-self.mark_underline_outer
			tl = [center[0]-base, center[1]-base]
			br = [center[0]+base, center[1]+base]
			draw.ellipse(tl+br, outline=self.mark_underline_color, width=self.mark_underline_width)

		# Button-top mark
		mark_image, mark = self.double_icon()
		radius = int(ICON_SIZE / 8)
		mark.regular_polygon((ICON_SIZE, ICON_SIZE, radius), n_sides=3,
							 fill=self.mark_fill_color, outline=self.mark_stroke_color) #, width=self.mark_width, # https://github.com/python-pillow/Pillow/pull/7132

		image.alpha_composite(mark_image)
		image = image.rotate(self.rotation, resample=Image.Resampling.NEAREST, center=center)
		base_image.alpha_composite(image)


		return self.move_and_send(base_image)


DECOR = {
	"A": "corner upper left",
	"B": "straight horizontal",
	"C": "corner upper right",
	"D": "corner lower left",
	"E": "corner lower right",
	"F": "straight vertical",
	"G": "cross",
	"+": "cross",
	"H": "cross over horizontal",
	"I": "straight vertical",
	"J": "cross over vertical",
	"K": "T",
	"T": "T",
	"L": "T invert",
	"M": "T left",
	"N": "T right",
}

class Decor(DrawBase):

	def __init__(self, config: dict, button: "Button"):

		DrawBase.__init__(self, config=config, button=button)

		self.decor = config.get("decor")

		self.type = self.decor.get("type", "line")
		self.code = self.decor.get("code", "")
		self.decor_width_horz = 10
		self.decor_width_vert = 10
		decor_width = self.decor.get("width")    # now accepts two width 10/20, for horizontal and/ vertical lines
		if decor_width is not None:
			a = str(decor_width).split("/")
			if len(a) > 1:
				self.decor_width_horz = int(a[0])
				self.decor_width_vert = int(a[1])
			else:
				self.decor_width_horz = int(decor_width)
				self.decor_width_vert = int(decor_width)
		self.decor_color = self.decor.get("color", "lime")
		self.decor_color = convert_color(self.decor_color)


	def get_image_for_icon(self):

		def draw_segment(d, code):
			# From corners 1
			if "A" in code:
				d.line([(0, 0), (ICON_SIZE-r, ICON_SIZE-r)], fill=self.decor_color, width=self.decor_width_horz)
			if "C" in code:
				d.line([(ICON_SIZE+r, ICON_SIZE-r), (FULL_WIDTH, 0)], fill=self.decor_color, width=self.decor_width_horz)
			if "R" in code:
				d.line([(ICON_SIZE-r, ICON_SIZE+r), (0, FULL_HEIGHT)], fill=self.decor_color, width=self.decor_width_horz)
			if "T" in code:
				d.line([(ICON_SIZE+r, ICON_SIZE+r), (FULL_WIDTH, FULL_HEIGHT)], fill=self.decor_color, width=self.decor_width_horz)
			# From corners 2
			if "D" in code:
				d.line([(ICON_SIZE-r, ICON_SIZE-r), (ICON_SIZE-s, ICON_SIZE-s)], fill=self.decor_color, width=self.decor_width_horz)
			if "E" in code:
				d.line([(ICON_SIZE+s, ICON_SIZE-s), (ICON_SIZE+r, ICON_SIZE-r)], fill=self.decor_color, width=self.decor_width_horz)
			if "P" in code:
				d.line([(ICON_SIZE-r, ICON_SIZE+r), (ICON_SIZE-s, ICON_SIZE+s)], fill=self.decor_color, width=self.decor_width_horz)
			if "Q" in code:
				d.line([(ICON_SIZE+s, ICON_SIZE+s), (ICON_SIZE+r, ICON_SIZE+r)], fill=self.decor_color, width=self.decor_width_horz)
			# From corners 3
			if "A" in code:
				d.line([(ICON_SIZE-r, ICON_SIZE-r), (ICON_SIZE, ICON_SIZE)], fill=self.decor_color, width=self.decor_width_horz)
			if "C" in code:
				d.line([(ICON_SIZE, ICON_SIZE), (ICON_SIZE+r, ICON_SIZE-r)], fill=self.decor_color, width=self.decor_width_horz)
			if "R" in code:
				d.line([(ICON_SIZE-r, ICON_SIZE+r), (ICON_SIZE, ICON_SIZE)], fill=self.decor_color, width=self.decor_width_horz)
			if "T" in code:
				d.line([(ICON_SIZE, ICON_SIZE), (ICON_SIZE+r, ICON_SIZE+r)], fill=self.decor_color, width=self.decor_width_horz)
			# Horizontal bars
			if "I" in code:
				d.line([(0, ICON_SIZE), (ICON_SIZE-r, ICON_SIZE)], fill=self.decor_color, width=self.decor_width_horz)
			if "J" in code:
				d.line([(ICON_SIZE-r, ICON_SIZE), (ICON_SIZE, ICON_SIZE)], fill=self.decor_color, width=self.decor_width_horz)
			if "K" in code:
				d.line([(ICON_SIZE, ICON_SIZE), (ICON_SIZE+r, ICON_SIZE)], fill=self.decor_color, width=self.decor_width_horz)
			if "L" in code:
				d.line([(ICON_SIZE+r, ICON_SIZE), (FULL_WIDTH, ICON_SIZE)], fill=self.decor_color, width=self.decor_width_horz)
			# Vertical bars
			if "B" in code:
				d.line([(ICON_SIZE, 0), (ICON_SIZE, ICON_SIZE-r)], fill=self.decor_color, width=self.decor_width_vert)
			if "G" in code:
				d.line([(ICON_SIZE, ICON_SIZE-r), (ICON_SIZE, ICON_SIZE)], fill=self.decor_color, width=self.decor_width_vert)
			if "N" in code:
				d.line([(ICON_SIZE, ICON_SIZE), (ICON_SIZE, ICON_SIZE+r)], fill=self.decor_color, width=self.decor_width_vert)
			if "S" in code:
				d.line([(ICON_SIZE, ICON_SIZE+r), (ICON_SIZE, FULL_HEIGHT)], fill=self.decor_color, width=self.decor_width_vert)
			# Circle
			if "0" in code:
				d.arc(tl+br, start=180, end=225, fill=self.decor_color, width=self.decor_width_horz)
			if "1" in code:
				d.arc(tl+br, start=225, end=270, fill=self.decor_color, width=self.decor_width_horz)
			if "2" in code:
				d.arc(tl+br, start=270, end=315, fill=self.decor_color, width=self.decor_width_horz)
			if "3" in code:
				d.arc(tl+br, start=315, end=0, fill=self.decor_color, width=self.decor_width_horz)
			if "4" in code:
				d.arc(tl+br, start=0, end=45, fill=self.decor_color, width=self.decor_width_horz)
			if "6" in code:
				d.arc(tl+br, start=45, end=90, fill=self.decor_color, width=self.decor_width_horz)
			if "6" in code:
				d.arc(tl+br, start=90, end=135, fill=self.decor_color, width=self.decor_width_horz)
			if "7" in code:
				d.arc(tl+br, start=135, end=180, fill=self.decor_color, width=self.decor_width_horz)

		def draw_line(d, code):
			if code == "A":
				d.line([(cw, ch), (FULL_WIDTH, ch)], fill=self.decor_color, width=self.decor_width_horz)
				d.line([(cw, ch), (cw, FULL_HEIGHT)], fill=self.decor_color, width=self.decor_width_horz)
			if code in "BG+J":
				d.line([(0, ch), (FULL_WIDTH, ch)], fill=self.decor_color, width=self.decor_width_horz)
			if code == "C":
				d.line([(0, ch), (ICON_SIZE, ch)], fill=self.decor_color, width=self.decor_width_horz)
				d.line([(cw, ch), (cw, FULL_HEIGHT)], fill=self.decor_color, width=self.decor_width_horz)
			if code == "D":
				d.line([(cw, ch), (FULL_WIDTH, ch)], fill=self.decor_color, width=self.decor_width_horz)
				d.line([(cw, ch), (cw, 0)], fill=self.decor_color, width=self.decor_width_horz)
			if code == "E":
				d.line([(0, ch), (ICON_SIZE, ch)], fill=self.decor_color, width=self.decor_width_horz)
				d.line([(cw, ch), (cw, 0)], fill=self.decor_color, width=self.decor_width_horz)
			if code in "FIG+H":
				d.line([(ICON_SIZE, 0), (ICON_SIZE, FULL_HEIGHT)], fill=self.decor_color, width=self.decor_width_horz)
			if code == "H":
				d.line([(0, ch), (ICON_SIZE-r, ch)], fill=self.decor_color, width=self.decor_width_horz)
				d.line([(ICON_SIZE+r, ch), (FULL_WIDTH, ch)], fill=self.decor_color, width=self.decor_width_horz)
				tl = [cw-r, ch-r]
				br = [cw+r, ch+r]
				d.arc(tl+br, start=180, end=0, fill=self.decor_color, width=self.decor_width_horz)
			if code == "J":
				r = ICON_SIZE/4
				d.line([(cw, 0), (cw, ICON_SIZE-r)], fill=self.decor_color, width=self.decor_width_horz)
				d.line([(cw, ICON_SIZE+r), (cw, FULL_HEIGHT)], fill=self.decor_color, width=self.decor_width_horz)
				d.arc(tl+br, start=90, end=270, fill=self.decor_color, width=self.decor_width_horz)
			if code in "KT":
				d.line([(0, ch), (FULL_WIDTH, ch)], fill=self.decor_color, width=self.decor_width_horz)
				d.line([(cw, ch), (cw, FULL_HEIGHT)], fill=self.decor_color, width=self.decor_width_horz)
			if code in "L":
				d.line([(0, ch), (FULL_WIDTH, ch)], fill=self.decor_color, width=self.decor_width_horz)
				d.line([(cw, ch), (cw, 0)], fill=self.decor_color, width=self.decor_width_horz)
			if code in "M":
				d.line([(0, ch), (ICON_SIZE, ch)], fill=self.decor_color, width=self.decor_width_horz)
				d.line([(ICON_SIZE, 0), (ICON_SIZE, FULL_HEIGHT)], fill=self.decor_color, width=self.decor_width_horz)
			if code in "N":
				d.line([(ICON_SIZE, 0), (ICON_SIZE, FULL_HEIGHT)], fill=self.decor_color, width=self.decor_width_horz)
				d.line([(cw, ch), (FULL_WIDTH, ch)], fill=self.decor_color, width=self.decor_width_horz)


		image, draw = self.double_icon()

		# Square icons so far...
		FULL_WIDTH  = 2 * ICON_SIZE
		FULL_HEIGHT = 2 * ICON_SIZE
		center = [ICON_SIZE, ICON_SIZE]
		cw = center[0]
		ch = center[1]
		d = int(ICON_SIZE/2)
		r = int(ICON_SIZE/4)
		s = int(r * math.sin(math.radians(45)))
		tl = [cw-r, ch-r]
		br = [cw+r, ch+r]

		DECOR_TYPES = ["line", "segment"]

		if self.type not in DECOR_TYPES:
			draw.line([(0, ch), (FULL_WIDTH, ch)], fill="red", width=int(ICON_SIZE/2))
			return self.move_and_send(image)

		# SEGMENT
		if self.type == "segment":
			draw_segment(draw, self.code)
			return self.move_and_send(image)

		# LINE
		if self.code not in DECOR.keys():
			draw.line([(0, ch), (FULL_WIDTH, ch)], fill="red", width=int(ICON_SIZE/2))
			return self.move_and_send(image)
		draw_line(draw, self.code)
		return self.move_and_send(image)
