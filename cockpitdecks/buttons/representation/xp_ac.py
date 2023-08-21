# ###########################
# Representation that displays the content of sim/aircraft/view/acf_ICAO on an icon.
# These buttons are highly XP specific.
#
import os
import logging

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE, AIRCRAFT_DATAREF_IPC, now
from .draw import DrawBase

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


AIRCRAFT_DATAREF_BASE = "sim/aircraft/view/acf_ICAO"
AIRCRAFT_DATAREF_SIZE = 4   # sim/aircraft/view/acf_ICAO declared as byte[40], we only fetch first 4 chars...

class AircraftIcon(DrawBase):

	def __init__(self, config: dict, button: "Button"):
		self._inited = False
		self.fetched_string = None	# Aircraft/Extra Aircraft/ToLiss A321/liveries/Airbus Prototype - A321 Neo PW XLR/
		self.aircraft = None
		self._ac_count = 0
		self._cached = None
		self._last_updated = None
		self._acconfig = config.get("aircraft")
		self._drefcoll = config.get("dataref-collections")
		self._dataref = None
		self._array = 0

		DrawBase.__init__(self, config=config, button=button)

	def init(self):
		if self._inited:
			return
		if self._drefcoll is not None:
			self._collname = self._drefcoll[0].get("name", "unnamed")  # aircraft_icao
			self._dataref = self._drefcoll[0].get("datarefs", [AIRCRAFT_DATAREF_BASE])[0]
			self._array = self._drefcoll[0].get("array", AIRCRAFT_DATAREF_SIZE)
		else:
			logger.info(f"no dataref")
		self.notify_aircraft_updated()
		self._inited = True
		logger.debug(f"inited")

	def notify_aircraft_updated(self):
		if self.aircraft is not None:
			self._ac_count = self._ac_count + 1
			self.button._activation._write_dataref(AIRCRAFT_DATAREF_IPC, float(self._ac_count))
			self._last_updated = now()
			logger.info(f"notified of new aircraft {self._ac_count} ({self.aircraft})")

	def get_aircraft_name(self):
		return self.fetched_string if self.fetched_string != "" else None

	def updated(self):
		def updated_recently(how_long_ago: int = 10):  # secs
			# prevents multiple notification on startup or during string
			if self._last_updated is not None:
				delta = now().timestamp() - self._last_updated.timestamp()
				return delta < how_long_ago  # seconds
			return False

		drefs = self.button.sim.collector.collections[self._collname].datarefs
		# 1. Collect string character per character :-D
		new_string = ""
		updated = False
		cnt = 0
		for d in drefs.values():
			if d.current_value is not None:
				cnt = cnt + 1
				c = chr(int(d.current_value))
				new_string = new_string + c
		self.fetched_string = new_string

		if cnt < self._array:  # we did not fetch all chars yet
			logger.debug(f"received {cnt}/{self._array}")
			return False

		logger.debug(f"received {cnt}/{self._array} (completed)")
		# 2. Has the aircraft changed?
		ac = self.get_aircraft_name()
		if ac is not None:
			updated = self.aircraft != ac
			if updated:
				self.aircraft = ac
				if not updated_recently():
					self.notify_aircraft_updated()  # notifies writable dataref
				else:
					# self._last_updated should not be None as we reach here
					logger.debug(f"new aircraft string {self.aircraft} but no notification, collection in progress, notified at {self._last_updated}")
		return updated

	def get_image_for_icon(self):
		"""
		Helper function to get button image and overlay label on top of it.
		Label may be updated at each activation since it can contain datarefs.
		Also add a little marker on placeholder/invalid buttons that will do nothing.
		"""
		if not self.updated() and self._cached is not None:
			return self._cached

		image, draw = self.double_icon(width=ICON_SIZE, height=ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)
		inside = round(0.04 * image.width + 0.5)

		text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self._acconfig, "text")
		text = self.aircraft
		if text is None:
			text = "no aircraft"

		font = self.get_font(text_font, text_size)
		w = image.width / 2
		p = "m"
		a = "center"
		if text_position[0] == "l":
			w = inside
			p = "l"
			a = "left"
		elif text_position[0] == "r":
			w = image.width - inside
			p = "r"
			a = "right"
		h = image.height / 2
		if text_position[1] == "t":
			h = inside + text_size / 2
		elif text_position[1] == "r":
			h = image.height - inside - text_size / 2
		# logger.debug(f"position {(w, h)}")
		draw.multiline_text((w, h),  # (image.width / 2, 15)
				  text=text,
				  font=font,
				  anchor=p+"m",
				  align=a,
				  fill=text_color)


		# Paste image on cockpit background and return it.
		bg = self.button.deck.get_icon_background(name=self.button_name(), width=ICON_SIZE, height=ICON_SIZE, texture_in=self.icon_texture, color_in=self.icon_color, use_texture=True, who="Data")
		bg.alpha_composite(image)
		self._cached = bg.convert("RGB")
		return self._cached
