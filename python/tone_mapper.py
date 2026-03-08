import wgpu

from passes import Access, Attachment, Binding, RenderPass
from resources import Sampler

class ToneMapPass(RenderPass):

    def __init__(self, name='tone mapping'):

        super().__init__(name)
        self.input = None
        self.input_sampler = Sampler(self.make_label('input sampler'))
        self.output = None
        self.shader_file = 'tone_map.wgsl'
        self.shader = self.read_shader(self.shader_file)

    def resources(self):
        assert self.input is not None
        assert self.input_sampler is not None
        assert self.output is not None
        return [
            Binding((0, 0), 'input texture', self.input, Access.RO),
            Binding((0, 1), 'input sampler', self.input_sampler, Access.RO),
            Attachment('output', self.output),
        ]

    def bind_input(self, tex):
        self.input = tex
        return self

    def attach_output(self, tex):
        self.output = tex
        return self

    def instantiate(self, device):
        assert self.input is not None
        assert self.input_sampler is not None
        assert self.output is not None

        # shader
        shader_module = device.create_shader_module(
            label=self.make_label(f'shader {self.shader_file}'),
            code=self.shader,
        )

        # pipeline
        self.instantiate_pipeline(device, shader_module)

        # # bind group(s)
        self.instantiate_bind_groups(device)

        # render pass descriptor
        self.instantiate_pass_descriptor()

    def resize(self, device, size):
        current_view = self.output.current_view()
        self.rebind_group(device, 'input texture')
        self.pass_descriptor.color_attachments[0].view = current_view

    def execute(self, device, encoder):

        # Get the output texture.
        current_texture = self.output.current_texture()
        current_view = self.output.current_view()

        # Update the output view
        self.pass_descriptor.color_attachments[0].view = current_view

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)
