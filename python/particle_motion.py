import wgpu

from constants import *
from passes import Binding, ComputePass, Access
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
        self.uvs = None
        self.uniform_buffer = UniformBuffer('particle uniforms', self._Uniforms)
        self.shader = self.read_shader('particles.wgsl')

    def bindings(self):
        assert self.uvs and self.uniform_buffer
        return [
            Binding('uv', self.uvs, Access.RW),
            Binding('uniforms', self.uniform_buffer, Access.RW),
        ]

    def bind_uvs(self, buffer):
        self.uvs = buffer

    def instantiate(self, device):
        assert self.shader
        assert self.uvs

        shader_module = device.create_shader_module(
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
            label=self.make_label('compute pass descriptor'),
        )
