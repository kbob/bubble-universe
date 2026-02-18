import wgpu

from constants import *
from passes import Access, Binding, RenderPass
from resources import StorageBuffer, UniformBuffer
from wgsl_types import *


class DrawingPass(RenderPass):


    class _Parameters:
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
        self._parameters = self._Parameters()
        self.uvs = None
        self.output = None
        self.uniform_buffer = UniformBuffer('drawing uniforms', self._Uniforms)
        self.shader_file = 'draw.wgsl'
        self.shader = self.read_shader(self.shader_file)

    def update_parameters(self, seq_count, seq_length, particle_size):
        self._parameters.seq_count = seq_count
        self._parameters.seq_length = seq_length
        self._parameters.particle_size = particle_size

    def bindings(self):
        assert self.uvs
        assert self.uniform_buffer
        return [
            Binding('uv', self.uvs, Access.RO),
            Binding('uniforms', self.uniform_buffer, Access.RW),
            Binding('color output', self.output, Access.RW),
        ]

    def bind_uvs(self, buffer):
        self.uvs = buffer
        return self

    def bind_color_output(self, texture):
        self.output = texture
        return self

    def instantiate(self, device):
        assert self.shader
        assert self.uvs
        assert self.uniform_buffer

        shader_module = device.create_shader_module(
            label=self.make_label(f'shader {self.shader_file}'),
            code=self.shader,
        )

        self.pipeline = device.create_render_pipeline(
            label=self.make_label('pipeline'),
            layout='auto',
            vertex=wgpu.VertexState(
                module=shader_module,
            ),
            fragment=wgpu.FragmentState(
                module=shader_module,
                targets=[
                    wgpu.ColorTargetState(
                        blend=self._choose_blend_mode(),
                        format=self.output.format,
                    ),
                ],
            )
        )

        self.uv_bind_group = device.create_bind_group(
            label=self.make_label('uv bind group'),
            layout=self.pipeline.get_bind_group_layout(0),
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self.uvs.resource_descriptor(),
                ),
            ],
        )

        self.uniforms_bind_group = device.create_bind_group(
            label=self.make_label('uniforms bind group'),
            layout=self.pipeline.get_bind_group_layout(1),
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self.uniform_buffer.resource_descriptor(),
                ),
            ],
        )

        self.pass_descriptor = wgpu.RenderPassDescriptor(
            label=self.make_label('render pass'),
            color_attachments=[
                wgpu.RenderPassColorAttachment(
                    clear_value=(0, 0, 0, 1),
                    load_op='clear',
                    store_op='store',
                    view=...,   # set in execute()
                ),
            ],
        )

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

        vertex_count = 6 * self._parameters.seq_count * self._parameters.seq_length
        rpass = encoder.begin_render_pass(**self.pass_descriptor)
        rpass.set_pipeline(self.pipeline)
        rpass.set_bind_group(0, self.uv_bind_group)
        rpass.set_bind_group(1, self.uniforms_bind_group)
        rpass.draw(vertex_count)
        rpass.end()

    def _choose_blend_mode(self):
        if BLEND_MODE == 'add':
            return wgpu.BlendState(
                color=wgpu.BlendComponent(
                    operation='add',
                    src_factor='one',
                    dst_factor='one',
                ),
                alpha=wgpu.BlendComponent(
                    operation='add',
                    src_factor='one',
                    dst_factor='one',
                ),
            )
        elif BLEND_MODE == 'blend':
            return wgpu.BlendState(
                color=wgpu.BlendComponent(
                    operation='add',
                    src_factor='one',
                    dst_factor='one-minus-src-alpha',
                ),
                alpha=wgpu.BlendComponent(
                    operation='add',
                    src_factor='one',
                    dst_factor='one-minus-src-alpha',
                ),
            )
        else:
            assert False, f'unknown BLEND_MODE of {BLEND_MODE!r}'
