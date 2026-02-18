import wgpu

from passes import Access, Binding, RenderPass
from resources import Sampler

class ToneMapPass(RenderPass):

    def __init__(self, name='tone mapping'):

        super().__init__(name)
        self.input = None
        self.input_sampler = Sampler(self.make_label('input sampler'))
        self.output = None
        self.shader_file = 'tone_map.wgsl'
        self.shader = self.read_shader(self.shader_file)

    def bindings(self):
        assert self.input is not None
        assert self.input_sampler is not None
        assert self.output is not None
        return [
            Binding('input texture', self.input, Access.RO),
            Binding('input sampler', self.input_sampler, Access.RO),
            Binding('output', self.output, Access.RO),
        ]

    def bind_input(self, tex):
        self.input = tex
        return self

    def bind_color_output(self, tex):
        self.output = tex
        return self

    def instantiate(self, device):
        # shader
        shader_module = device.create_shader_module(
            label=self.make_label(f'shader {self.shader_file}'),
            code=self.shader,
        )

        # pipeline
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
                        format=self.output.format,
                    ),
                ],
            ),
        )

        # bind groups
        self.input_bind_group = device.create_bind_group(
            label=self.make_label('input bind group'),
            layout=self.pipeline.get_bind_group_layout(0),
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self.input.current_view(),
                ),
                wgpu.BindGroupEntry(
                    binding=1,
                    resource=self.input_sampler.resource_descriptor(),
                ),
            ],
        )

        # render pass descriptor
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

    def resize(self, device, size):
        self.input_bind_group = device.create_bind_group(
            label=self.make_label('input bind group (resized)'),
            layout=self.pipeline.get_bind_group_layout(0),
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self.input.current_view(),
                ),
                wgpu.BindGroupEntry(
                    binding=1,
                    resource=self.input_sampler.resource_descriptor(),
                )
            ],
        )

    def execute(self, device, encoder):

        # Get the output texture.
        current_texture = self.output.current_texture()
        current_view = self.output.current_view()

        # Update the output view
        self.pass_descriptor.color_attachments[0].view = current_view

        vertex_count = 3
        rpass = encoder.begin_render_pass(**self.pass_descriptor)
        rpass.set_pipeline(self.pipeline)
        rpass.set_bind_group(0, self.input_bind_group)
        rpass.draw(vertex_count)
        rpass.end()
