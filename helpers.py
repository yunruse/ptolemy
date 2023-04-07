"Various generic helpers for Ptolemy"

import sys
from PIL import ImageFont

def get_font(*names, size=20):
    "Get a PIL font by its name"
    from matplotlib import font_manager as fm
    names = names or ['Calamity', 'Helvetica', 'Arial']
    return ImageFont.truetype(fm.findfont(fm.FontProperties(family=names)), size=size)

def font_for_width(font: ImageFont.FreeTypeFont, text: str, width: int):
    "Get a font, its size such that text will have a given width"
    pixel_w, pixel_h = font.getsize(text)
    return font.font_variant(size=int(font.size * (width / pixel_w)))

def exit(code, message):
    print(message, sys.stdout)
    exit(code)