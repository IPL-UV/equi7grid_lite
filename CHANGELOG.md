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

Unreleased changes here.

## [0.1.1] - 2024-06-09

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