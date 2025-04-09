# Creates KML 3D flight path for visualisation in Google Earth or alike
from typing import List, Tuple

import simplekml

from cockpitdecks import __version__

KML_EXPORT = "1.0.0"


def toKML(path: List[Tuple[float, float, float]], name: str = "Flight Path", desc: str = "Flight path", airport: dict = {}) -> str:
    kml = simplekml.Kml(open=1, name="Emitpy Flight Path", description=f"Emitpy Flight Path (rel. {__version__}, KML export {KML_EXPORT})")
    ls = kml.newlinestring(name=name, description=desc)
    ls.coords = path
    ls.altitudemode = simplekml.AltitudeMode.relativetoground
    ls.extrude = 1
    ls.style.linestyle.color = simplekml.Color.yellow
    ls.style.linestyle.width = 4
    ls.style.polystyle.color = "80ffff00"  # a,b,g,r

    # if len(airport) > 0:
    #     ls.lookat.gxaltitudemode = simplekml.GxAltitudeMode.relativetoseafloor
    #     ls.lookat.latitude = airport.get("lat")
    #     ls.lookat.longitude = airport.get("lon")
    #     ls.lookat.range = 70000
    #     ls.lookat.heading = 0
    #     ls.lookat.tilt = 70

    return kml.kml(format=True)


# Possible and easy to animate with TimeStamp added to each segment.
