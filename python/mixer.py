from dataclasses import dataclass

from wgsl_types import *

from parameterized import ParameterizedMixIn
from passes import Access, Attachment, Binding, RenderPass
from resources import Sampler


shader_source = '''
    struct Uniforms {
        amount: f32,
    };

    @group(0) @binding(0) var in_color_A: texture_2d<f32>;
    @group(0) @binding(1) var in_sampler_A: sampler;
    @group(0) @binding(2) var in_color_B: texture_2d<f32>;
    @group(0) @binding(3) var in_sampler_B: sampler;

    @group(1) @binding(0) var<uniform> uniforms: Uniforms;

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

        let U = uniforms;

        let color_A = textureSample(in_color_A, in_sampler_A, in.texcoord);
        let color_B = textureSample(in_color_B, in_sampler_B, in.texcoord);
        let color = mix(color_A, color_B, U.amount);

        return vec4f(color);
    };
'''

class MixerPass(RenderPass, ParameterizedMixIn):

    @dataclass
    class Parameters:
        enabled: bool = True
        amount: float = 0

    class _Uniforms(Uniforms):
        amount: f32 = 0

    def __init__(self, name='mixing'):
        super().__init__(name)
        self.input_A = None
        self.input_sampler_A = Sampler(f'{name} input sampler A')
        self.input_B = None
        self.input_sampler_B = Sampler(f'{name} input sampler B')
        self.output = None

    def resources(self):
        assert self.input_A is not None
        assert self.input_sampler_A is not None
        assert self.input_B is not None
        assert self.input_sampler_B is not None
        assert self.uniform_buffer is not None
        assert self.output is not None
        return [
            Binding((0, 0), 'input texture A', self.input_A, Access.RO),
            Binding((0, 1), 'input sampler A', self.input_sampler_A, Access.RO),
            Binding((0, 2), 'input texture B', self.input_B, Access.RO),
            Binding((0, 3), 'input sampler B', self.input_sampler_B, Access.RO),
            Binding((1, 0), 'uniforms', self.uniform_buffer, Access.RO),
            Attachment('output', self.output),
        ]

    def bind_input_A(self, tex):
        self.input_A = tex
        return self

    def bind_input_B(self, tex):
        self.input_B = tex
        return self

    def attach_output(self, tex):
        self.output = tex
        return self

    def instantiate(self, device):
        assert self.input_A is not None
        assert self.input_sampler_A is not None
        assert self.input_B is not None
        assert self.input_sampler_B is not None
        assert self.uniform_buffer is not None
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
        self.rebind_group(device, 'input texture A')
        self.rebind_group(device, 'input texture B')

    def execute(self, device, encoder):

        if not self._parameters.enabled:
            return

        # Get the output view.
        current_view = self.output.current_view()

        # Update the output view.  It's easier to update it every frame
        # than to track when it's changed(?)
        self.pass_descriptor.color_attachments[0].view = current_view

        # Update uniforms
        uniforms = self._Uniforms(
            amount=self._parameters.amount,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)
