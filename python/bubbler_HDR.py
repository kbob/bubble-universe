from dataclasses import dataclass

from constants import *
from copier import CopyPass
from drawer import DrawingPass
from light_bloom import BloomSubgraph
from parameterized import ParameterizedMixIn
from particle_motion import ParticleMotionPass
from rendergraph import RenderGraph
from resources import StorageBuffer, Texture
from tone_mapper import ToneMapPass
from wgsl_types import *


class BubblerHDR(ParameterizedMixIn):

    @dataclass
    class Parameters:
        seq_count: int = Defaults.SEQ_COUNT
        seq_length: int = Defaults.SEQ_LENGTH
        fps: float = MAX_FPS
        speed: float = Defaults.SPEED
        r: float = Defaults.R
        particle_size: float = Defaults.PARTICLE_SIZE

        def calc_dt(self, fps):
            return self.speed / fps


    def __init__(self):
        super().__init__()
        self._time = 0
        self._last_size = None


    def build_render_graph(self, device, outputs):
        """first renderer controls the output size"""
        assert len(outputs) > 0
        self.device = device
        self.outputs = outputs
        self.resize_controller = self.outputs[0]

        # Create resources

        render_size = outputs[0].current_size()
        self.uvs = StorageBuffer(
            name='uvs',
            type_=vec2f,
            shape=(MAX_SEQ_COUNT, MAX_SEQ_LENGTH),
        )
        self.HDR_image = Texture(
            name='HDR image pre-bloom',
            format=HDR_PIXEL_FORMAT,
            shape=(*render_size, 4),
            renderable=True,
        )
        self.bloomed_image = Texture(
            name='HDR image post-bloom',
            format=HDR_PIXEL_FORMAT,
            shape=(*render_size, 4),
            renderable=True,
        )
        self._last_size = render_size
        if self._is_multi_output:
            self.image_texture = Texture(
                name='image',
                format='rgba8unorm',
                shape=(*render_size, 4),
                renderable=True,
            )
            tone_mapping_dest = self.image_texture
        else:
            tone_mapping_dest = outputs[0]

        # Create compute and render passes

        self.particles = (
            ParticleMotionPass()
                .bind_uvs(self.uvs)
        )
        self.drawer = (
            DrawingPass()
                .bind_uvs(self.uvs)
                .attach_color_output(self.HDR_image)
        )
        self.bloomer = (
            BloomSubgraph()
                .bind_input(self.HDR_image)
                .attach_output(self.bloomed_image)
        )
        self.mapper = (
            ToneMapPass()
                .bind_input(self.bloomed_image)
                .attach_output(tone_mapping_dest)
        )
        passes = [
            self.particles,
            self.drawer,
            self.bloomer,
            self.mapper,
        ]

        if self._is_multi_output:
            self.copiers = [
                CopyPass()
                    .bind_input(self.image_texture)
                    .attach_output(out)
                for out in outputs]
            passes += self.copiers

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

            # Resize textures
            self.HDR_image.resize(self.device, size)
            self.bloomed_image.resize(self.device, size)

            # Resize passes
            self.bloomer.resize(self.device, size)
            self.mapper.resize(self.device, size)
            if self._is_multi_output:
                self.image_texture.resize(self.device, size)
                for cp in self.copiers:
                    cp.resize(self.device, size)

        # Run the compute and render passes

        self.rendergraph.execute(self.device)

        # Next!

        self._inc_time(1 / self._parameters.fps)


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
