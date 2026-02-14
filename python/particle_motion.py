import wgpu

from constants import *
from math import ceil
from passes import Access, Binding, ComputePass
from resources import StorageBuffer, UniformBuffer
from wgsl_types import *


class ParticleMotionPass(ComputePass):

    class _Uniforms(Uniforms):
        seq_count: u32 = Defaults.SEQ_COUNT
        seq_length: u32 = Defaults.SEQ_LENGTH
        t: f32 = 0
        r: f32 = Defaults.R

    def __init__(self, name='particles'):
        super().__init__(name)
        self._uniforms = self._Uniforms()
        self.uvs = None
        self.uniform_buffer = UniformBuffer('particle uniforms', self._Uniforms)
        self.shader_file='particles.wgsl'
        self.shader = self.read_shader(self.shader_file)

    def update_parameters(self, seq_count, seq_length, t, r):
        self._uniforms.seq_count = seq_count
        self._uniforms.seq_length = seq_length
        self._uniforms.t = t
        self._uniforms.r = r

    def bindings(self):
        assert self.uvs
        assert self.uniform_buffer
        return [
            Binding('uv', self.uvs, Access.RW),
            Binding('uniforms', self.uniform_buffer, Access.RW),
        ]

    def bind_uvs(self, buffer):
        self.uvs = buffer
        return self

    def instantiate(self, device):
        assert self.shader
        assert self.uvs

        shader_module = device.create_shader_module(
            label=self.make_label(f'shader {self.shader_file}'),
            code=self.shader,
        )

        uv_layout = device.create_bind_group_layout(
            label=self.make_label('uv bind group layout'),
            entries=[
                wgpu.BindGroupLayoutEntry(
                    binding=0,
                    visibility=wgpu.ShaderStage.COMPUTE,
                    buffer=wgpu.BufferBindingLayout(
                        type='storage',
                    ),
                ),
            ],
        )

        uniforms_layout = device.create_bind_group_layout(
            label=self.make_label('uniforms bind group layout'),
            entries=[
                wgpu.BindGroupLayoutEntry(
                    binding=0,
                    visibility=wgpu.ShaderStage.COMPUTE,
                    buffer=wgpu.BufferBindingLayout(
                        type='uniform',
                    ),
                ),
            ],
        )

        self.uv_bind_group = device.create_bind_group(
            label=self.make_label('uv bind group'),
            layout=uv_layout,
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self.uvs.resource_descriptor(),
                ),
            ],
        )

        self.uniforms_bind_group = device.create_bind_group(
            label=self.make_label('uniforms bind group'),
            layout=uniforms_layout,
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=wgpu.BufferBinding(
                        buffer=self.uniform_buffer.resource_descriptor(),
                    ),
                ),
            ],
        )

        pipeline_layout=device.create_pipeline_layout(
            label=self.make_label('pipeline layout'),
            bind_group_layouts=[
                uv_layout,
                uniforms_layout,
            ]
        )

        self.pipeline = device.create_compute_pipeline(
            label=self.make_label('pipeline'),
            layout=pipeline_layout,
            compute=wgpu.ProgrammableStage(
                module=shader_module,
            ),
        )

        self.pass_descriptor = wgpu.ComputePassDescriptor(
            label=self.make_label('compute pass'),
        )

    def execute(self, device, encoder):

        # TO DO: update uniforms
        self.uniform_buffer.write_buffer(device, self._uniforms.as_data())

        workgroup_count = ceil(Defaults.SEQ_COUNT / WORKGROUP_SIZE)
        cpass = encoder.begin_compute_pass(**self.pass_descriptor)
        cpass.set_pipeline(self.pipeline)
        cpass.set_bind_group(0, self.uv_bind_group)
        cpass.set_bind_group(1, self.uniforms_bind_group)
        cpass.dispatch_workgroups(workgroup_count)
        cpass.end()
