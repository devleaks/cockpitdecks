from .icons import icons as FA_ICONS  # Font Awesome Icons ${fa:arrow-up}
from .weathericons import WEATHER_ICONS  # Weather Icons ${wi:day-sunny}

DEFAULT_WEATHER_ICON = "wi_day_cloudy_high"


ICON_FONT = "fontawesome.otf"
WEATHER_ICON_FONT = "weathericons.otf"

FAR = "Font Awesome 6 Free-Regular-400.otf"
FAS = "Font Awesome 6 Free-Solid-900.otf"

# prefix: (font file, icon names)
ICON_FONTS = {
    "fa": (ICON_FONT, FA_ICONS),
    "far": (FAR, FA_ICONS),
    "fas": (FAS, FA_ICONS),
    "wi": (WEATHER_ICON_FONT, WEATHER_ICONS)
}
