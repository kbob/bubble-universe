#!/usr/bin/env python

import argparse
from dataclasses import dataclass
from inspect import get_annotations
from math import tau
import re
import sys

import numpy as np
from rendercanvas.auto import RenderCanvas, loop
import wgpu

from constants import *
from copier import CopyPass
from drawer import DrawingPass
from particle_motion import ParticleMotionPass
from rendergraph import RenderGraph
from resources import CanvasTexture, StorageBuffer, Texture
from video import VideoOutputFile
from wgsl_types import *


class Bubbler:

    @dataclass
    class Parameters:
        seq_count: int = Defaults.SEQ_COUNT
        seq_length: int = Defaults.SEQ_LENGTH
        speed: float = Defaults.SPEED
        r: float = Defaults.R
        particle_size: float = Defaults.PARTICLE_SIZE

        def calc_dt(self, fps):
            return self.speed / fps


    def __init__(self):
        self._parameters = self.Parameters()
        self._time = 0
        self._last_size = None


    def update_parameters(
        self,
        seq_count=None,
        seq_length=None,
        speed=None,
        r=None,
        particle_size=None,
    ):
        loco = locals()
        def update(name):
            if loco[name] is not None:
                setattr(self._parameters, name, loco[name])
        for param in get_annotations(self.Parameters):
            update(param)


    def build_render_graph(self, device, outputs):
        """first renderer controls the output size"""
        assert len(outputs) > 0
        self.device = device
        self.outputs = outputs
        self.resize_controller = self.outputs[0]

        # Create resources

        self.uvs = StorageBuffer(
            name='uvs',
            type_=vec2f,
            shape=(Defaults.SEQ_COUNT, Defaults.SEQ_LENGTH),
        )
        render_size = outputs[0].current_size()
        self._last_size = render_size
        if self._is_multi_output:
            self.image_texture = Texture(
                name='image',
                format='rgba8unorm',
                shape=(*render_size, 4),
                readable=True,
                renderable=True,
            )
            drawing_dest = self.image_texture
        else:
            drawing_dest = outputs[0]

        # Create compute and render passes

        self.particles = (
            ParticleMotionPass()
            .bind_uvs(self.uvs)
        )

        self.drawer = (
            DrawingPass()
            .bind_uvs(self.uvs)
            .bind_color_output(drawing_dest)
        )
        passes = [
            self.particles,
            self.drawer,
        ]

        if self._is_multi_output:
            self.copiers = [
                CopyPass()
                    .bind_input(self.image_texture)
                    .bind_color_output(out)
                for out in outputs]
            passes.extend(self.copiers)

        # create render graph

        self.rendergraph = RenderGraph(device, passes)


    def draw_frame(self):

        # update passes' parameters

        self.particles.update_parameters(
            seq_count=self._parameters.seq_count,
            seq_length=self._parameters.seq_length,
            t=self._time,
            r=self._parameters.r,
        )
        self.drawer.update_parameters(
            seq_count=self._parameters.seq_count,
            seq_length=self._parameters.seq_length,
            particle_size=self._parameters.particle_size,
        )

        # Set intermediate textures' sizes

        size = self.resize_controller.current_size()
        if self._last_size != size:
            self._last_size = size
            if self._is_multi_output:
                self.image_texture.resize(self.device, size)
                self.drawer.bind_color_output(self.image_texture)
                for cp in self.copiers:
                    cp.resize(self.device, size)

        # Run the compute and render passes

        self.rendergraph.execute(self.device)

        # Next!
        self._inc_time(1 / MAX_FPS)

    @property
    def _is_multi_output(self):
        return len(self.outputs) > 1

    def _inc_time(self, dt):
        inc = self._parameters.speed * dt
        assert -tau < inc < tau
        self._time += inc
        if self._time < 0:
            self._time += tau
        if self._time >= tau:
            self._time -= tau
     

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

    bubbler = Bubbler()
    bubbler.build_render_graph(device, [canvas_texture])

    def draw_frame():
        bubbler.draw_frame()

    canvas.request_draw(draw_frame)

    loop.run()


def run_record(args):
    print(f'record: {args = }')
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
    print(f'canvas texture shape = {canvas_texture.current_size()}')
    video_texture = Texture(
        name='video',
        format='rgba8unorm-srgb',
        shape=(*video_res, 4),
        renderable=True,
        readable=True,
    )

    # init video out
    video_out = VideoOutputFile(args.output, video_res, fps=args.fps)

    bubbler = Bubbler()
    bubbler.build_render_graph(device, [video_texture, canvas_texture])

    frame_num = [0]
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
        if frame_num[0] == args.duration:
            loop.stop()
        frame_num[0] += 1

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
