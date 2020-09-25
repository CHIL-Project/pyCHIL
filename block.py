from geopy import Point
from geopy.distance import distance
from typing import Dict
from math import floor
from requests import get
from io import BytesIO
from PIL import Image
from urllib.parse import unquote
from PIL import UnidentifiedImageError
from aiohttp import ClientSession, ClientConnectorError
import sys
import utils
import logging

log = logging.getLogger(__name__)


class BlockException(Exception):
    pass


class Block:
    """A class representing a quadrilateral part of the Topographic Map.

    This subdivision of the topographic map is due to the used
    Web Map Service that only allows requests for images of at most 2000
    pixels per side.

    Attributes:
        scale (int):
        bl_point (geopy.point.Point): Bottom left point of the bounding frame.
        tr_point (geopy.point.Point): Top right point of the bounding frame.
        br_point (geopy.point.Point): Bottom right point of the bounding frame.

        image (PIL.Image.Image): Object representing the image containing the map's portion
        resolution (int): Pixels per inch for the image containing the map's portion
        width (int): Width of the frame in pixels.
        height (int): Height of the frame in pixels.

        northern_block (Block):
        eastern_block (Block):
        x (int):
        y (int):
        """
    def __init__(self, bl_point: Point, tr_point: Point, resolution: int, scale: int, x, y, width=2048, height=2048,
                 northern_block: 'Block' = None, eastern_block: 'Block' = None):
        self.br_point = Point(bl_point.latitude, tr_point.longitude)
        self.bl_point = bl_point
        self.tr_point = tr_point
        self.northern_block = northern_block
        self.eastern_block = eastern_block
        self.resolution = resolution
        self.scale = scale
        self.height = height
        self.width = width
        self.image = None
        self.x = x
        self.y = y

        if self.width > 2048 or self.height > 2048:
            raise BlockException('Image size out of range: WIDTH and HEIGHT must be between 1 and 2048 pixels.')
        if self.bl_point.longitude > self.br_point.longitude or self.bl_point.latitude > self.br_point.latitude:
            raise BlockException('Invalid values for BBOX.')

    def __str__(self):
        return "Block ({} {}), {}x{}: {} -> {}".format(self.x, self.y, self.height, self.width,
                                                       utils.format_point(self.bl_point),
                                                       utils.format_point(self.tr_point))

    async def async_fetch(self, session: ClientSession) -> None:
        """
        Asynchronous fetching of images.

        Args:
          session (aiohttp".client.ClientSession): object needed for aiohttp methods

        Returns:
          None

        """
        params = self.get_params()
        try:
            response = await session.get('http://wms.pcn.minambiente.it/ogc', params=params)
            content = await response.read()
            log.info(f'Fetching {self}\n {" " * 24} with URL:{unquote(str(response.request_info.url))}')
            try:
                self.image = Image.open(BytesIO(content))
            except UnidentifiedImageError:
                log.exception(f'UnidentifiedImageError on {self}')

        except ClientConnectorError:
            log.exception(f'Error')

    def sync_fetch(self) -> None:
        """
        Strait synchronous fetching of images.

        It uses requests package, No longer used.

        Returns:
          None

        """
        params = self.get_params()
        req = get('http://wms.pcn.minambiente.it/ogc', params=params)
        log.info(f'Fetching {self}\n {" "*24} with URL:{unquote(req.request.url)}')
        try:
            self.image = Image.open(BytesIO(req.content))
        except UnidentifiedImageError:
            log.exception(f'UNHANDLED EXCEPTION on {self}')

    def get_params(self) -> Dict:
        """
        Function used to build GET parameters.

        Use those links to learn about "Web Map Service":
            - https://geoserver.geo-solutions.it/downloads/releases/2.8.x-ld/doc/services/wms/reference.html
            - http://portal.opengeospatial.org/files/?artifact_id=14416

        Returns:
          params, Dict with WMS-API parameters

        """
        params = dict()
        params['BBOX'] = '{},{},{},{}'.format(self.bl_point.latitude, self.bl_point.longitude,
                                              self.tr_point.latitude, self.tr_point.longitude)
        params['map'] = '/ms_ogc/WMS_v1.3/raster/IGM_25000.map'
        params['SERVICE'] = 'WMS'
        params['VERSION'] = '1.3.0'
        params['REQUEST'] = 'GetMap'
        params['LAYERS'] = 'CB.IGM25000.33,CB.IGM25000.32'
        params['STYLES'] = 'default'
        params['SRS'] = 'EPSG:4326'
        params['CRS'] = 'EPSG:4326'
        params['WIDTH'] = self.width
        params['HEIGHT'] = self.height
        params['FORMAT'] = 'image/png'
        params['TRANSPARENT'] = 'true'
        # params['BGCOLOR'] = ''
        # params['EXCEPTIONS'] = ''
        # params['TIME'] = ''
        # params['SLD'] = ''
        # params['SLD_BODY'] = ''
        # params['ELEVATION'] = ''
        return params

    def set_northern_block(self, lat: float, last=False) -> 'Block':
        bl_point_ntblock = Point(self.tr_point.latitude, self.bl_point.longitude)
        tr_point_ntblock = Point(self.tr_point.latitude + lat, self.tr_point.longitude)
        try:
            ntblock = Block(bl_point_ntblock, tr_point_ntblock, self.resolution, self.scale, self.x, self.y + 1)
            ntblock.set_width(self.width)
            if last:
                ntblock.set_height(ntblock.get_dots(ntblock.br_point, ntblock.tr_point))
        except BlockException:
            log.exception("Tried to create Block ({} {}): {} -> {}".format(self.x, self.y + 1,
                                                                           utils.format_point(bl_point_ntblock),
                                                                           utils.format_point(tr_point_ntblock)))
            sys.exit(1)
        self.northern_block = ntblock
        log.info(f'Used lat= {utils.format_coord(lat)} to produce {ntblock}')
        return ntblock

    def set_eastern_block(self, long: float, last=False) -> 'Block':
        bl_point_etblock = Point(self.bl_point.latitude, self.tr_point.longitude)
        tr_point_etblock = Point(self.tr_point.latitude, self.tr_point.longitude + long)
        try:
            etblock = Block(bl_point_etblock, tr_point_etblock, self.resolution, self.scale, self.x + 1, self.y)
            etblock.set_height(self.height)
            if last:
                etblock.set_width(etblock.get_dots(etblock.bl_point, etblock.br_point))
        except BlockException:
            log.exception("Tried to create Block ({} {}): {} -> {}".format(self.x + 1, self.y,
                                                                           utils.format_point(bl_point_etblock),
                                                                           utils.format_point(tr_point_etblock)))
            sys.exit(1)
        self.eastern_block = etblock
        log.info(f'Used long= {utils.format_coord(long)} to produce {etblock}')
        return etblock

    def get_dots(self, coord1: Point, coord2: Point) -> float:
        """Calculate distances in pixels.

        Calculate the distance (measured in pixels) between two points on the map,
        given the map scale and image resolution from the block.

        Args:
          coord1:
            First Point.
          coord2:
            Second Point.

        Returns:
          The number of pixels for the distance in the map.

        """
        km = distance(coord1, coord2).km
        cm_on_map = km * 100000 / self.scale
        inches_on_map = cm_on_map / 2.54
        return floor(self.resolution * inches_on_map)

    def set_width(self, width: float) -> None:
        """
        Set the width on the Block obj.

        Returns:
          width - need to be float due to consistency with math.floor function in utils.get_dots

        Raises:
          BlockException: When the block width is greater than 2048.
        """
        if width > 2048:
            raise BlockException(f'Image size out of range: WIDTH is {width} but must be between 1 and 2048 pixels.')
        else:
            self.width = width

    def set_height(self, height: float) -> None:
        """
        Set the height on the Block obj.

        Returns:
          height - need to be float due to consistency with math.floor function in utils.get_dots

        Raises:
          BlockException: When the block height is greater than 2048.
        """
        if height > 2048:
            raise BlockException(f'Image size out of range: HEIGHT is {height} but must be between 1 and 2048 pixels.')
        else:
            self.height = height
