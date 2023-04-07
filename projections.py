from PIL import Image, ImageDraw
from math import sin, cos, pi, asin

def lerp(x, a, b):
    return a + (b-a)*x

def xy_to_longlat(x, y):
    '''assuming x, y in [0, 1], returns lat-long pair in radians'''
    
    return lerp(x, -pi, pi), lerp(y, -pi/2, pi/2)

def eckert_iv(lat, long, central_lat=0):
    '''quick Eckert algorithm'''
    # x + sin(x)cos(x) + 2sin(x) = (2+pi/2) sin(theta)
    x = long
    # very naively inverted by wolfram|alpha
    theta = asin(2 * (x + 2*sin(x) + sin(x)*cos(x)) / (4+pi))

    SCALE = 0.18824
    return (
        0.5 + SCALE * 0.422_2382 * (lat-central_lat) * (1 + cos(theta)),
        0.5 + SCALE * 1.326_5004 * sin(theta)
    )

PROJECTIONS = {'eckert_iv': eckert_iv}

def project(img: Image, function, size=None):
    new = Image.new("RGBA", size or img.size)
    draw = ImageDraw.Draw(new)
    for x in range(img.width):
        long = lerp(x / img.width, -pi, pi)
        for y in range(img.height):
            lat = lerp(y / img.height, -pi/2, pi/2)
            
            (xn, yn) = function(long, lat)
            draw.point(
                (int(xn*new.width), int(yn*new.height)),
                img.getpixel((x, y)))

    return new
