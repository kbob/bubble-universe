from dataclasses import dataclass

import wgpu

from constants import *
from copier import CopyPass
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

rotor = Rotor(1 + 2 * BLOOM_MIP_LEVELS)

class BloomSubgraph(Subgraph):

    """light bloom"""

    @dataclass
    class _Parameters:
        bloom_amount: float = Defaults.BLOOM_AMOUNT
        bloom_size: float = Defaults.BLOOM_SIZE

    def __init__(self, name='bloomer'):
        super().__init__(name)
        self.input = None
        self.output = None
        self._parameters = self._Parameters()
        self.mip_textures = None
        shader_file = 'bloom.wgsl'
        shader_source = self.read_shader(shader_file)
        self.shader = Shader(shader_file, shader_source)
        self.downsampler = Downsampler(self.shader)
        self.upsampler = Upsampler(self.shader)
        self.upsample_mixer = UpsampleMixer(self.shader)
        # DEBUG
        self.copier = CopyPass()

    def update_parameters(self, bloom_amount, bloom_size):
        self._parameters.bloom_amount = bloom_amount
        self._parameters.bloom_size = bloom_size

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
        print('BloomSubpass instantiate')
        assert self.input is not None
        assert self.output is not None

        # Calculate mip texture sizes
        size = self.input.current_size()
        assert size == self.output.current_size()
        self.mip_sizes = [
            (max(1, size[0] // 2**i), max(1, size[1] // 2**i))
            for i in range(1, BLOOM_MIP_LEVELS + 1)
        ]
        # self.mip_sizes = [
        #     (max(1, size[0] // 2**i), max(1, size[1] // 2**i))
        #     for i in range(1, 6)
        # ]
        print(f'{self.mip_sizes = }')

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
        (self.downsampler
            .bind_input(self.input)
            .bind_color_output(self.output)
        )
        (self.upsampler
            .bind_input(self.input)
            .bind_color_output(self.output)
        )
        (self.upsample_mixer
            .bind_image_input(self.input)
            .bind_bloom_input(self.mip_textures[0])
            .bind_color_output(self.output)
        )
        # DEBUG
        (self.copier
            .bind_input(self.mip_textures[-1])
            .bind_color_output(self.output)
        )
        self.instantiate_subgraph(
            device=device,
            passes=[
                self.downsampler,
                # DEBUG
                self.copier,
                self.upsampler,
                self.upsample_mixer,
            ],
            external_resources=[
                self.input,
                self.output,
            ],
        )

    def resize(self, device, size):
        # who knows?
        raise NotImplementedError()
    
    def execute(self, device, encoder):
        global rotor
        rotor.inc()
        # print(f'Subgraph.execute: {int(rotor) = }')

        def short_return(texture):
            (self.copier
                .bind_input(texture)
                .bind_color_output(self.output)
                .resize(device, None)
            )
            self.copier.execute(device, encoder)

        # check for buffer size change

        if rotor == 0:
            return short_return(self.input)

        # Downsample


        src = self.input
        for (i, dest) in enumerate(self.mip_textures, 1):
            src_size = src.current_size()
            dest_size = dest.current_size()
            # if min(dest_size) < 6:
            #     break
            (self.downsampler.update_parameters(
                    viewport_size=src_size,
                )
                .bind_input(src)
                .bind_color_output(dest)
                .execute(device, encoder)
            )
            src = dest
            if rotor == i:
                print(f'downsampling return {i = }')
                return short_return(src)

        # Upsample

        self.upsampler.update_parameters(
            bloom_size=self._parameters.bloom_size,
        )
        for (i, dest) in enumerate(self.mip_textures[-2::-1], 1 + BLOOM_MIP_LEVELS):
            dest_size = dest.current_size()
            (self.upsampler
                .bind_input(src)
                .bind_color_output(dest)
                .execute(device, encoder)
            )
            src = dest
            if rotor == i:
                print(f'downsampling return {i = }')
                return short_return(src)
            # if i == 10:
            #     return short_return(src)

        # Final upsample and mix

        # XXX can set the bindings once per resize
        (self.upsample_mixer.update_parameters(
                bloom_size=self._parameters.bloom_size,
                bloom_amount=self._parameters.bloom_amount,
            )
            .bind_image_input(self.input)
            .bind_bloom_input(self.mip_textures[0])
            .bind_color_output(self.output)
            .execute(device, encoder)
        )


@dataclass
class Shader:
    file: str
    code: str

# common uniforms struct across all three render passes
class _Uniforms(Uniforms):
    viewport_size: vec2f = (1, 1)
    filter_radius: f32 = Defaults.BLOOM_SIZE
    bloom_strength: f32 = Defaults.BLOOM_AMOUNT


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Downsampler

class Downsampler(RenderPass):

    @dataclass
    class _Parameters:
        viewport_size: tuple[float, float] = Defaults.CANVAS_SIZE

    # class _Uniforms(Uniforms):
    #     size: f32 = 1

    def __init__(self, shader):
        super().__init__('bloom downsampler')
        self._parameters = self._Parameters()
        self.input = None
        self.input_sampler = Sampler(
            name='downsampler input sampler',
            min_filter='linear',
            mag_filter='linear',
        )
        self.uniform_buffer = UniformBuffer('downsampler uniforms', _Uniforms)
        self.output = None
        self.shader = shader

    def update_parameters(self, viewport_size):
        self._parameters.viewport_size = viewport_size
        return self

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
        print(f'Downsampler instantiate')
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
        # self.input_bind_group = device.create_bind_group(
        #     label=self.make_label('input bind group'),
        #     layout=self.pipeline.get_bind_group_layout(0),
        #     entries=[
        #         wgpu.BindGroupEntry(
        #             binding=0,
        #             resource=self.input.current_view(),
        #         ),
        #         wgpu.BindGroupEntry(
        #             binding=1,
        #             resource=self.input_sampler.resource_descriptor(),
        #         )
        #     ],
        # )
        self.uniforms_bind_group = device.create_bind_group(
            label=self.make_label('uniforms bind group'),
            layout=self.pipeline.get_bind_group_layout(1),
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self.uniform_buffer.resource_descriptor(),
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
        assert self.input is not None
        assert self.input_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None

        # current_size = self.output.current_size()
        current_view = self.output.current_view()
        current_size = current_view.size[:2]
        src_size = self.input.current_view().size[:2]
        # print(f'Downsampler.execute: {current_view.label = }')
        # print(f'                     {current_size       = }')
        # print(f'                     {src_size           = }')

        uniforms = _Uniforms(
            viewport_size=src_size,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())        

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

        self.pass_descriptor.color_attachments[0].view = current_view

        vertex_count = 3
        rpass = encoder.begin_render_pass(**self.pass_descriptor)
        rpass.set_pipeline(self.pipeline)
        rpass.set_bind_group(0, self.input_bind_group)
        rpass.set_bind_group(1, self.uniforms_bind_group)
        rpass.draw(vertex_count)
        rpass.end()


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Upsampler

class Upsampler(RenderPass):

    @dataclass
    class _Parameters:
        bloom_size: float = Defaults.BLOOM_SIZE

    def __init__(self, shader):
        super().__init__('bloom upsampler')
        self._parameters = self._Parameters()
        self.input = None
        self.input_sampler = Sampler(
            name='upsampler input sampler',
            min_filter='linear',
            mag_filter='linear',
        )
        self.uniform_buffer = UniformBuffer('uniforms', _Uniforms)
        self.output = None
        self.shader = shader

    def update_parameters(self, bloom_size):
        self._parameters.bloom_size = bloom_size
        return self

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
        # self.input_bind_group = device.create_bind_group(
        #     label=self.make_label('input bind group'),
        #     layout=self.pipeline.get_bind_group_layout(0),
        #     entries=[
        #         wgpu.BindGroupEntry(
        #             binding=0,
        #             resource=self.input.current_view(),
        #         ),
        #         wgpu.BindGroupEntry(
        #             binding=1,
        #             resource=self.input_sampler.resource_descriptor(),
        #         )
        #     ],
        # )
        self.uniforms_bind_group = device.create_bind_group(
            label=self.make_label('uniforms bind group'),
            layout=self.pipeline.get_bind_group_layout(1),
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self.uniform_buffer.resource_descriptor(),
                ),
            ],
        )

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
                ),
            ],
        )

    def execute(self, device, encoder):
        assert self.input is not None
        assert self.input_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None

        current_view = self.output.current_view()
        current_size = current_view.size[:2]
        # print(f'Upsampler.execute:   {current_view = }')
        # print(f'                     {current_size = }')

        uniforms = _Uniforms(
            filter_radius = self._parameters.bloom_size,
        )
        # print(f'Upsampler.execute: {uniforms.filter_radius = }')
        self.uniform_buffer.write_buffer(device, uniforms.as_data())        

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

        self.pass_descriptor.color_attachments[0].view = current_view

        vertex_count = 3
        rpass = encoder.begin_render_pass(**self.pass_descriptor)
        rpass.set_pipeline(self.pipeline)
        rpass.set_bind_group(0, self.input_bind_group)
        rpass.set_bind_group(1, self.uniforms_bind_group)
        rpass.draw(vertex_count)
        rpass.end()


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Upsample Mixer

