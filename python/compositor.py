from dataclasses import dataclass

from wgsl_types import *

from parameterized import ParameterizedMixIn
from passes import Access, Attachment, Binding, RenderPass
from resources import Sampler


shader_source = '''

    struct Uniforms {
        background_amount: f32,
        overlay_amount: f32,
        overlay_origin: vec2f,
        overlay_size: vec2f,
    };

    @group(0) @binding(0) var background_tex: texture_2d<f32>;
    @group(0) @binding(1) var trails_tex: texture_2d<f32>;
    @group(0) @binding(2) var particles_tex: texture_2d<f32>;
    @group(0) @binding(3) var overlay_tex: texture_2d<f32>;
    @group(0) @binding(4) var all_sampler: sampler;
    @group(1) @binding(0) var<uniform> uniforms: Uniforms;

    struct InterStage {
        @builtin(position) position: vec4f,
        @location(0) texcoord: vec2f,
    };

    @vertex fn vertex_shader(
        @builtin(vertex_index) vertex_index: u32,
    ) -> InterStage {

        var pos = array(
            vec2f(-1f, -1f),
            vec2f(-1f,  3f),
            vec2f( 3f, -1f),
        );

        let xy = pos[vertex_index];

        var out: InterStage;
        out.position = vec4f(xy, 0f, 1f);
        out.texcoord = xy * vec2f(0.5, -0.5) + vec2f(0.5);
        return out;
    };

    @fragment fn fragment_shader(
        in: InterStage
    ) -> @location(0) vec4f {

        let U = uniforms;

        let bg = textureSample(background_tex, all_sampler, in.texcoord);
        let trails = textureSample(trails_tex, all_sampler, in.texcoord);
        let particles = textureSample(particles_tex, all_sampler, in.texcoord);

        var rgb = U.background_amount * bg.rgb;

        let ta = clamp(trails.a, 0f, 1f);
        rgb = trails.rgb + (1f - ta) * rgb;

        let pa = clamp(particles.a, 0f, 1f);
        rgb = particles.rgb + (1f - pa) * rgb;

        // Is this fragment in the overlay rectangle?
        let oc: vec2<bool> = in.position.xy >= U.overlay_origin;
        let xc: vec2<bool> = in.position.xy < U.overlay_origin + U.overlay_size;
        var in_overlay: bool = oc.x && oc.y && xc.x && xc.y;

        if in_overlay {
            let ocoord = (in.position.xy - U.overlay_origin) / U.overlay_size;
            let overlay = textureSample(overlay_tex, all_sampler, ocoord);
            let oa = overlay.a * U.overlay_amount;
            rgb = mix(rgb, overlay.rgb, oa);
        }

        let color = vec4f(rgb, 1f);
        return color;
    };
'''

class CompositorPass(RenderPass, ParameterizedMixIn):

    @dataclass
    class Parameters:
        background_amount: float = 1
        overlay_amount: float = 1

    class _Uniforms(Uniforms):
        background_amount: f32 = 1
        overlay_amount: f32 = 1
        overlay_origin: vec2f
        overlay_size: vec2f

    def __init__(self, name='compositor'):
        super().__init__(name)
        self.background = None
        self.trails = None
        self.particles = None
        self.overlay = None
        self.sampler = Sampler('compositor sampler')

    def resources(self):
        assert self.background is not None
        assert self.trails is not None
        assert self.particles is not None
        assert self.overlay is not None
        assert self.sampler is not None
        assert self.output is not None
        return [
            Binding((0, 0), 'background', self.background, Access.RO),
            Binding((0, 1), 'trails', self.trails, Access.RO),
            Binding((0, 2), 'particles', self.particles, Access.RO),
            Binding((0, 3), 'overlay', self.overlay, Access.RO),
            Binding((0, 4), 'sampler', self.sampler, Access.RO),
            Binding((1, 0), 'uniforms', self.uniform_buffer, Access.RO),
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

    def bind_overlay(self, tex):
        self.overlay = tex
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

        # Update the output view.
        current_view = self.output.current_view()
        self.pass_descriptor.color_attachments[0].view = current_view

        # Update uniforms
        (cw, ch) = self.output.current_size()
        osize = self.overlay.current_size()
        oorigin = (round(0.03 * cw), round(0.97 * ch) - osize[1])

        uniforms = self._Uniforms(
            background_amount=self._parameters.background_amount,
            overlay_amount=self._parameters.overlay_amount,
            overlay_origin=oorigin,
            overlay_size=osize,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)
