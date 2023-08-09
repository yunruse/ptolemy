'''
Ptolemy: a mapping tile fetch-and-stitch tool.

Tiles are fetches to the tiles/ folder for caching/use,
and the output is stitched together with optional coordinates to help you find what you want to map.
A useful start is `-s3 -i [style]` - this will show you the whole world split into 8x8 to further zoom in on.
'''

import argparse
import csv
import os
from itertools import product
from dataclasses import dataclass
from pathlib import Path
from math import floor, ceil

from PIL import Image, ImageDraw
import requests
from alive_progress import alive_bar, alive_it

from coords import add_coordinate_options, process_coordinate_niceties
from helpers import font_for_width, get_font

try:
    from projections import PROJECTIONS, project
except:
    PROJECTIONS = {}
    project = None

CACHE = os.path.expanduser(os.environ.get('XDG_CACHE_HOME', '~/.cache'))
STORAGE = CACHE + "/ptolemy/{kind}/{z}/{x}/{y}.jpg"

@dataclass(slots=True)
class Tile:
    path: str
    was_downloaded: bool

@dataclass(slots=True)
class Tilemap:
    kind: str
    name: str
    url: str
    tile_size: int
    user_agent: str | None = None

    def grab_file(self, to_fmt: str, redownload=False, **fmt):
        out = to_fmt.format(**fmt)

        download = redownload or not os.path.isfile(out)
        if download:
            folder, _ = os.path.split(out)
            if not os.path.exists(folder):
                os.makedirs(folder)

            url = self.url.format(**fmt)
            headers = {}
            if self.user_agent:
                headers['User-Agent'] = self.user_agent
            try:
                r = requests.get(url, headers=headers)
                r.raise_for_status()
                with open(out, 'wb') as fout:
                    fout.write(r.content)
            except requests.exceptions.HTTPError as e:
                print(e)
                exit(10)
        return Tile(out, download)

    Bound = tuple[tuple[float, float], tuple[float, float]]

    def get_tiles(self, bounds: Bound, zoom: int):
        (x0, y0), (x1, y1) = bounds
        x0 = floor(x0)
        y0 = floor(y0)
        x1 = ceil(x1)
        y1 = ceil(y1)

        tiles: dict[tuple[int, int], Tile] = {}
        with alive_bar(total=int((y1-y0) * (x1-x0)), title=f'Fetching {self.kind}...') as bar:
            for x, y in product(range(x0, x1), range(y0, y1)):
                tile = self.grab_file(STORAGE, x=x, y=y, z=zoom, kind=self.kind)
                tiles[x, y] = tile
                bar(skipped=not tile.was_downloaded)
            
        return tiles


with open('tilemaps.csv') as f:
    STYLES: dict[str, Tilemap] = {}
    reader = csv.reader(f)
    next(reader)  # header
    for line in reader:
        assert len(line) == 4, "is there a missed comma in tilemaps.csv?"
        kind, name, url, size = line
        STYLES[kind] = Tilemap(kind, name, url, int(size))

def paint(args):
    '''
    Stitch tiles given zoom and bounds. 
    '''
    styles = [STYLES[s] for s in args.styles]

    if args.scale < 0:
        args.bound //= int(2 ** -args.scale)
    else:
        args.bound *= int(2 ** args.scale)
    size = (args.bound[1]-args.bound[0])

    zoom = args.zoom + args.scale
    tile_size = styles[0].tile_size

    img = Image.new('RGBA', tuple(size * tile_size))
    draw = ImageDraw.Draw(img)

    for style in styles:
        style.user_agent = args.user_agent

        tiles = style.get_tiles(args.bound, zoom)
        for c, tile in alive_it(tiles.items(), title=f'Painting {style.kind}...'):
            if tile.path is None:
                # TODO: fill with default sea color
                continue
            tile = Image.open(tile.path).convert('RGBA')
            if style.tile_size != tile_size:
                tile = tile.resize((tile_size, tile_size))
            x, y = tile_size * (c - args.bound[0])
            img.alpha_composite(tile, (x, y))

    if args.indicators:
        font = get_font()

        # tile coords

        coords = enumerate(tiles.keys())
        for i, c in alive_it(coords, title='Adding indicators...'):
            x, y = tile_size * (c - args.bound[0])
            draw.rectangle(
                (x, y, x+tile_size, y+tile_size),
                fill=None, outline='red', width=1)
            
            text = f"{c[0]}, {c[1]}"
            sized_font = font_for_width(font, text, tile_size * 0.5)
            if i == 0:
                text += f" @ {zoom}"
            _, _, w, h = sized_font.getbbox(text, anchor='lt')
            draw.rectangle(
                (x, y, x+w, y+h), fill='#ffffff')

            draw.text((x+2, y), text, font=sized_font, fill='red')

    # TODO: raise error if projecting and not on Z=0 (?)
    if f := PROJECTIONS.get(args.project):
        print(f'Projecting to {args.project}...')
        img = project(img, f)
    print(f'Saving to: {args.out}')
    img.save(args.out)


#% ARGUMENT PARSING


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('--zoom', '-z', type=int, default=0,
                    help='zoom factor (doubles per unit)')
parser.add_argument('styles', type=str, nargs='+', choices=STYLES.keys(), metavar='STYLE',
                    help='Map tile source(s) to use, as defined in tilemaps.csv.'
                    ' Choices are: %(choices)s')
parser.add_argument('--indicators', '-i', action='store_true',
                    help='Draw helpful coordinate indicators.')
parser.add_argument('--scale', '-s', metavar='dz', type=int, default=0,
                    help='Zoom factor to scale in by. ')
parser.add_argument('--user-agent', '-u', type=str, default=None,
                    help='HTTP user agent for fetching.')
parser.add_argument('--out', '-o', default=None,
                    help='File to output result to.'
                    ' Defaults to output/<args>.png.')
parser.add_argument('--project', '-p', choices=PROJECTIONS.keys(),
                    help='Project to a certain map projection. Works only if viewing whole Earth.')
add_coordinate_options(parser)

if __name__ == '__main__':
    args = parser.parse_args()
    process_coordinate_niceties(args)

    Path('./output').mkdir(exist_ok=True)

    if args.out is None:
        from sys import argv
        # TODO: use paths. make sure `/output/` exists. fix relative paths. etc
        args.out = 'output/' + ' '.join(argv[1:]).replace('/', '_') + '.png'
    paint(args)
