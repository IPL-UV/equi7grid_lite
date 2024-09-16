import importlib
import math
import pickle
from typing import Dict

import geopandas as gpd
import shapely.geometry


def load_grid() -> Dict[str, gpd.GeoDataFrame]:
    """Load the dataset from a file.

    Returns:
        Dict[str, gpd.GeoDataFrame]: A dictionary containing the grid data.
    """

    # Load the dataset from a file
    path_file = importlib.resources.files("equi7grid_lite.data") / "metadata.pkl"

    # Load the grid from the file
    with open(path_file, "rb") as f:
        grid = pickle.load(f)

    return grid


def get_id(polygon: shapely.geometry.Polygon, distance: int, zone_id: str) -> str:
    """Get the id of specific grid cells at level 0.

    Args:
        local_grid (shapely.geometry.Polygon): The grid cells.
        distance (Optional[int], optional): The distance between the
            cells. Defaults to 10000.

    Returns:
        str: The name of the grid cells.
    """
    bbox = polygon.bounds
    minx, miny, maxx, maxy = bbox
    east_code = str(int(minx // distance)).zfill(4)
    north_code = str(int(miny // distance)).zfill(4)
    distance_code = str(int(distance))

    return f"{zone_id}{distance_code}_E{east_code}N{north_code}"


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate the great-circle distance between two points on
    the Earth's surface.

    Args:
        lon1 (float): The longitude of the first point in degrees.
        lat1 (float): The latitude of the first point in degrees.
        lon2 (float): The longitude of the second point in degrees.
        lat2 (float): The latitude of the second point in degrees.

    Returns:
        float: The distance between the two points in degrees.
    """

    # Convert latitude and longitude from degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distance in radians
    distance_radians = c

    # Convert distance from radians to degrees
    distance_degrees = math.degrees(distance_radians)

    return distance_degrees


def intersects_func(geometry, land):
    return land.intersects(geometry)
