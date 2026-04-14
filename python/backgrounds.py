# from colorsys import hsv_to_rgb
from dataclasses import dataclass
# from enum import StrEnum
import enum

from colors import Theme
from constants import *
from parameterized import ParameterizedMixIn
from passes import Access, Attachment, Binding, RenderPass
from wgsl_types import *


class BackgroundPass(RenderPass, ParameterizedMixIn):

    @dataclass
    class Parameters:
        theme: Theme = Theme(Defaults.THEME)
        t: float = 0

    class _Uniforms(Uniforms):
        theme: u32 = int(Theme(Defaults.THEME))
        t: f32 = 0
        viewport_size: vec2u = Defaults.CANVAS_SIZE

    def __init__(self, name='background'):
        super().__init__(name)
        self.output = None
        self._enabled = True
        self.shader_file = 'backgrounds.wgsl'
        self.shader = self.read_shader(self.shader_file)

    def enable(self):
        self._enabled = True

    def update_parameters(self, **kwargs):
        if 'theme' in kwargs and kwargs['theme'] != self._parameters.theme:
            self._enabled = True
        super().update_parameters(**kwargs)

    def resources(self):
        assert self.output is not None
        assert self.uniform_buffer is not None
        return [
            Binding((0, 0), 'uniforms', self.uniform_buffer, Access.RO),
            Attachment('output', self.output),
        ]

    def attach_output(self, tex):
        self.output = tex
        return self

    def instantiate(self, device):
        assert self.output is not None
        assert self.uniform_buffer is not None

        shader_module = device.create_shader_module(
            label=self.make_label(f'shader {self.shader_file}'),
            code=self.shader,
        )        

        self.instantiate_pipeline(device, shader_module)
        self.instantiate_bind_groups(device)
        self.instantiate_pass_descriptor()

    def execute(self, device, encoder):

        if not self._enabled:
            return
        if not self._parameters.theme.background_animated:
            self._enabled = False

        # Get the output texture.
        current_texture = self.output.current_texture()
        current_view = self.output.current_view()
        view_size = self.output.current_size()

        # Update the output view
        self.pass_descriptor.color_attachments[0].view = current_view

        uniforms = self._Uniforms(
            theme=int(self._parameters.theme),
            t=self._parameters.t,
            viewport_size=view_size,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)
