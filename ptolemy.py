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
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFont

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


with open('tilemaps.csv') as f:
    STYLES: dict[str, Tilemap] = {}
    reader = csv.reader(f)
    next(reader)  # header
    for line in reader:
        assert len(line) == 4, "is there a missed comma in tilemaps.csv?"
        kind, name, url, size = line
        STYLES[kind] = Tilemap(kind, name, url, int(size))

STORAGE = "tiles/{kind}/{z}/{x}/{y}.jpg"


def get_font(*names, size=20):
    from matplotlib import font_manager as fm

    names = names or ['Calamity', 'Helvetica', 'Arial']
    return ImageFont.truetype(fm.findfont(fm.FontProperties(family=names)), size=size)

def font_for_width(font: ImageFont.FreeTypeFont, text: str, width: int):
    pixel_w, pixel_h = font.getsize(text)
    return font.font_variant(size=int(font.size * (width / pixel_w)))

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
            if path == 'empty':
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


def exit(code, message):
    print(message, sys.stdout)
    exit(code)


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

coords = parser.add_argument_group('coordinates', description='''\
Coordinates are from 0 to 2 ^ zoom.
If you want to keep the same coordinates but increase the tile resolution,
increase scale; if you increase zoom by 1 you must also double the coordinates
(and so on.)
x and y must be provided. If no width options are provided a single tile is produced.
For convenience you can do `-x1,2` for `-x1 -y2` and likewise for `-W` and `-X`.
''')

def ints(string: str):
    return map(int, string.split(','))

OPTINT = dict(type=int, default=None)
OPTINT2 = dict(type=ints, default=None)

parser.add_argument(            '-x',           **OPTINT2, help='x of top-left tile')
parser.add_argument(            '-y',           **OPTINT,  help='y of top-left tile')
parser.add_argument('--x1',     '-X', dest='X', **OPTINT2, help='x of bottom-right tile')
parser.add_argument('--y1',     '-Y', dest='Y', **OPTINT,  help='y of bottom-right tile')
parser.add_argument('--width',  '-W', dest='W', **OPTINT2, help='width of image')
parser.add_argument('--height', '-H', dest='H', **OPTINT,  help='y of bottom-right tile')
parser.add_argument('--radius', '-r', dest='R', **OPTINT,
                    help='Treat (x,y) as the centre of a square and use RADIUS'
                    ' as its width.')

def process_coordinate_niceties(A: argparse.Namespace):
    "parse and produce bounding box for tilemap"
    # Warning! Here lies a tiny sliver of wondrous madness
    # as does all mathematics I suppose.
    # I just wish Namespace allowed for subscripting...

    # I love a good DSL!

    def g(k):
        "Get"
        return getattr(A, k)
    def s(k, v):
        "Set"
        setattr(A, k, v)

    def d(v, d):
        "Default for keys"
        return d if v is None else v
    
    def e(k):
        "Exists"
        return g(k) is not None

    def es(*ks):
        "Exists (plural)"
        return map(e, ks)


    def pair(xk, yk, yk_defaults_to_xk=False):
        "parse pairs of coordinate-like arguments"
        if not e(xk):
            # clearly this mode isn't in use
            if e(yk):
                raise TypeError(f'Cannot define -{yk} but not -{xk}')
            return
        
        XV = g(xk)
        XV = list(XV)

        # cute parsing trick for eg `-x 7,4` `-x7 -y4`
        print(xk, yk, XV)
        L = len(XV)
        if L > 2:
            exit(2, f'Only 1 or 2 values to -{xk} allowed!')
        
        s(xk, XV[0])
        if L == 2:
            # -x7,4
            s(yk, XV[1])
        elif yk_defaults_to_xk:
            # -W3 (square)
            s(yk, XV[0])
        else:
            # -x7 -y4
            if not e(yk):
                raise TypeError(f'Cannot define -{xk} but not -{yk}')
            # yk is already set

    # x,y parsing
    A.x = d(A.x, 0)
    A.y = d(A.y, 0)

    # PIN      = any(es('x', 'y'))
    ABSOLUTE = any(es('X', 'Y'))
    RELATIVE = any(es('W', 'H'))
    RADIUS   =      e('R')
    pair('x', 'y')

    M = ABSOLUTE + RELATIVE + RADIUS  # N_modes
    if M == 0:
        RELATIVE = True
        A.W = [1]
        A.H = 1
    elif M > 1:
        exit(2, "Only one 'width mode' (X,Y / W,H / R) can be selected!")

    # only 1 mode, then!

    def setbound(src):
        # safe eval - no user input
        A.bound = eval(src, None, A.__dict__)

    if ABSOLUTE:
        pair('X', 'Y')
        setbound('[x, y, X, Y]')
    elif RELATIVE:
        pair('W', 'H', yk_defaults_to_xk=True)
        setbound('[x, y, x+W, y+H]')
    elif RADIUS:
        setbound('[x-R, y-R, x+R, y+R]')


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
