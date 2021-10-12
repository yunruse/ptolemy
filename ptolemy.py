'''
Ptolemy: a mapping tile fetch-and-stitch tool.

Tiles are fetches to the tiles/ folder for caching/use,
and the output is stitched together with optional debugging symbols.
'''

import argparse
import csv
import os
from itertools import product
import urllib.request
import sys

import numpy as np
from PIL import Image, ImageDraw

from projections import PROJECTIONS, project

class Tilemap:
    def __init__(self, kind, url, size):
        self.kind = kind
        self.url = url
        self.tile_size = int(size)
        self.user_agent = None
        # TODO: API keys?

    def grab_file(self, to_fmt, redownload=False, **fmt):
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
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request) as fin:
                    with open(out, 'wb') as fout:
                        fout.write(fin.read())
            except urllib.error.HTTPError as e:
                print(url)
                print(e)
                return 'empty'
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

with open('styles.txt') as f:
    STYLES = {
        kind: Tilemap(kind, url, size)
        for (kind, url, size)
        in csv.reader(f)
    }

STORAGE = "tiles/{kind}/{z}/{x}/{y}.jpg"

def paint(args):
    '''
    Stitch tiles given zoom and bounds. 
    '''
    styles = []
    for s in args.styles:
        # TODO: custom zoom for each style?
        styles.append(STYLES[s])
    
    bounds = np.array([[args.x0, args.y0], [args.x1, args.y1]], dtype=int)
    if args.scale < 0:
        bounds //= int(2 ** -args.scale)
    else:
        bounds *= int(2 ** args.scale)
    size = (bounds[1]-bounds[0])
    N = size[0] * size[1]

    zoom = args.zoom + args.scale
    S = styles[0].tile_size

    print(f'drawing {N} tiles')
    print(f'zoom:     {zoom}')
    print(f'top left: {bounds[0]}')
    print(f'size:     {size}')
    
    img = Image.new('RGBA', tuple(size * S))
    draw = ImageDraw.Draw(img)

    
    for style in styles:
        print(f'fetching {style.kind}')
        style.user_agent = args.user_agent
        
        tiles = style.get_tiles(
            bounds, zoom, lambda i: print(f'{i/N*100:>6.2f}%'))
        for c, path in tiles.items():
            if path == 'empty':
                # TODO: fill with default sea color
                continue
            tile = Image.open(path).convert('RGBA')
            if style.tile_size != S:
                tile = tile.resize((S, S))
            x, y = S * (c - bounds[0])
            img.alpha_composite(tile, (x, y))

    if args.indicators:
        for c in tiles.keys():
            x, y = S * (c - bounds[0])
            text = "{}, {}".format(*c)
            draw.rectangle(
                (x, y, x+6*len(text)+1, y+10),
                fill='white')
            draw.rectangle(
                (x, y, x+style.tile_size, y+style.tile_size),
                fill=None, outline='red', width=1)
            draw.text((x+2, y), text, fill='red')

    if f := PROJECTIONS.get(args.project):
        print(f'Projecting to {args.project}...')
        img = project(img, f)
    img.save(args.out)

epilog = '''\
Coordinates are from 0 to 2 ^ zoom.
If you want to keep the same coordinates but increase the tile resolution,
increas scale; if you increase zoom by 1 you must also double the coordinates
(and so on.)
x and y must be provided. (x1,y1) and (width, height) must be provided together.
If multiple options for size are provided, precedence is established in the order
(x1, y1) > (width, height) > radius.
'''
parser = argparse.ArgumentParser(description=__doc__, epilog=epilog)

OPTINT = dict(type=int, default=None)
parser.add_argument('--zoom', '-z', type=int, default=0, help='zoom factor (doubles per unit)')
parser.add_argument('-x', **OPTINT, help='x of top-left tile')
parser.add_argument('-y', **OPTINT, help='y of top-left tile')
parser.add_argument('--x1', **OPTINT, help='x of bottom-right tile')
parser.add_argument('--y1', **OPTINT, help='y of bottom-right tile')
parser.add_argument('--width', '-W', **OPTINT, help='width of image')
parser.add_argument('--height', '-H', **OPTINT, help='y of bottom-right tile')
parser.add_argument('--radius', '-r', **OPTINT,
                    help='Treat (x,y) as the centre of a square and use RADIUS'
                    ' as its width.')
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
                    help='Project to a certain map projection.')

def exit(code, message):
    print(message, sys.stdout)
    exit(code)

if __name__ == '__main__':
    args = parser.parse_args()
    # x,y parsing
    if not (args.x and args.y):
        args.x0 = args.y0 = 0
        args.x1 = args.y1 = 1
        
    elif args.x1 or args.y1:
        if not (args.x1 and args.y1):
            exit(2, "--x1 and --y1 must both be present")
    elif args.width or args.height:
        if not (args.width and args.height):
            exit(2, "--width and --height must both be present")
        args.x1 = args.x + args.width
        args.y1 = args.y + args.width
    elif args.radius:
        args.x0 = args.x - args.radius
        args.y0 = args.y - args.radius
        args.x1 = args.x + args.radius
        args.y1 = args.y + args.radius
    
    if args.out is None:
        from sys import argv
        args.out = ' '.join(argv[1:]).replace('/', '_') + '.png'
    if args.user_agent is not None:
        args.user_agent = args.user_agent.replace('_', '/')
    paint(args)
