# Internal: Round a few rapidly changing datarefs
DATAREF_ROUND = {
    "sim/cockpit/autopilot/heading_mag": 2,
    "sim/flightmodel/position/latitude": 8,    # used in Weather button, 3 or 4 decimals sufficient...
    "sim/flightmodel/position/longitude": 8,
    "AirbusFBW/BatVolts[0]": 1,
    "AirbusFBW/BatVolts[1]": 1,
    "AirbusFBW/OHPLightsATA34[6]": 3,
    "AirbusFBW/OHPLightsATA34[8]": 3,
    "AirbusFBW/OHPLightsATA34[10]": 3,
    "AirbusFBW/OHPLightsATA30[0]": 3,
    "AirbusFBW/OHPLightsATA30[1]": 3,
    "AirbusFBW/OHPLightsATA30[2]": 3,
    "AirbusFBW/OHPLightsATA30[3]": 3,
    "AirbusFBW/OHPLightsATA30[4]": 3,
    "AirbusFBW/OHPLightsATA30[5]": 3,
    "AirbusFBW/OHPLightsATA30[10]": 3,
    "AirbusFBW/OHPLightsATA30[11]": 3,
    "AirbusFBW/OHPLightsATA21[13]": 3,   # cabin pressure ditching
    "dataref": 0
}

# THese datarefs don't need to be refreshed as often (normal is 2 per second)
DATAREF_SLOW = {
    "sim/flightmodel/position/latitude": 1,
    "sim/flightmodel/position/longitude": 1,
    "dataref": 0
}
