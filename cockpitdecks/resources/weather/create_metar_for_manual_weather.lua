-- Create Metar For Manual Weather
-- For use with Pilot2ATC
-- Make sure "SIM Weather" is selected in "Config" 
-- William R. Good 01-05-24

-- After selecting "Manually Enter Wether" then "Done"
-- Click on "Reload all Lua script files" so datarefs are re read.

-- After selecting "Download Real Weather" then "Done"
-- Click on "Reload all Lua script files" so datarefs are re read.
-- And this script will be disabled.


-- Only run this script if manual weather is set
-- What system is currently controlling the weather. 0 = Preset, 1 = Real Weather, 2 = Controlpad, 3 = Plugin.
dataref("weather_source","sim/weather/region/weather_source","readonly")
if weather_source == 0 then


if not SUPPORTS_FLOATING_WINDOWS then
    -- to make sure the script doesn't stop old FlyWithLua versions
    logMsg("imgui not supported by your FlyWithLua version")
    return
end


-- degrees	[0 - 360] The direction the wind is blowing from in degrees from true north clockwise.
wind_direction_degt = dataref_table("sim/weather/aircraft/wind_direction_degt")
-- >=	0. The wind speed in knots.
wind_speed_kts = dataref_table("sim/weather/aircraft/wind_speed_kts")
-- Gust speed in knots	
dataref("wind_gust_kts","sim/weather/view/wind_gust_kts","readonly")
-- >= 0. The reported visibility (e.g. what the METAR/weather window says).
dataref("visibility_reported_sm","sim/weather/aircraft/visibility_reported_sm","readonly")

-- CLR = 0  FEW = 0.125  SCT = 0.375  BKN = 0.75  OVC = 1
-- These numbers are only correct if "Manually Enter Weather" is selected.
-- If "Download Real Weather" is selected they are very different.
-- Not sure if at this time it is a bug or just the way it is.    
cloud_coverage = dataref_table("sim/weather/aircraft/cloud_coverage_percent")

-- meters	MSL >= 0. The base altitude for this cloud layer.
cloud_base_msl_m = dataref_table("sim/weather/aircraft/cloud_base_msl_m")

-- degreesC Temperature	and ISA temperature at pressure altitudes given in C
dataref("temperatures_aloft_deg_c","sim/weather/aircraft/temperatures_aloft_deg_c","readonly")

-- degreesC	The dew point at specified levels in the atmosphere.
dataref("dewpoint_deg_c","sim/weather/aircraft/dewpoint_deg_c","readonly")

-- pascals	Pressure at sea level, current planet
dataref("sealevel_pressure_pas","sim/weather/region/sealevel_pressure_pas","readonly")

-- True if VR is enabled, false if it is disabled
dataref("vr_enabled","sim/graphics/VR/enabled","readonly")

cmfmw_wnd = nil
cmfmw_vr_enabled_delayed = 0
cmfmw_vr_disabled_delayed = 0
loop_count = 0
first_time = 0
delay_start = 0

local airport_ICAO
local wrote_minute00 = 0
local wrote_minute30 = 0


function cmfmw_on_build(cmfmw_wnd, x, y)
	
	if imgui.Button("Create Metar", 150, 25) then
		create_metar()
	end

end


function create_metar_for_manual_weather(wnd)
    local _ = wnd -- Reference to window, which triggered the call.
    -- This function is called when the user closes the window. Drawing or calling imgui
    -- functions is not allowed in this function as the window is already destroyed.
end


