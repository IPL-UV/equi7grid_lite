# Changelog

All notable changes to the `opensr-test` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### Added
- For new features.
### Changed
- For changes in existing functionality.
### Deprecated
- For soon-to-be removed features.
### Removed
- For now removed features.
### Fixed
- For any bug fixes.
### Security
- In case of vulnerabilities.

## [Unreleased]

## [0.6.0] - 2024-06-22

- Iterating to obtain a better API. We now only have three core methods in the Equi7Grid class. The methods are `lonlat2grid`, `grid2lonlat`, and `create_grid`. We prefer to keep the API simple and easy to use.

- We have two new auxiliary methods in the Equi7Grid class. The methods are `grid2grid` and `cubo_utm_parameters`. The `grid2grid` method is used to obtain the subgrids at the finest level given a superior grid tile. This method runs in parallel to speed up the process and does not run validations. The `cubo_utm_parameters` method is used to obtain the CUBO UTM parameters given a lonlat coordinate.

- ReadME updated with examples.


## [0.4.0] - 2024-06-12

- Bug in a regex expression fixed. `grid2lonlat` method now works with regions outside South America.
- New method added to the Equi7Grid class. The method is called `lonlat2grid_ids`. This method is used to convert geographic coordinates to Equi7Grid tile ids given a specific level.


## [0.3.0] - 2024-06-11

- A new attribute added self.levels to the Equi7Grid constructor. This attribute is a List of the available levels in the QuadTree structure.
- New arguments added to lonlat2grid and grid2lonlat methods. First a centroid argument. This argument is used to specify if user wants the centroid of the grid or the bottom-left corner. By default, the centroid is True in order to keep compatibility with the cubo package. The level argument is used to specify the level of the QuadTree structure reference. By default, the level is 0.
- New method added to the Equi7Grid class. The method is called align2grid. This method is used to align coordinates to the QuadTree structure.

## [0.2.0] - 2024-06-10

- Documentation in README.md and code comments improved.
- Shameful bug respect to the initial level. It must be 0 no 1. I'm not in R!
- Fix a bug with respect to the float precision. We only consider 8 decimal places. Now 
the next statement is always true:
    ```python
    grid_id = lonlat2grid(...)
    grid2lonlat(grid_id) == grid2lonlat(lonlat2grid(grid2lonlat(grid_id)))
    ```
- We have added a new method `Equi7Grid.reproject()` to convert rioxarray and shapely geometries to the Equi7Grid.



## [0.1.0] - 2024-06-09

- First release.