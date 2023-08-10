# ###########################
# Buttons that are drawn on render()
#
# These buttons are highly XP specific.
#
import os
import logging
import random
from datetime import datetime
import traceback

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE, AIRCRAFT_DATAREF_IPC
from cockpitdecks.resources.iconfonts import WEATHER_ICONS, WEATHER_ICON_FONT
from cockpitdecks.resources.color import convert_color, light_off, TRANSPARENT_PNG_COLOR
from cockpitdecks.simulator import Dataref

from .animation import DrawAnimation
from .draw import DrawBase


logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
logger.setLevel(logging.DEBUG)


DEFAULT_ICON = "wi-day-cloudy-high"

REAL_WEATHER_REGION_DATAREFS = [
	### ADD current altitude reference (ground, not in flight) for MSL/AGL convertions
	"sim/weather/region/change_mode",
	"sim/weather/region/qnh_base_elevation",
	"sim/weather/region/rain_percent",
	"sim/weather/region/runway_friction",
	"sim/weather/region/sealevel_pressure_pas",
	"sim/weather/region/sealevel_temperature_c",
	"sim/weather/region/thermal_rate_ms",
	"sim/weather/region/update_immediately",
	"sim/weather/region/variability_pct",
	"sim/weather/region/visibility_reported_sm",
	"sim/weather/region/wave_amplitude",
	"sim/weather/region/wave_dir",
	"sim/weather/region/wave_length",
	"sim/weather/region/wave_speed",
	"sim/weather/region/weather_source",
]

REAL_WEATHER_REGION_DATAREFS_ARRAYS = {
	"sim/weather/region/cloud_base_msl_m": 3,
	"sim/weather/region/cloud_coverage_percent": 3,
	"sim/weather/region/cloud_tops_msl_m": 3,
	"sim/weather/region/cloud_type": 3,
	"sim/weather/region/atmosphere_alt_levels_m": 13,
	"sim/weather/region/dewpoint_deg_c": 13,
	"sim/weather/region/temperatures_aloft_deg_c": 13,
	"sim/weather/region/temperature_altitude_msl_m": 13,
	"sim/weather/region/wind_altitude_msl_m": 13,
	"sim/weather/region/wind_direction_degt": 13,
	"sim/weather/region/wind_speed_msc": 13,
	"sim/weather/region/turbulence": 13,
	"sim/weather/region/shear_direction_degt": 13,
	"sim/weather/region/shear_speed_msc": 13,
}

def mkdrefarr_REGION():
	base = REAL_WEATHER_REGION_DATAREFS
	for k, v in REAL_WEATHER_REGION_DATAREFS_ARRAY.items():
		for i in range(v):
			base.append(f'{k}[{i}]')
	return base

DISPLAY_DATAREFS_REGION = {
	"press": "sim/weather/region/sealevel_pressure_pas",
	"temp": "sim/weather/region/sealevel_temperature_c",
	"dewp": "sim/weather/region/dewpoint_deg_c",
	"vis": "sim/weather/region/visibility_reported_sm",
	"wind_dir": "sim/weather/region/wind_direction_degt",
	"wind_speed": "sim/weather/region/wind_speed_msc"
}

REAL_WEATHER_AIRCRAFT_DATAREFS = [
	"sim/weather/aircraft/altimeter_temperature_error",
	"sim/weather/aircraft/barometer_current_pas",
	"sim/weather/aircraft/gravity_mss",
	"sim/weather/aircraft/precipitation_on_aircraft_ratio",
	"sim/weather/aircraft/qnh_pas",
	"sim/weather/aircraft/relative_humidity_sealevel_percent",
	"sim/weather/aircraft/speed_sound_ms",
	"sim/weather/aircraft/temperature_ambient_deg_c",
	"sim/weather/aircraft/temperature_leadingedge_deg_c",
	"sim/weather/aircraft/thermal_rate_ms",
	"sim/weather/aircraft/visibility_reported_sm",
	"sim/weather/aircraft/wave_amplitude",
	"sim/weather/aircraft/wave_dir",
	"sim/weather/aircraft/wave_length",
	"sim/weather/aircraft/wave_speed",
	"sim/weather/aircraft/wind_now_x_msc",
	"sim/weather/aircraft/wind_now_y_msc",
	"sim/weather/aircraft/wind_now_z_msc",
	"sim/weather/aircraft/wind_speed_msc"
]

REAL_WEATHER_AIRCRAFT_DATAREFS_ARRAY = {
	"sim/weather/aircraft/cloud_base_msl_m": 3,
	"sim/weather/aircraft/cloud_coverage_percent": 3,
	"sim/weather/aircraft/cloud_tops_msl_m": 3,
	"sim/weather/aircraft/cloud_type": 3,
	"sim/weather/aircraft/dewpoint_deg_c": 13,
	"sim/weather/aircraft/shear_direction_degt": 13,
	"sim/weather/aircraft/shear_speed_kts": 13,
	"sim/weather/aircraft/temperatures_aloft_deg_c": 13,
	"sim/weather/aircraft/turbulence": 13,
	"sim/weather/aircraft/wind_altitude_msl_m": 13,
	"sim/weather/aircraft/wind_direction_degt": 13,
	"sim/weather/aircraft/wind_speed_kts": 13,
}

