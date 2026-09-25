#!/usr/bin/env python3
"""Draw the addon's icon for the AddOns list.

    python tools/make_icon.py                   # write DoesItDie/icon.tga
    python tools/make_icon.py --preview <png>   # also a strip at the sizes it is seen at

Drawn at 1024 and shrunk to 64, because the AddOns list shows it at about
twenty pixels and anything drawn at that size directly turns to porridge. It
shows what the addon draws in the game: a health bar whose last stretch is the
striped DoT marker, and the red cross that means "your DoTs finish it".

  - a dark disc with one ring, so it reads on the list's dark and light rows;
  - the cross above, the bar below: two shapes, each still readable at twenty
    pixels, rather than one busy picture;
  - hard stripes and a bright spark at the marker's edge, because a soft
    gradient at twenty pixels is a smudge.

The TGA is 32-bit uncompressed with an alpha channel, which is what the client
reads, and 64 is a power of two, which it insists on.
"""

import pathlib
import sys
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent.parent
BIG = 1024
S = BIG / 64.0   # everything below is in 64-pixel units, scaled up to draw


def disc(size):
    """The dark round plate the rest sits on, with one ring and a highlight."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pad = 0.8 * S
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / size
        gd.line([(0, y), (size, y)],
                fill=(int(26 + 30 * (1 - t)), int(22 + 20 * (1 - t)), int(34 + 30 * (1 - t)), 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([pad, pad, size - pad, size - pad], fill=255)
    img.paste(grad, (0, 0), mask)

    ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse([pad, pad, size - pad, size - pad],
                                 outline=(120, 96, 136, 255), width=int(2.0 * S))
    shine = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shine).ellipse([pad, pad, size - pad, size - pad],
                                  outline=(214, 190, 232, 255), width=int(2.0 * S))
    fade = Image.new("L", (size, size), 0)
    fd = ImageDraw.Draw(fade)
    for y in range(size):
        fd.line([(0, y), (size, y)], fill=max(0, int(255 * (1 - y / (size * 0.62)))))
    ring.paste(shine, (0, 0), fade)
    return Image.alpha_composite(img, ring)


def health_bar(size):
    """Red health, the last stretch of it striped green: what the DoTs still deal."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, x1, y0, y1 = 10 * S, 54 * S, 36 * S, 47 * S
    health_end, marker_start = 46 * S, 29 * S
    d.rounded_rectangle([x0 - 1.2 * S, y0 - 1.2 * S, x1 + 1.2 * S, y1 + 1.2 * S],
                        radius=2.4 * S, fill=(12, 6, 8, 255))                      # frame
    d.rectangle([x0, y0, x1, y1], fill=(46, 18, 20, 255))                           # missing health
    d.rectangle([x0, y0, health_end, y1], fill=(196, 44, 38, 255))                   # health

    stripes = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stripes)
    sd.rectangle([marker_start, y0, health_end, y1], fill=(40, 120, 52, 255))
    step = 4.0 * S
    x = marker_start - (y1 - y0)
    while x < health_end:
        sd.polygon([(x, y1), (x + 2.0 * S, y1), (x + 2.0 * S + (y1 - y0), y0), (x + (y1 - y0), y0)],
                   fill=(110, 226, 120, 255))
        x += step
    clip = Image.new("L", (size, size), 0)
    ImageDraw.Draw(clip).rectangle([marker_start, y0, health_end, y1], fill=255)
    layer.paste(stripes, (0, 0), clip)

    d = ImageDraw.Draw(layer)
    d.rectangle([marker_start - 0.7 * S, y0 - 0.8 * S, marker_start + 0.7 * S, y1 + 0.8 * S],
                fill=(255, 236, 196, 255))                                          # the spark
    return layer


def cross(size):
    """The red cross the addon puts on the portrait when the DoTs will finish the target."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a, b, c, e = (22 * S, 9 * S), (42 * S, 29 * S), (42 * S, 9 * S), (22 * S, 29 * S)
    for p, q in ((a, b), (c, e)):
        d.line([p, q], fill=(26, 8, 8, 220), width=int(7.4 * S))     # outline, for contrast
    for p, q in ((a, b), (c, e)):
        d.line([p, q], fill=(232, 52, 44, 255), width=int(4.8 * S))
    for p, q in ((a, b), (c, e)):
        d.line([(p[0], p[1] - 0.7 * S), (q[0], q[1] - 0.7 * S)], fill=(255, 150, 136, 170), width=int(1.2 * S))
    return layer


def build(size):
    img = disc(size)
    img = Image.alpha_composite(img, health_bar(size))
    return Image.alpha_composite(img, cross(size))


def main():
    big = build(BIG)
    out = HERE / "DoesItDie" / "icon.tga"
    big.resize((64, 64), Image.LANCZOS).save(out)
    if "--preview" in sys.argv:
        target = pathlib.Path(sys.argv[sys.argv.index("--preview") + 1])
        sizes = [64, 32, 20, 16]
        strip = Image.new("RGBA", (sum(sizes) + 20 * (len(sizes) + 1), 80), (40, 40, 44, 255))
        x = 20
        for s in sizes:
            small = big.resize((s, s), Image.LANCZOS)
            strip.paste(small, (x, (80 - s) // 2), small)
            x += s + 20
        strip.resize((strip.width * 3, strip.height * 3), Image.NEAREST).save(target)
        print("preview: %s" % target)
    head = out.read_bytes()[:18]
    print("%s %.1f kB, TGA type %d (2 = uncompressed truecolour), %d bits, %dx%d" % (
        out.relative_to(HERE), out.stat().st_size / 1024, head[2], head[16],
        head[12] | head[13] << 8, head[14] | head[15] << 8))


if __name__ == "__main__":
    main()
