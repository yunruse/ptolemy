'''
Parse coordinate arguments on the command-line.
'''

import argparse

import numpy as np

def ints(string: str):
    return map(int, string.split(','))

OPTINT = dict(type=int, default=None)
OPTINT2 = dict(type=ints, default=None)

def add_coordinate_options(parser: argparse.ArgumentParser):
    coords = parser.add_argument_group('coordinates', description='''\
    Coordinates are from 0 to 2 ^ zoom.
    If you want to keep the same coordinates but increase the tile resolution,
    increase scale; if you increase zoom by 1 you must also double the coordinates
    (and so on.)
    x and y must be provided. If no width options are provided a single tile is produced.
    For convenience you can do `-x1,2` for `-x1 -y2` and likewise for `-W` and `-X`.
    ''')

    coords.add_argument(            '-x',           **OPTINT2, help='x of top-left tile')
    coords.add_argument(            '-y',           **OPTINT,  help='y of top-left tile')
    coords.add_argument('--x1',     '-X', dest='X', **OPTINT2, help='x of bottom-right tile')
    coords.add_argument('--y1',     '-Y', dest='Y', **OPTINT,  help='y of bottom-right tile')
    coords.add_argument('--width',  '-W', dest='W', **OPTINT2, help='width of image')
    coords.add_argument('--height', '-H', dest='H', **OPTINT,  help='y of bottom-right tile')
    coords.add_argument('--radius', '-r', dest='R', **OPTINT,
                        help='Treat (x,y) as the centre of a square and use RADIUS'
                        ' as its width.')
    return coords

def process_coordinate_niceties(args: argparse.Namespace):
    "Parse and produce bounding box for tilemap"
    def get(k):
        return getattr(args, k)
    def set(k, v):
        setattr(args, k, v)
    def exists(k):
        return get(k) is not None

    def pair(xk, yk, yk_defaults_to_xk=False):
        "parse pairs of coordinate-like arguments"
        if not exists(xk):
            # clearly this mode isn't in use
            if exists(yk):
                raise TypeError(f'Cannot define -{yk} but not -{xk}')
            return
        
        XV = get(xk)
        XV = list(XV)

        # cute parsing trick for eg `-x 7,4` `-x7 -y4`
        L = len(XV)
        if L > 2:
            exit(2, f'Only 1 or 2 values to -{xk} allowed!')
        
        set(xk, XV[0])
        if L == 2:
            # -x7,4
            set(yk, XV[1])
        elif yk_defaults_to_xk:
            # -W3 (square)
            set(yk, XV[0])
        else:
            # -x "52.118N 2.325W"

            # -x7 -y4
            if not exists(yk):
                raise TypeError(f'Cannot define -{xk} but not -{yk}')
            # yk is already set

    # x,y parsing
    args.x = args.x or [0]
    args.y = args.y or 0
    pair('x', 'y')

    # PIN      = any(es('x', 'y'))
    ABSOLUTE = exists('X') or exists('Y')
    RELATIVE = exists('W') or exists('H')
    RADIUS   = exists('R')

    N_MODES_USED = ABSOLUTE + RELATIVE + RADIUS
    if N_MODES_USED == 0:
        RELATIVE = True
        args.W = [1]
        args.H = 1
    elif N_MODES_USED > 1:
        exit(2, "Only one 'width mode' (X,Y / W,H / R) can be selected!")

    # only 1 mode, then!

    def setbound(src):
        # safe eval - no user input
        bound = eval(src, None, args.__dict__)
        args.bound = np.array(bound, dtype=int).reshape((2, 2))

    if ABSOLUTE:
        pair('X', 'Y')
        setbound('[x, y, X, Y]')
    elif RELATIVE:
        pair('W', 'H', yk_defaults_to_xk=True)
        setbound('[x, y, x+W, y+H]')
    elif RADIUS:
        setbound('[x-R, y-R, x+R, y+R]')