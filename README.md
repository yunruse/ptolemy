# ptolemy

A map tile fetch-and-stitch tool. Great for grabbing regions of the world at various resolutions with a careful CLI.

Requires Python 3 (3.9, I think?) and `pip install requests alive-progress`.

## Tile servers

Currently, `ptolemy` has a small subset of named tile servers. They are all ran generously pro bono; please do not abuse them. If you want to look out for other styles, consider OpenStreetMap's excellent list of [raster tile providers](https://wiki.openstreetmap.org/wiki/Raster_tile_providers).

## Todo

[ ] Interpret directly from URL, in addition to `tilemaps.csv`
[ ] Interpret long/lat input
[ ] OpenStreetMap URL extractor for `[...] z/lat/LONG [...]`
[ ] Simple cache manager - `touch` a tile when fetched from cache, and have the option to cull long-unused tiles