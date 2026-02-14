#!/usr/bin/env python

from dataclasses import dataclass
from inspect import get_annotations

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

    def build_render_graph(self, device, context, display_format):
        self.device = device

        # Create resources

        self.uvs = StorageBuffer(
            name='uvs',
            type_=vec2f,
            shape=(Defaults.SEQ_COUNT, Defaults.SEQ_LENGTH),
        )
        self.canvas = CanvasTexture('display', context, display_format)
        self.image_texture = Texture(
            name='image',
            format='rgba8unorm',
            shape=(*CANVAS_SIZE, 4),
            readable=True,
            renderable=True,
        )

        # Create compute and render passes

        self.particles = (
            ParticleMotionPass()
            .bind_uvs(self.uvs)
        )

        self.drawer = (
            DrawingPass()
            .bind_uvs(self.uvs)
            .bind_color_output(self.image_texture)
        )

        self.copier = (
            CopyPass()
            .bind_input(self.image_texture)
            .bind_color_output(self.canvas)
        )

        # Build the graph

        self.rendergraph = RenderGraph(
            device=device,
            passes=[
                self.particles,
                self.drawer,
                self.copier,
            ],
        )

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
        size = self.canvas.current_size()
        if self._last_size != size:
            self._last_size = size
            self.image_texture.resize(self.device, size)
            self.copier.resize(self.device, size)

        # Run the compute and render passes
        self.rendergraph.execute(self.device)

        self._inc_time(1 / MAX_FPS)

    def _inc_time(self, dt):
        inc = self._parameters.speed * dt
        assert -tau < inc < tau
        self._time += inc
        if self._time < 0:
            self._time += tau
        if self._time >= tau:
            self._time -= tau
     

def main():
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

    bubbler = Bubbler()
    bubbler.build_render_graph(device, context, preferred_format)

    def draw_frame():
        bubbler.draw_frame()

    canvas.request_draw(draw_frame)

    loop.run()

if __name__ == '__main__':
    main()