def mkdrefarr_AIRCRAFT():
	base = REAL_WEATHER_AIRCRAFT_DATAREFS
	for k, v in REAL_WEATHER_AIRCRAFT_DATAREFS_ARRAY.items():
		for i in range(v):
			base.append(f'{k}[{i}]')
	return base

DISPLAY_DATAREFS_AIRCRAFT = {
	"press": "sim/weather/aircraft/qnh_pas",
	"temp": "sim/weather/aircraft/temperature_ambient_deg_c",
	"dewp": "sim/weather/aircraft/dewpoint_deg_c",
	"vis": "sim/weather/aircraft/visibility_reported_sm",
	"wind_dir": "sim/weather/aircraft/wind_direction_degt",
	"wind_speed": "sim/weather/aircraft/wind_speed_msc"
}


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
		self.display_datarefs = DISPLAY_DATAREFS_REGION  # or DISPLAY_DATAREFS_AIRCRAFT
		self.weather_datarefs = self.display_datarefs.values()
		self.weather_icon = None

		self.anim_start()

	def init(self):
		if self._inited:
			return
		self.weather_icon = self.select_weather_icon()
		self._inited = True
		logger.debug(f"inited")

	def get_datarefs(self):
		return list(self.weather_datarefs)

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
			self.weather_icon = self.select_weather_icon()
			updated = True
			self._upd_count = self._upd_count + 1
			self._last_updated = datetime.now()
			logger.info(f"UPDATED: Real weather")
		else:
			diff = datetime.now().timestamp() - self._last_updated.timestamp()
			if diff > RealWeatherIcon.MIN_UPDATE:
				self.weather_icon = self.select_weather_icon()
				updated = True
				self._upd_count = self._upd_count + 1
				self._last_updated = datetime.now()
				logger.info(f"UPDATED: Real weather")
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
			logger.warning(f"no metar summary ({icao})")

		# Paste image on cockpit background and return it.
		bg = self.button.deck.get_icon_background(name=self.button_name(), width=ICON_SIZE, height=ICON_SIZE, texture_in=self.icon_texture, color_in=self.icon_color, use_texture=True, who="Weather")
		bg.alpha_composite(image)
		self._cache = bg.convert("RGB")
		return self._cache

	def get_lines(self) -> list:
		lines = list()
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


AIRCRAFT_DATAREF_BASE = "sim/aircraft/view/acf_ICAO"
AIRCRAFT_DATAREF_SIZE = 4   # sim/aircraft/view/acf_ICAO declared as byte[40], we only fetch 4...

class AircraftIcon(DrawBase):

	def __init__(self, config: dict, button: "Button"):
		self._inited = False
		self.acf_livery_path = None	# Aircraft/Extra Aircraft/ToLiss A321/liveries/Airbus Prototype - A321 Neo PW XLR/
		self.aircraft = None
		self._ac_count = 0
		self._cached = None
		self._last_updated = None
		self._acconfig = config.get("aircraft")

		DrawBase.__init__(self, config=config, button=button)

	def init(self):
		if self._inited:
			return
		self.notify_aircraft_updated()
		self._inited = True
		logger.debug(f"inited")

	def notify_aircraft_updated(self):
		if self.aircraft is not None:
			self._ac_count = self._ac_count + 1
			self.button._activation._write_dataref(AIRCRAFT_DATAREF_IPC, float(self._ac_count))
			self._last_updated = datetime.now()
			logger.info(f"notified of new aircraft {self._ac_count} ({self.aircraft})")

	def get_datarefs(self):
		if self.datarefs is None:
			drefs = []
			for i in range(AIRCRAFT_DATAREF_SIZE):
				drefs.append(f"{AIRCRAFT_DATAREF_BASE}[{i}]")
			self.datarefs = drefs
		return self.datarefs

	def get_aircraft_name(self):
		return self.acf_livery_path if self.acf_livery_path != "" else None

	def updated_recently(self):
		if self._last_updated is not None:
			delta = datetime.now().timestamp() - self._last_updated.timestamp()
			return delta < 10  # seconds
		return False

	def updated(self):
		# 1. Collect string character per character :-D
		new_string = ""
		updated = False
		for i in range(AIRCRAFT_DATAREF_SIZE):
			a = self.button.get_dataref_value(f"{AIRCRAFT_DATAREF_BASE}[{i}]")
			if a is not None:
				c = chr(int(a))
				new_string = new_string + c
		self.acf_livery_path = new_string

		# 2. Has the aircraft part changed?
		ac = self.get_aircraft_name()
		if ac is not None:		
			updated = self.aircraft != ac
			if updated:
				self.aircraft = ac
				if not self.updated_recently():
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
		image, draw = self.double_icon(width=ICON_SIZE, height=ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)
		inside = round(0.04 * image.width + 0.5)

		if not self.updated() and self._cached is not None:
			return self._cached

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
