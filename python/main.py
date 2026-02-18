#!/usr/bin/env python

import argparse
from math import tau
import sys

import numpy as np
from rendercanvas.auto import RenderCanvas, loop
import wgpu

from bubbler import Bubbler
from bubbler_HDR import BubblerHDR
from constants import *
from resources import CanvasTexture, Texture
from video import VideoOutputFile


def run(args):
    adapter = wgpu.gpu.request_adapter_sync()
    device = adapter.request_device_sync()

    canvas = RenderCanvas(
        size=Defaults.CANVAS_SIZE,
        title='Bubble Universe',
        update_mode='continuous',
        max_fps=MAX_FPS,
        )
    context = canvas.get_wgpu_context()
    preferred_format = context.get_preferred_format(adapter)
    context.configure(device=device, format=preferred_format)

    canvas_texture = CanvasTexture('display', context, preferred_format)

    if USE_HDR:
        bubbler = BubblerHDR()
    else:
        bubbler = Bubbler()
    bubbler.build_render_graph(device, [canvas_texture])

    def draw_frame():
        bubbler.draw_frame()

    canvas.request_draw(draw_frame)

    loop.run()


def run_record(args):
    video_res = args.resolution
    adapter = wgpu.gpu.request_adapter_sync()
    device = adapter.request_device_sync()

    canvas = RenderCanvas(
        size=video_res,
        title='Bubble Universe',
        update_mode='continuous',
        max_fps=args.fps,
        )
    context = canvas.get_wgpu_context()
    preferred_format = context.get_preferred_format(adapter)
    context.configure(device=device, format=preferred_format)

    canvas_texture = CanvasTexture('display', context, preferred_format)
    video_texture = Texture(
        name='video',
        format='rgba8unorm-srgb',
        shape=(*video_res, 4),
        renderable=True,
        readable=True,
    )

    # init video out
    video_out = VideoOutputFile(args.output, video_res, fps=args.fps)

    if USE_HDR:
        bubbler = BubblerHDR()
    else:
        bubbler = Bubbler()
    bubbler.build_render_graph(device, [video_texture, canvas_texture])

    frame_num = 0

    def draw_frame():
        bubbler.draw_frame()

        # read frame and save to video file
        texture_data = video_texture.read_texture(device)
        image_data = (
            np.frombuffer(texture_data, dtype=np.uint8)
            .reshape((*video_res[::-1], 4))
        )
        video_out.append_frame(image_data)

        # stop after enough frames
        nonlocal frame_num
        frame_num += 1
        if frame_num == args.duration:
            loop.stop()

    canvas.request_draw(draw_frame)

    loop.run()
    video_out.close()


def build_argparser():

    def resolution(s):
        # function name appears in an error message.
        m = re.match(r'(\d+)x(\d+)', s)
        if not m:
            raise ValueError('your mother dresses you funny')
        return (int(m.group(1)), int(m.group(2)))


    # Main parser and global  args
    parser = argparse.ArgumentParser(
        description='Explore the bubble universe',
    )
    # parser.add_argument(
    #     '-v', '--verbose',
    #     action='count',

    #     help='show actions (repeat for more)',
    # )
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
        '-r', '--resolution',
        type=resolution,
        default=Defaults.CANVAS_SIZE,

        help=f'set video resolution (default {Defaults.CANVAS_SIZE})',
    )
    rec_parser.add_argument(
        '-f', '--fps',
        type=int,
        default=MAX_FPS,

        help=f'set frames per second (default {MAX_FPS})',
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
    if args.cmd == 'record':
        run_record(args)
    else:
        assert args.cmd is None
        run(args)

if __name__ == '__main__':
    main()
