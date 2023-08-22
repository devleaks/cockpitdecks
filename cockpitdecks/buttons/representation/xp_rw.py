# ###########################
# Button that displays the real weather in X-Plane.
# It gets updated when real wheather changes.
# These buttons are highly XP specific.
#
import os
import logging
import random

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE, now
from cockpitdecks.resources.iconfonts import WEATHER_ICONS, WEATHER_ICON_FONT, DEFAULT_WEATHER_ICON
from cockpitdecks.resources.color import light_off, TRANSPARENT_PNG_COLOR
from .draw import DrawBase
from .xpweatherdrefs import DISPLAY_DATAREFS_REGION, DISPLAY_DATAREFS_AIRCRAFT

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class RealWeatherIcon(DrawBase):
	"""
	Depends on simulator weather
	"""
	MIN_UPDATE = 600  # seconds between two station updates

	def __init__(self, config: dict, button: "Button"):
		self._inited = False
		self._moved = False	# True if we get Metar for location at (lat, lon), False if Metar for default station
		self._upd_calls = 0
		self._upd_count = 0

		self.weather = config.get("real-weather", {})
		self.mode = self.weather.get("mode", "region")

		DrawBase.__init__(self, config=config, button=button)

		self._last_updated = None
		self._cache = None

		# Working variables
		self.display_datarefs = DISPLAY_DATAREFS_REGION if self.mode == "region" else DISPLAY_DATAREFS_AIRCRAFT
		self.weather_datarefs = self.display_datarefs.values()
		self.weather_icon = None

	def init(self):
		if self._inited:
			return
		self.weather_icon = self.select_weather_icon()
		self._inited = True
		logger.debug(f"inited")

	def get_datarefs(self):
		return list(self.weather_datarefs)

	def is_updated(self, force: bool = False) -> bool:
		"""
		Creates or updates Metar. Call to avwx may fail, so it is wrapped into try/except block

		:param	  force:  The force
		:type	   force:  bool

		:returns:   { description_of_the_return_value }
		:rtype:	 bool
		"""
		self._upd_calls = self._upd_calls + 1
		updated = False
		if self._last_updated is None:
			self.weather_icon = self.select_weather_icon()
			updated = True
			self._last_updated = now()
			logger.info(f"updated Real weather")
		else:
			diff = now().timestamp() - self._last_updated.timestamp()
			if diff > RealWeatherIcon.MIN_UPDATE:
				self.weather_icon = self.select_weather_icon()
				updated = True
				self._last_updated = now()
				logger.info(f"updated Real weather")
			else:
				logger.debug(f"Real weather does not need updating")
		return True

	def get_image_for_icon(self):
		"""
		Helper function to get button image and overlay label on top of it.
		Label may be updated at each activation since it can contain datarefs.
		Also add a little marker on placeholder/invalid buttons that will do nothing.
		"""

		logger.debug(f"updating ({self._upd_count}/{self._upd_calls})..")
		if not self.is_updated() and self._cache is not None:
			logger.debug(f"..not updated, using cache")
			return self._cache

		self._upd_count = self._upd_count + 1

		image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)					 # annunciator text and leds , color=(0, 0, 0, 0)
		draw = ImageDraw.Draw(image)
		inside = round(0.04 * image.width + 0.5)

		# Weather Icon
		icon_font = self._config.get("icon-font", WEATHER_ICON_FONT)
		icon_size = int(image.width / 2)
		icon_color = "white"
		font = self.get_font(icon_font, icon_size)
		inside = round(0.04 * image.width + 0.5)
		w = image.width / 2
		h = image.height / 2
		logger.debug(f"icon: {self.weather_icon}")
		icon_text = WEATHER_ICONS.get(self.weather_icon)
		if icon_text is None:
			logger.warning(f"icon: {self.weather_icon} not found, using default")
			icon_text = WEATHER_ICONS.get(DEFAULT_WEATHER_ICON)
			if icon_text is None:
				logger.warning(f"default icon not found, using default")
				icon_text = "\uf00d"
		draw.text((w, h),  # (image.width / 2, 15)
				  text=icon_text,
				  font=font,
				  anchor="mm",
				  align="center",
				  fill=light_off(icon_color, 0.6))

		# Weather Data
		lines = self.get_lines()

		if lines is not None:
			text_font = self._config.get("weather-font", self.label_font)
			text_size = int(image.width / 10)
			font = self.get_font(text_font, text_size)
			w = inside
			p = "l"
			a = "left"
			h = image.height / 3
			il = text_size
			for line in lines:
				draw.text((w, h),  # (image.width / 2, 15)
						  text=line.strip(),
						  font=font,
						  anchor=p+"m",
						  align=a,
						  fill=self.label_color)
				h = h + il
		else:
			logger.warning(f"no summary ({icao})")

		# Paste image on cockpit background and return it.
		bg = self.button.deck.get_icon_background(name=self.button_name(), width=ICON_SIZE, height=ICON_SIZE, texture_in=self.icon_texture, color_in=self.icon_color, use_texture=True, who="Weather")
		bg.alpha_composite(image)
		self._cache = bg.convert("RGB")
		return self._cache

	def get_lines(self) -> list:
		lines = list()
		lines.append(f"Mode: {self.mode}")
		press = self.button.get_dataref_value(self.display_datarefs["press"])
		if press is not None:
			press = int(press/100)
		lines.append(f"Press: {press}")
		temp = self.button.get_dataref_value(self.display_datarefs["temp"])
		lines.append(f"Temp: {temp}")
		dewp = self.button.get_dataref_value(self.display_datarefs["dewp"])
		lines.append(f"DewP:{dewp}")  # "sim/weather/region/sealevel_temperature_c"
		vis = self.button.get_dataref_value(self.display_datarefs["vis"])
		lines.append(f"Vis: {vis} sm")
		wind_dir = self.button.get_dataref_value(self.display_datarefs["wind_dir"])
		wind_speed = self.button.get_dataref_value(self.display_datarefs["wind_speed"])
		lines.append(f"Winds: {wind_speed} m/s {wind_dir}°")
		return lines

	def select_weather_icon(self):
		return self.select_random_weather_icon()

	def select_random_weather_icon(self):
		return random.choice(list(WEATHER_ICONS.keys()))
