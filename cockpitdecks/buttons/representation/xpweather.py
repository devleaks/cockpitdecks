import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..')) # we assume we're in subdir "bin/"

from datetime import datetime, timezone
from cockpitdecks.simulator import Dataref


# Mapping between python class instance attributes and datarefs:
# weather.baro get dataref "sim/weather/aircraft/barometer_current_pas" current value.
#
DATAREF_AIRCRAFT = {
	# WEATHER
	"alt_error": "sim/weather/aircraft/altimeter_temperature_error",
	"baro": "sim/weather/aircraft/barometer_current_pas",
	"gravity": "sim/weather/aircraft/gravity_mss",
	"precipitations": "sim/weather/aircraft/precipitation_on_aircraft_ratio",
	"qnh": "sim/weather/aircraft/qnh_pas",
	"rel_humidity": "sim/weather/aircraft/relative_humidity_sealevel_percent",
	"speed_of_sound": "sim/weather/aircraft/speed_sound_ms",
	"temp": "sim/weather/aircraft/temperature_ambient_deg_c",
	"temp-leading_edge": "sim/weather/aircraft/temperature_leadingedge_deg_c",
	"thermal_rete": "sim/weather/aircraft/thermal_rate_ms",
	"visibility": "sim/weather/aircraft/visibility_reported_sm",
	"wave_ampl": "sim/weather/aircraft/wave_amplitude",
	"wave_dir": "sim/weather/aircraft/wave_dir",
	"wave_length": "sim/weather/aircraft/wave_length",
	"wave_speed": "sim/weather/aircraft/wave_speed",
	"wind_speed": "sim/weather/aircraft/wind_speed_msc",
	# CLOUDS
	"base": "sim/weather/aircraft/cloud_base_msl_m",
	"coverage": "sim/weather/aircraft/cloud_coverage_percent",
	"tops": "sim/weather/aircraft/cloud_tops_msl_m",
	"cloud_type": "sim/weather/aircraft/cloud_type",
	# WINDS
	"alt_msl": "sim/weather/aircraft/wind_altitude_msl_m",
	"direction": "sim/weather/aircraft/wind_direction_degt",
	"speed_kts": "sim/weather/aircraft/wind_speed_kts",
	"temp_alotf": "sim/weather/aircraft/temperatures_aloft_deg_c",
	"dew_point": "sim/weather/aircraft/dewpoint_deg_c",
	"turbulence": "sim/weather/aircraft/turbulence",
	"shear_dir": "sim/weather/aircraft/shear_direction_degt",
	"shear_kts": "sim/weather/aircraft/shear_speed_kts"
}

# Mapping between python class instance attributes and datarefs:
# weather.baro get dataref "sim/weather/aircraft/barometer_current_pas" current value.
#
DATAREF_REGION = {
	# WEATHER
	"change_mode": "sim/weather/region/change_mode",
	"qnh_bqse": "sim/weather/region/qnh_base_elevation",
	"rain_pct": "sim/weather/region/rain_percent",
	"runway_friction": "sim/weather/region/runway_friction",
	"pressure_msl": "sim/weather/region/sealevel_pressure_pas",
	"temperature_msl": "sim/weather/region/sealevel_temperature_c",
	"thermal_rate": "sim/weather/region/thermal_rate_ms",
	"update": "sim/weather/region/update_immediately",
	"variability": "sim/weather/region/variability_pct",
	"visibility": "sim/weather/region/visibility_reported_sm",
	"wave_amp": "sim/weather/region/wave_amplitude",
	"wave_dir": "sim/weather/region/wave_dir",
	"wave_length": "sim/weather/region/wave_length",
	"wave_speed": "sim/weather/region/wave_speed",
	"source": "sim/weather/region/weather_source",
	# CLOUDS
	"base_msl_m": "sim/weather/region/cloud_base_msl_m",
	"coverage_pct": "sim/weather/region/cloud_coverage_percent",
	"tops_msl_m": "sim/weather/region/cloud_tops_msl_m",
	"type": "sim/weather/region/cloud_type",
	# WINDS
	"alt_levels_m": "sim/weather/region/atmosphere_alt_levels_m",
	"dewpoint": "sim/weather/region/dewpoint_deg_c",
	"temp_aloft": "sim/weather/region/temperatures_aloft_deg_c",
	"temp_alt_msl": "sim/weather/region/temperature_altitude_msl_m",
	"wind_alt_msl": "sim/weather/region/wind_altitude_msl_m",
	"wind_dir": "sim/weather/region/wind_direction_degt",
	"wind_speed": "sim/weather/region/wind_speed_msc",
	"turbulence": "sim/weather/region/turbulence",
	"shear_dir": "sim/weather/region/shear_direction_degt",
	"shear_speed": "sim/weather/region/shear_speed_msc"
}

