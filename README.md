# ptolemy

A map tile fetch-and-stitch tool. Great for grabbing regions of the world at various resolutions with a careful CLI.

Requires Python 3.10 and `pip install numpy matplotlib requests alive-progress pillow geopy`.

## Tile servers

Currently, `ptolemy` has a small subset of named tile servers. They are all ran generously pro bono; please do not abuse them. If you want to look out for other styles, consider OpenStreetMap's excellent list of [raster tile providers](https://wiki.openstreetmap.org/wiki/Raster_tile_providers).

Tiles are cached to [`$XDG_CACHE_HOME/ptolemy`](https://xdgbasedirectoryspecification.com) (default: `~/.cache/ptolemy`).

## Todo

- [ ] Accept a "sea colour" as a background for tile-fetching errors
- [ ] Interpret style directly from URL
- [ ] Interpret from openstreetmap/gsm URL: `[...] z/lat/LONG [...]`
- [ ] Handle map projections with e.g. [geopandas](https://geopandas.org/en/stable/docs/user_guide/projections.html)
- [ ] Simple cache manager - `touch` a tile when fetched from cache, and have the option to cull long-unused tiles
- [ ] pyproject.toml, upload to PyPI