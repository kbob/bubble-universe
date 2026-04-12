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
    bubbler.update_parameters(fps=args.fps)
    bubbler.build_render_graph(
        device=device,
        outputs=output_textures,
        use_HDR=args.hdr,
    )

    # Define the main loop
    frame_num = 0

    CYCLE_THEMES = False
    if CYCLE_THEMES:
        from itertools import cycle
        from math import isfinite

        fn2 = 0
        cycle_frame_count = round(tau / Defaults.SPEED * args.fps)
        if isfinite(duration):
            theme_count = len(list(Theme))
            theme_frame_count = cycle_frame_count // theme_count
        else:
            theme_frame_count = args.fps * 3

        theme_rotor = cycle(Theme)
        next(theme_rotor) # skip Classic


    def draw_frame():

        nonlocal frame_num

        # tdf = (frame_num % 1000) / 1000
        # tdf = 1
        # bubbler.update_parameters(
        #     # r=1,
        #     seq_count=80,
        #     seq_length=50,
        #     # particle_size=0.707,
        #     particle_size=1.414,
        #     trail_persistence=0.94,
        #     trail_diffusion=0.9,
        #     bloom_amount=0.0,
        # )

        if CYCLE_THEMES:
            nonlocal fn2
            fn2 += 1
            if fn2 == theme_frame_count:
                new_theme = next(theme_rotor)
                bubbler.change_theme(new_theme, frames=40)
                fn2 = 0

        bubbler.draw_frame()

        if recording_video:
            texture_data = video_texture.read_texture(device)
            image_data = (np
                .frombuffer(texture_data, dtype=np.uint8)
                .reshape((*output_res[::-1], 4))
            )
            video_out.append_frame(image_data)

            frame_num += 1
            if frame_num == duration:
                loop.stop()

    # Run the main loop
    canvas.request_draw(draw_frame)
    loop.run()

    # Finish
    if recording_video:
        video_out.close()


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
        '-r', '--resolution',
        type=resolution,
        default=Defaults.CANVAS_SIZE,

        help=f'set video resolution (default {Defaults.CANVAS_SIZE})',
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
    run(args)

if __name__ == '__main__':
    main()
