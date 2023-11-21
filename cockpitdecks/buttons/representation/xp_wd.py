# ###########################
# XP Weather datarefs grouped by categories, or layers.
#
# ######################################################
# REGION DATAREFS
#
#
TIME_DATAREFS = [
    "sim/cockpit2/clock_timer/local_time_hours"
    "sim/cockpit2/clock_timer/local_time_minutes"
    "sim/cockpit2/clock_timer/zulu_time_hours"
    "sim/cockpit2/clock_timer/zulu_time_minutes"
    "sim/cockpit2/clock_timer/current_day"
    "sim/time/local_date_days"
]

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
    # "sim/weather/region/wave_amplitude",
    # "sim/weather/region/wave_dir",
    # "sim/weather/region/wave_length",
    # "sim/weather/region/wave_speed",
    "sim/weather/region/weather_source",
]

REAL_WEATHER_REGION_CLOUDS_DATAREFS = [
    "sim/weather/region/cloud_base_msl_m",
    "sim/weather/region/cloud_coverage_percent",
    "sim/weather/region/cloud_tops_msl_m",
    "sim/weather/region/cloud_type",
]

REAL_WEATHER_REGION_WINDS_DATAREFS = [
    "sim/weather/region/atmosphere_alt_levels_m",
    "sim/weather/region/dewpoint_deg_c",
    "sim/weather/region/temperatures_aloft_deg_c",
    "sim/weather/region/temperature_altitude_msl_m",
    "sim/weather/region/wind_altitude_msl_m",
    "sim/weather/region/wind_direction_degt",
    "sim/weather/region/wind_speed_msc",
    "sim/weather/region/turbulence",
    "sim/weather/region/shear_direction_degt",
    "sim/weather/region/shear_speed_msc",
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

DISPLAY_DATAREFS_REGION = {
    "press": "sim/weather/region/sealevel_pressure_pas",
    "temp": "sim/weather/region/sealevel_temperature_c",
    "dewp": "sim/weather/region/dewpoint_deg_c",
    "vis": "sim/weather/region/visibility_reported_sm",
    "wind_dir": "sim/weather/region/wind_direction_degt",
    "wind_speed": "sim/weather/region/wind_speed_msc",
}


# ######################################################
# AIRCRAFT DATAREFS
#
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
    # "sim/weather/aircraft/wave_amplitude",
    # "sim/weather/aircraft/wave_dir",
    # "sim/weather/aircraft/wave_length",
    # "sim/weather/aircraft/wave_speed",
    "sim/weather/aircraft/wind_now_x_msc",
    "sim/weather/aircraft/wind_now_y_msc",
    "sim/weather/aircraft/wind_now_z_msc",
    "sim/weather/aircraft/wind_speed_msc",
]

REAL_WEATHER_AIRCRAFT_CLOUDS_DATAREFS = [
    "sim/weather/aircraft/cloud_base_msl_m",
    "sim/weather/aircraft/cloud_coverage_percent",
    "sim/weather/aircraft/cloud_tops_msl_m",
    "sim/weather/aircraft/cloud_type",
]

REAL_WEATHER_AIRCRAFT_WINDS_DATAREFS = [
    "sim/weather/aircraft/dewpoint_deg_c",
    "sim/weather/aircraft/shear_direction_degt",
    "sim/weather/aircraft/shear_speed_kts",
    "sim/weather/aircraft/temperatures_aloft_deg_c",
    "sim/weather/aircraft/turbulence",
    "sim/weather/aircraft/wind_altitude_msl_m",
    "sim/weather/aircraft/wind_direction_degt",
    "sim/weather/aircraft/wind_speed_kts",
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

DISPLAY_DATAREFS_AIRCRAFT = {
    "press": "sim/weather/aircraft/qnh_pas",
    "temp": "sim/weather/aircraft/temperature_ambient_deg_c",
    "dewp": "sim/weather/aircraft/dewpoint_deg_c",
    "vis": "sim/weather/aircraft/visibility_reported_sm",
    "wind_dir": "sim/weather/aircraft/wind_direction_degt",
    "wind_speed": "sim/weather/aircraft/wind_speed_msc",
}
