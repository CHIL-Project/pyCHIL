"""Module with a shared collection of functions.
"""
from geopy import Point
from math import modf
from munch import Munch
import logging


log = logging.getLogger(__name__)


def format_point(point: Point) -> str:
    """Return a str representing a Point object.

    Args:
      point:
        Point obj to represent.

    Returns:
      A string representing the Point with ° for grades, ' for minutes and " for seconds.
        Latitude is written before Longitude.
        Example Output: 30°21'12", 10°21'22"

    """
    lat = to_sexagesimal(point.latitude)
    long = to_sexagesimal(point.longitude)
    return f'[{lat.deg}°{lat.min}\'{lat.sec}\", {long.deg}°{long.min}\'{long.sec}\"]'


def format_coord(dec_coord: float) -> str:
    """Return a str representing a coordinate of a Point.

    Args:
      dec_coord:
        Float

    Returns:
      A string representing the coordinate with ° for grades, ' for minutes and " for seconds.

    """
    coord = to_sexagesimal(dec_coord)
    return "{}{}{}".format((str(coord.deg)+'° ') if coord.deg != 0 else "",
                           (str(coord.min)+'\' ') if coord.min != 0 else "",
                           (str(coord.sec)+'"') if coord.sec != 0 else "")


def to_sexagesimal(dec_coord) -> Munch:
    """Convert a coordinate from decimal form to sexagesimal.

    Args:
      dec_coord:
        Float

    Returns:
      A Munch obj with 3 attributes, deg for degrees, min for minutes, sec for seconds.

    """
    coord = Munch()
    dec_part, int_part = modf(dec_coord)
    coord.deg = int(int_part)
    coord.min = abs(int(modf(dec_part * 60)[1]))
    coord.sec = abs(round(modf(dec_part * 60)[0] * 60, 2))
    return coord
