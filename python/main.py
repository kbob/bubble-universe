#!/usr/bin/env python

from dataclasses import dataclass
from inspect import get_annotations
from math import tau

from rendercanvas.auto import RenderCanvas, loop
import wgpu

from constants import *
from drawer import DrawingPass
from particle_motion import ParticleMotionPass
from rendergraph import RenderGraph
from resources import CanvasTexture, StorageBuffer
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
            # print(f'setting {param} to {loco[param]}')
            update(param)
        # print(f'B.u_p: {self._parameters.particle_size = }')
        # import time.sleep
        # sleep(0.3)

    def build_render_graph(self, device, context, display_format):
        self.device = device
        self.uv = StorageBuffer(
            name='uvs',
            type_=vec2f,
            shape=(Defaults.SEQ_COUNT, Defaults.SEQ_LENGTH))
        self.canvas = CanvasTexture('display', context, display_format)

        self.particles = ParticleMotionPass()
        self.particles.bind_uvs(self.uv)

        self.drawer = DrawingPass()
        self.drawer.bind_uvs(self.uv)
        self.drawer.bind_output(self.canvas)

        self.rendergraph = RenderGraph(
            device=device,
            passes=[
                self.particles,
                self.drawer,
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

    # # Don't need resize events, every frame checks its size
    # @canvas.add_event_handler('resize')
    # def handle_event(event):
    #     print(f'Event: {event["event_type"]!r}, size = {canvas.get_physical_size()}')

    bubbler = Bubbler()
    bubbler.build_render_graph(device, context, preferred_format)
    # bubbler.init_graphics(device, preferred_format)
    # parameters = BubblerParameters()

    def draw_frame():
        global frame
        try:
            frame += 1
        except NameError:
            frame = 0
        fc = 750
        n = fc // 2
        hn = n // 2
        z = 1 + min(frame % n, n - frame % n)
        p = 1 + (hn - z) / 10
        if hn <= frame % fc < 3 * hn:
            c = hn; l = z
        else:
            c = z; l = hn
        bubbler.update_parameters(seq_count=c, seq_length=l, particle_size=p)

        bubbler.draw_frame()

    canvas.request_draw(draw_frame)

    loop.run()

if __name__ == '__main__':
    main()