class UpsampleMixer(RenderPass):

    @dataclass
    class _Parameters:
        bloom_size: float = Defaults.BLOOM_SIZE
        bloom_amount: float = Defaults.BLOOM_AMOUNT

    def __init__(self, shader):
        super().__init__('bloom upsample mixer')
        self._parameters = self._Parameters()
        self.image_input = None
        self.image_sampler = Sampler('mix input sampler')
        self.bloom_input = None
        self.bloom_sampler = Sampler(
            name='miz input sampler',
            min_filter='linear',
            mag_filter='linear',
        )
        self.uniform_buffer = UniformBuffer('uniforms', _Uniforms)
        self.output = None
        self.shader = shader

    def update_parameters(self, bloom_size, bloom_amount):
        self._parameters.bloom_size = bloom_size
        self._parameters.bloom_amount = bloom_amount
        return self

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
        print(f'UpsampleMixer instantiate')
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
        print(f'UpsampleMixer.instantiate: {self.image_input.name = }')
        print(f'                           {self.bloom_input.name = }')
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
        self.uniforms_bind_group = device.create_bind_group(
            label=self.make_label('uniforms bind group'),
            layout=self.pipeline.get_bind_group_layout(1),
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self.uniform_buffer.resource_descriptor(),
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
        raise NotImplementedError()

    def execute(self, device, encoder):
        assert self.image_input is not None
        assert self.image_sampler is not None
        assert self.bloom_input is not None
        assert self.bloom_sampler is not None
        assert self.uniform_buffer is not None
        assert self.output is not None

        current_view = self.output.current_view()
        current_size = current_view.size[:2]
        # print(f'UpsampleMixer.execute: {current_view = }')
        # print(f'                       {current_size = }')

        uniforms = _Uniforms(
            filter_radius = self._parameters.bloom_size,
            bloom_strength = self._parameters.bloom_amount,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())        

        self.pass_descriptor.color_attachments[0].view = current_view

        # print(f'UpsampleMixer.execute: {self.image_input.name = }')
        # print(f'                       {self.bloom_input.name = }')

        vertex_count = 3
        rpass = encoder.begin_render_pass(**self.pass_descriptor)
        rpass.set_pipeline(self.pipeline)
        rpass.set_bind_group(0, self.image_input_bind_group)
        rpass.set_bind_group(1, self.uniforms_bind_group)
        rpass.set_bind_group(2, self.bloom_input_bind_group)
        rpass.draw(vertex_count)
        rpass.end()
