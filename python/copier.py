import wgpu

from passes import Access, Attachment, Binding, RenderPass
from resources import Sampler

shader_source = '''
    @group(0) @binding(0) var in_color: texture_2d<f32>;
    @group(0) @binding(1) var in_sampler: sampler;

    struct InterStage {
        @builtin(position) position: vec4f,
        @location(0) texcoord: vec2f,
    };

    @vertex fn vertex_shader(
        @builtin(vertex_index) vertex_index: u32,
    ) -> InterStage {

        var pos = array(
            vec2f(-1.0, -1.0),
            vec2f(-1.0,  3.0),
            vec2f( 3.0, -1.0),
        );

        let xy = pos[vertex_index];

        var out: InterStage;
        out.position = vec4f(xy, 0.0, 1.0);
        out.texcoord = xy * vec2f(0.5, -0.5) + vec2f(0.5);
        return out;
    };

    @fragment fn fragment_shader(
        in: InterStage
    ) -> @location(0) vec4f {
        let color = textureSample(in_color, in_sampler, in.texcoord);
        return vec4f(color);
    };
'''

class CopyPass(RenderPass):

    def __init__(self, name='copying'):
        super().__init__(name)
        self.input = None
        self.input_sampler = Sampler(f'{name} input sampler')
        self.output = None

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
            label=self.make_label('shader'),
            code=shader_source,
        )

        # pipeline
        self.instantiate_pipeline(device, shader_module)

        # bind groups
        self.instantiate_bind_groups(device)

        # render pass descriptor
        self.instantiate_pass_descriptor()

    def resize(self, device, size):
        self.rebind_group(device, 'input texture')

    def execute(self, device, encoder):

        # Get the output texture.
        current_texture = self.output.current_texture()
        current_view = self.output.current_view()

        # Update the output view
        self.pass_descriptor.color_attachments[0].view = current_view

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)
