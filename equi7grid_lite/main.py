import math
import re
from typing import Dict, List, Literal, Optional, Tuple, Union

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely.wkt
from nptyping import NDArray, Shape
from shapely.geometry import Point

from equi7grid_lite.dataclass import (Equi7GridZone, InternalDataset,
                                      dict_to_datamodel)
from equi7grid_lite.utils import load_grid, utils_add_id, haversine_distance


class Equi7Grid:
    """
    The `Equi7Grid` class facilitates the creation of
    Equi7Grid grids with a Quad-Tree structure.

    The Equi7Grid system provides a global grid based on
    regional azimuthal equidistant projections, dividing the
    Earth's surface into seven zones: Antarctica (AN), North
    America (NA), Oceania (OC), South America (SA), Africa (AF),
    Europe (EU), and Asia (AS).

    For information about the Equi7Grid system, please
    visit: https://github.com/TUW-GEO/Equi7Grid
    """

    def __init__(self, min_grid_size: int = 2560):
        """
        Initialize the `Equi7Grid` class.

        Args:
            min_grid_size (int, optional): The size of the grid tile at the finest level,
                measured in meters. Defaults to 2560.

        Attributes:
            min_grid_size (int): The size of the grid tile at the finest level.
            zone_names (List[str]): The names of the Equi7Grid zones.
            zone_geometry (List[str]): The geometrical boundaries of the Equi7Grid zones.
            zone_land (List[str]): The land geometries within the Equi7Grid zones.
            zone_crs (List[str]): The Coordinate Reference Systems (CRS) of the Equi7Grid zones.
            zone_bounds (List[Tuple[float, float, float, float]]): The bounding boxes of the
                Equi7Grid zones in WGS84 coordinates.
            land_bounds (List[Tuple[float, float, float, float]]): The bounding boxes of the
                land areas within the Equi7Grid zones in WGS84 coordinates.
            zone_geometry_max_grids (Dict[str, gpd.GeoDataFrame]): The maximum grid size per
                zone, used as a reference to create subgrids. Grids larger than this size
                cannot be created.
            max_grid_size (int): The maximum grid size in meters.
        """

        # Define the minimum grid size
        self.min_grid_size = min_grid_size

        # Load the Equi7Grid metadata
        zone_metadata = InternalDataset(**load_grid())
        self.zone_names = zone_metadata.id
        self.zone_geometry = zone_metadata.geometry_equi7grid
        self.zone_land = zone_metadata.landmasses_equi7grid
        self.zone_crs = zone_metadata.crs
        self.zone_origin = zone_metadata.origin

        # Define the upper bounds (maximum grid size per zone)
        self.zone_geometry_max_grids, self.max_grid_size = self.create_init_grid()

        # Calculate the levels
        max_level: int = int(np.log2(self.max_grid_size / self.min_grid_size))
        self.levels = list(range(max_level))


        # Define the Equi7Grid zones metadata
        self.AN: Equi7GridZone = dict_to_datamodel(zone_metadata, 0)
        self.NA: Equi7GridZone = dict_to_datamodel(zone_metadata, 1)
        self.OC: Equi7GridZone = dict_to_datamodel(zone_metadata, 2)
        self.SA: Equi7GridZone = dict_to_datamodel(zone_metadata, 3)
        self.AF: Equi7GridZone = dict_to_datamodel(zone_metadata, 4)
        self.EU: Equi7GridZone = dict_to_datamodel(zone_metadata, 5)
        self.AS: Equi7GridZone = dict_to_datamodel(zone_metadata, 6)

    def create_init_grid(self) -> Tuple[Dict[str, gpd.GeoDataFrame], int]:
        """
        Creates the upper bound grid for each Equi7Grid zone.

        The coarsest grid level is determined as the nearest lower distance
        to a 2_500_000 meter square. This grid serves as the upper bound for
        creating subgrids (internal grids).

        This method generates the initial maximum grid for each zone based on
        this coarsest level, which is then used to manage and subdivide the
        subgrids efficiently.

        Returns:
            Tuple[Dict[str, gpd.GeoDataFrame], int]:
                - A dictionary mapping Equi7Grid zone names to their respective
                    GeoDataFrame representations of the maximum grid.
                - The maximum grid size in meters.
        """

        # Calculate the maximum level
        numerator: int = 2_500_000  # Define the coarsest grid level
        denominator: int = self.min_grid_size  # Distance in the finest grid
        ratio = numerator / denominator
        max_level: int = math.floor(math.log(ratio, 2))

        # Calculate the tile size at the coarsest grid level
        max_grid_size: int = (self.min_grid_size) * (2**max_level)
        max_level_order: str = f"Z{max_level}"

        # Load the zones
        zone_containers = dict()
        for name, geometry, crs in zip(
            self.zone_names, self.zone_geometry, self.zone_crs
        ):

            # Create the GeoDataFrame
            zone = gpd.GeoDataFrame(geometry=[geometry], crs=crs)

            # Obtain the boundaries of the zone
            bound: NDArray[Shape["4"], np.float64] = zone.geometry.total_bounds
            width: float = bound[2] - bound[0]
            height: float = bound[3] - bound[1]

            # Get a number of tiles on the top level grid
            nx_tile: int = int(np.ceil(width / max_grid_size))
            ny_tile: int = int(np.ceil(height / max_grid_size))

            # Create the grid (Iterate in the x and y direction)
            tiles: List[Tuple[shapely.geometry.Polygon]] = []
            for ny in range(ny_tile):
                ym: float = ny * max_grid_size
                for nx in range(nx_tile):

                    # Define the bottom left corner of each tile
                    xm: float = nx * max_grid_size

                    # Define coordinates of the tile polygon
                    bbox: List[float] = [xm, ym, xm + max_grid_size, ym + max_grid_size]

                    # Create the tile polygon
                    tile = shapely.geometry.box(*bbox)
                    tiles.append(tile)

            # Create the GeoDataFrame
            grid = gpd.GeoDataFrame(geometry=tiles, crs=crs)
            grid["zone"] = name
            grid["level"] = max_level_order
            zone_containers[name] = grid

        return zone_containers, max_grid_size

    def create_grid(
        self,
        level: int,
        zone: Literal["AN", "NA", "OC", "SA", "AF", "EU", "AS"],
        mask: Optional[shapely.geometry.base.BaseGeometry] = None,
        coverland: Optional[bool] = True
    ) -> gpd.GeoDataFrame:
        """Create a grid for a specific zone.

        Args:
            level (int): The level of the grid. The level must be
                less than or equal to the maximum level defined by
                the `create_init_grid` method.
            zone (Literal["AN", "NA", "OC", "SA", "AF", "EU", "AS"]): The
                Equi7Grid zone.
            coverland (bool, optional): If True, the grid system will be created
                only for the land area. Defaults to True.
            mask (Optional[shapely.geometry.base.BaseGeometry], optional): If
                provided, the grid will be created only within the mask.
                Defaults to None.

        Returns:
            gpd.GeoDataFrame: The grid system for the specified zone.
        """

        # Check the grid level
        max_level: int = int(math.log(self.max_grid_size / self.min_grid_size, 2))

        # Check if the grid level is less than the maximum level
        if max_level < level:
            raise ValueError(
                f"The grid level must be less than or equal to {max_level}"
            )

        # Obtain the index of the zone in the metadata
        zone_index = self.zone_names.index(zone)

        # Define the zone geometry
        zone_geometry = self.zone_geometry[zone_index]

        # Intersect the zone with the land if land is True
        if coverland:
            land_geometry = self.zone_land[zone_index]
            zone_geometry = zone_geometry.intersection(land_geometry)

        # Intersect the zone with the mask if mask is not None
        if mask is not None:
            mask_gpd = gpd.GeoDataFrame(geometry=[mask], crs="EPSG:4326")
            mask_plane = mask_gpd.to_crs(self.zone_crs[zone_index]).geometry[0]
            zone_geometry = zone_geometry.intersection(mask_plane)

            # Consider only 8 decimal of precision
            # This is helpful to avoid floating point errors
            zone_geometry = shapely.wkt.loads(
                shapely.wkt.dumps(zone_geometry, rounding_precision=8)
            )

        # Obtain the bounding box of the specified zone
        bbox_geo = zone_geometry.bounds
        grid_user_distance = self.min_grid_size * (2 ** level)

        # coordinate bottom left
        x_min, y_min, x_max, y_max = bbox_geo

        # Get the rounded coordinates (Xmin)
        diff_x_min = x_min % grid_user_distance
        x_init_rounded = x_min - diff_x_min

        # Get the rounded coordinates (Ymin)
        diff_y_min = y_min % grid_user_distance
        y_init_rounded = y_min - diff_y_min

        # Get the rounded coordinates (Xmax)
        diff_x_max = x_max % grid_user_distance
        x_last_rounded = x_max - diff_x_max + grid_user_distance

        # Get the rounded coordinates (Ymax)
        diff_y_max = y_max % grid_user_distance
        y_last_rounded = y_max - diff_y_max + grid_user_distance

        # Create the grid
        nxtiles = int((x_last_rounded - x_init_rounded) / grid_user_distance)
        nytiles = int((y_last_rounded - y_init_rounded) / grid_user_distance)

        # Iterate in the x and y direction
        new_polys = []
        for i in range(nxtiles):
            for j in range(nytiles):
                x1 = x_init_rounded + i * grid_user_distance
                y1 = y_init_rounded + j * grid_user_distance
                x2 = x1 + grid_user_distance
                y2 = y1 + grid_user_distance
                new_poly = shapely.geometry.box(x1, y1, x2, y2)
                new_polys.append(new_poly)

        # Create the final grid
        local_grid = gpd.GeoDataFrame(geometry=new_polys, crs=self.zone_crs[zone_index])
        local_grid.insert(
            0, "id", utils_add_id(local_grid, distance=self.min_grid_size, zone_id=zone)
        )
        local_grid.insert(1, "zone", zone)
        local_grid.insert(2, "level", f"Z{level}")

        # intersect the grid with the zone geometry
        return local_grid[local_grid.intersects(zone_geometry)]

    def lonlat2grid(
        self,
        lon: float,
        lat: float,
        level: Optional[int] = 0,
        centroid: Optional[bool] = True
    ) -> gpd.GeoDataFrame:
        """Convert a latitude and longitude to an Equi7Grid Tile.

        Args:
            lon (float): The longitude.
            lat (float): The latitude.
            level (Optional[int], optional): The grid level. Defaults to 0.
            centroid (Optional[bool], optional): If True, it will return the
                centroid of the grid tile. Defaults to True.

        Returns:
            gpd.GeoDataFrame: The Equi7Grid Tile.
        """
        
        # Create a gp dataframe
        point = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")

        # Find the zone where this point is located
        haversine_distance_min = math.inf
        for index, zone in enumerate(self.zone_names):            
            # Load the Zone
            zone_geom = self.zone_geometry[index]
            zone_crs = self.zone_crs[index]
            zone_gpd = gpd.GeoDataFrame(geometry=[zone_geom], crs=self.zone_crs[index])
            zone_geom = zone_gpd.geometry[0]

            # Intersect the point with the zone
            condition = point.to_crs(zone_crs).intersects(zone_geom)[0]

            # If the point is within many zones, select the closest one
            # to the origin of the zone
            if condition:
                lon_ref, lat_ref = self.zone_origin[index]
                arc_distance = haversine_distance(lon, lat, lon_ref, lat_ref)
                
                # Update the minimum distance and set the best index (best zone)
                if arc_distance < haversine_distance_min:
                    haversine_distance_min = arc_distance
                    best_index = index

        # Get the Equi7Grid Zone name
        name = self.zone_names[best_index]

        # Search in the level 1 grid & add bottom left coordinates
        q = self.create_grid(level=level, zone=name, mask=point.geometry[0], coverland=False)
        
        if centroid:
            q.insert(1, "x", q.geometry.centroid.x)
            q.insert(2, "y", q.geometry.centroid.y)
        else:
            q.insert(1, "x", q.geometry.bounds.minx)
            q.insert(2, "y", q.geometry.bounds.miny)        

        return q

    def grid2lonlat(
        self,
        grid_id: Union[str, gpd.GeoDataFrame],
        xy_coords: Optional[bool] = False,
        centroid: Optional[bool] = True
    ) -> pd.DataFrame:
        """Convert an Equi7Grid Tile to a latitude and longitude.

        Args:
            grid_id (str): The Equi7Grid Tile ID.
            xy_coords (Optional[bool], optional): If True, it will
                also return the X and Y coordinates in the Equi7Grid
                system. Defaults to True.
            centroid (Optional[bool], optional): If True, it will 
                return the centroid of the grid tile. Defaults to 
                True.

        Returns:
            pd.DataFrame: A DataFrame with the latitude and longitude
        """
        # Check if the grid_id is a string or a GeoDataFrame
        if isinstance(grid_id, gpd.GeoDataFrame):
            grid_id = grid_id.id.values[0]
            
        ## Extract the zone
        zone = grid_id[:2]

        ## Extract the metadata from the grid_id
        re_expr = re.compile(r"SA(\d+)_E(\d+)N(\d+)")
        distance = int(re_expr.search(grid_id).group(1))
        nxtile = int(re_expr.search(grid_id).group(2))
        nytile = int(re_expr.search(grid_id).group(3))

        # From Grid to Equi7Grid coordinates
        if centroid:
            x = (nxtile + 0.5) * distance
            y = (nytile + 0.5) * distance
        else:
            x = nxtile * distance
            y = nytile * distance

        point_local = Point(x, y)

        # From Equi7Grid to Geographic coordinates
        zone_crs = self.zone_crs[self.zone_names.index(zone)]
        point_geo = gpd.GeoDataFrame(geometry=[point_local], crs=zone_crs)
        point_geo = point_geo.to_crs("EPSG:4326").geometry[0]

        # Return the coordinates
        if xy_coords:
            results = {"lon": point_geo.x, "lat": point_geo.y, "x": x, "y": y}
        else:
            results = {"lon": point_geo.x, "lat": point_geo.y}

        # from dict to dataframe
        return pd.DataFrame(results, index=[0])

    def align2grid(
        self,
        lon: float,
        lat: float,    
        level: Optional[int] = 0,
        centroid: Optional[bool] = True
    ) -> gpd.GeoDataFrame:
        """ Align the grid to the nearest grid tile.

        Args:
            lon (float): The longitude.
            lat (float): The latitude.
            level (int): The grid level. Defaults to 0.
            centroid (Optional[bool], optional): If True, it will 
                return the centroid of the grid tile. Defaults to
                True.

        Returns:
            gpd.GeoDataFrame: A GeoDataFrame with the coordinates
                aligned to the grid.
        """
        return self.grid2lonlat(
            grid_id=self.lonlat2grid(lon, lat, level=level, centroid=centroid),
            centroid=centroid,
            xy_coords=False
        )
        

    def __str__(self) -> str:
        """Display the Equi7Grid information.

        Returns:
            str: A string representation of the Equi7Grid information.
        """

        # If levels has more than 4 elements
        if len(self.levels) > 4:
            levels0 = self.levels[0]
            levels1 = self.levels[1]
            levelsn = self.levels[-1]
            levelsn1 = self.levels[-2]
            level_msg = f"{levels0}, {levels1}, ... , {levelsn1}, {levelsn}"
        else:
            level_msg = f"{', '.join(map(str, self.levels))}"

        message = f"Equi7Grid(min_grid_size={self.min_grid_size})\n"
        message += f"----------------\n"
        message += f"levels: {level_msg}\n"
        message += f"zones: {', '.join(self.zone_names)}\n"
        message += f"min_grid_size: {self.min_grid_size} meters\n"
        message += f"max_grid_size: {self.max_grid_size} meters\n"
        return message

    def __repr__(self) -> str:
        """Display the Equi7Grid information.

        Returns:
            str: A string representation of the Equi7Grid information.
        """
        return self.__str__()
