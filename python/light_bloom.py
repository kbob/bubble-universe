from dataclasses import dataclass

import wgpu

from constants import *
from copier import CopyPass
from parameterized import ParameterizedMixIn
from passes import Access, Attachment, Binding, BlendMode, RenderPass, Subgraph
from resources import Sampler, Texture, UniformBuffer
from wgsl_types import *


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## BloomSubgraph

class Rotor:
    def __init__(self, modulus):
        self.pos = -1
        self.modulus = modulus
    def inc(self):
        self.pos = (self.pos + 1) % self.modulus
    def __int__(self):
        return self.pos
    def __eq__(self, other):
        return False
        return self.pos == other

rotor = Rotor(1 + 2 * BLOOM_MIP_LEVELS + 5)

class BloomSubgraph(Subgraph, ParameterizedMixIn):

    """light bloom"""

    @dataclass
    class Parameters:
        bloom_amount: float = Defaults.BLOOM_AMOUNT
        bloom_size: float = Defaults.BLOOM_SIZE

    def __init__(self, name='bloomer'):
        super().__init__(name)
        self.input = None
        self.output = None
        shader_file = 'bloom.wgsl'
        shader_source = self.read_shader(shader_file)
        self.shader = Shader(shader_file, shader_source)
        self.mip_textures = None
        self.downsamplers = [
            Downsampler(self.shader)
            for i in range(BLOOM_MIP_LEVELS)
        ]
        self.upsamplers = [
            Upsampler(self.shader)
            for i in range(BLOOM_MIP_LEVELS - 1)
        ]
        self.upsample_mixer = UpsampleMixer(self.shader)
        # DEBUG
        self.copier = CopyPass()

    def resources(self):
        assert self.input is not None
        assert self.output is not None
        return [
            Binding(None, 'input', self.input, Access.RO),
            Attachment('output', self.output, Access.WO),
        ]

    def bind_input(self, texture):
        self.input = texture
        return self

    def attach_output(self, texture):
        self.output = texture
        return self

    def instantiate(self, device):
        assert self.input is not None
        assert self.output is not None

        # Calculate mip texture sizes
        size = self.input.current_size()
        assert size == self.output.current_size()
        self.mip_sizes = [
            (max(1, size[0] // 2**i), max(1, size[1] // 2**i))
            for i in range(1, BLOOM_MIP_LEVELS + 1)
        ]

        # Create mip textures
        self.mip_textures = [
            Texture(
                name=f'bloom mip {i}',
                format=HDR_PIXEL_FORMAT,
                shape=(*sz, 4),
                renderable=True,
            )
            for (i, sz) in enumerate(self.mip_sizes)
        ]
        for tex in self.mip_textures:
            tex.instantiate(device)

        # Instantiate subpasses

        for (dn, in_, out) in zip(
            self.downsamplers,                  # pass
            [self.input] + self.mip_textures,   # read from previous
            self.mip_textures,                  # write to next
        ):
            dn.bind_input(in_)
            dn.attach_output(out)

        for (up, in_, out) in zip(
            self.upsamplers,                    # pass
            self.mip_textures[::-1],            # read from next
            self.mip_textures[-2::-1],          # write to previous
        ):
            up.bind_input(in_)
            up.attach_output(out)

        (self.upsample_mixer
            .bind_image_input(self.input)
            .bind_bloom_input(self.mip_textures[0])
            .attach_output(self.output)
        )

        (self.copier                            # DEBUG
            .bind_input(self.mip_textures[-1])
            .attach_output(self.output)
        )
        self.instantiate_subgraph(
            device=device,
            passes=self.downsamplers + self.upsamplers + [
                self.upsample_mixer,
                self.copier,                    # DEBUG
            ],
            external_resources=[
                self.input,
                self.output,
            ],
        )

    def resize(self, device, size):

        # Resize all MIP textures
        self.mip_sizes = [
            (max(1, size[0] // 2**i), max(1, size[1] // 2**i))
            for i in range(1, BLOOM_MIP_LEVELS + 1)
        ]
        for (tex, size) in zip(self.mip_textures, self.mip_sizes):
            tex.resize(device, size)

        # Resize all resampling passes
        for (dn, size) in zip(self.downsamplers, self.mip_sizes):
            dn.resize(device, size)
        for (up, size) in zip(self.upsamplers, self.mip_sizes[:0:-1]):
            up.resize(device, size)
        self.upsample_mixer.resize(device, size)

    def execute(self, device, encoder):
        global rotor
        rotor.inc()

        def short_return(texture):
            (self.copier
                .bind_input(texture)
                .attach_output(self.output)
                .resize(device, None)
            )
            self.copier.execute(device, encoder)

        if rotor == 0:
            return short_return(self.input)

        # Downsample

        for (i, dn) in enumerate(self.downsamplers):
            dn.execute(device, encoder)
            if rotor == i + 1:
                return short_return(self.mip_textures[i])

        # Upsample

        for (i, up) in enumerate(self.upsamplers):
            up.execute(device, encoder)
            if rotor == i + 1 + BLOOM_MIP_LEVELS:
                return short_return(self.mip_textures[BLOOM_MIP_LEVELS - i - 2])

        # Final upsample and mix

        self.upsample_mixer.execute(device, encoder)


@dataclass
class Shader:
    file: str
    code: str


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Downsampler

class Downsampler(RenderPass):

    class _Uniforms(Uniforms):
        viewport_size: vec2f = (1, 1)

    def __init__(self, shader):
        super().__init__('bloom downsampler')
        self.input = None
        self.input_sampler = Sampler(
            name='downsampler input sampler',
            min_filter='linear',
            mag_filter='linear',
        )
        self.output = None
        self.shader = shader

    def resources(self):
        assert self.input is not None
        assert self.input_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None
        return [
            Binding((0, 0), 'input', self.input, Access.RO),
            Binding((0, 1), 'input sampler', self.input_sampler, Access.RO),
            Binding((1, 0), 'uniforms', self.uniform_buffer, Access.RW),
            Attachment('output', self.output),
        ]

    def bind_input(self, texture):
        self.input = texture
        return self

    def attach_output(self, texture):
        self.output = texture
        return self

    def instantiate(self, device):
        assert self.input is not None
        assert self.input_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None

        # shader module
        shader_module = device.create_shader_module(
            label=self.make_label(f'shader {self.shader.file}'),
            code=self.shader.code,
        )

        # pipeline
        self.instantiate_pipeline(
            device,
            shader_module,
            fragment_entry='downsampler_fragment_shader',
        )

        # bind groups
        self.instantiate_bind_groups(device)

        # render pass descriptor
        self.instantiate_pass_descriptor()

    def resize(self, device, size):
        self.rebind_group(device, 'input')

    def execute(self, device, encoder):
        assert self.input is not None
        assert self.input_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None

        current_view = self.output.current_view()
        src_size = self.input.current_view().size[:2]

        uniforms = self._Uniforms(
            viewport_size=src_size,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())        

        self.pass_descriptor.color_attachments[0].view = current_view

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Upsampler

class Upsampler(RenderPass, ParameterizedMixIn):

    @dataclass
    class Parameters:
        bloom_size: float = Defaults.BLOOM_SIZE

    class _Uniforms(Uniforms):
        filter_radius: f32

    def __init__(self, shader):
        super().__init__('bloom upsampler')
        self.input = None
        self.input_sampler = Sampler(
            name='upsampler input sampler',
            min_filter='linear',
            mag_filter='linear',
        )
        self.output = None
        self.shader = shader

    def resources(self):
        assert self.input is not None
        assert self.input_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None
        return [
            Binding((0, 0), 'input', self.input, Access.RO),
            Binding((0, 1), 'input sampler', self.input_sampler, Access.RO),
            Binding((1, 0), 'uniforms', self.uniform_buffer, Access.RW),
            Attachment(
                'output',
                self.output,
                blend=BlendMode.ADD,
                load_op='load',
            ),
        ]

    def bind_input(self, texture):
        self.input = texture
        return self

    def attach_output(self, texture):
        self.output = texture
        return self

    def instantiate(self, device):

        # shader module
        shader_module = device.create_shader_module(
            label=self.make_label(f'shader module {self.shader.file}'),
            code=self.shader.code,
        )

        # pipeline
        self.instantiate_pipeline(
            device,
            shader_module,
            fragment_entry='upsampler_fragment_shader',
        )

        # create bind groups
        self.instantiate_bind_groups(device)

        # create render pass descriptor
        self.instantiate_pass_descriptor()

    def resize(self, device, size):
        self.rebind_group(device, 'input')

    def execute(self, device, encoder):
        assert self.input is not None
        assert self.input_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None

        current_view = self.output.current_view()

        uniforms = self._Uniforms(
            filter_radius = self._parameters.bloom_size,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())        

        self.pass_descriptor.color_attachments[0].view = current_view

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Upsample Mixer

class UpsampleMixer(RenderPass, ParameterizedMixIn):

    @dataclass
    class Parameters:
        bloom_size: float = Defaults.BLOOM_SIZE
        bloom_amount: float = Defaults.BLOOM_AMOUNT

    class _Uniforms(Uniforms):
        filter_radius: f32 = Defaults.BLOOM_SIZE
        bloom_strength: f32 = Defaults.BLOOM_AMOUNT
    
    def __init__(self, shader):
        super().__init__('bloom upsample mixer')
        self.image_input = None
        self.image_sampler = Sampler('mix input sampler')
        self.bloom_input = None
        self.bloom_sampler = Sampler(
            name='miz input sampler',
            min_filter='linear',
            mag_filter='linear',
        )
        self.output = None
        self.shader = shader

    def resources(self):
        assert self.image_input is not None
        assert self.image_sampler is not None
        assert self.bloom_input is not None
        assert self.bloom_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None
        return [
            Binding((0, 0), 'image input', self.image_input, Access.RO),
            Binding((0, 1), 'image sampler', self.image_sampler, Access.RO),
            Binding((2, 0), 'bloom input', self.bloom_input, Access.RO),
            Binding((2, 1), 'bloom sampler', self.bloom_sampler, Access.RO),
            Binding((1, 0), 'uniforms', self.uniform_buffer, Access.RW),
            Attachment('output', self.output),
        ]

    def bind_image_input(self, texture):
        self.image_input = texture
        return self

    def bind_bloom_input(self, texture):
        self.bloom_input = texture
        return self

    def attach_output(self, texture):
        self.output = texture
        return self

    def instantiate(self, device):
        assert self.image_input is not None
        assert self.image_sampler is not None
        assert self.bloom_input is not None
        assert self.bloom_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None

        # shader module
        shader_module = device.create_shader_module(
            label=self.make_label(f'shader {self.shader.file}'),
            code=self.shader.code,
        )

        # pipeline
        self.instantiate_pipeline(
            device,
            shader_module,
            fragment_entry='upsample_mixer_fragment_shader',
        )

        # bind groups
        self.instantiate_bind_groups(device)

        # render pass descriptor
        self.instantiate_pass_descriptor()

    def resize(self, device, size):
        self.rebind_group(device, 'image input')
        self.rebind_group(device, 'bloom input')

    def execute(self, device, encoder):
        assert self.image_input is not None
        assert self.image_sampler is not None
        assert self.bloom_input is not None
        assert self.bloom_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None

        current_view = self.output.current_view()

        uniforms = self._Uniforms(
            filter_radius = self._parameters.bloom_size,
            bloom_strength = self._parameters.bloom_amount,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())        

        self.pass_descriptor.color_attachments[0].view = current_view

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)