function cmfmw_check_for_vr()
	if vr_enabled == 1 and cmfmw_vr_enabled_delayed == 1 then
		if cmfmw_wnd then
			float_wnd_destroy(cmfmw_wnd)
		end
		cmfmw_wnd = float_wnd_create(170, 50, 0, true)
		float_wnd_set_title(cmfmw_wnd, "Create Metar for VR")
		--                                                0x Alphia Red Green Blue
		imgui.PushStyleColor(imgui.constant.Col.WindowBg, 0xCC101112) -- Black like Background
		float_wnd_set_imgui_builder(cmfmw_wnd, "cmfmw_on_build")
		cmfmw_vr_disabled_delayed = 0
	end
	if vr_enabled == 1 and cmfmw_vr_enabled_delayed < 2 then
		cmfmw_vr_enabled_delayed = cmfmw_vr_enabled_delayed + 1	
	end
	
	if vr_enabled == 0 and cmfmw_vr_disabled_delayed == 1 then
		if cmfmw_wnd then
			float_wnd_destroy(cmfmw_wnd)
		end
		cmfmw_wnd = float_wnd_create(170, 50, 1, true)
		float_wnd_set_title(cmfmw_wnd, "Create Metar for 2d")
		float_wnd_set_position(cmfmw_wnd, 400, 350)
		--                                                0x Alphia Red Green Blue
		imgui.PushStyleColor(imgui.constant.Col.WindowBg, 0xCC101112) -- Black like Background
		float_wnd_set_imgui_builder(cmfmw_wnd, "cmfmw_on_build")
		cmfmw_vr_enabled_delayed = 0
	end
	if vr_enabled == 0 and cmfmw_vr_disabled_delayed < 2 then
		cmfmw_vr_disabled_delayed = cmfmw_vr_disabled_delayed + 1	
	end
end


function find_nearest_airport()
	-- find the ICAO name of the airport
    _, _, _, _, _, _, airport_ICAO, _ = XPLMGetNavAidInfo( XPLMFindNavAid( nil, nil, LATITUDE, LONGITUDE, nil, xplm_Nav_Airport) )
end


