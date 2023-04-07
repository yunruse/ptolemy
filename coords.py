import argparse


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
    A.x = d(A.x, [0])
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