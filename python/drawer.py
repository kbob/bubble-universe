from dataclasses import dataclass

import wgpu

from constants import *
from passes import Access, Attachment, Binding, BlendMode, RenderPass
from parameterized import ParameterizedMixIn
from resources import StorageBuffer, UniformBuffer
from wgsl_types import *


class DrawingPass(RenderPass, ParameterizedMixIn):


    @dataclass
    class Parameters:
        seq_count: int = Defaults.SEQ_COUNT
        seq_length: int = Defaults.SEQ_LENGTH
        particle_size: float = Defaults.PARTICLE_SIZE

    class _Uniforms(Uniforms):
        particle_size: vec2f = (
            (Defaults.PARTICLE_SIZE / Defaults.CANVAS_SIZE[1], ) * 2
        )
        scale: vec2f = (1, 1)
        seq_count: u32 = Defaults.SEQ_COUNT
        seq_length: u32 = Defaults.SEQ_LENGTH


    def __init__(self, name='drawing'):
        super().__init__(name)
        self.uvs = None
        self.output = None
        self.shader_file = 'draw.wgsl'
        self.shader = self.read_shader(self.shader_file)

    def resources(self):
        assert self.uvs is not None
        assert self.uniform_buffer is not None
        return [
            Binding((0, 0), 'uv', self.uvs, Access.RO),
            Binding((1, 0), 'uniforms', self.uniform_buffer, Access.RW),
            Attachment(
                'color output',
                self.output,
                blend=BlendMode(BLEND_MODE),
            ),
        ]

    def bind_uvs(self, buffer):
        self.uvs = buffer
        return self

    def attach_color_output(self, texture):
        self.output = texture
        return self

    def instantiate(self, device):
        assert self.shader is not None
        assert self.uvs is not None
        assert self.uniform_buffer is not None

        shader_module = device.create_shader_module(
            label=self.make_label(f'shader {self.shader_file}'),
            code=self.shader,
        )

        # pipeline
        self.instantiate_pipeline(device, shader_module)

        # bind groups
        self.instantiate_bind_groups(device)

        # pass descriptor
        self.instantiate_pass_descriptor()

    def execute(self, device, encoder):

        # Get the output texture.
        current_size = self.output.current_size()
        current_view = self.output.current_view()

        def adjust_for_aspect(x):
            w, h = current_size
            assert w != 0 and h != 0
            if h > w:
                return (x, x * w / h)
            else:
                return (x * h / w, x)

        uniforms = self._Uniforms(
            particle_size=adjust_for_aspect(
                self._parameters.particle_size / Defaults.CANVAS_SIZE[1],
            ),
            scale=adjust_for_aspect((1 - BORDER) / 2),
            seq_count=self._parameters.seq_count,
            seq_length=self._parameters.seq_count,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())

        self.pass_descriptor.color_attachments[0].view = current_view

        vertex_count = (
            6 * self._parameters.seq_count * self._parameters.seq_length
        )
        self.encode_render_pass_draw(encoder, vertex_count)
