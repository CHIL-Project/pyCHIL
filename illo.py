"""CHIL: Cartographic Helper for Intrepid Land-explorers, Illo! Illo!

    CHIL is a simple tool written to help boy scouts in their adventures.
    Chil is a brahminy kite, a character in "The Jungle Book" by R. Kipling.
    He is the messenger of the jungle, he knows all the places and can observe
    everything from above ... so who better than he can help orienting?
    Are you in cartographic trouble? Just call Chil with his master word...
    Illo! Illo!

"""
import os
import sys
import logging
from numpy import mean
from typing import List, Tuple
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from geopy.distance import geodesic
from geopy.point import Point
from map import Map


def get_bbox(reference_point_latitude, reference_point_longitude, lat_distance_top=None, long_distance_dx=None,
             lat_distance_bot=None, long_distance_sx=None, radius=None) -> Tuple[Point, Point]:
    if radius and not lat_distance_top and not long_distance_dx and not lat_distance_bot and not long_distance_sx:
        lat_distance_top = long_distance_dx = lat_distance_bot = long_distance_sx = radius
    elif not radius and lat_distance_top and long_distance_dx and lat_distance_bot and long_distance_sx:
        pass
    else:
        raise ValueError("Radius or distances")

    reference_point = Point(reference_point_latitude, reference_point_longitude)
    geodesic_obj = geodesic()
    point0 = geodesic_obj.destination(reference_point, 0, lat_distance_top)
    point90 = geodesic_obj.destination(reference_point, 90, long_distance_dx)
    point180 = geodesic_obj.destination(reference_point, 180, lat_distance_bot)
    point270 = geodesic_obj.destination(reference_point, 270, long_distance_sx)
    bottom_left_point = Point(round(point180.latitude, 6), round(point270.longitude, 6))
    top_right_point = Point(round(point0.latitude, 6), round(point90.longitude, 6))
    return bottom_left_point, top_right_point


def get_central_point(points_list: List[Point]):
    # noinspection PyTypeChecker
    return Point(mean([c.latitude for c in points_list]), mean([c.longitude for c in points_list]))


script_folder = os.path.dirname(__file__)
# project_folder=os.path.dirname(script_folder)
path = script_folder + '/output/'

# noinspection PyTypeChecker
argparse_obj = ArgumentParser(prog='illo.py', formatter_class=RawDescriptionHelpFormatter, description=__doc__)

argparse_obj.add_argument('--resolution', default=200, help='DPI Resolution for the Map (default: 400 dpi)')
argparse_obj.add_argument('--scale', default=25000, help='Scale of the Map (default: 25000)')
argparse_obj.add_argument('--center_lat', required=True, help='Latitude of the central point of the map')
argparse_obj.add_argument('--center_long', required=True, help='Longitude of the central point of the map')
argparse_obj.add_argument('--cm_height', default=60, help='Desired height ( in cm ) for the Map')
argparse_obj.add_argument('--cm_width', default=60, help='Desired width ( in cm ) for the Map')
argparse_obj.add_argument('--title', default='', help='Title for the Map')
argparse_obj.add_argument('--filename', default='Map', help='Name for the output file')
extensions = ['png']
argparse_obj.add_argument('--extension', default='png', choices=extensions, help='Extension for the output file (png)')
argparse_obj.add_argument('--folder', default=path, help='Folder in which the Map will be saved')
levels = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
argparse_obj.add_argument('--log-level', default='ERROR', choices=levels)

if len(sys.argv) == 1:
    argparse_obj.print_help()
    sys.exit(0)
args = argparse_obj.parse_args()


logging.basicConfig(level=args.log_level, format='%(levelname)s %(name)s.%(funcName)s | %(message)8s')
log = logging.getLogger(__name__)

km_height = args.cm_height * args.scale / 100000
km_width = args.cm_width * args.scale / 100000
bl_point, tr_point = get_bbox(args.center_lat, args.center_long,
                              km_height / 2, km_width / 2, km_height / 2, km_width / 2)

print(f'Chil have heard you shouting the Master Word, and now he is flying over that area to memorize it!')
print(f'Wait there! ...\n')
map_obj = Map(bl_point, tr_point, args.resolution, args.scale, lat_extent_km=km_height, long_extent_km=km_width)
map_obj.set_blocks()
print('These are the information about the map that Chil is processing\
      \n_______________________________________________________________')
print(f'{map_obj}')
print(f'---------------------------------------------------------------\n')
map_obj.check_blocks_consistency()
map_obj.build_map(args.folder, args.filename, args.extension)
map_obj.print_rulers(args.folder, args.filename + "_rulers", args.extension)

print("All done! Good Hunting!")
