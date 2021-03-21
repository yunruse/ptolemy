'''
Tile downloader.

'''

import argparse
import os
from itertools import product
import urllib.request

import numpy as np

STAMEN_1X = "http://tile.stamen.com/{kind}/{z}/{x}/{y}.jpg"
STAMEN_2X = STAMEN_1X.replace('.jpg', '@2x.png')
OSM = 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png '

STYLES = {
    # kind: (url, tile_size)
    'watercolor': (STAMEN_1X, 256),
    'toner': (STAMEN_2X, 512),
    'toner-background': (STAMEN_2X, 512),
    'toner-labels': (STAMEN_2X, 512),
    'terrain': (STAMEN_2X, 512),
    'osm': (OSM, 256)
}
# TODO: toner merges background w/ labels
# (to save on network costs)

STORAGE = "tiles/{kind}/{z}/{x}/{y}.jpg"

def grab_file(from_fmt, to_fmt, redownload=False, user_agent=None, **fmt):
    '''
    Download a file with formatted strings.
    Returns output path.
    '''
    out = to_fmt.format(**fmt)
    folder, _ = os.path.split(out)
    if redownload or not os.path.isfile(out):
        if not os.path.exists(folder):
            os.makedirs(folder)
        headers = {}
        if user_agent:
            headers['User-Agent'] = user_agent
        with urllib.request.urlopen(urllib.request.Request(
            from_fmt.format(**fmt), headers=headers
        )) as fin:
            with open(out, 'wb') as fout:
                fout.write(fin.read())
    return out

def get_tiles(url, bounds, zoom, kind, callback=lambda x: None, ):
    (x0, y0), (x1, y1) = bounds
    coords = product(range(x0, x1), range(y0, y1))
    tiles = {}
    for i, c in enumerate(coords):
        tiles[c] = grab_file(url, STORAGE, x=c[0], y=c[1], z=zoom, kind=kind)
        callback(i)
    return tiles

def paint(kind, zoom, bounds, out, debug_marks=False, zoomfactor=0):
    '''
    Stitch tiles given zoom and bounds. 
    '''
    bounds = np.array(bounds)
    bounds.resize((2, 2))
    (url, tile_size) = STYLES[kind]
    if zoomfactor < 0:
        bounds //= int(2 ** -zoomfactor)
    else:
        bounds *= int(2 ** zoomfactor)
    zoom += zoomfactor
    size = (bounds[1]-bounds[0])

    print(f'zoom:     {zoom}')
    print(f'top left: {bounds[0]}')
    print(f'size:     {size}')

    from PIL import Image, ImageDraw

    img = Image.new('RGB', tuple(tile_size * size))
    draw = ImageDraw.Draw(img)

    N = size[0] * size[1]
    tiles = get_tiles(
        url, bounds, zoom, kind,
        lambda i: print(f'{i/N*100:>6.2f}%')
    )
        
    for c, path in tiles.items():
        tile = Image.open(path)
        x, y = tile_size * (c - bounds[0])
        img.paste(tile, (x, y))
        if debug_marks:
            draw.rectangle(
                (x, y, x+tile_size, y+tile_size),
                fill=None, outline='red', width=1)
            draw.text((x+4, y), "{}, {}".format(*m), fill='red')
    img.save(out)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('mode', type=str)
parser.add_argument('zoom', type=int)
parser.add_argument('x0', type=int)
parser.add_argument('y0', type=int)
parser.add_argument('x1', type=int)
parser.add_argument('y1', type=int)
parser.add_argument('--relative', '-r', action='store_true',
                    help='provide (w, h) instead of (x1, y1)')
parser.add_argument('--debug', '-d', action='store_true',
                    help='draw helpful coordinate indicators')
parser.add_argument('--zoomfactor', '-z', type=int, default=0)
parser.add_argument('--out', '-o', type=str, default='out.png')

if __name__ == '__main__':
    args = parser.parse_args()
    if args.relative:
        args.x1 += args.x0
        args.y1 += args.y0
    paint(args.mode, args.zoom, [args.x0, args.y0, args.x1, args.y1],
          out=args.out, zoomfactor=args.zoomfactor, debug_marks=args.debug)
