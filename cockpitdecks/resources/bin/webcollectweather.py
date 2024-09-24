import requests
import json
import logging

logging.basicConfig(level=logging.DEBUG)


# BASE_URL = "http://localhost:8086/api/v1/datarefs"
BASE_URL = "http://mac-mini-de-pierre.local:8080/api/v1/datarefs"
DATA = "data"
IDENT = "id"


def get_dataref_specs(path: str) -> dict | None:
    payload = {"filter[name]": path}
    print("send", BASE_URL, payload)
    response = requests.get(BASE_URL, params=payload)
    resp = response.json()
    print("received", resp)
    if DATA in resp:
        return resp[DATA][0]
    print(resp)
    return None


def get_dataref_id(path: str) -> int | None:
    specs = get_dataref_specs(path)
    if specs is not None and IDENT in specs:
        return specs[IDENT]
    print(specs)
    return None


def get_dataref_value(path: str):
    dref = get_dataref_specs(path)
    if dref is None or IDENT not in dref:
        print(f"error for {path}")
        return None
    url = f"{BASE_URL}/{dref[IDENT]}/value"
    print("send", url)
    response = requests.get(url)
    data = response.json()
    print("received", data)
    if DATA in data:
        return data[DATA]
    print(f"no value for {path}")
    return None


# print(get_dataref_value("sim/weather/region/sealevel_pressure_pas"))
WEATHER_DATAREFS = [
    "sim/weather/aircraft/visibility_reported_sm",
    "sim/weather/aircraft/altimeter_temperature_error",
    "sim/weather/aircraft/wind_altitude_msl_m",
    "sim/weather/aircraft/wind_speed_kts",
    "sim/weather/aircraft/wind_direction_degt",
    "sim/weather/aircraft/shear_speed_kts",
    "sim/weather/aircraft/shear_direction_degt",
    "sim/weather/aircraft/turbulence",
    "sim/weather/aircraft/dewpoint_deg_c",
    "sim/weather/aircraft/relative_humidity_sealevel_percent",
    "sim/weather/aircraft/qnh_pas",
    "sim/weather/aircraft/temperatures_aloft_deg_c",
    "sim/weather/aircraft/cloud_type",
    "sim/weather/aircraft/cloud_coverage_percent",
    "sim/weather/aircraft/cloud_base_msl_m",
    "sim/weather/aircraft/cloud_tops_msl_m",
    "sim/weather/aircraft/barometer_current_pas",
    "sim/weather/aircraft/wind_now_direction_degt",
    "sim/weather/aircraft/wind_now_speed_msc",
    "sim/weather/aircraft/wind_now_x_msc",
    "sim/weather/aircraft/wind_now_y_msc",
    "sim/weather/aircraft/wind_now_z_msc",
    "sim/weather/aircraft/precipitation_on_aircraft_ratio",
    "sim/weather/aircraft/snow_on_aircraft_ratio",
    "sim/weather/aircraft/hail_on_aircraft_ratio",
    "sim/weather/aircraft/thermal_rate_ms",
    "sim/weather/aircraft/wave_amplitude",
    "sim/weather/aircraft/wave_length",
    "sim/weather/aircraft/wave_speed",
    "sim/weather/aircraft/wave_dir",
    "sim/weather/aircraft/gravity_mss",
    "sim/weather/aircraft/speed_sound_ms",
    "sim/weather/aircraft/temperature_ambient_deg_c",
    "sim/weather/aircraft/temperature_leadingedge_deg_c",
    "sim/weather/region/visibility_reported_sm",
    "sim/weather/region/sealevel_pressure_pas",
    "sim/weather/region/sealevel_temperature_c",
    "sim/weather/region/qnh_base_elevation",
    "sim/weather/region/qnh_pas",
    "sim/weather/region/rain_percent",
    "sim/weather/region/change_mode",
    "sim/weather/region/weather_source",
    "sim/weather/region/update_immediately",
    "sim/weather/region/atmosphere_alt_levels_m",
    "sim/weather/region/wind_altitude_msl_m",
    "sim/weather/region/wind_speed_msc",
    "sim/weather/region/wind_direction_degt",
    "sim/weather/region/shear_speed_msc",
    "sim/weather/region/shear_direction_degt",
    "sim/weather/region/turbulence",
    "sim/weather/region/dewpoint_deg_c",
    "sim/weather/region/temperature_altitude_msl_m",
    "sim/weather/region/temperatures_aloft_deg_c",
    "sim/weather/region/cloud_type",
    "sim/weather/region/cloud_coverage_percent",
    "sim/weather/region/cloud_base_msl_m",
    "sim/weather/region/cloud_tops_msl_m",
    "sim/weather/region/tropo_temp_c",
    "sim/weather/region/tropo_alt_m",
    "sim/weather/region/thermal_rate_ms",
    "sim/weather/region/wave_amplitude",
    "sim/weather/region/wave_length",
    "sim/weather/region/wave_speed",
    "sim/weather/region/wave_dir",
    "sim/weather/region/runway_friction",
    "sim/weather/region/variability_pct",
    "sim/weather/region/weather_preset",
    "sim/weather/view/rain_ratio",
    "sim/weather/view/snow_ratio",
    "sim/weather/view/hail_ratio",
    "sim/weather/view/urban_ratio",
    "sim/weather/view/wind_speed_msc",
    "sim/weather/view/wind_relative_heading_deg",
    "sim/weather/view/wind_relative_pitch_deg",
    "sim/weather/view/wind_base_speed_kts",
    "sim/weather/view/wind_gust_kts",
    "sim/weather/view/wind_shear_deg",
    "sim/weather/view/temperature_C",
]

WEATHER = {}
for d in WEATHER_DATAREFS:
    print(d)
    WEATHER[d] = get_dataref_value(d)

print(json.dumps(WEATHER, indent=2))

with open("weather.json", "w") as fp:
    json.dump(WEATHER, fp, indent=4)
