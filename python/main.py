#!/usr/bin/env python

import argparse
from math import tau
import re
import sys

import numpy as np
from rendercanvas.auto import RenderCanvas, loop
import wgpu

from bubbler import Bubbler
from colors import Theme
from constants import *
from resources import CanvasTexture, Texture
from video import VideoOutputFile


def run(args):

    # Process command
    recording_video = False
    duration = float('inf')
    if args.cmd == 'record':
        recording_video = True
        duration = args.duration
    else:
        assert args.cmd is None

    # Init wgsl
    adapter = wgpu.gpu.request_adapter_sync()
    device = adapter.request_device_sync()

    # Init the on-screen canvas
    output_res = args.resolution
    canvas = RenderCanvas(
        size=output_res,
        title=WINDOW_TITLE,
        update_mode='continuous',
        max_fps=args.fps,
    )
    context = canvas.get_wgpu_context()
    preferred_format = context.get_preferred_format(adapter)
    context.configure(device=device, format=preferred_format)
    canvas_texture = CanvasTexture('display', context, preferred_format)
    output_textures = [canvas_texture]

    # Init the video file output
    if recording_video:
        video_texture = Texture(
            name='video',
            format='rgba8unorm-srgb',
            shape=(*output_res, 4),
            renderable=True,
            readable=True,
        )
        video_out = VideoOutputFile(args.output, output_res, fps=args.fps)
        # video texture comes first because it controls the output resolution
        output_textures = [video_texture] + output_textures

    # Init the bubbler
    bubbler = Bubbler()
    bubbler.update_parameters(fps=args.fps, theme=args.theme)
    bubbler.build_render_graph(
        device=device,
        outputs=output_textures,
        use_HDR=args.hdr,
    )

    # Define the main loop
    frame_num = 0

    if args.cycle_themes:
        from itertools import cycle
        from math import isfinite

        fn2 = 0
        if isfinite(duration):
            theme_count = len(Theme)
            theme_frame_count = duration // theme_count
        else:
            theme_frame_count = args.fps * 3
        tfc = theme_frame_count
        tff = theme_fade_frames = round(0.2 * tfc)
        ofif = overlay_fadein_frames = round(0.1 * tfc)
        ofof = overlay_fadeout_frames = round(0.4 * tfc)
        ofisf = overlay_fadein_start_frame = 0
        tfsf = theme_fade_start_frame = tfc - tff
        ofosf = overlay_fadeout_start_frame = tfsf - ofof
        # print(f'run: ')
        # print(f'    {theme_frame_count = }')
        # print(f'    {overlay_fadein_start_frame = }')
        # print(f'    {overlay_fadeout_start_frame = }')
        # print(f'    {theme_fade_start_frame = }')

        # print(f'    {theme_fade_frames = }')
        # print(f'    {overlay_fadein_frames = } ')
        # print(f'    {overlay_fadeout_frames = }')

        theme_rotor = cycle(Theme)
        next(theme_rotor)       # skip Classic


    def draw_frame():

        nonlocal frame_num

        if args.cycle_themes:
            nonlocal fn2
            if ofisf <= fn2 < ofisf + ofif:
                # fading overlay in
                ovl = _smoothstep(ofisf, ofisf + ofif, fn2)
            elif fn2 < ofosf:
                # overlay is in
                ovl = 1
            elif ofosf <= fn2 < ofosf + ofof:
                # fading overlay out
                ovl = _smoothstep(ofosf + ofof, ofosf, fn2)
            else:
                ovl = 0
            bubbler.update_parameters(overlay_amount=ovl)
            if fn2 == tfsf:
                new_theme = next(theme_rotor)
                bubbler.change_theme(new_theme, frames=theme_fade_frames)

            fn2 += 1
            if fn2 == theme_frame_count:
                fn2 = 0

        bubbler.draw_frame()
        frame_num += 1

        if recording_video:
            texture_data = video_texture.read_texture(device)
            image_data = (np
                .frombuffer(texture_data, dtype=np.uint8)
                .reshape((*output_res[::-1], 4))
            )
            video_out.append_frame(image_data)

            if frame_num == duration:
                loop.stop()

    # Run the main loop
    canvas.request_draw(draw_frame)
    loop.run()

    # Finish
    if recording_video:
        video_out.close()


def _smoothstep(e0, e2, x):
    assert e0 != e2
    sx = max(0, min(1, (x - e0) / (e2 - e0)))
    return -2 * sx**3 + 3 * sx**2


def list_themes():
    print('Available themes:')
    for theme in Theme:
        if theme == Defaults.THEME:
            default_label = ' (default)'
        else:
            default_label = ''
        print(f'    {theme!s}{default_label}')


def build_argparser():

    def resolution(s):
        # function name appears in an error message.
        m = re.match(r'(\d+)x(\d+)', s)
        if not m:
            raise ValueError('your mother dresses you funny')
        return (int(m.group(1)), int(m.group(2)))


    # Main parser and global args
    parser = argparse.ArgumentParser(
        prefix_chars='-+',
        allow_abbrev=True,

        description='Explore the bubble universe',
    )
    parser.add_argument(
        '-t', '--theme',
        type=Theme.from_string,
        default=Theme(Defaults.THEME),
        
        help=f'set theme (default {Defaults.THEME})',
    )
    parser.add_argument(
        '-c', '--cycle-themes',
        action='store_true',

        help='cycle through all themes',
    )
    parser.add_argument(
        '-r', '--resolution',
        type=resolution,
        default=Defaults.CANVAS_SIZE,

        help=
            f'set video resolution '
            f'(default {Defaults.CANVAS_SIZE[0]}x{Defaults.CANVAS_SIZE[1]})',
    )
    parser.add_argument(
        '+h', '--no-hdr',
        dest='hdr',
        action='store_false',

        help='do not render in high dynamic range (HDR)'
    )
    parser.add_argument(
        '-f', '--fps',
        type=int,
        default=MAX_FPS,

        help=f'set frames per second (default {MAX_FPS})',
    )
    subparsers = parser.add_subparsers(
        dest='cmd',

        title='Subcommands',
        help='Action',
        metavar='Command',
    )

    # 'list-themes' subcommand
    theme_parser = subparsers.add_parser(
        'list-themes',

        help='list available themes',
        description='List available themes',
    )


    # 'record' subcommand
    default_frame_count = round(tau / Defaults.SPEED * MAX_FPS)
    rec_parser = subparsers.add_parser(
        'record',

        help='record video to a file',
        description='Record video to a file',
    )
    rec_parser.add_argument(
        '-o', '--output',
        default=Defaults.VIDEO_FILE,

        metavar='FILE',
        help=f'output file (default {Defaults.VIDEO_FILE})',
    )
    rec_parser.add_argument(
        '-d', '--duration',
        type=int,
        default=default_frame_count,

        metavar='FRAMES',
        help=f'video duration (default {default_frame_count})',
    )
    return parser


def main():
    parser = build_argparser()
    args = parser.parse_args(sys.argv[1:])
    if args.cmd == 'list-themes':
        list_themes()
    else:
        run(args)

if __name__ == '__main__':
    main()
