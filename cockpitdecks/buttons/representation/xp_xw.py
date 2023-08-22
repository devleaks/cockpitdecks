# ###########################
# Buttons that are drawn on render()
#
# These buttons are highly XP specific.
#
import os
import logging
import random
from datetime import datetime

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE, AIRCRAFT_DATAREF_IPC, now
from cockpitdecks.resources.iconfonts import WEATHER_ICONS, WEATHER_ICON_FONT, DEFAULT_WEATHER_ICON
from cockpitdecks.resources.color import convert_color, light_off, TRANSPARENT_PNG_COLOR
from cockpitdecks.simulator import Dataref
from .draw import DrawBase
from .xpweather import XPWeather


logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
# logger.setLevel(logging.DEBUG)


class XPWeatherIcon(DrawBase):
	"""
	Depends on simulator weather
	"""
	MIN_UPDATE = 600  # seconds between two station updates

	def __init__(self, config: dict, button: "Button"):
		self._inited = False
		self._moved = False	# True if we get Metar for location at (lat, lon), False if Metar for default station
		self._upd_calls = 0
		self._upd_count = 0

		self.weather = config.get("xp-weather", {})
		self.mode = self.weather.get("mode", "region")
		self.xpweather = None
		self.weather_icon = None

		self._weather_last_updated = None
		self._icon_last_updated = None
		self._cache = None

		DrawBase.__init__(self, config=config, button=button)

		# Working variables
		self.collector = self.button.sim.collector

		self.all_collections = ["weather"]
		self.all_collections = self.all_collections + [f"cloud#{i}" for i in range(3)]
		self.all_collections = self.all_collections + [f"wind#{i}" for i in range(13)]

	def init(self):
		if self._inited:
			return
		self.weather_icon = self.select_weather_icon()
		self._inited = True
		logger.debug(f"inited")

	def collect_all_datarefs(self):
		drefs = {}
		for cname in self.all_collections:
			drefs = drefs | self.collector.collections[cname].datarefs
		return drefs

	def collect_last_updated(self):
		last_updated = None
		for name, collection in [(name, self.collector.collections.get(name)) for name in self.all_collections]:

			if collection is None:
				logger.debug(f"collection {name} missing")
				return None

			if collection.last_completed is None:
				logger.debug(f"collection {name} not completed")
				return None

			if last_updated is not None:
				if last_updated < collection.last_completed:
					last_updated = collection.last_completed
			else:
				last_updated = collection.last_completed
			# logger.debug(f"collection {collection.name} completed at {collection.last_completed}")

		logger.debug(f"all collections completed at {last_updated}")
		return last_updated

	def dataref_collection_changed(self, dataref_collection):
		logger.debug(f"{dataref_collection.name} completed")
		self.update_weather()

	def update_weather(self):
		last_updated = self.collect_last_updated()
		if last_updated is not None:
			self.xpweather = XPWeather(self.collect_all_datarefs())
			logger.debug(f"XPWeather reconstructed METAR: {self.xpweather.make_metar()}")

			self.weather_icon = self.select_weather_icon()
			self._weather_last_updated = now()
			logger.info(f"updated XP weather at {now().strftime('%H:%M:%S')}")
			return True
		logger.debug(f"Dataref collector has not completed")
		return False

	def is_updated(self) -> bool:
		self._upd_calls = self._upd_calls + 1
		if self.update_weather():
			if self._icon_last_updated is not None:
				return self._weather_last_updated > self._icon_last_updated
			return True
		return False

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
		self._icon_last_updated = now()

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
		# logger.debug(f"icon: {self.weather_icon}")
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

		if self.xpweather is None:
			lines.append(f"Mode: {self.mode}")
			lines.append(f"No weather")
			return lines

		lu = self.collect_last_updated()
		if lu is not None:
			dt = lu.strftime("%d %H:%M")
		else:
			dt = "NO TIME"
		lines.append(f"{dt} /M:{self.mode[0:4]}")

		press = round(self.xpweather.weather.qnh / 100)
		lines.append(f"Press: {press}")

		temp = round(self.xpweather.weather.temp, 1)
		lines.append(f"Temp: {temp}")

		idx = 0
		dewp = round(self.xpweather.wind_layers[idx].dew_point, 1)
		lines.append(f"DewP:{dewp} (L{idx})")

		vis = round(self.xpweather.weather.visibility, 1)
		lines.append(f"Vis: {vis} sm")

		wind_dir = round(self.xpweather.wind_layers[idx].direction)
		wind_speed = round(self.xpweather.weather.wind_speed, 1)
		lines.append(f"Winds: {wind_speed} m/s {wind_dir}° (L{idx})")

		return lines

	def select_weather_icon(self):
		return self.select_random_weather_icon()

	def select_random_weather_icon(self):
		return random.choice(list(WEATHER_ICONS.keys()))