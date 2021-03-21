'''
Tile downloader.

'''

import argparse
import csv
import os
from itertools import product
import urllib.request

import numpy as np

with open('styles.txt') as f:
    STYLES = {
        kind: (url, size)
        for (kind, url, size)
        in csv.reader(f)
    }

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

def get_tiles(url, bounds, zoom, kind, callback=lambda x: None):
    (x0, y0), (x1, y1) = bounds
    coords = product(range(x0, x1), range(y0, y1))
    tiles = {}
    for i, c in enumerate(coords):
        tiles[c] = grab_file(url, STORAGE, x=c[0], y=c[1], z=zoom, kind=kind)
        callback(i)
    return tiles

def paint(args):
    '''
    Stitch tiles given zoom and bounds. 
    '''
    master_tile_size = STYLES[args.styles[0]][1]
    
    bounds = np.array([[args.x0, args.y0], [args.x1, args.y1]], dtype=int)
    if args.scale < 0:
        bounds //= int(2 ** -args.scale)
    else:
        bounds *= int(2 ** args.scale)
    size = (bounds[1]-bounds[0])
    N = size[0] * size[1]

    zoom = args.zoom + args.scale

    print(f'drawing {N} tiles')
    print(f'zoom:     {zoom}')
    print(f'top left: {bounds[0]}')
    print(f'size:     {size}')

    from PIL import Image, ImageDraw
    img = Image.new('RGB', tuple(size * int(master_tile_size)))
    draw = ImageDraw.Draw(img)
    
    for style in args.styles:
        url, tile_size = STYLES[style]
        # TODO: resample for different sizes?
        assert tile_size == master_tile_size
        
        tiles = get_tiles(
            url, bounds, zoom, style,
            lambda i: print(f'{i/N*100:>6.2f}%')
        )
        for c, path in tiles.items():
            tile = Image.open(path)
            x, y = tile_size * (c - bounds[0])
            img.paste(tile, (x, y))
    
    if args.debug:
        draw.rectangle(
            (x, y, x+tile_size, y+tile_size),
            fill=None, outline='red', width=1)
        draw.text((x+4, y), "{}, {}".format(*m), fill='red')
    img.save(args.out)

epilog = 'Layer styles availale in styles.txt are:\n'
epilog += ', '.join(STYLES.keys())
parser = argparse.ArgumentParser(description=__doc__, epilog=epilog)

parser.add_argument('zoom', type=int, help='zoom factor (doubles per unit)')
parser.add_argument('x0', type=int, help='x of top-left tile')
parser.add_argument('y0', type=int, help='y of top-left tile')
parser.add_argument('x1', type=int, help='x of bottom-right tile')
parser.add_argument('y1', type=int, help='y of bottom-right tile')
parser.add_argument('styles', type=str, nargs='+', help='map tile source')
parser.add_argument('--relative', '-r', action='store_true',
                    help='provide (w, h) instead of (x1, y1)')
parser.add_argument('--debug', '-d', action='store_true',
                    help='draw helpful coordinate indicators')
parser.add_argument('--scale', '-s', metavar='dz', type=int, default=0,
                    help='zoom factor to scale by')
parser.add_argument('--out', '-o', type=str, default='out.png')

if __name__ == '__main__':
    args = parser.parse_args()
    if args.relative:
        args.x1 += args.x0
        args.y1 += args.y0
    paint(args)
