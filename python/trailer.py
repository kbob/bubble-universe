from dataclasses import dataclass

from wgsl_types import *

from constants import *
from copier import CopyPass
from parameterized import ParameterizedMixIn
from passes import Access, Attachment, Binding, RenderPass, Subgraph
from resources import Sampler, Texture


shader_source = '''
    struct Uniforms {
        persistence: f32,
        diffusion: f32,
        blur_sample_width: vec2f,      // in texture coordinates
    };

    @group(0) @binding(0) var in_trails: texture_2d<f32>;
    @group(0) @binding(1) var blur_sampler: sampler;
    @group(0) @binding(2) var in_particles: texture_2d<f32>;
    @group(0) @binding(3) var image_sampler: sampler;

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

    @fragment fn pass1_fragment_shader(
        in: InterStage
    ) -> @location(0) vec4f {
        
        let U = uniforms;

        let delta = vec2f(U.blur_sample_width[0], 0.0);

        // Samples
        let ts = textureSample(in_trails, image_sampler, in.texcoord);
        let ds = blur_1d(in.texcoord, delta);

        // Weighted samples
        let trails = (1.0 - U.diffusion) * ts;
        let diffused = U.diffusion * ds;

        // Composite
        let color = U.persistence * (trails + diffused);

        return color;
    }

    @fragment fn pass2_fragment_shader(
        in: InterStage
    ) -> @location(0) vec4f {

        let U = uniforms;

        let delta = vec2f(0.0, U.blur_sample_width[1]);

        // Samples
        let ts = textureSample(in_trails, image_sampler, in.texcoord);
        let ds = blur_1d(in.texcoord, delta);
        let ps = textureSample(in_particles, image_sampler, in.texcoord);

        // Weighted samples
        let trails = (1.0 - U.diffusion) * ts;
        let diffused = U.diffusion * ds;
        let particles = ps;

        // Composite
        let color = U.persistence * (trails + diffused + particles);

        return vec4f(color.rgb, saturate(color.a));
    };

    fn blur_1d(coord: vec2f, delta: vec2f) -> vec4f {
        let a = textureSample(in_trails, blur_sampler, coord - delta);
        let b = textureSample(in_trails, image_sampler, coord);
        let c = textureSample(in_trails, blur_sampler, coord + delta);

        return
            0.3125 * (a + c) +
            0.375 * b;
    }
'''


class TrailerSubgraph(Subgraph, ParameterizedMixIn):

    @dataclass
    class Parameters:
        persistence: float = Defaults.TRAIL_PERSISTENCE
        diffusion: float = Defaults.TRAIL_DIFFUSION

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
        self.pass1.update_parameters(
            persistence=self._parameters.persistence,
            diffusion=self._parameters.diffusion,
        )
        self.pass2.update_parameters(
            persistence=self._parameters.persistence,
            diffusion=self._parameters.diffusion,
        )
        self.pass1.execute(device, encoder)
        self.pass2.execute(device, encoder)


class _T1Pass(RenderPass, ParameterizedMixIn):

    @dataclass
    class Parameters:
        persistence: float = Defaults.TRAIL_PERSISTENCE
        diffusion: float = Defaults.TRAIL_DIFFUSION

    class _Uniforms(Uniforms):
        persistence: f32 = Defaults.TRAIL_PERSISTENCE
        diffusion: f32 = Defaults.TRAIL_DIFFUSION
        blur_sample_width: vec2f = (0, 0)

    def __init__(self, name='trailer 2nd pass'):
        super().__init__(name)
        self.input = None
        self.image_sampler = Sampler(f'{name} image sampler')
        self.blur_sampler = Sampler(f'{name} blur sampler', mag_filter='linear')
        self.output = None

    def resources(self):
        assert self.input is not None
        assert self.image_sampler is not None
        assert self.blur_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None
        return [
            Binding((0, 0), 'input', self.input, Access.RO),
            Binding((0, 1), 'blur sampler', self.blur_sampler, Access.RO),
            # Binding((0, 2), 'input', self.input, Access.RO),
            Binding((0, 3), 'image sampler', self.image_sampler, Access.RO),
            Binding((1, 0), 'uniforms', self.uniform_buffer, Access.RO),
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
        assert self.image_sampler is not None
        assert self.blur_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None

        # shader
        shader_module = device.create_shader_module(
            label=self.make_label('shader'),
            code=shader_source,
        )

        # pipeline
        self.instantiate_pipeline(
            device=device,
            shader_module=shader_module,
            fragment_entry='pass1_fragment_shader',
        )

        # bind groups
        self.instantiate_bind_groups(device)

        # render pass descriptor
        self.instantiate_pass_descriptor()

    def resize(self, device, size):
        self.rebind_group(device, 'input')

    def execute(self, device, encoder):

        # Update the output view.
        current_view = self.output.current_view()
        self.pass_descriptor.color_attachments[0].view = current_view

        # Update uniforms
        image_size = self.output.current_size()
        width = [1.4 / d for d in image_size]
        # print(f'T1.x: diffusion = {self._parameters.diffusion}')
        uniforms = self._Uniforms(
            persistence=self._parameters.persistence,
            diffusion=self._parameters.diffusion,
            blur_sample_width=width,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)


class _T2Pass(RenderPass, ParameterizedMixIn):

    @dataclass
    class Parameters:
        persistence: float = Defaults.TRAIL_PERSISTENCE
        diffusion: float = Defaults.TRAIL_DIFFUSION

    class _Uniforms(Uniforms):
        persistence: f32 = Defaults.TRAIL_PERSISTENCE
        diffusion: f32 = Defaults.TRAIL_DIFFUSION
        blur_sample_width: vec2f = (0, 0)

    def __init__(self, name='trailer 2nd pass'):
        super().__init__(name)
        self.trails = None
        self.particles = None
        self.image_sampler = Sampler(f'{name} image sampler')
        self.blur_sampler = Sampler(f'{name} blur sampler', mag_filter='linear')
        self.output = None

    def resources(self):
        assert self.trails is not None
        assert self.particles is not None
        assert self.image_sampler is not None
        assert self.blur_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None
        return [
            Binding((0, 0), 'trails', self.trails, Access.RO),
            Binding((0, 1), 'blur sampler', self.blur_sampler, Access.RO),
            Binding((0, 2), 'particles', self.particles, Access.RW),
            Binding((0, 3), 'image sampler', self.image_sampler, Access.RO),
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
        assert self.image_sampler is not None
        assert self.blur_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None

        # shader
        shader_module = device.create_shader_module(
            label=self.make_label('shader'),
            code=shader_source,
        )

        # pipeline
        self.instantiate_pipeline(
            device=device,
            shader_module=shader_module,
            fragment_entry='pass2_fragment_shader',
        )

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
        image_size = self.output.current_size()
        width = [1.4 / d for d in image_size]
        # print(f'T2.x: diffusion = {self._parameters.diffusion}')
        uniforms = self._Uniforms(
            persistence=self._parameters.persistence,
            diffusion=self._parameters.diffusion,
            blur_sample_width=width,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)
