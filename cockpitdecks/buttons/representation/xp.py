# ###########################
# Buttons that are drawn on render()
#
# Buttons were isolated here bevcause they use quite larger packages (avwx-engine),
# call and rely on external services.
#
import logging
import random
from datetime import datetime
import traceback

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.resources.iconfonts import WEATHER_ICONS, WEATHER_ICON_FONT
from cockpitdecks.resources.color import convert_color, light_off, TRANSPARENT_PNG_COLOR
from cockpitdecks.simulator import Dataref

from .animation import DrawAnimation


logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
logger.setLevel(logging.DEBUG)


DEFAULT_ICON = "wi-day-cloudy-high"



class RealWeatherIcon(DrawAnimation):
	"""
	Depends on simulator weather
	"""
	MIN_UPDATE = 600  # seconds between two station updates

	def __init__(self, config: dict, button: "Button"):
		self._inited = False
		self._moved = False	# True if we get Metar for location at (lat, lon), False if Metar for default station
		self._upd_calls = 0
		self._upd_count = 0

		self.weather = config.get("weather")
		if self.weather is not None and isinstance(self.weather, dict):
			config["animation"] = config.get("weather")
		else:
			config["animation"] = {}
			self.weather = {}

		DrawAnimation.__init__(self, config=config, button=button)

		self._last_updated = None
		self._cache = None

		# "Animation" (refresh)
		speed = self.weather.get("refresh", 30)	# minutes, should be ~30 minutes
		self.speed = int(speed) * 60			# minutes

		updated = self.weather.get("refresh-location", 10) # minutes
		RealWeatherIcon.MIN_UPDATE = int(updated) * 60

		# Working variables
		self.weather_icon = self.select_random_weather_icon()  # None

		self.anim_start()

	def init(self):
		if self._inited:
			return
		self._inited = True
		logger.debug(f"inited")

	def get_datarefs(self):
		return [
			### ADD current altitude reference (ground, not in flight) for MSL/AGL convertions
			"sim/weather/region/atmosphere_alt_levels_m",
			"sim/weather/region/change_mode",
			"sim/weather/region/cloud_base_msl_m",
			"sim/weather/region/cloud_coverage_percent",
			"sim/weather/region/cloud_tops_msl_m",
			"sim/weather/region/cloud_type",
			"sim/weather/region/dewpoint_deg_c",
			"sim/weather/region/qnh_base_elevation",
			"sim/weather/region/rain_percent",
			"sim/weather/region/runway_friction",
			"sim/weather/region/sealevel_pressure_pas",
			"sim/weather/region/sealevel_temperature_c",
			"sim/weather/region/shear_direction_degt",
			"sim/weather/region/shear_speed_msc",
			"sim/weather/region/temperature_altitude_msl_m",
			"sim/weather/region/temperatures_aloft_deg_c",
			"sim/weather/region/thermal_rate_ms",
			"sim/weather/region/turbulence",
			"sim/weather/region/update_immediately",
			"sim/weather/region/variability_pct",
			"sim/weather/region/visibility_reported_sm",
			"sim/weather/region/wave_amplitude",
			"sim/weather/region/wave_dir",
			"sim/weather/region/wave_length",
			"sim/weather/region/wave_speed",
			"sim/weather/region/weather_source",
			"sim/weather/region/wind_altitude_msl_m",
			"sim/weather/region/wind_direction_degt",
			"sim/weather/region/wind_speed_msc"
		]

	def should_run(self) -> bool:
		"""
		Check conditions to animate the icon.
		In this case, always runs
		"""
		return True

	def update(self, force: bool = False) -> bool:
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
			updated = True
			self._upd_count = self._upd_count + 1
			self._last_updated = datetime.now()
			logger.info(f"UPDATED: Real weather")
		else:
			diff = datetime.now().timestamp() - self._last_updated.timestamp()
			if diff > RealWeatherIcon.MIN_UPDATE:
				updated = True
				self._upd_count = self._upd_count + 1
				self._last_updated = datetime.now()
				logger.info(f"UPDATED: Real weather")
			else:
				logger.debug(f"Real weather does not need updating")
		return updated

	def get_image_for_icon(self):
		"""
		Helper function to get button image and overlay label on top of it.
		Label may be updated at each activation since it can contain datarefs.
		Also add a little marker on placeholder/invalid buttons that will do nothing.
		"""

		logger.debug(f"updating ({self._upd_count}/{self._upd_calls})..")
		if not self.update():
			logger.debug(f"..not updated, using cache")
			return self._cache

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
			icon_text = WEATHER_ICONS.get(DEFAULT_ICON)
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
		lines = None

		lines = ["X-Plane", "Real Weather"]

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
			logger.warning(f"no metar summary ({icao})")

		# Paste image on cockpit background and return it.
		bg = self.button.deck.get_icon_background(name=self.button_name(), width=ICON_SIZE, height=ICON_SIZE, texture_in=self.icon_texture, color_in=self.icon_color, use_texture=True, who="Weather")
		bg.alpha_composite(image)
		self._cache = bg.convert("RGB")
		return self._cache

	def select_weather_icon(self):
		return self.select_random_weather_icon()

	def select_random_weather_icon(self):
		return random.choice(list(WEATHER_ICONS.keys()))

