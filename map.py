from sys import version_info as python_version, platform
from geopy.distance import distance, geodesic
from geopy.point import Point
from typing import Tuple, List
from block import Block
from munch import Munch
from time import perf_counter
from PIL import Image, ImageDraw
from pathlib import Path
from math import ceil, floor
import aiohttp
import asyncio
import utils
import logging

log = logging.getLogger(__name__)


class MapException(Exception):
    pass


class Map:
    """A class used to represent a Topographic Map

    Attributes:
        geodesic_obj (geopy.distance.geodesic): Geopy object used as base to calculate distances.

        system (): Geodetic System
        scale (int):
        bl_point (geopy.point.Point): Bottom left point of the bounding frame.
        tl_point (geopy.point.Point): Top left point of the bounding frame.
        tr_point (geopy.point.Point): Top right point of the bounding frame.
        br_point (geopy.point.Point): Bottom right point of the bounding frame.

        image (PIL.Image.Image): Object representing the image containing the map
        resolution (int): Pixels per inch for the image containing the map
        width (int): Width of the frame in pixels.
        height (int): Height of the frame in pixels.
        title (str): Title to put on the output file

        blocks (Block): 2D Array of Block objects whose composition represents a Map
        """

    def __init__(self, bl_point: Point, tr_point: Point, resolution: int, scale: int,
                 frame_height_cm: float = None, frame_width_cm: float = None,
                 long_extent_km: float = None, lat_extent_km: float = None,
                 title: str = None, system='WGS84'):
        self.geodesic_obj = geodesic()
        self.bl_point = bl_point
        self.tr_point = tr_point
        self.tl_point = Point(tr_point.latitude, bl_point.longitude)
        self.br_point = Point(bl_point.latitude, tr_point.longitude)
        self.resolution = resolution
        self.scale = scale
        self.blocks = []
        self.width = 0
        self.height = 0
        self.title = title
        self.system = system
        self.image = None
        if frame_height_cm and frame_height_cm:
            self.frame_height_cm = frame_height_cm
            self.frame_width_cm = frame_width_cm
            self.lat_extent_km = frame_width_cm * scale / 100000
            self.long_extent_km = frame_height_cm * scale / 100000
        elif long_extent_km and lat_extent_km:
            self.lat_extent_km = lat_extent_km
            self.long_extent_km = long_extent_km
            self.frame_height_cm = 100000 * long_extent_km / scale
            self.frame_width_cm = 100000 * lat_extent_km / scale
        else:
            self.lat_extent_km = distance(self.br_point, self.tr_point).km
            self.long_extent_km = distance(bl_point, self.br_point).km
            self.frame_height_cm = 100000 * self.long_extent_km / scale
            self.frame_width_cm = 100000 * self.lat_extent_km / scale

    def __str__(self):
        return "Title   : " + str(self.title) + \
               "\nGeodetic System : " + str(self.system) + \
               "\nScale : " + str(self.scale) + \
               "\nResolution : " + str(self.resolution) + \
               "\nBbox Bottom Left Point : " + self.bl_point.format(deg_char='°', min_char='\'', sec_char='"') + \
               "\nBbox Top Left Point    : " + self.tl_point.format(deg_char='°', min_char='\'', sec_char='"') + \
               "\nBbox Top Right Point   : " + self.tr_point.format(deg_char='°', min_char='\'', sec_char='"') + \
               "\nBbox Bottom Right Point: " + self.br_point.format(deg_char='°', min_char='\'', sec_char='"') + \
               "\nGeodesic frame height: " + str(round(distance(self.tl_point, self.bl_point).km, 3)) + ' km'\
               ', Requested: ' + str(self.lat_extent_km) + ' km'\
               "\nGeodesic frame width: " + str(round(distance(self.br_point, self.bl_point).km, 3)) + ' km'\
               ', Requested: ' + str(self.long_extent_km) + ' km'\
               "\nPixels frame height x width: " + str(self.height) + "x" + str(self.width) + \
               "\nPixels per centimeter: " + str(floor(self.resolution / 2.54))

    def get_max_block(self) -> Munch:
        """
        Calculate the max usable geodetic dimensions for fetching from the service.

        The service used for fetching, located at http://wms.pcn.minambiente.it/
        only allows requests for images of at most 2000 pixels per side,
        for this reason this method calculate the 2 max geodetic dimensions
        (latitude and longitude) for that block with 2000 pixels per side
         and specified scale and resolution.
         NOTE: The geodetic distance calculation must be done starting from
         the Bottom left point, because of the geodesic model.

        Returns:
          A Munch object containing the 2 max geodetic dimension usable for fetching

        """
        max_block = Munch()

        inches = 2048 / self.resolution  # max_pixels per block / pixels in 1 inch
        centimeters = inches * 2.54
        kilometers = centimeters * self.scale / 100000

        max_tl_point = self.geodesic_obj.destination(self.bl_point, 0, kilometers)
        if max_tl_point.latitude <= self.tl_point.latitude:
            max_block.latitude = max_tl_point.latitude - self.bl_point.latitude
        else:
            max_block.latitude = self.tl_point.latitude - self.bl_point.latitude

        max_br_point = self.geodesic_obj.destination(self.bl_point, 90, kilometers)
        if max_br_point.longitude <= self.br_point.longitude:
            max_block.longitude = max_br_point.longitude - self.bl_point.longitude
        else:
            max_block.longitude = self.br_point.longitude - self.bl_point.longitude

        return max_block

    def get_first_block(self, lat: float, long: float) -> Block:
        bl_block_point = self.bl_point
        tr_block_point = Point(self.bl_point.latitude + lat, self.bl_point.longitude + long)
        return Block(bl_block_point, tr_block_point, self.resolution, self.scale, 0, 0)

    def set_blocks(self) -> None:
        """
        Procedure to populate the self.blocks list

        Returns:
          None

        """
        max_block = self.get_max_block()
        lat = max_block.latitude
        long = max_block.longitude
        self.blocks = []
        self.blocks.append([])
        self.blocks[0].append(self.get_first_block(lat, long))
        log.info(f'Max Block with lat: {utils.format_coord(max_block.latitude)} ~ {max_block.latitude}\n'
                 f'{" " * 33}and long: {utils.format_coord(max_block.longitude)} ~ {max_block.longitude}')
        log.info(f'Created {self.blocks[0][0]}')

        i = 0
        column_first_block = self.blocks[0][0]
        self.width = column_first_block.width
        self.height = column_first_block.height
        block_starting_longitude = column_first_block.bl_point.longitude
        block_ending_longitude = block_starting_longitude + long
        while block_starting_longitude < self.tr_point.longitude:
            log.info(
                f'Cycle {i}; \
                We have {utils.format_coord(block_starting_longitude - self.tr_point.longitude)} left in longitude')
            log.info(f'Cycle {i} stats: H {utils.format_coord(block_starting_longitude)}, '
                     f'K {utils.format_coord(block_ending_longitude)}, '
                     f'Limit: {utils.format_coord(self.tr_point.longitude)} ')

            if i != 0:
                '''Enter here if the program is not in the first loop '''
                self.blocks.append([])
                if block_ending_longitude <= self.tr_point.longitude:
                    '''Enter here if the first block of the now-to-be-proceeded-column is a complete block '''
                    self.blocks[i].append(column_first_block.set_eastern_block(long))
                    log.info(f'Block ({i}), COMPLETE')

                else:
                    self.blocks[i].append(
                        column_first_block.set_eastern_block(
                            self.tr_point.longitude - block_starting_longitude, last=True))
                    log.info(f'Block ({i} 0), NotComplete, {utils.format_coord(self.tr_point.longitude)}')

                column_first_block = column_first_block.eastern_block
                self.width += column_first_block.width

            column_block = column_first_block
            next_block_starting_latitude = column_first_block.tr_point.latitude
            next_block_ending_latitude = next_block_starting_latitude + lat
            while next_block_starting_latitude < self.tr_point.latitude:

                if next_block_ending_latitude <= self.tr_point.latitude:
                    '''Enter here if next block is a complete block (next_block.latitude == max latitude )'''
                    self.blocks[i].append(column_block.set_northern_block(lat))
                else:
                    '''Enter here if next block is not a complete block'''
                    self.blocks[i].append(column_block.set_northern_block(
                        self.tr_point.latitude - next_block_starting_latitude, last=True))

                column_block = column_block.northern_block
                if i == 0:
                    self.height += column_block.height

                next_block_starting_latitude = next_block_ending_latitude
                next_block_ending_latitude += lat

            block_starting_longitude = block_ending_longitude
            block_ending_longitude += long
            i = i + 1

        self.fetch_blocks_concurrently()

    def fetch_blocks_concurrently(self) -> None:
        """
        Main asyncio procedure

        [...]

        Returns:
          None

        """
        time = perf_counter()

        if python_version[0] == 3 and python_version[1] >= 8 and platform.startswith('win'):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(self.gather_fetch_workers())
        log.info(f'Asynchronous Fetching finished in {perf_counter() - time}')

    async def gather_fetch_workers(self) -> None:
        """
        Procedure to manage aiohttp session and to launch block.async_fetch procedures

        [...]

        Returns:
          None

        """
        async with aiohttp.ClientSession() as session:
            tasks = []
            for i in self.blocks:
                for j in i:
                    tasks.append(j.async_fetch(session))
            await asyncio.gather(*tasks)

    def check_blocks_consistency(self) -> None:
        j = 0
        for i in self.blocks:
            for j in i:
                continue

        if j.tr_point.longitude != self.tr_point.longitude or \
                j.tr_point.latitude != self.tr_point.latitude:
            raise MapException(f'Map is not well built')

    def build_map(self, folder: str, title='Map', ext='png') -> None:
        """
        Print the Map image combining pieces in self.blocks.

        Args:
          self
          folder (str): Folder to save the Map
          title (str): Title for the image file
          ext (str): Output format for the image file

        Returns:
          None

        """
        with Image.new('RGB', (self.width, self.height)) as new_im:
            x = 0
            for column in self.blocks:
                y = 0
                for block in reversed(column):
                    log.info(f'{block} pasted in png-position ({x},{y})')
                    new_im.paste(block.image, (x, y))
                    y += block.height
                x += block.width

            print("Saving ...")
            self.image = new_im
            try:
                new_im.save("{}/{}.{}".format(folder, title, ext))
            except FileNotFoundError:
                Path(folder).mkdir(parents=True, exist_ok=True)
                new_im.save("{}/{}.{}".format(folder, title, ext))

            print(f'Map saved as {title}.{ext} in {folder if not "." else "the script folder"}')

    def print_rulers(self, folder, title='Map_rulers', ext='png') -> None:
        """
        Print a second image with 5mm-width topographic rulers.

        Args:
          self
          folder (str): Folder to save the Map
          title (str): Title for the image file
          ext (str): Output format for the image file

        Returns:
          None

        """
        line_width = round(0.05 / 2.54 * self.resolution)
        ruler_width = line_width * 10
        imagerlr_width = self.width + ruler_width
        imagerlr_height = self.height + ruler_width
        log.info(f'Adding rules to image')
        with Image.new('RGB', (imagerlr_width, imagerlr_height), color="#ffffff") as imagerlr:

            imagerlr.paste(self.image, (ruler_width, 0))
            draw_obj = ImageDraw.Draw(imagerlr)
            draw_obj.rectangle([(0, 0),
                                (ruler_width - 1, self.height - 1)], width=line_width, outline="#000000")
            draw_obj.rectangle([(ruler_width, self.height),
                                (imagerlr_width - 1, imagerlr_height - 1)], width=line_width, outline="#000000")

            height_list, width_list = self.get_interval_list()

            flip_flop = i = j = 0
            for k in height_list:
                if flip_flop:
                    draw_obj.rectangle([(line_width, i),
                                        (ruler_width - line_width, j + k - 1)], outline="#000000", fill="#000000")
                flip_flop ^= 1
                j += k
                i = j

            flip_flop = 0
            i = j = ruler_width
            for k in width_list:
                if flip_flop:
                    draw_obj.rectangle([(i, self.height + line_width),
                                        (j + k - 1, imagerlr_height - line_width)], outline="#000000", fill="#000000")
                flip_flop ^= 1
                j += k
                i = j

            print("Saving ...")
            try:
                imagerlr.save("{}/{}.{}".format(folder, title, ext))
            except FileNotFoundError:
                Path(folder).mkdir(parents=True, exist_ok=True)
                imagerlr.save("{}/{}.{}".format(folder, title, ext))

        print(f'Map saved as {title}.{ext} in {folder if not "." else "the script folder"}')

    def get_interval_list(self) -> Tuple[List[float], List[float]]:
        """
        Calculate 2 Lists of floats representing the topographic rulers.

        Function used by the print_rulers procedure to define the intervals
        to be represented in the rulers.
        The measurement of these intervals is first calculated in seconds
        and then in pixels by comparing the first with the dimensions of the map.

        Args:
          self

        Returns:
          2 Lists of floats

        Raises:
          None

        """
        latitude_list = []
        longitude_list = []
        bl_latitude = utils.to_sexagesimal(self.bl_point.latitude)
        tl_latitude = utils.to_sexagesimal(self.tl_point.latitude)
        bl_longitude = utils.to_sexagesimal(self.bl_point.longitude)
        br_longitude = utils.to_sexagesimal(self.br_point.longitude)

        latitude_list.append(bl_latitude.sec) if bl_latitude.sec != 0 else latitude_list.append(60)
        longitude_list.append(bl_longitude.sec) if bl_longitude.sec != 0 else longitude_list.append(60)

        for i in range(bl_latitude.min + 1, tl_latitude.min): latitude_list.append(60)
        for i in range(bl_longitude.min + 1, br_longitude.min): longitude_list.append(60)

        latitude_list.append(tl_latitude.sec) if tl_latitude.sec != 0 else latitude_list.append(0)
        longitude_list.append(br_longitude.sec) if br_longitude.sec != 0 else longitude_list.append(0)

        height_list = []
        width_list = []
        for i in latitude_list:
            height_list.append(round(self.height * i / sum(latitude_list)))
        for i in longitude_list:
            width_list.append(round(self.width * i / sum(longitude_list)))

        return height_list, width_list

    # TODO: Del
    def __deprecated_set_blocks(self):
        max_block = self.get_max_block()
        lat = max_block.latitude
        long = max_block.longitude
        self.blocks = []
        self.blocks.append([])
        self.blocks[0].append(self.get_first_block(lat, long))
        log.info(f'Max Block with lat: {utils.format_coord(max_block.latitude)} ~ {max_block.latitude}\n'
                 f'{" " * 33}and long: {utils.format_coord(max_block.longitude)} ~ {max_block.longitude}')
        log.info(f'Created {self.blocks[0][0]}')

        i = 0
        next_block = current_block = self.blocks[0][0]
        self.width = current_block.width
        self.height = current_block.height
        h = current_block.tr_point.longitude
        k = current_block.tr_point.longitude + long
        while h < self.tr_point.longitude + long:
            log.info(f'Cycle {i}; We have {utils.format_coord(h - self.tr_point.longitude)} left in longitude')
            log.info(f'Cycle {i} stats: H {utils.format_coord(h)}, '
                     f'K {utils.format_coord(k)}, '
                     f'Limit: {utils.format_coord(self.tr_point.longitude)} ')

            if h != self.blocks[0][0].tr_point.longitude:  # TODO simplify if stat with i variable
                '''Enter here if current_block is not the first block (not first loop) '''

                self.blocks.append([])
                current_block = next_block
                if k <= self.tr_point.longitude:
                    '''Enter here if next block is a complete block (next_block.longitude == max longitude )'''
                    self.blocks[i].append(current_block.set_eastern_block(long))
                    next_block = current_block.eastern_block
                    current_block = next_block
                    # current_block.sync_fetch()
                    log.info(f'Block ({i}), COMPLETE')
                    h = k
                    k = k + long
                else:
                    self.blocks[i].append(
                        current_block.set_eastern_block((self.tr_point.longitude - h + long) % long, last=True))
                    next_block = current_block.eastern_block
                    current_block = next_block
                    # current_block.sync_fetch()
                    log.info(f'Block ({i} 0), NotComplete, {utils.format_coord(self.tr_point.longitude)}')
                    h = self.tr_point.longitude + long

                self.width += next_block.width

                if h == self.blocks[0][0].tr_point.longitude + long:
                    self.blocks[0][0].eastern_block = current_block
            else:
                '''Enter here if current_block is the first block (first loop) '''
                h = k
                k = k + long

            m = current_block.tr_point.latitude
            n = current_block.tr_point.latitude + lat
            while m < self.tr_point.latitude:

                if n <= self.tr_point.latitude:
                    '''Enter here if next block is a complete block (next_block.latitude == max latitude )'''
                    self.blocks[i].append(current_block.set_northern_block(lat))
                    m = n
                    n = n + lat
                else:
                    '''Enter here if next block is not a complete block'''
                    self.blocks[i].append(current_block.set_northern_block(self.tr_point.latitude - m, last=True))
                    m = self.tr_point.latitude

                current_block = current_block.northern_block
                # current_block.sync_fetch()
                if h == self.blocks[0][0].tr_point.longitude + long:
                    '''Enter here if we are processing the first column; "+ long" is due to "h = k" in prev lines '''
                    self.height += current_block.height
                    # if m - self.blocks[0][0].tr_point.latitude < lat or m == self.blocks[0][0].tr_point.latitude + lat
                    if m <= self.blocks[0][0].tr_point.latitude + lat:
                        '''Enter here if we are processing the second (complete or not) block in the column'''
                        self.blocks[0][0].northern_block = current_block
            i = i + 1

        self.fetch_blocks_concurrently()

    def __deprecated_print_rulers(self, folder, title='Map_rulers', ext='png'):

        cm_latitude_interval = round(distance((33, 22), (33.01666667, 22)).km * 100 / 25, 4)  # 7.38
        cm_longitude_interval = round(distance((33, 22), (33, 22.01666667)).km * 100 / 25, 4)  # 5.42
        log.info(f'{cm_latitude_interval} {cm_longitude_interval}')
        dpcm = self.resolution * 2.54

        interval_dim = [floor(cm_latitude_interval * dpcm), floor(cm_longitude_interval * dpcm)]
        log.info(f'Pixel Dimension of Latitude and Longitude Intervals: {interval_dim[0]}, {interval_dim[1]}')

        tl_lat = utils.to_sexagesimal(self.tl_point.latitude)
        bl_lat = utils.to_sexagesimal(self.bl_point.latitude)
        bl_long = utils.to_sexagesimal(self.bl_point.longitude)
        br_long = utils.to_sexagesimal(self.br_point.longitude)

        latitude_offset1 = ceil(tl_lat.sec / 60 * interval_dim[0])
        latitude_offset2 = floor((60 - bl_lat.sec) / 60 * interval_dim[0])
        num_of_latitude_intervals = (tl_lat.deg * 60 + tl_lat.min) - (bl_lat.deg * 60 + bl_lat.min) - (bl_lat.sec and 1)
        log.info(f'Num of pixels of the top most (incomplete) interval: {latitude_offset1}')
        log.info(f'Num of pixels of the bottom most (incomplete) interval: {latitude_offset2}')
        log.info(f'Num of Complete Latitude Intervals: {num_of_latitude_intervals}')
        longitude_offset1 = floor((60 - bl_long.sec) / 60 * interval_dim[1])
        longitude_offset2 = ceil(br_long.sec / 60 * interval_dim[1])
        num_of_longitude_intervals = (br_long.deg * 60 + br_long.min) - (bl_long.deg * 60 + bl_long.min) - (
                bl_long.sec and 1)
        log.info(f'Num of pixels of the left most (incomplete) interval: {longitude_offset1}')
        log.info(f'Num of pixels of the right most (incomplete) interval: {longitude_offset2}')
        log.info(f'Num of Complete Longitude Intervals: {num_of_longitude_intervals}')

        lat_error = self.height - latitude_offset1 - latitude_offset2 - num_of_latitude_intervals * interval_dim[0]
        long_error = self.width - longitude_offset1 - longitude_offset2 - num_of_longitude_intervals * interval_dim[
            1]
        log.info(f'Pixel Error in Latitude: {lat_error}')
        log.info(f'Pixel Error in Latitude: {long_error}')
        if (lat_error % (num_of_latitude_intervals + 1) > dpcm * 0.4 or long_error % (
                num_of_longitude_intervals + 1) > dpcm * 0.4):
            log.warning(f'total pixel error is greater than 4 mm')

        lat_error = [int(lat_error / (num_of_latitude_intervals + 2)), lat_error % (num_of_latitude_intervals + 2)]
        lat_pixel_adj = []
        for i in range(0, num_of_latitude_intervals + 1):
            lat_pixel_adj.append(lat_error[0] + (1 and lat_error[1]))
            lat_error[1] -= (1 and lat_error[1])

        long_error = [int(long_error / (num_of_longitude_intervals + 2)), long_error % (num_of_longitude_intervals + 2)]
        long_pixel_adj = []
        for i in range(0, num_of_longitude_intervals + 1):
            long_pixel_adj.append(long_error[0] + (1 and long_error[1]))
            long_error[1] -= (1 and long_error[1])

        latitude_intervals = []
        latitude_intervals.append(latitude_offset1 + lat_pixel_adj[0])
        for i in range(1, num_of_latitude_intervals + 1):
            latitude_intervals.append(interval_dim[0] + lat_pixel_adj[i])
        latitude_intervals.append(latitude_offset2 + lat_pixel_adj[num_of_latitude_intervals])

        longitude_intervals = []
        longitude_intervals.append(longitude_offset1 + long_pixel_adj[0])
        for i in range(1, num_of_longitude_intervals + 1):
            longitude_intervals.append(interval_dim[1] + long_pixel_adj[i])
        longitude_intervals.append(longitude_offset2 + long_pixel_adj[num_of_longitude_intervals])

        new_width = self.width + 133
        new_height = self.height + 133
        img = Image.new('RGB', (new_width, new_height), color="#ffffff")

        img.paste(self.image, (133, 0))
        draw = ImageDraw.Draw(img)
        draw.line((0, 0, 0, self.height), width=61, fill="#000000")
        draw.line((117, 0, 117, self.height), width=31, fill="#000000")
        j = 0
        flip_flop = 0
        for i in latitude_intervals:

            k = j + i - 1

            flip_flop = flip_flop != 1
            if flip_flop:
                draw.line((66, j, 66, k), width=72, fill="#000000")
            else:
                draw.line((66, j, 66, k), width=72, fill="#ffffff")

            j = k + 1

        draw.line((133, self.height + 15, new_width, self.height + 15), width=31, fill="#000000")
        draw.line((133, new_height - 15, new_width, new_height - 15), width=31, fill="#000000")

        j = 0
        flip_flop = 0
        for i in longitude_intervals:

            k = j + i - 1

            flip_flop = flip_flop != 1
            if flip_flop:
                draw.line((j + 133, new_height - 66, k + 133, new_height - 66), width=75, fill="#000000")
            else:
                draw.line((j + 133, new_height - 66, k + 133, new_height - 66), width=75, fill="#ffffff")

            j = k + 1

        draw.line((134, self.height, 134, new_width), width=3, fill="#000000")
        draw.line((new_width, self.height, new_width, new_height), width=3, fill="#000000")
        draw.line((0, 0, 132, 0), width=3, fill="#000000")
        draw.line((0, self.height - 1, 132, self.height - 1), width=3, fill="#000000")

        print("Saving...")
        img.save("{}/{}.{}".format(folder, title, ext))
        print(f'Map with rulers saved as {title}.{ext} in {folder if not "." else "the script folder"}')

    def __deprecated_set_first_block(self, lat, long):
        bl_block_point = self.bl_point
        tr_block_point = Point(self.bl_point.latitude + lat, self.bl_point.longitude + long)
        self.first_block = Block(bl_block_point, tr_block_point, self.resolution, self.scale, 0, 0)
        log.info(f'{self.first_block}')
