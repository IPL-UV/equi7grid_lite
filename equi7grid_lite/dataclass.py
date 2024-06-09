from typing import Any, List, Literal, Tuple

import pydantic
import shapely.geometry


class InternalDataset(pydantic.BaseModel):
    """An internal pickle file containing the geographical data of
    the Equi7Grid Zones. The file is stored in the data subfolder of
    the package.

    Fields:
        id (List[Literal["AN", "NA", "OC", "SA", "AF", "EU", "AS"]]): The
            names of the Equi7Grid zones.
        crs (List[str]): The CRS of the Equi7Grid zones.
        zone (List[shapely.geometry.Polygon]): The geometry of the
            Equi7Grid zones.
        geometry_geo (List[shapely.geometry.Polygon]): The geometry of
            the Equi7Grid zones in EPSG:4326.
        geometry_equi7grid (List[shapely.geometry.Polygon]): The geometry of
            the Equi7Grid zones in the Equi7Grid CRS.
        bbox_geo (List[Tuple[float, float, float, float]]): The bounding box
            of the Equi7Grid zones in EPSG:4326.
        bbox_equi7grid (List[Tuple[float, float, float, float]]): The bounding box
            of the Equi7Grid zones.
        landmasses_equi7grid (List[shapely.geometry.Polygon]): The landmasses
            of the Equi7Grid zones in the Equi7Grid CRS.
        origin (List[Tuple[float, float]]): The origin of the Equi7Grid zones.
    """

    id: List[Literal["AN", "NA", "OC", "SA", "AF", "EU", "AS"]]
    crs: List[str]
    geometry_geo: List[Any]
    geometry_equi7grid: List[Any]
    bbox_geo: List[Tuple[float, float, float, float]]
    bbox_equi7grid: List[Tuple[float, float, float, float]]
    landmasses_equi7grid: List[Any]
    origin: List[Tuple[float, float]]

    @pydantic.field_validator(
        "geometry_geo", "geometry_equi7grid", "landmasses_equi7grid"
    )
    def check_geometry(cls, values: str) -> str:
        for value in values:
            # Check if the geometry is a valid shapely object
            if not isinstance(value, shapely.geometry.base.BaseGeometry):
                raise ValueError("The geometry must be a valid shapely object.")
        return values

    def __str__(self):
        fields = [
            "id",
            "crs",
            "geometry_geo",
            "geometry_equi7grid",
            "bbox_geo",
            "bbox_equi7grid",
            "landmasses_equi7grid",
            "origin",
        ]
        return f"Equi7GridLite data: {self.id}" + f"\nFields: {fields}"

    def __repr__(self):
        return self.__str__()


class Equi7GridZone(pydantic.BaseModel):
    """A data model representing the Equi7Grid zone.

    Fields:
        id (str): The zone ID code.
        crs (str): The WKT representation of the CRS.
        geometry_geo (Any): The geometry of the zone in EPSG:4326.
        geometry_equi7grid (Any): The geometry of the zone in the Equi7Grid CRS.
        bbox_geo (Tuple[float, float, float, float]): The bounding box of the zone in EPSG:4326.
        bbox_equi7grid (Tuple[float, float, float, float]): The bounding box of the zone
            in the Equi7Grid CRS.
        landmasses_equi7grid (Any): The landmasses of the zone in the Equi7Grid CRS.
        origin (Tuple[float, float]): The origin of the zone.
    """

    id: str
    crs: str
    geometry_geo: Any
    geometry_equi7grid: Any
    bbox_geo: Tuple[float, float, float, float]
    bbox_equi7grid: Tuple[float, float, float, float]
    landmasses_equi7grid: Any
    origin: Tuple[float, float]

    @pydantic.field_validator(
        "geometry_geo", "geometry_equi7grid", "landmasses_equi7grid"
    )
    def check_geometry(cls, value: Any) -> Any:
        # Check if the geometry is a valid shapely object
        if not isinstance(value, shapely.geometry.base.BaseGeometry):
            raise ValueError("The geometry must be a valid shapely object.")
        return value


def dict_to_datamodel(
    metadata: InternalDataset,
    index: int
) -> Equi7GridZone:
    """From a dictionary, create an Equi7GridZone data model.

    Args:
        metadata (InternalDataset): A datamodel containing the metadata of the
            Equi7Grid zones.
        index (int, optional): The index of the zone to create the data model
            from.

    Returns:
        Equi7GridZone: An Equi7GridZone data model.
    """
    return Equi7GridZone(
        id=metadata.id[index],
        crs=metadata.crs[index],
        geometry_geo=metadata.geometry_geo[index],
        geometry_equi7grid=metadata.geometry_equi7grid[index],
        bbox_geo=metadata.bbox_geo[index],
        bbox_equi7grid=metadata.bbox_equi7grid[index],
        landmasses_equi7grid=metadata.landmasses_equi7grid[index],
        origin=metadata.origin[index]
    )
