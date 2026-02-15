#!/usr/bin/env python

import argparse
from dataclasses import dataclass
from inspect import get_annotations
from math import tau
import sys

from rendercanvas.auto import RenderCanvas, loop
import wgpu

from constants import *
from copier import CopyPass
from drawer import DrawingPass
from particle_motion import ParticleMotionPass
from rendergraph import RenderGraph
from resources import CanvasTexture, StorageBuffer, Texture
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
        if self._is_multi_output:
            self.image_texture = Texture(
                name='image',
                format='rgba8unorm',
                shape=(*CANVAS_SIZE, 4), # XXX
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
                (
                    CopyPass()
                    .bind_input(self.image_texture)
                    .bind_color_output(out)
                ) for out in outputs]
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
                for cp in self.copiers[1:]:
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
        size=CANVAS_SIZE,
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
    adapter = wgpu.gpu.request_adapter_sync()
    device = adapter.request_device_sync()

    # basically the same as run() but with update_mode='ondemand'
    # and an extra module in the render graph, and then a main loop
    # that calls request_draw() N times.
    #
    # class RecordingBubbler:
    #     def __init__(): ...
    #     def 


def build_argparser():

    # Main parser and global  args
    parser = argparse.ArgumentParser(
        description='Explore argument parsing',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='count',

        help='show actions (repeat for more)'
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

        help='save to video',
        description='Save to video',
    )
    rec_parser.add_argument(
        '-o', '--output',
        default=Defaults.VIDEO_FILE,

        metavar='FILE',
        help=f'output file (default {Defaults.VIDEO_FILE})'
    )
    rec_parser.add_argument(
        '-d', '--duration',
        type=int,
        default=default_frame_count,

        metavar='FRAMES',
        help=f'video duration (default {default_frame_count})'
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
