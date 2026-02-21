from dataclasses import dataclass

import wgpu

from constants import *
from copier import CopyPass
from parameterized import Parameterized
from passes import Access, Binding, RenderPass, Subgraph
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

class BloomSubgraph(Subgraph, Parameterized):

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
        self.downsamplers = [Downsampler(self.shader) for i in range(BLOOM_MIP_LEVELS)]
        self.upsamplers = [Upsampler(self.shader) for i in range(BLOOM_MIP_LEVELS - 1)]
        self.upsample_mixer = UpsampleMixer(self.shader)
        # DEBUG
        self.copier = CopyPass()

    def bindings(self):
        assert self.input is not None
        assert self.output is not None
        return [
            Binding('input', self.input, Access.RO),
            Binding('color output', self.output, Access.RW),
        ]

    def bind_input(self, texture):
        self.input = texture
        return self

    def bind_color_output(self, texture):
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
            dn.bind_color_output(out)

        for (up, in_, out) in zip(
            self.upsamplers,                    # pass
            self.mip_textures[::-1],            # read from next
            self.mip_textures[-2::-1],          # write to previous
        ):
            up.bind_input(in_)
            up.bind_color_output(out)

        (self.upsample_mixer
            .bind_image_input(self.input)
            .bind_bloom_input(self.mip_textures[0])
            .bind_color_output(self.output)
        )

        (self.copier                            # DEBUG
            .bind_input(self.mip_textures[-1])
            .bind_color_output(self.output)
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
                .bind_color_output(self.output)
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

    def bindings(self):
        assert self.input is not None
        assert self.input_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None
        return [
            Binding('input', self.input, Access.RO),
            Binding('input sampler', self.input_sampler, Access.RO),
            Binding('uniforms', self.uniform_buffer, Access.RW),
            Binding('color output', self.output, Access.RW),
        ]

    def bind_input(self, texture):
        self.input = texture
        return self

    def bind_color_output(self, texture):
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
        self.pipeline = self.create_pipeline(
            device,
            shader_module,
            fragment_entry='downsampler_fragment_shader',
        )

        # bind groups
        self.instantiate_input_bind_group(device)
        self.instantiate_uniforms_bind_group(device, 1)

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
        self.instantiate_input_bind_group(device)

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
        rpass = encoder.begin_render_pass(**self.pass_descriptor)
        rpass.set_pipeline(self.pipeline)
        rpass.set_bind_group(0, self.input_bind_group)
        rpass.set_bind_group(1, self.uniforms_bind_group)
        rpass.draw(vertex_count)
        rpass.end()

    def instantiate_input_bind_group(self, device):
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
                )
            ],
        )


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Upsampler

class Upsampler(RenderPass, Parameterized):

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

    def bindings(self):
        assert self.input is not None
        assert self.input_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None
        return [
            Binding('input', self.input, Access.RO),
            Binding('input sampler', self.input_sampler, Access.RO),
            Binding('uniforms', self.uniform_buffer, Access.RW),
            Binding('color output', self.output, Access.RW),
        ]

    def bind_input(self, texture):
        self.input = texture
        return self

    def bind_color_output(self, texture):
        self.output = texture
        return self

    def instantiate(self, device):

        # shader module
        shader_module = device.create_shader_module(
            label=self.make_label(f'shader module {self.shader.file}'),
            code=self.shader.code,
        )

        # pipeline
        self.pipeline = self.create_pipeline(
            device,
            shader_module,
            fragment_entry='upsampler_fragment_shader',
            blend=wgpu.BlendState(
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
            ),
        )

        # create bind groups
        self.instantiate_input_bind_group(device)
        self.instantiate_uniforms_bind_group(device, 1)

        # create render pass descriptor
        self.pass_descriptor = wgpu.RenderPassDescriptor(
            label=self.make_label('render pass'),
            color_attachments=[
                wgpu.RenderPassColorAttachment(
                    clear_value=(0, 0, 0, 1),
                    load_op='load',
                    store_op='store',
                    view=...,   # set in execute()
                ),
            ],
        )

    def resize(self, device, size):
        self.instantiate_input_bind_group(device)

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
        rpass = encoder.begin_render_pass(**self.pass_descriptor)
        rpass.set_pipeline(self.pipeline)
        rpass.set_bind_group(0, self.input_bind_group)
        rpass.set_bind_group(1, self.uniforms_bind_group)
        rpass.draw(vertex_count)
        rpass.end()

    def instantiate_input_bind_group(self, device):
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
                )
            ],
        )


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Upsample Mixer

class UpsampleMixer(RenderPass, Parameterized):

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

    def bindings(self):
        assert self.image_input is not None
        assert self.image_sampler is not None
        assert self.bloom_input is not None
        assert self.bloom_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None
        return [
            Binding('image input', self.image_input, Access.RO),
            Binding('image sampler', self.image_sampler, Access.RO),
            Binding('bloom input', self.bloom_input, Access.RO),
            Binding('bloom sampler', self.bloom_sampler, Access.RO),
            Binding('uniforms', self.uniform_buffer, Access.RW),
            Binding('color output', self.output, Access.RW),
        ]

    def bind_image_input(self, texture):
        self.image_input = texture
        return self

    def bind_bloom_input(self, texture):
        self.bloom_input = texture
        return self

    def bind_color_output(self, texture):
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
        self.pipeline = self.create_pipeline(
            device,
            shader_module,
            fragment_entry='upsample_mixer_fragment_shader',
        )

        # bind groups
        self.instantiate_image_input_bind_group(device)
        self.instantiate_bloom_input_bind_group(device)
        self.instantiate_uniforms_bind_group(device, 1)

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
        self.instantiate_image_input_bind_group(device)
        self.instantiate_bloom_input_bind_group(device)

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
        rpass = encoder.begin_render_pass(**self.pass_descriptor)
        rpass.set_pipeline(self.pipeline)
        rpass.set_bind_group(0, self.image_input_bind_group)
        rpass.set_bind_group(1, self.uniforms_bind_group)
        rpass.set_bind_group(2, self.bloom_input_bind_group)
        rpass.draw(vertex_count)
        rpass.end()

    def instantiate_image_input_bind_group(self, device):
        self.image_input_bind_group = device.create_bind_group(
            label=self.make_label('image input bind group'),
            layout=self.pipeline.get_bind_group_layout(0),
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self.image_input.current_view(),
                ),
                wgpu.BindGroupEntry(
                    binding=1,
                    resource=self.image_sampler.resource_descriptor(),
                ),
            ],
        )

    def instantiate_bloom_input_bind_group(self, device):
        self.bloom_input_bind_group = device.create_bind_group(
            label=self.make_label('bloom input bind group'),
            layout=self.pipeline.get_bind_group_layout(0),
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self.bloom_input.current_view(),
                ),
                wgpu.BindGroupEntry(
                    binding=1,
                    resource=self.bloom_sampler.resource_descriptor(),
                ),
            ],
        )