function create_metar()
	local d = os.date("!%Y/%m/%d %H:%M")
	local dd = os.date("!%d%H%M")
	local _year = os.date("!%Y")
	local _month = os.date("!%m")
	local _day = os.date("!%d")
	local _hour = os.date("!%H")
	local _minute = os.date("!%M")
	io.output(io.open("./Output/real weather/metar-" .. _year .. "-" .. _month .. "-" .. _day .. "-" .. _hour .. "-" .. _minute .. ".txt", "a"))
	io.write(d, "\n")
	find_nearest_airport()
	io.write(airport_ICAO, " ", dd, "Z ", string.format("%03.0f", wind_direction_degt[0]), string.format("%02.0f", wind_speed_kts[0]), "KT ")
	if visibility_reported_sm > 10 then
		visibility_reported_sm = 10
	end	
	io.write(visibility_reported_sm, "SM ")
	if cloud_coverage[0] < 0.05 then
		io.write("CLR ")
	elseif (cloud_coverage[0] > 0.05) and  (cloud_coverage[0] < 0.25) then
		io.write("FEW")
		local cloud_base_msl_f0 = cloud_base_msl_m[0] * .03281
		io.write(string.format("%03.0f", cloud_base_msl_f0))
	elseif (cloud_coverage[0] > 0.25) and (cloud_coverage[0] < 0.50) then
		io.write("SCT")
		local cloud_base_msl_f0 = cloud_base_msl_m[0] * .03281
		io.write(string.format("%03.0f", cloud_base_msl_f0))		
	elseif (cloud_coverage[0] > 0.50) and (cloud_coverage[0] < 0.90) then	
		io.write("BKN")
		local cloud_base_msl_f0 = cloud_base_msl_m[0] * .03281
		io.write(string.format("%03.0f", cloud_base_msl_f0))		
	elseif cloud_coverage[0] > 0.90 then
		io.write("OVC")
		local cloud_base_msl_f0 = cloud_base_msl_m[0] * .03281
		io.write(string.format("%03.0f", cloud_base_msl_f0))		
	end
	
	if (cloud_coverage[1] > 0.05) and  (cloud_coverage[1] < 0.25) then
		io.write(" FEW")
		local cloud_base_msl_f1 = cloud_base_msl_m[1] * .03281
		io.write(string.format("%03.0f", cloud_base_msl_f1))
	elseif (cloud_coverage[1] > 0.25) and (cloud_coverage[1] < 0.50) then
		io.write(" SCT")
		local cloud_base_msl_f1 = cloud_base_msl_m[1] * .03281
		io.write(string.format("%03.0f", cloud_base_msl_f1))		
	elseif (cloud_coverage[1] > 0.50) and (cloud_coverage[1] < 0.90) then	
		io.write(" BKN")
		local cloud_base_msl_f1 = cloud_base_msl_m[1] * .03281
		io.write(string.format("%03.0f", cloud_base_msl_f1))		
	elseif cloud_coverage[1] > 0.90 then
		io.write(" OVC")
		local cloud_base_msl_f1 = cloud_base_msl_m[1] * .03281
		io.write(string.format("%03.0f", cloud_base_msl_f1))		
	end
	
	if (cloud_coverage[2] > 0.05) and  (cloud_coverage[2] < 0.25) then
		io.write(" FEW")
		local cloud_base_msl_f2 = cloud_base_msl_m[2] * .03281
		io.write(string.format("%03.0f", cloud_base_msl_f2))
	elseif (cloud_coverage[2] > 0.25) and (cloud_coverage[2] < 0.50) then
		io.write(" SCT")
		local cloud_base_msl_f2 = cloud_base_msl_m[2] * .03281
		io.write(string.format("%03.0f", cloud_base_msl_f2))		
	elseif (cloud_coverage[2] > 0.50) and (cloud_coverage[2] < 0.90) then	
		io.write(" BKN")
		local cloud_base_msl_f2 = cloud_base_msl_m[2] * .03281
		io.write(string.format("%03.0f", cloud_base_msl_f2))		
	elseif cloud_coverage[2] > 0.90 then
		io.write(" OVC")
		local cloud_base_msl_f2 = cloud_base_msl_m[2] * .03281
		io.write(string.format("%03.0f", cloud_base_msl_f2))		
	end	
	

	io.write(" ")
	if temperatures_aloft_deg_c < 0 then
		io.write("M")
		temperatures_aloft_deg_c = temperatures_aloft_deg_c * -1
	end
	temperatures_aloft_deg_c = string.format("%02.0f", temperatures_aloft_deg_c)
	io.write(temperatures_aloft_deg_c)
	io.write("/")
	if dewpoint_deg_c < 0 then
		io.write("M")
		dewpoint_deg_c = dewpoint_deg_c * -1
	end
	dewpoint_deg_c = string.format("%02.0f", dewpoint_deg_c)
	io.write(dewpoint_deg_c)
	io.write(" A")
	local sealevel_pressure_inhg = sealevel_pressure_pas / 33.86
	io.write(string.format("%04.0f", sealevel_pressure_inhg))
	io.write(" \n")
	io.write("\n")
	io.close()

end

function every_thirty_minutes()
	local __minute = os.date("!%M")
	if __minute == "00" then
		if wrote_minute00 == 0 then
			create_metar()
			wrote_minute00 = 1
		end	
	end
	if __minute == "01" then
		wrote_minute00 = 0
	end
	if __minute == "30" then
		if wrote_minute30 == 0 then
			create_metar()
			wrote_minute30 = 1
		end	
	end
	if __minute == "31" then
		wrote_minute30 = 0
	end
end


function delay_start_first_time()
	if delay_start < 3 then
		delay_start = delay_start + 1
	end
	if delay_start == 2 then
		if first_time == 0 then
			create_metar()
			first_time = 1
		end
		delay_start = 3
	end
end


do_often("cmfmw_check_for_vr()")
do_sometimes("every_thirty_minutes()")
do_sometimes("delay_start_first_time()")


-- end of "if weather_source == 0 then"
end