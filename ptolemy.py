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

import numpy as np
from PIL import Image, ImageDraw
import requests

from coords import add_coordinate_options, process_coordinate_niceties
from helpers import font_for_width, get_font

try:
    from projections import PROJECTIONS, project
except:
    PROJECTIONS = {}
    project = None


@dataclass
class Tilemap:
    kind: str
    name: str
    url: str
    tile_size: int

    def __post_init__(self):
        self.user_agent = None
        # TODO: API keys?

    def grab_file(self, to_fmt: str, redownload=False, **fmt):
        out = to_fmt.format(**fmt)
        if redownload or not os.path.isfile(out):
            folder, _ = os.path.split(out)
            if not os.path.exists(folder):
                os.makedirs(folder)

            url = self.url.format(**fmt)
            headers = {}
            if self.user_agent:
                headers['User-Agent'] = self.user_agent
            try:
                r = requests.get(url, headers=headers)
                with open(out, 'wb') as fout:
                    fout.write(r.content)
            except requests.exceptions.HTTPError as e:
                print(url)
                print(e)
                return None
        return out

    def get_tiles(self, bounds, zoom, callback=lambda x: None):
        (x0, y0), (x1, y1) = bounds
        coords = product(range(x0, x1), range(y0, y1))
        tiles = {}
        for i, c in enumerate(coords):
            tiles[c] = self.grab_file(
                STORAGE,
                x=c[0], y=c[1], z=zoom, kind=self.kind)
            callback(i)
        return tiles


with open('tilemaps.csv') as f:
    STYLES: dict[str, Tilemap] = {}
    reader = csv.reader(f)
    next(reader)  # header
    for line in reader:
        assert len(line) == 4, "is there a missed comma in tilemaps.csv?"
        kind, name, url, size = line
        STYLES[kind] = Tilemap(kind, name, url, int(size))

STORAGE = "tiles/{kind}/{z}/{x}/{y}.jpg"

def paint(args):
    '''
    Stitch tiles given zoom and bounds. 
    '''
    styles = [STYLES[s] for s in args.styles]

    bounds = np.array(args.bound, dtype=int).reshape((2, 2))
    print(bounds)
    if args.scale < 0:
        bounds //= int(2 ** -args.scale)
    else:
        bounds *= int(2 ** args.scale)
    size = (bounds[1]-bounds[0])
    N = size[0] * size[1]

    zoom = args.zoom + args.scale
    tile_size = styles[0].tile_size

    print(f'drawing {N} tiles')
    print(f'zoom:     {zoom}')
    print(f'top left: {bounds[0]}')
    print(f'size:     {size}')

    img = Image.new('RGBA', tuple(size * tile_size))
    draw = ImageDraw.Draw(img)

    for style in styles:
        print(f'fetching {style.kind}')
        style.user_agent = args.user_agent

        tiles = style.get_tiles(
            bounds, zoom, lambda i: print(f'{i/N*100:>6.2f}%'))
        for c, path in tiles.items():
            if path is None:
                # TODO: fill with default sea color
                continue
            tile = Image.open(path).convert('RGBA')
            if style.tile_size != tile_size:
                tile = tile.resize((tile_size, tile_size))
            x, y = tile_size * (c - bounds[0])
            img.alpha_composite(tile, (x, y))

    if args.indicators:
        font = get_font()

        # tile coords
        for i, c in enumerate(tiles.keys()):
            x, y = tile_size * (c - bounds[0])
            draw.rectangle(
                (x, y, x+tile_size, y+tile_size),
                fill=None, outline='red', width=1)
            
            text = f"{c[0]}, {c[1]}"
            sized_font = font_for_width(font, text, tile_size * 0.5)
            if i == 0:
                text += f" @ {zoom}"
            w, h = sized_font.getsize(text)
            draw.rectangle(
                (x, y, x+w, y+h), fill='#ffffff')

            draw.text((x+2, y), text, font=sized_font, fill='red')

    # TODO: raise error if projecting and not on Z=0 (?)
    if f := PROJECTIONS.get(args.project):
        print(f'Projecting to {args.project}...')
        img = project(img, f)
    img.save(args.out)


#% ARGUMENT PARSING


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('--zoom', '-z', type=int, default=0,
                    help='zoom factor (doubles per unit)')
parser.add_argument('styles', type=str, nargs='+', choices=STYLES.keys(),
                    help='Map tile source to use, as defined in styles.txt.',)
parser.add_argument('--indicators', '-i', action='store_true',
                    help='Draw helpful coordinate indicators.'
                    'Useful for finding exactly what size you want.')
parser.add_argument('--scale', '-s', metavar='dz', type=int, default=0,
                    help='Zoom factor to scale in by. ')
parser.add_argument('--user-agent', '-u', type=str, default=None,
                    help='HTTP user agent. Provide `_` in place of `/`.')
parser.add_argument('--out', '-o', default=None,
                    help='File to output result to.'
                    ' Defaults to the arguments provided in the current folder,'
                    ' for easy comparison of different options.')
parser.add_argument('--project', '-p', choices=PROJECTIONS.keys(),
                    help='Project to a certain map projection. Works only if viewing whole Earth.')
add_coordinate_options(parser)

if __name__ == '__main__':
    args = parser.parse_args()
    process_coordinate_niceties(args)

    if args.out is None:
        from sys import argv
        # TODO: use paths. make sure `/output/` exists. fix relative paths. etc
        args.out = 'output/' + ' '.join(argv[1:]).replace('/', '_') + '.png'
    if args.user_agent is not None:
        args.user_agent = args.user_agent.replace('_', '/')
    paint(args)
