#!/usr/bin/env python

from contextlib import contextmanager
from copy import copy
from dataclasses import dataclass
# from functools import cache
from math import ceil, pi

from cairo import Context, FORMAT_ARGB32, ImageSurface, Rectangle
import numpy as np
from PIL import Image

from colors import Theme
from constants import *
from parameterized import ParameterizedMixIn
from passes import Access, Attachment, Binding, Pass
from wgsl_types import *


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## OverlayPass

class OverlayPass(Pass, ParameterizedMixIn):

    @dataclass
    class Parameters:
        theme: Theme = Theme(Defaults.THEME)
        canvas_size: tuple[int, int] = Defaults.CANVAS_SIZE

    def __init__(self, name='overlay'):
        super().__init__(name)
        self.output = None
        self._prev_state = None

    def resources(self):
        assert self.output is not None
        return [
            Attachment('output', self.output),
        ]

    def attach_output(self, tex):
        self.output = tex
        return self

    def instantiate(self, device):
        # Anything to do?
        ...

    def execute(self, device, encoder):
        if self._prev_state == self._parameters:
            return

        surface = render_overlay(
            self._parameters.canvas_size,
            self._parameters.theme,
            )
        size = (surface.get_width(), surface.get_height())
        data = surface.get_data()
        recast_data = data.cast('I', (*size, 1))
        self.output.write_texture(
            device=device,
            data=recast_data,
            shape={'width': size[0], 'height': size[1]})

        self._prev_state = copy(self._parameters)

    @classmethod
    def overlay_size(cls, canvas_size):
        sz = _Sizes(canvas_size)
        return sz.overlay_pixels


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Overlay rendering in pycairo

# Colors
# N.B., color channels are ordered B, G, R, A.
OUTLINE_COLOR = (0.6, 0.6, 0.6, 1)
TEXT_COLOR = (0.6, 0.6, 0.6, 1)
BACKGROUND_COLOR = (0, 0, 0, 0.6)

# Draw in units of points.  (1 pt. = 1/72 inch ~= 0.353mm)

TEXT_PT_SIZE = 18
BOTTOM_PAD_PT = 30 - 21
SIDE_PAD_PT = 10
OUTLINE_PT_WIDTH = 220          # guess
OUTLINE_PT_HEIGHT = 30
OUTLINE_PT_RADIUS = 5
OUTLINE_PT_STROKE_WIDTH = 0.7

# Fonts
DEFAULT_FONT = 'Open Sans'
THEME_FONTS = {
    Theme.VAPOR: 'Vermin Vibes',
    Theme.MIDNIGHT: 'Creepster',
    Theme.FIESTA: 'Mexican City Free Trial',
    Theme.EASTER: 'Irish Grover',
    Theme.OSCOPE: 'Jupiter',
}
FONT_SCALES = {
    Theme.VAPOR: 1.4,
    Theme.MIDNIGHT: 1.0,
    Theme.FIESTA: 1.2,
    Theme.EASTER: 1.1,
    Theme.OSCOPE: 1.65,
}

class _Sizes:

    """Collect all the size and scaling calculations in one place."""

    def __init__(self, canvas_size):
        self.canvas_size = canvas_size

    @property
    def scale(self):
        canvas_min = min(self.canvas_size)
        return canvas_min / Defaults.CANVAS_SIZE[1]

    @property
    def overlay_pixels(self):
        scale = self.scale
        w = ceil(scale * (OUTLINE_PT_WIDTH + OUTLINE_PT_STROKE_WIDTH))
        oh = ceil(scale * (OUTLINE_PT_HEIGHT + OUTLINE_PT_STROKE_WIDTH))
        return (w, oh)

    @property
    def user_to_device(self):
        return (self.scale, ) * 2


@contextmanager
def push(ctx):
    """save/restore cairo context in a `with` statement"""
    ctx.save()
    yield
    ctx.restore()


def round_rect(ctx, rect, radius):
    with push(ctx):
        ctx.translate(rect.x, rect.y)
        ctx.move_to(rect.width, radius)
        lc = tc = radius
        rc, bc = rect.width - radius, rect.height - radius

        ctx.arc(rc, bc, radius, 0, pi/2)
        ctx.arc(lc, bc, radius, pi/2, pi)
        ctx.arc(lc, tc, radius, pi, 3*pi/2)
        ctx.arc(rc, tc, radius, 3*pi/2, 0)


def draw_overlay(ctx, theme):

    def do_text(draw_function):

        ctx.select_font_face(DEFAULT_FONT)
        ctx.set_font_size(TEXT_PT_SIZE)
        result_a = draw_function('Theme: ')

        ctx.select_font_face(theme_font)
        ctx.set_font_size(theme_font_scale * TEXT_PT_SIZE)
        result_b = draw_function(theme)

        return (result_a, result_b)

    # Theme text.  Label is in Open Sans 18, and the theme name is
    # in its own font with its own scale (relative to 18 pt).
    theme_font = THEME_FONTS.get(theme, DEFAULT_FONT)
    theme_font_scale = FONT_SCALES.get(theme, 1)

    # Calculate text extents to see how wide the outline needs to be.
    results = do_text(ctx.text_extents)
    text_width = sum(r.x_advance for r in results)
    outline_width = text_width + 2 * SIDE_PAD_PT

    # Outline.  Fill with transparent black, then stroke with white.
    outline_rect = Rectangle(0, 0, outline_width, OUTLINE_PT_HEIGHT)
    round_rect(ctx, outline_rect, OUTLINE_PT_RADIUS)
    ctx.set_source_rgba(*BACKGROUND_COLOR)
    ctx.fill_preserve()
    ctx.set_source_rgba(*OUTLINE_COLOR)
    ctx.set_line_width(OUTLINE_PT_STROKE_WIDTH)
    ctx.stroke()

    # Draw the text.
    ctx.move_to(SIDE_PAD_PT, OUTLINE_PT_HEIGHT - BOTTOM_PAD_PT)
    ctx.set_source_rgba(*TEXT_COLOR)
    do_text(ctx.show_text)


def render_overlay(canvas_size, theme):
    sz = _Sizes(canvas_size)

    # init cairo
    surface = ImageSurface(FORMAT_ARGB32, *sz.overlay_pixels)
    ctx = Context(surface)

    # set up transform.
    ohsw = OUTLINE_PT_STROKE_WIDTH / 2
    ctx.scale(*sz.user_to_device)
    ctx.translate(ohsw, ohsw)

    draw_overlay(ctx, theme)
    return surface


def main(argv):
    import os

    test_size = Defaults.CANVAS_SIZE
    # test_size = (1080, 1920)    # portrait
    surface = render_overlay(test_size, Theme.VAPOR)
    size = (surface.get_width(), surface.get_height())
    data = surface.get_data()
    print(f'{size = }')
    print(f'{data = }')
    print(f'{type(data) = }')
    print(f'{data.shape = }')
    print(f'{data.strides = }')
    print(f'{data.nbytes = }')

    recast_data = data.cast('B', (*size, 4))

    print(f'{recast_data.shape = }')
    print(f'{recast_data.strides = }')
    print(f'{recast_data.nbytes = }')

    surface.write_to_png('overlays.png')
    os.system('open overlays.png')


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
