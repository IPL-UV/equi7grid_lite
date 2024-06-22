# equi7grid-lite

<p align="center">
  <a href="https://ipl-uv.github.io"><img src="docs/logo.jpeg" alt="header" width="50%"></a>
</p>

<p align="center">
    <em>
    No one will drive us from the paradise which Equi7Grid created for us
    </em>
</p>

<p align="center">
<a href='https://pypi.python.org/pypi/equi7grid-lite'>
<img src='https://img.shields.io/pypi/v/equi7grid-lite.svg' alt='PyPI' />
</a>
<a href='https://colab.research.google.com/drive/1SBjl4GVgCFUpVch2Prju5oiXN8WyzZTi?usp=sharing'>
<img src='https://colab.research.google.com/assets/colab-badge.svg' alt='COLAB' />
</a>
<a href="https://opensource.org/licenses/MIT" target="_blank">
<img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License">
</a>
<a href="https://github.com/psf/black" target="_blank">
<img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Black">
</a>
<a href="https://pycqa.github.io/isort/" target="_blank">
<img src="https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336" alt="isort">
</a>
</p>

The `equi7grid-lite` package implements a user-friendly Python interface to interact with the [**Equi7Grid**](https://github.com/TUW-GEO/Equi7Grid) grid system. 

`equi7grid-lite` is an **unofficial Python implementation of [**Equi7Grid**](https://github.com/TUW-GEO/Equi7Grid)**. With this package, users can convert geographic coordinates to Equi7Grid tiles and vice versa. This implementation differs from the official version in tree key ways:

- *Quad-Tree Grid Splitting*: Users are required to split the grid in a Quad-Tree fashion, meaning each grid level is divided into four tiles. For example, transitioning from level 1 to level 0 involves splitting each tile into four regular smaller tiles.

- *Revised Grid ID Encoding*: The grid ID is always encoded in meters, and the reference to the tile system (e.g., "T1", "T3", "T6") is removed. Instead, tiles are dynamically defined by the `min_grid_size` parameter. Here is a comparison between the original Equi7Grid and equi7grid-lite name conventions:

    - 'EU500M_E036N006T6' -> 'EU2560_E4521N3011'

    Where 'EU' is the Equi7Grid zone, '2560' is the `min_grid_size`, 'E4521' is the position in the *x* tile grid, and 'N3011' is the position in the *y* tile grid.

- *Upper Bound Level*: The maximum grid level is determined as the nearest lower distance to 2_500_000 meters. This threshold serves as a limit to create the Quad-Tree grid structure.


<p align="center">
  <img src="docs/equi7grid_tiling.gif" alt="equi7grid-lite" width="100%"/>
</p>

Please refer to the [Equi7Grid repository](https://github.com/TUW-GEO/Equi7Grid) for **more information of the official implementation**.

## Installation

The `equi7grid-lite` package is available on PyPI and can be installed using `pip`:

```python
pip install equi7grid-lite
```

## Usage

The `equi7grid-lite` package provides a single class, `Equi7Grid`, which can be used to convert between geographic coordinates and Equi7Grid tiles.

```python
from equi7grid_lite import Equi7Grid

grid_system = Equi7Grid(min_grid_size=2560)
# Equi7Grid(min_grid_size=2560)
# ----------------
# levels: 0, 1, ... , 7, 8
# zones: AN, NA, OC, SA, AF, EU, AS
# min_grid_size: 2560 meters
# max_grid_size: 1310720 meters
```

To convert between geographic coordinates and Equi7Grid tiles, use the `lonlat2grid` method.

```python

lon, lat = -79.5, -5.49
grid_system.lonlat2grid(lon=lon, lat=lat)
#                  id        lon       lat          x          y zone level  land             geometry
#0  SA2560_E2009N2525 -79.507568 -5.485739  5144320.0  6465280.0   SA    Z0  True  POLYGON ((514560...
```

Use the `grid2lonlat` method to convert from Equi7Grid tile id to geographic coordinates.


```python
grid_system.grid2lonlat(grid_id="SA2560_E2009N2525")
#                  id        lon       lat          x          y zone level  land             geometry
#0  SA2560_E2009N2525 -79.507568 -5.485739  5144320.0  6465280.0   SA    Z0  True  POLYGON ((514560...
```

The `Equi7Grid` class also provides a method to create a grid of Equi7Grid upper-level tiles that
cover a given bounding box.

```python
import geopandas as gpd

from equi7grid_lite import Equi7Grid

# Define a POLYGON geometry
world_filepath = gpd.datasets.get_path('naturalearth_lowres')
world = gpd.read_file(world_filepath)
country = world[world.name == "Peru"].geometry

# Create a grid of Equi7Grid tiles that cover the bounding box of the POLYGON geometry
grid = grid_system.create_grid(
    level=4,
    zone="SA",
    mask=country # Only include tiles that intersect the polygon
)

# Export the grid to a GeoDataFrame
grid.to_file("grid.shp")
```

By running `create_grid` with different levels, you can obtain its corresponding Equi7Grid Quad-Tree grid structure for any region.

![grid](docs/equi7grid_demo.gif)

Obtain the metadata of each Equi7Grid zone:

```python
from equi7grid_lite import Equi7Grid

# Zones: SA, EU, AF, AS, NA, AU
Equi7Grid.SA
```

Each zone has the following attributes:

- *id*: The zone ID code.
- *crs*: The WKT representation of the CRS.
- *geometry_geo*: The geometry of the zone in EPSG:4326.
- *geometry_equi7grid*: The geometry of the zone in the Equi7Grid CRS.
- *bbox_geo*: The bounding box of the zone in EPSG:4326.
- *bbox_equi7grid*: The bounding box of the zone in the Equi7Grid CRS.
- *landmasses_equi7grid*: The landmasses of the zone in the Equi7Grid CRS.
- *origin*: The central meridian and the latitude of origin.

## Use Equi7Grid with cubo

The `equi7grid-lite` package can be used in conjunction with the [cubo](https://github.com/ESDS-Leipzig/cubo) to retrieve Earth Observation (EO) data.

```python
import cubo
import matplotlib.pyplot as plt
import numpy as np
import rioxarray
from rasterio.enums import Resampling

from equi7grid_lite import Equi7Grid

# Initialize Equi7Grid system
grid_system = Equi7Grid(min_grid_size=2560)

# Specify the center coordinates
lon, lat = -122.4194, 37.7749

# Retrieve parameters for the CUBO request
cubo_parameters = grid_system.cubo_utm_parameters(lon=lon, lat=lat)

# Define the cube request using CUBO
da = cubo.create(
    lat=cubo_parameters["lat"],
    lon=cubo_parameters["lon"],
    collection="sentinel-2-l2a",  # Name of the STAC collection
    bands=["B04", "B03", "B02"],   # Bands to retrieve
    start_date="2021-08-01",       # Start date of the cube
    end_date="2021-10-30",         # End date of the cube
    edge_size=cubo_parameters["distance"] // 10,  # Distance in pixels
    resolution=10,                 # Pixel size of the cube (m)
    query={"eo:cloud_cover": {"lt": 50}}  # Query parameters
)

# Add the CRS to the cube
da = da.rio.write_crs(f"epsg:{da.attrs['epsg']}")
da = da.drop_vars("cubo:distance_from_center")

# Convert the cube to a dataset and compute median over time
image = da.to_dataset("band").median("time", skipna=True)

# Increase the resolution of the cube with Lanczos resampling
image_reprojected = image.rio.reproject(
    cubo_parameters["crs"],
    resolution=2.5,
    resampling=Resampling.lanczos
)

# Downsample the cube with nearest neighbor resampling
image_reprojected = image_reprojected.rio.reproject(
    cubo_parameters["crs"],
    resolution=10,
    resampling=Resampling.nearest
)

# Clip the cube to the specified polygon
composite_e7g = image_reprojected.rio.clip([cubo_parameters["polygon"]]).to_array()

# Save the images in UTM and E7G projections
composite_e7g.rio.to_raster("composite_e7g.tif")
image.to_array().rio.to_raster("composite_utm.tif")
```

## License

This package is released under the MIT License. For more information, see the [LICENSE](LICENSE) file.

## Contributing

Contributions are welcome! For bug reports or feature requests, please open an issue on GitHub. For contributions, please submit a pull request with a detailed description of the changes.

## Citation

This is a simple adaptation of the Equi7Grid paper and code. If you use this package in your research, please consider citing the original Equi7Grid package and paper.

**Package:**

```
@software{bernhard_bm_2023_8252376,
  author       = {Bernhard BM and
                  Sebastian Hahn and
                  actions-user and
                  cnavacch and
                  Manuel Schmitzer and
                  shochsto and
                  Senmao Cao},
  title        = {TUW-GEO/Equi7Grid: v0.2.4},
  month        = aug,
  year         = 2023,
  publisher    = {Zenodo},
  version      = {v0.2.4},
  doi          = {10.5281/zenodo.8252376},
  url          = {https://doi.org/10.5281/zenodo.8252376}
}
```

**Paper:**

```
@article{BAUERMARSCHALLINGER201484,
title = {Optimisation of global grids for high-resolution remote sensing data},
journal = {Computers & Geosciences},
volume = {72},
pages = {84-93},
year = {2014},
issn = {0098-3004},
doi = {https://doi.org/10.1016/j.cageo.2014.07.005},
url = {https://www.sciencedirect.com/science/article/pii/S0098300414001629},
author = {Bernhard Bauer-Marschallinger and Daniel Sabel and Wolfgang Wagner},
keywords = {Remote sensing, High resolution, Big data, Global grid, Projection, Sampling, Equi7 Grid}
}
```
