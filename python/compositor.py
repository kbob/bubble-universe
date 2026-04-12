from dataclasses import dataclass

from wgsl_types import *

from passes import Access, Attachment, Binding, RenderPass
from resources import Sampler


shader_source = '''
    @group(0) @binding(0) var background_tex: texture_2d<f32>;
    @group(0) @binding(1) var trails_tex: texture_2d<f32>;
    @group(0) @binding(2) var particles_tex: texture_2d<f32>;
    @group(0) @binding(3) var all_sampler: sampler;

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

        let bg = textureSample(background_tex, all_sampler, in.texcoord);
        let trails = textureSample(trails_tex, all_sampler, in.texcoord);
        let particles = textureSample(particles_tex, all_sampler, in.texcoord);

        var color = bg;
        color += trails;
        color += particles;

        return color;
    };
'''

class CompositorPass(RenderPass):

    def __init__(self, name='compositor'):
        super().__init__(name)
        self.background = None
        self.trails = None
        self.particles = None
        self.sampler = Sampler('compositor sampler')

    def resources(self):
        assert self.background is not None
        assert self.trails is not None
        assert self.particles is not None
        assert self.sampler is not None
        assert self.output is not None
        return [
            Binding((0, 0), 'background', self.background, Access.RO),
            Binding((0, 1), 'trails', self.trails, Access.RO),
            Binding((0, 2), 'particles', self.particles, Access.RO),
            Binding((0, 3), 'sampler', self.sampler, Access.RO),
            Attachment('output', self.output),
        ]

    def bind_background(self, tex):
        self.background = tex
        return self

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
        assert self.background is not None
        assert self.trails is not None
        assert self.particles is not None
        assert self.sampler is not None
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
        self.rebind_group(device, 'background')
        self.rebind_group(device, 'trails')
        self.rebind_group(device, 'particles')

    def execute(self, device, encoder):

        # Get the output view.
        current_view = self.output.current_view()

        # Update the output view.
        self.pass_descriptor.color_attachments[0].view = current_view

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)
