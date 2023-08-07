'''
Parse coordinate arguments on the command-line.
'''

import argparse
import re
from math import ceil, floor, log, tan, pi
from typing import Callable

from helpers import exit

import numpy as np

OPTINT = dict(type=int, default=None)
OPTINT2 = dict(default=None)

COORD = r'''
([-+]?)  # sign
(?:
    (\d+) \s* °  # degrees
\s* (\d+) \s* [′']  # minutes
\s* (?: (\d+ (?:\.\d+)?) \s* [″\"])?  # seconds
|
    (\d+ (?:\.\d+)? \s* °?)  # decimal
)
'''
LETTER = r'\s*([NSEW])?'

A = rf'^{COORD}{LETTER}[,\s]\s*{COORD}{LETTER}$'
COORDINATES = re.compile(A, re.VERBOSE)

def _process_coord(sign: str, degrees: str | None, minutes: str | None, seconds: str | None, decimal: str | None, letter: str):

    if decimal is not None:
        result = float(decimal)
    else:
        result = int(degrees)
        result += int(minutes) / 60
        result += int(seconds) / 3600

    if sign == '-' or (letter or '') in 'SW':
        result *= -1

    return result, letter



def parse_longlat(match: re.Match[str]):
    """
    Parse eg '47.61N 122.33W' into long,lat coords
    Takes the results of COORDINATES.match
    """
    # TODO: parse e.g. 51° 30′ 26″
    m: tuple[str | None] = match.groups()
    a, a_letter = _process_coord(*m[:6])
    b, b_letter = _process_coord(*m[6:])

    if not a_letter and not b_letter:
        # simple lat,long coords
        return b, a
    if not a_letter or not b_letter:
        raise ValueError('Invalid compass directions')

    if b_letter in 'NS':
        if a_letter not in 'EW':
            raise ValueError('Invalid compass directions')
        return a, b
    else:
        if a_letter not in 'NS':
            raise ValueError('Invalid compass directions')
        return b, a


def longlat_to_mercator(long: float, lat: float):
    "Convert longitude and geodetic latitude (in degrees) to unscaled Web Mercator in [0, 1]"
    return (
        (long + 180) / 360,
        (pi - log(tan(pi/4 + lat*pi/360))) / (pi * 2)
    )

def add_coordinate_options(parser: argparse.ArgumentParser):
    coords = parser.add_argument_group('coordinates', description='''\
    Coordinates are from 0 to 2 ^ zoom.
    If you want to keep the same coordinates but increase the tile resolution,
    increase scale; if you increase zoom by 1 you must also double the coordinates
    (and so on.)
    x and y must be provided. If no width options are provided a single tile is produced.
    For convenience you can do `-x1,2` for `-x1 -y2` and likewise for `-W` and `-X`.
    ''')

    coords.add_argument('--x0',     '-x', dest='x', **OPTINT2, help='x of top-left tile')
    coords.add_argument('--y0',     '-y', dest='y', **OPTINT,  help='y of top-left tile')
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

    CoordFunc = Callable[[float | int], int] | None
    def pair(xk: str, yk: str, yk_defaults_to_xk=False, coord_func: CoordFunc = None):
        "parse pairs of coordinate-like arguments"
        if not exists(xk):
            # clearly this mode isn't in use
            if exists(yk):
                raise TypeError(f'Cannot define -{yk} but not -{xk}')
            return
        
        XV = get(xk)

        match = COORDINATES.match(XV)
        if coord_func is not None and match:
            
            # TODO: swap out coord_func for a nicer handler
            # that works better with --radius?

            # 38.904 N, 77.016 E
            x, y = longlat_to_mercator(*parse_longlat(match))
            set(xk, coord_func(x * 2**args.zoom))
            set(yk, coord_func(y * 2**args.zoom))
            return
        
        try:
            XV = [int(x) for x in XV.split(',')]
        except ValueError:
            exit(2, f'Error in parsing: {XV!r} is not an integer')

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
            # -x7 -y4
            if not exists(yk):
                raise TypeError(f'Cannot define -{xk} but not -{yk}')

    # x,y parsing
    args.x = args.x or 0
    args.y = args.y or 0
    pair('x', 'y', coord_func=floor)

    # PIN      = any(es('x', 'y'))
    ABSOLUTE = exists('X') or exists('Y')
    RELATIVE = exists('W') or exists('H')
    RADIUS   = exists('R')

    N_MODES_USED = ABSOLUTE + RELATIVE + RADIUS
    if N_MODES_USED == 0:
        RELATIVE = True
        args.W = '1'
        args.H = '1'
    elif N_MODES_USED > 1:
        exit(2, "Only one 'width mode' (X,Y / W,H / R) can be selected!")

    # only 1 mode, then!

    def setbound(src):
        # safe eval - no user input
        bound = eval(src, None, args.__dict__)
        args.bound = np.array(bound, dtype=int).reshape((2, 2))

    if ABSOLUTE:
        pair('X', 'Y', coord_func=ceil)
        setbound('[x, y, X, Y]')
    elif RELATIVE:
        pair('W', 'H', yk_defaults_to_xk=True)
        setbound('[x, y, x+W, y+H]')
    elif RADIUS:
        setbound('[x-R, y-R, x+R, y+R]')