DATAREF = DATAREF_AIRCRAFT  # DATAREF_REGION

class DatarefCollection:

	def __init__(self, drefs, index: int = None):
		self.__datarefs__ = drefs
		self.__drefidx__ = index

	def __getattr__(self, name: str):
#		print("converting", name)
		if self.__drefidx__ is None:
			name = DATAREF[name]
		else:
			name = f"{DATAREF[name]}[{self.__drefidx__}]"
#		print("getting", name)
		dref = self.__datarefs__.get(name)
		return dref.current_value if dref is not None else None

class WindLayer(DatarefCollection):
	def __init__(self, drefs, index):
		DatarefCollection.__init__(self, drefs=drefs, index=index)

class CloudLayer(DatarefCollection):
	def __init__(self, drefs, index):
		DatarefCollection.__init__(self, drefs=drefs, index=index)

class Weather(DatarefCollection):
	def __init__(self, drefs):
		DatarefCollection.__init__(self, drefs=drefs)


class XPWeather:
	# Data accessor shell class.
	# Must be supplied with dict of {path: Dataref(path)}
	# Make dataref accessible through instance attributes like weather.temperature.
	#
	def __init__(self, drefs):
		self.weather = Weather(drefs)
		self.wind_layers = []		#  Defined wind layers. Not all layers are always defined. up to 13 layers(!)
		self.cloud_layers = []		#  Defined cloud layers. Not all layers are always defined. up to 3 layers

		for i in range(3):
			self.cloud_layers.append(CloudLayer(drefs, i))

		for i in range(13):
			self.wind_layers.append(WindLayer(drefs, i))

	def make_metar(self):
		metar = self.getStation()
		metar = metar + " " +self.getTime()
		metar = metar + " " +self.getAuto()
		metar = metar + " " +self.getWind()
		if self.is_cavok():
			metar = metar + " CAVOK"
		else:
			metar = metar + " " +self.getVisibility()
			metar = metar + " " +self.getPhenomenae()
			metar = metar + " " +self.getClouds()
		metar = metar + " " +self.getTemperatures()
		metar = metar + " " +self.getPressure()
		metar = metar + " " +self.getForecast()
		metar = metar + " " +self.getRemarks()
		return metar

	def getStation(self):
		return "XXXX"

	def getTime(self):
		t = datetime.now().astimezone(tz=timezone.utc)
		m = "00"
		if t.minute > 30:
			m = "30"
		return t.strftime(f"%D%H{m}Z")

	def getAuto(self):
		return "AUTO"

	def getWind(self):
		return "00000KT"

	def is_cavok(self):
		return True

	def getVisibility(self):
		return ""

	def getPhenomenae(self):
		return ""

	def getClouds(self):
		return ""

	def getTemperatures(self):
		return ""

	def getPressure(self):
		return ""

	def getForecast(self):
		return ""

	def getRemarks(self):
		return ""

	def parse_metar(self, metar):
		return metar

# # Tests
# w = XPWeather({
# 	"sim/weather/aircraft/barometer_current_pas": Dataref("sim/weather/aircraft/barometer_current_pas"),
# 	"sim/weather/aircraft/wind_altitude_msl_m[7]": Dataref("sim/weather/aircraft/wind_altitude_msl_m[7]"),
# 	"sim/weather/region/cloud_type[2]": Dataref("sim/weather/region/cloud_type[2]")})
# print(w.weather.baro)
# print(w.wind_layers[7].alt_msl)
# print(w.cloud_layers[2].cloud_type)
# m = w.make_metar()
# print(m)