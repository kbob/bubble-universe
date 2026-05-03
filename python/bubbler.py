from dataclasses import dataclass

from backgrounds import BackgroundPass
from colors import ColormapPass, Theme
from compositor import CompositorPass
from constants import *
from copier import CopyPass
from drawer_mapped import ColorMappedDrawingPass
from light_bloom import BloomSubgraph
from mixer import MixerPass
from overlay import OverlayPass
from parameterized import ParameterizedMixIn
from particle_motion import ParticleMotionPass
from rendergraph import RenderGraph
from resources import StorageBuffer, Texture
from tone_mapper import ToneMapPass
from trailer import TrailerSubgraph
from wgsl_types import *


class Bubbler(ParameterizedMixIn):


    @dataclass
    class Parameters:
        theme: Theme = Theme(Defaults.THEME)
        seq_count: int = Defaults.SEQ_COUNT
        seq_length: int = Defaults.SEQ_LENGTH
        s_blocks: int = Defaults.S_BLOCKS
        fps: float = MAX_FPS
        speed: float = Defaults.SPEED
        r: float = Defaults.R
        s: float = Defaults.S
        particle_size: float = Defaults.PARTICLE_SIZE
        trail_persistence: float = Defaults.TRAIL_PERSISTENCE
        trail_diffusion: float = Defaults.TRAIL_DIFFUSION
        background_amount: float = Defaults.BACKGROUND_AMOUNT
        trails_amount: float = Defaults.TRAILS_AMOUNT
        particles_amount: float = Defaults.PARTICLES_AMOUNT
        overlay_amount: float = Defaults.OVERLAY_AMOUNT
        bloom_amount: float = Defaults.BLOOM_AMOUNT
        bloom_size: float = Defaults.BLOOM_SIZE

        def calc_dt(self, fps):
            return self.speed / fps


    def __init__(self):
        super().__init__()
        self._time = 0
        self._last_cmap_size = None
        self._last_render_size = None
        self._theme_ramp = [0] # push initial blend amount


    def build_render_graph(self, device, outputs, use_HDR=USE_HDR):
        """first render output controls the output size"""
        assert len(outputs) > 0
        self.device = device
        self.outputs = outputs
        self._use_HDR = use_HDR
        self.resize_controller = self.outputs[0]


        # Create resources

        cmap_size = (self._parameters.seq_count, self._parameters.seq_length)
        render_size = outputs[0].current_size()
        self.colormap_A = Texture(
            name='colormap A',
            format='rgba8unorm',
            shape=(*cmap_size, 4),
            renderable=True,
        )
        self.colormap_B = Texture(
            name='colormap B',
            format='rgba8unorm',
            shape=(*cmap_size, 4),
            renderable=True,
        )
        self.colormap = Texture(
            name='colormap',
            format='rgba8unorm',
            shape=(*cmap_size, 4),
            renderable=True,
        )
        self.background_image_A = Texture(
            name='background A',
            format='rgba8unorm',
            shape=(*render_size, 4),
            renderable=True,
        )
        self.background_image_B = Texture(
            name='background B',
            format='rgba8unorm',
            shape=(*render_size, 4),
            renderable=True,
        )
        self.background_image = Texture(
            name='background',
            format='rgba8unorm',
            shape=(*render_size, 4),
            renderable=True,
        )
        self.uvs = StorageBuffer(
            name='uvs',
            type_=vec2f,
            shape=(MAX_SEQ_COUNT, MAX_SEQ_LENGTH),
        )
        if self._use_HDR:
            overlay_size = OverlayPass.overlay_size(render_size)
            self.overlay_texture = Texture(
                name='overlay',
                format='rgba8unorm',
                shape=(*overlay_size, 4),
                writable=True,
            )
            self.trails_image = Texture(
                name='trails',
                format=HDR_PIXEL_FORMAT,
                shape=(*render_size, 4),
                renderable=True,
            )
            self.particles_image = Texture(
                name='particles',
                format=HDR_PIXEL_FORMAT,
                shape=(*render_size, 4),
                renderable=True,
            )
            self.composite_image = Texture(
                name='composite',
                format=HDR_PIXEL_FORMAT,
                shape=(*render_size, 4),
                renderable=True,
            )
            self.bloomed_image = Texture(
                name='composite post-bloom',
                format=HDR_PIXEL_FORMAT,
                shape=(*render_size, 4),
                renderable=True,
            )
            drawing_dest = self.particles_image

        self._last_cmap_size = cmap_size
        self._last_render_size = render_size
        if self._is_multi_output:
            self.image_texture = Texture(
                name='image',
                format='rgba8unorm',
                shape=(*render_size, 4),
                renderable=True,
            )
            image_dest = self.image_texture
        else:
            image_dest = outputs[0]
        if not self._use_HDR:
            drawing_dest = image_dest


        # Create compute and render passes

        self.colors_A = (
            ColormapPass('colors A')
                .attach_colormap_output(self.colormap_A)
        )
        self.colors_B = (
            ColormapPass('colors B')
                .attach_colormap_output(self.colormap_B)
        )
        self._active_colors = self.colors_A
        self.color_mixer = (
            MixerPass('color mixer')
                .bind_input_A(self.colormap_A)
                .bind_input_B(self.colormap_B)
                .attach_output(self.colormap)
        )
        self.background_A = (
            BackgroundPass('background A')
                .attach_output(self.background_image_A)
        )
        self.background_B = (
            BackgroundPass('background B')
                .attach_output(self.background_image_B)
        )
        self._active_background = self.background_A
        self.background_mixer = (
            MixerPass('background mixer')
                .bind_input_A(self.background_image_A)
                .bind_input_B(self.background_image_B)
                .attach_output(self.background_image)
        )
        self.particles = (
            ParticleMotionPass()
                .bind_uvs(self.uvs)
        )
        self.drawer = (
            ColorMappedDrawingPass()
                .bind_uvs(self.uvs)
                .bind_colormap(self.colormap)
                .attach_color_output(drawing_dest)
        )
        # self.drawer = (
        #     DrawingPass()
        #         .bind_uvs(self.uvs)
        #         .attach_color_output(drawing_dest)
        # )
        passes = [
            self.colors_A,
            self.colors_B,
            self.color_mixer,
            self.background_A,
            self.background_B,
            self.background_mixer,
            self.particles,
            self.drawer,
        ]

        if self._use_HDR:
            self.overlayer = (
                OverlayPass()
                    .attach_output(self.overlay_texture)
            )
            self.compositor = (
                CompositorPass()
                    .bind_background(self.background_image)
                    .bind_trails(self.trails_image)
                    .bind_particles(self.particles_image)
                    .bind_overlay(self.overlay_texture)
                    .attach_output(self.composite_image)
            )
            self.trailer = (
                TrailerSubgraph()
                    .bind_particles(self.particles_image)
                    .attach_trails(self.trails_image)
            )
            self.bloomer = (
                BloomSubgraph()
                    .bind_input(self.composite_image)
                    .attach_output(self.bloomed_image)
            )
            self.mapper = (
                ToneMapPass()
                    .bind_input(self.bloomed_image)
                    .attach_output(image_dest)
            )
            passes += [
                self.overlayer,
                self.compositor,
                self.trailer,
                self.bloomer,
                self.mapper,
            ]

        if self._is_multi_output:
            self.copiers = [
                CopyPass()
                    .bind_input(self.image_texture)
                    .attach_output(out)
                for out in outputs
            ]
            passes += self.copiers


        # create render graph

        self.rendergraph = RenderGraph(device, passes)


    def draw_frame(self):

        # update passes' parameters

        if self._theme_ramp:
            mix_amount = self._theme_ramp.pop()
            self.color_mixer.update_parameters(
                enabled=True,
                amount=mix_amount,
            )
            self.background_mixer.update_parameters(
                enabled=True,
                amount=mix_amount,
            )
        else:
            self.color_mixer.update_parameters(
                enabled=self._theme.colors_animated,
            )
            self.background_mixer.update_parameters(
                enabled=self._theme.background_animated,
            )

        self._active_colors.update_parameters(
            theme=self._parameters.theme,
        )
        self.colors_A.update_parameters(
            t=self._time,
        )
        self.colors_B.update_parameters(
            t=self._time,
        )
        self._active_background.update_parameters(
            theme=self._parameters.theme,
        )
        self.background_A.update_parameters(
            t=self._time,
        )
        self.background_B.update_parameters(
            t=self._time,
        )
        self.particles.update_parameters(
            seq_count=self._parameters.seq_count,
            seq_length=self._parameters.seq_length,
            s_blocks=self._parameters.s_blocks,
            r=self._parameters.r,
            s=self._parameters.s,
            t=self._time,
        )
        self.drawer.update_parameters(
            seq_count=self._parameters.seq_count,
            seq_length=self._parameters.seq_length,
            particle_size=self._parameters.particle_size,
        )
        if self._use_HDR:
            self.overlayer.update_parameters(
                theme=self._parameters.theme,
                canvas_size=self.resize_controller.current_size(),
            )
            self.trailer.update_parameters(
                persistence=self._parameters.trail_persistence,
                diffusion=self._parameters.trail_diffusion,
            )
            self.compositor.update_parameters(
                background_amount=self._parameters.background_amount,
                trails_amount=self._parameters.trails_amount,
                particles_amount=self._parameters.particles_amount,
                overlay_amount=self._parameters.overlay_amount,
            )
            self.bloomer.update_parameters(
                bloom_amount=self._parameters.bloom_amount,
                bloom_size=self._parameters.bloom_size,
            )

        # Set intermediate textures' sizes

        cmap_size = (self._parameters.seq_count, self._parameters.seq_length)
        if self._last_cmap_size != cmap_size:
            self._last_cmap_size = cmap_size

            # Resize colormap
            self.colormap_A.resize(self.device, cmap_size)
            self.colormap_B.resize(self.device, cmap_size)
            self.colormap.resize(self.device, cmap_size)

            # Resize passes
            self.color_mixer.resize(self.device, cmap_size)
            self.drawer.resize_colormap(self.device, cmap_size)
            self.colors_A.enable()
            self.colors_B.enable()
            self.color_mixer.update_parameters(enabled=True)

        render_size = self.resize_controller.current_size()
        if self._last_render_size != render_size:
            self._last_render_size = render_size

            # Resize textures
            if self._use_HDR:
                self.background_image_A.resize(self.device, render_size)
                self.background_image_B.resize(self.device, render_size)
                self.background_image.resize(self.device, render_size)
                self.trails_image.resize(self.device, render_size)
                self.particles_image.resize(self.device, render_size)
                self.composite_image.resize(self.device, render_size)
                self.bloomed_image.resize(self.device, render_size)
                overlay_size = OverlayPass.overlay_size(render_size)
                self.overlay_texture.resize(self.device, overlay_size)
            if self._is_multi_output:
                self.image_texture.resize(self.device, render_size)

            # Resize passes
            self.background_mixer.resize(self.device, render_size)
            self.background_A.enable()
            self.background_B.enable()
            self.background_mixer.update_parameters(enabled=True)
            if self._use_HDR:
                self.trailer.resize(self.device, render_size)
                self.compositor.resize(self.device, render_size)
                self.bloomer.resize(self.device, render_size)
                self.mapper.resize(self.device, render_size)
            if self._is_multi_output:
                for cp in self.copiers:
                    cp.resize(self.device, render_size)

        # Run the compute and render passes

        self.rendergraph.execute(self.device)

        # Next!

        self._inc_time(1 / self._parameters.fps)

    @property
    def _theme(self):
        return self._parameters.theme

    def change_theme(self, theme, frames=1):
        # print(f'change theme -> {theme!s}')
        assert isinstance(theme, Theme)
        ramp = [
            _smoothstep(0, frames, i)
            for i in range(frames + 1)
        ]
        self._parameters.theme = theme

        if self._active_colors == self.colors_A:
            # self.colors_B.update_parameters(theme=theme)
            # self.background_B.update_parameters(theme=theme)
            self._theme_ramp.extend(ramp[:0:-1])
            self._active_colors = self.colors_B
            self._active_background = self.background_B
        else:
            # self.colors_A.update_parameters(theme=theme)
            # self.background_A.update_parameters(theme=theme)
            self._theme_ramp.extend(ramp[1:])
            self._active_colors = self.colors_A
            self._active_background = self.background_A
        self._active_colors.update_parameters(theme=theme)
        self._active_background.update_parameters(theme=theme)


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

def _smoothstep(e0, e2, x):
    assert e0 != e2
    sx = max(0, min(1, (x - e0) / (e2 - e0)))
    return -2 * sx**3 + 3 * sx**2
