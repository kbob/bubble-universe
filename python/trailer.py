from dataclasses import dataclass

from wgsl_types import *

from constants import *
from copier import CopyPass
from parameterized import ParameterizedMixIn
from passes import Access, Attachment, Binding, RenderPass, Subgraph
from resources import Sampler, Texture


shader_source = '''
    struct Uniforms {
        amount: f32,
        blur: f32,
    };

    @group(0) @binding(0) var in_trails: texture_2d<f32>;
    @group(0) @binding(1) var in_particles: texture_2d<f32>;
    @group(0) @binding(2) var image_sampler: sampler;

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

        let trails = textureSample(in_trails, image_sampler, in.texcoord);
        // let diffused = ...
        let particles = textureSample(in_particles, image_sampler, in.texcoord);
        let color = U.amount * (trails.rgb + particles.rgb);
        return vec4f(color, 1.0);
    };
'''


class TrailerSubgraph(Subgraph, ParameterizedMixIn):

    @dataclass
    class Parameters:
        amount: float = Defaults.TRAILS
        blur: float = Defaults.TRAILS_BLUR

    def __init__(self, name='trailer'):
        super().__init__(name)
        self.particles = None
        self.trails = None
        self.pass1 = _T1Pass('trailer 1')
        self.pass2 = _T2Pass('trailer 2')

    def resources(self):
        assert self.particles is not None
        assert self.trails is not None
        return [
            Binding(None, 'particles', self.particles, Access.RO),
            Attachment('trails', self.trails, Access.RW),
        ]

    def bind_particles(self, tex):
        self.particles = tex
        return self

    def attach_trails(self, tex):
        self.trails = tex
        return self

    def instantiate(self, device):
        assert self.particles is not None
        assert self.trails is not None

        render_size = self.trails.current_size()
        self.temp_image = Texture(
            name='trails temp',
            format=HDR_PIXEL_FORMAT,
            shape=(*render_size, 4),
            renderable=True,
        )

        (self.pass1
            .bind_input(self.trails)
            .attach_output(self.temp_image)
        )
        (self.pass2
            .bind_trails(self.temp_image)
            .bind_particles(self.particles)
            .attach_output(self.trails)
        )
        self.instantiate_subgraph(
            device=device,
            passes=[self.pass1, self.pass2],
            external_resources=[
                self.particles,
                self.trails,
            ],
        )

    def resize(self, device, size):
        self.temp_image.resize(device, size)
        self.pass1.resize(device, size)
        self.pass2.resize(device, size)

    def execute(self, device, encoder):
        self.pass2.update_parameters(
            amount=self._parameters.amount,
            blur=self._parameters.blur,
        )
        self.pass1.execute(device, encoder)
        self.pass2.execute(device, encoder)


_T1Pass = CopyPass              # Cheat for now


class _T2Pass(RenderPass, ParameterizedMixIn):

    @dataclass
    class Parameters:
        amount: float = Defaults.TRAILS
        blur: float = Defaults.TRAILS_BLUR

    class _Uniforms(Uniforms):
        amount: f32 = Defaults.TRAILS
        blur: f32 = Defaults.TRAILS_BLUR

    def __init__(self, name='trailer'):
        super().__init__(name)
        self.trails = None
        self.particles = None
        self.sampler = Sampler(f'{name} image sampler')
        self.output = None

    def resources(self):
        assert self.trails is not None
        assert self.particles is not None
        assert self.sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None
        return [
            Binding((0, 0), 'trails', self.trails, Access.RO),
            Binding((0, 1), 'particles', self.particles, Access.RW),
            Binding((0, 2), 'sampler', self.sampler, Access.RO),
            Binding((1, 0), 'uniforms', self.uniform_buffer, Access.RO),
            Attachment('output', self.output),
        ]

    def bind_trails(self, tex):
        self.trails = tex
        return self

    def bind_particles(self, tex):
        self.particles = tex
        return self

    def attach_output(self, tex):
        self.output = tex
        return self

    def instantiate(self, device):
        assert self.trails is not None
        assert self.particles is not None
        assert self.sampler is not None
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
        self.rebind_group(device, 'trails')
        self.rebind_group(device, 'particles')

    def execute(self, device, encoder):

        # Update the output view.
        current_view = self.output.current_view()
        self.pass_descriptor.color_attachments[0].view = current_view

        # Update uniforms
        uniforms = self._Uniforms(
            amount=self._parameters.amount,
            blur=self._parameters.blur,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)
