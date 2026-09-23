"""Generates DoesItDie's textures.

    python tools/make_textures.py

Patterns (white; tinted in-game with SetVertexColor):
DashH<n> / DashV<n>: n px on, n px off, for n in DASH_LENGTHS. Tiled along the outline edges.
Stripes: diagonal hatch, tiled over the damage fill.
Spark: soft vertical glow for the marker's leading edge.
Shine: soft vertical band swept across the marker.

Icons (full color):
Sunglasses: pixel-art "deal with it" shades, one of the lethal-icon choices.

Textures are uncompressed 32-bit TGA with power-of-two sizes. WoW only picks up new files in an
addon folder after a full client restart.
"""
import math
import os
import struct

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "DoesItDie", "Textures")
DASH_LENGTHS = (1, 2, 4, 8, 16)
STRIPES_SIZE = 16
STRIPE_PERIOD = 8
STRIPE_WIDTH = 3


def write_tga(path, width, height, alpha, rgb=None):
    """alpha(x, y) -> True/False for hard patterns, or a 0..1 float for soft ones.
    rgb(x, y) -> (r, g, b) 0..255; white when omitted (patterns are tinted in-game)."""
    header = struct.pack(
        "<BBBHHBHHHHBB",
        0,        # id length
        0,        # no color map
        2,        # uncompressed true-color
        0, 0, 0,  # color map spec
        0, 0,     # x/y origin
        width, height,
        32,       # bits per pixel (BGRA)
        0x28,     # 8 alpha bits, top-left origin
    )
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            a = alpha(x, y)
            r, g, b = rgb(x, y) if rgb else (255, 255, 255)
            pixels += bytes((b, g, r, round(max(0.0, min(1.0, float(a))) * 255)))
    with open(path, "wb") as f:
        f.write(header + pixels)


def main():
    os.makedirs(OUT, exist_ok=True)
    for n in DASH_LENGTHS:
        period = n * 2
        write_tga(os.path.join(OUT, f"DashH{n}.tga"), period, period, lambda x, y, n=n: x < n)
        write_tga(os.path.join(OUT, f"DashV{n}.tga"), period, period, lambda x, y, n=n: y < n)
    write_tga(os.path.join(OUT, "Stripes.tga"), STRIPES_SIZE, STRIPES_SIZE,
              lambda x, y: (x + y) % STRIPE_PERIOD < STRIPE_WIDTH)

    def gaussian(v, center, spread):
        return math.exp(-((v - center) / spread) ** 2)

    # Spark: bright narrow core, soft falloff sideways and toward the ends.
    write_tga(os.path.join(OUT, "Spark.tga"), 16, 64,
              lambda x, y: gaussian(x + 0.5, 8, 3.2) * (1 - abs(y + 0.5 - 32) / 32) ** 0.6)
    # Shine: soft band, full height.
    write_tga(os.path.join(OUT, "Shine.tga"), 32, 16, lambda x, y: gaussian(x + 0.5, 16, 7) * 0.9)

    write_pixel_art(os.path.join(OUT, "Sunglasses.tga"), SUNGLASSES)
    print("wrote", sorted(os.listdir(OUT)))


# 16x16 pixel art, scaled up 4x to 64x64 (square, like the other lethal icons, so it isn't stretched).
# "#" black frame/lens, "o" white glint, "." transparent.
SUNGLASSES = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "################",
    "################",
    ".#o####..#o####.",
    ".##o###..##o###.",
    "..#####...#####.",
    "...###.....###..",
    "................",
    "................",
    "................",
    "................",
    "................",
]
PIXEL_COLORS = {"#": (12, 12, 16), "o": (255, 255, 255)}


def write_pixel_art(path, rows, scale=4):
    size = len(rows) * scale
    write_tga(path, size, size,
              lambda x, y: rows[y // scale][x // scale] != ".",
              lambda x, y: PIXEL_COLORS.get(rows[y // scale][x // scale], (0, 0, 0)))


if __name__ == "__main__":
    main()
