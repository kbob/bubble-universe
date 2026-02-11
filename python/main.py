#!/usr/bin/env python

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


    # @dataclass
    # class Parameters:
    #     seq_count: int = Defaults.SEQ_COUNT
    #     seq_length: int = Defaults.SEQ_LENGTH
    #     speed: float = Defaults.SPEED
    #     r: float = Defaults.R
    #     particle_size = Defaults.PARTICLE_SIZE

    #     def calc_dt(self, fps):
    #         return self.speed / fps


    def __init__(self):
        # self._parameters = self.Parameters()
        self._time = 0

    

    def inc_time(self):
        assert -tau < dt < tau
        self._time += dt
        if self._time < 0:
            self._time += tau
        if self._time >= tau:
            self._time -= tau
     
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

        self.rendergraph.execute(self.device)
        # self.inc_time(parameters.calc_dt(MAX_FPS))

def main():
    adapter = wgpu.gpu.request_adapter_sync()
    device = adapter.request_device_sync()

    canvas = RenderCanvas(
        size=CANVAS_SIZE,
        title='Bubble Universe',
        update_mode='ondemand',
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
        # dest_texture = context.get_current_texture()
        bubbler.draw_frame()
        # bubbler.inc_time(parameters.calc_dt(MAX_FPS))

    canvas.request_draw(draw_frame)

    loop.run()

if __name__ == '__main__':
    main()
