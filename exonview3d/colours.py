"""Distinct exon colours.

A hand-picked palette is used first, ordered so that neighbouring exons
contrast strongly. Beyond the palette, hues are stepped by the golden angle,
which keeps any run of consecutive colours well separated, with lightness
alternating so that colours do not repeat.
"""

import colorsys

PALETTE = [
    "#e6194b",  # red
    "#4363d8",  # blue
    "#3cb44b",  # green
    "#f58231",  # orange
    "#911eb4",  # purple
    "#42d4f4",  # cyan
    "#f032e6",  # magenta
    "#bfa100",  # gold
    "#008080",  # teal
    "#9a6324",  # brown
    "#800000",  # maroon
    "#6b8e23",  # olive
    "#000075",  # navy
    "#e377c2",  # pink
    "#2ca02c",  # leaf
    "#17becf",  # sky
]

GOLDEN_ANGLE = 137.50776405003785


def _generated(index):

    hue = ((index * GOLDEN_ANGLE) % 360.0) / 360.0
    lightness = 0.42 if index % 2 == 0 else 0.62

    r, g, b = colorsys.hls_to_rgb(hue, lightness, 0.70)

    return "#{:02x}{:02x}{:02x}".format(
        round(r * 255), round(g * 255), round(b * 255)
    )


def exon_colours(count):
    """Return `count` distinct hex colours."""

    colours = []
    seen = set()

    index = 0

    while len(colours) < count:

        if index < len(PALETTE):
            colour = PALETTE[index]
        else:
            colour = _generated(index)

        index += 1

        if colour in seen:
            continue

        seen.add(colour)
        colours.append(colour)

    return colours
