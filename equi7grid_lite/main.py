import math
import multiprocessing as mp
import re
from functools import partial
from typing import Dict, List, Literal, Optional, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import shapely.geometry
import shapely.wkt
from nptyping import NDArray, Shape

from equi7grid_lite.dataclass import Equi7GridZone, InternalDataset, dict_to_datamodel
from equi7grid_lite.utils import get_id, haversine_distance, intersects_func, load_grid


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
            min_grid_size (int, optional): The size of the grid tile at the finest
                level, measured in meters. Defaults to 2560.

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
            zone_origin (List[Tuple[float, float]]): The origin of each
                Equi7Grid zone.
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

            # Add the zone and level
            grid.insert(loc=0, column="zone", value=name)
            grid.insert(loc=1, column="level", value=max_level_order)

            # Add the land column
            land = self.zone_land[self.zone_names.index(name)]
            grid.insert(loc=2, column="land", value=grid.intersects(land).values)
            zone_containers[name] = grid

        return zone_containers, max_grid_size

    def create_grid(
        self,
        level: int,
        zone: Literal["AN", "NA", "OC", "SA", "AF", "EU", "AS"],
        mask: Optional[gpd.GeoSeries] = None,
    ) -> gpd.GeoDataFrame:
        """Create a Equi7Grid polygon for a specific zone.

        Args:
            level (int): The level of the grid. The level must be
                less than or equal to the maximum level defined by
                the `create_init_grid` method.
            zone (Literal["AN", "NA", "OC", "SA", "AF", "EU", "AS"]): The
                Equi7Grid zone.
            mask (Optional[gpd.GeoSeries], optional): The mask to apply
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
        zone_index: int = self.zone_names.index(zone)

        # Define the zone geometry
        zone_geometry: shapely.geometry.Polygon = self.zone_geometry[zone_index]

        # Intersect the zone with the mask if mask is not None
        if mask is not None:
            # Always reset the index
            mask.reset_index(drop=True, inplace=True)
            
            if mask.crs is None:
                raise ValueError(
                    "The mask must have a Coordinate Reference System (CRS)"
                )
            mask = mask.to_crs(self.zone_crs[zone_index]).geometry[0]
            zone_geometry = zone_geometry.intersection(mask)

            # Consider only 8 decimal of precision
            # This is helpful to avoid floating point errors
            zone_geometry = shapely.wkt.loads(
                shapely.wkt.dumps(zone_geometry, rounding_precision=8)
            )

        # Obtain the bounding box of the specified zone
        bbox_geo: Tuple[float, float, float, float] = zone_geometry.bounds
        grid_user_distance: int = self.min_grid_size * (2**level)

        # coordinate bottom left
        x_min, y_min, x_max, y_max = bbox_geo

        # Get the rounded coordinates (Xmin)
        diff_x_min: float = x_min % grid_user_distance
        x_init_rounded: float = x_min - diff_x_min

        # Get the rounded coordinates (Ymin)
        diff_y_min: float = y_min % grid_user_distance
        y_init_rounded: float = y_min - diff_y_min

        # Get the rounded coordinates (Xmax)
        diff_x_max: float = x_max % grid_user_distance
        x_last_rounded: float = x_max - diff_x_max + grid_user_distance

        # Get the rounded coordinates (Ymax)
        diff_y_max: float = y_max % grid_user_distance
        y_last_rounded: float = y_max - diff_y_max + grid_user_distance

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

        # Add the zone and level
        local_grid.insert(loc=0, column="zone", value=zone)
        local_grid.insert(loc=1, column="level",value=f"Z{level}")

        # Add the land column
        land = self.zone_land[zone_index]
        local_grid.insert(loc=2, column="land", value=local_grid.intersects(land).values)

        # intersect the grid with the zone geometry
        final_result = local_grid[local_grid.intersects(zone_geometry)]
        final_result.reset_index(drop=True, inplace=True)

        return final_result

    def lonlat2grid(
        self, lon: float, lat: float, centroid: Optional[bool] = True
    ) -> gpd.GeoDataFrame:
        """Convert a latitude and longitude to an Equi7Grid Tile Metadata.

        Args:
            lon (float): The longitude in EPSG:4326.
            lat (float): The latitude in EPSG:4326.
            centroid (Optional[bool], optional): If True, it will align
                with respect to the centroid of the grid tile. Defaults to
                True.

        Returns:
            gpd.GeoDataFrame: The Equi7Grid tile metadata for the
                specified latitude and longitude.
        """

        # Create a GeoDataFrame with the point
        point = gpd.GeoDataFrame(
            geometry=[shapely.geometry.Point(lon, lat)], crs="EPSG:4326"
        )

        # Find the zone where this point is located
        haversine_distance_min: float = math.inf
        for index, zone in enumerate(self.zone_names):

            # Load the Zone
            zone_geom: shapely.geometry.Polygon = self.zone_geometry[index]
            zone_crs: str = self.zone_crs[index] # in PROJCS format
            zone_geom = gpd.GeoDataFrame(geometry=[zone_geom], crs=self.zone_crs[index]).geometry
            
            # Intersect the point with the zone
            condition: bool = point.to_crs(zone_crs).intersects(zone_geom)[0]

            # If the point is within many zones, select the closest one
            # to the origin of the zone
            if condition:
                lon_ref, lat_ref = self.zone_origin[index]

                # Calculate the arc distance between the point and the origin of the Equi7Grid zone
                arc_distance: float = haversine_distance(lon, lat, lon_ref, lat_ref)

                # Update the minimum distance and set the best index (best zone)
                if arc_distance < haversine_distance_min:
                    haversine_distance_min = arc_distance
                    best_index = index

        # Get the Equi7Grid Zone name
        name: str = self.zone_names[best_index]

        # Search in the level 0 grid & add reference coordinates
        q: gpd.GeoDataFrame = self.create_grid(level=0, zone=name, mask=point.geometry)

        # add the Equi7Grid tile ID
        q_id: str = get_id(polygon=q.geometry.values[0], distance=self.min_grid_size, zone_id=name)
        q.insert(loc=0, column="id", value=q_id)

        if centroid:
            x, y = q.geometry.centroid.x.values[0], q.geometry.centroid.y.values[0]
            q.insert(loc=1, column="x", value=x)
            q.insert(loc=2, column="y", value=y)
        else:
            x, y = q.geometry.bounds.minx.values[0], q.geometry.bounds.miny.values[0]
            q.insert(loc=1, column="x", value=x)
            q.insert(loc=2, column="y", value=y)

        # Add the lonlat coordinates
        lon, lat = pyproj.Transformer.from_crs(
            crs_from=q.crs, crs_to="EPSG:4326", always_xy=True
        ).transform(x, y)
        q.insert(loc=1, column="lon", value=lon)
        q.insert(loc=2, column="lat", value=lat)

        return q

    def grid2lonlat(
        self, grid_id: str, centroid: Optional[bool] = True
    ) -> pd.DataFrame:
        """Convert an Equi7Grid grid id to a Equi7Grid Tile Metadata. 

        Args:
            grid_id (str): The Equi7Grid grid id.
            centroid (Optional[bool], optional): If True, it will align
                with respect to the centroid of the grid tile. Defaults to
                True.

        Returns:
            pd.DataFrame: A DataFrame with the Equi7Grid tile metadata
        """

        # Extract the metadata from the grid_id
        re_expr = re.compile(r"\b([A-Z]+)(\d+)_E(\d+)N(\d+)")
        zone = re_expr.search(grid_id).group(1)
        distance = int(re_expr.search(grid_id).group(2))
        nxtile = int(re_expr.search(grid_id).group(3))
        nytile = int(re_expr.search(grid_id).group(4))

        # From Grid to Equi7Grid coordinates
        if centroid:
            x: float = (nxtile + 0.5) * distance
            y: float = (nytile + 0.5) * distance
        else:
            x: float = nxtile * distance
            y: float = nytile * distance

        # Get the grid CRS
        crs: str = self.zone_crs[self.zone_names.index(zone)]
        lon, lat = pyproj.Transformer.from_crs(
            crs_from=crs, crs_to="EPSG:4326", always_xy=True
        ).transform(x, y)

        return self.lonlat2grid(lon=lon, lat=lat, centroid=centroid)

    def zone_metadata(self, zone: Literal["AN", "NA", "OC", "SA", "AF", "EU", "AS"]) -> Equi7GridZone:
        """Obtain the metadata of a specific Equi7Grid zone.

        Args:
            zone (str): The Equi7Grid zone.

        Returns:
            Equi7GridZone: The metadata of the Equi7Grid zone.
        """
        return getattr(self, zone)

    def grid2grid(
        self, poly: shapely.geometry.Polygon, region_code: str
    ) -> gpd.GeoDataFrame:
        """Given a superior grid tile, return the subgrids at
        the finest level. This function runs in parallel to
        speed up the process and do not run validations.

        Args:
            poly (shapely.geometry.Polygon): The superior grid tile.
            region_code (str): The region code of the grid tile.
            centroid (Optional[bool], optional): If True, it will align
                with respect to the centroid of the grid tile. Defaults to
                True.
        Returns:
            gpd.GeoDataFrame: The subgrids at the finest level.
        """

        # Obtain the boundaries of the grid
        minx, miny, maxx, maxy = poly.bounds
        distance: int = self.min_grid_size

        # Calculate the number of steps in the x and y directions
        x_steps: int = math.ceil((maxx - minx) / distance)
        y_steps: int = math.ceil((maxy - miny) / distance)

        # Project the Equi7Grid to Geographic coordinates
        poly_crs: str = self.zone_metadata(region_code).crs # in PROJCS format
        reprojector = pyproj.Transformer.from_crs(
            crs_from=poly_crs, crs_to="EPSG:4326", always_xy=True
        )

        # Initialize an empty list to store the DataFrames for each grid
        grids = []
        for i in range(x_steps):
            # Create a new DataFrame for the current x step
            grids_j = pd.DataFrame()

            # Initialize lists to store x, y coordinates and names for the current grid
            x_list = []
            y_list = []
            name_list = []
            bbox_list = []

            # Iterate over the number of y steps
            for j in range(y_steps):
                # Calculate the x and y coordinates for the current grid cell
                x = minx + i * distance + distance // 2
                y = miny + j * distance + distance // 2

                # Calculate the boundaries of each grid cell
                cell_minx = str(int(x / distance)).zfill(4)
                cell_miny = str(int(y / distance)).zfill(4)

                # calculate bbox
                bbox: List[float] = [
                    x - distance // 2,
                    y - distance // 2,
                    x + distance // 2,
                    y + distance // 2,
                ]
                tile = shapely.geometry.box(*bbox)

                # Generate the unique id for the current grid cell
                name = f"{region_code}{distance}_E{cell_minx}N{cell_miny}"
                name_list.append(name)
                x_list.append(x)
                y_list.append(y)
                bbox_list.append(tile)

            # Assign the lists to the DataFrame columns
            grids_j["id"] = name_list
            grids_j["x"] = x_list
            grids_j["y"] = y_list

            # Convert Equi7Grid coordinates to geographic coordinates (longitude, latitude)
            grids_j["lon"], grids_j["lat"] = reprojector.transform(
                grids_j["x"], grids_j["y"]
            )

            # Add the region code as the zone for the current grid
            grids_j["zone"] = region_code

            # Add the geometry column
            grids_j["geometry"] = bbox_list

            # Append the DataFrame for the current grid to the list of grids
            grids.append(grids_j)

        # Concatenate the DataFrames for each grid cell
        dataset = gpd.GeoDataFrame(pd.concat(grids, ignore_index=True), crs=poly_crs)

        # Intersect the grid with the land
        land: shapely.geometry.MultiPolygon = self.zone_metadata(region_code).landmasses_equi7grid

        # Use multiprocessing to speed up the process
        with mp.Pool(mp.cpu_count()) as pool:
            intersects_func_partial = partial(intersects_func, land=land)
            dataset["land"] = pool.starmap(
                intersects_func_partial,
                zip(
                    dataset["geometry"],
                ),
            )

        return dataset

    def cubo_utm_parameters(
        self, lon: float, lat: float, rotation_compensation: float = 1.1
    ) -> Dict[str, float]:
        """Get the parameters for a CUBO request given a lonlat

        Args:
            lon (float): The longitude of the point in EPSG:4326.
            lat (float): The latitude of the point in EPSG:4326.
            rotation_compensation (float, optional): Compensation 
                factor to avoid border effects. Defaults to 1.1.

        Returns:
            dict: A dictionary with the parameters for a 
                CUBO request. The dictionary contains the
                following keys:
                - lon: The fixed longitude of the point.
                - lat: The fixed latitude of the point.
                - utm: The UTM EPSG code.
                - distance: The distance of the CUBO request.
                - polygon: The POLYGON in the UTM coordinates.
                - zone: The Equi7Grid zone.
                - crs: The CRS of the zone.                
        """

        # Obtain the new coordinates and POLYGON
        gmeta: gpd.GeoDataFrame = self.lonlat2grid(lon, lat)

        # Get the UTM EPSG from latlon
        epsg: str = pyproj.database.query_utm_crs_info(
            datum_name="WGS 84",
            area_of_interest=pyproj.aoi.AreaOfInterest(lon, lat, lon, lat),
        )[0].code
        utm_crs: pyproj.CRS = pyproj.CRS.from_epsg(epsg)

        # Convert the polygon to UTM and obtain max distance
        gpoly: Tuple[float, float, float, float] = gmeta["geometry"].to_crs(epsg).values[0].bounds
        x_dist: float = gpoly[2] - gpoly[0]
        y_dist: float = gpoly[3] - gpoly[1]

        # add a extra distance to avoid border effects
        distance = int(np.ceil(max(x_dist, y_dist) * rotation_compensation))

        return {
            "lon": gmeta["lon"].values[0],
            "lat": gmeta["lat"].values[0],
            "utm": "EPSG:{}".format(utm_crs.to_epsg()),
            "distance": distance,
            "polygon": gmeta["geometry"].values[0],
            "zone": gmeta["zone"].values[0],
            "crs": self.__dict__.get(gmeta["zone"].values[0]).crs,
        }

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
