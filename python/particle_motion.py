from dataclasses import dataclass

import wgpu

from constants import *
from math import ceil
from parameterized import Parameterized
from passes import Access, Binding, ComputePass
from resources import StorageBuffer, UniformBuffer
from wgsl_types import *


class ParticleMotionPass(ComputePass, Parameterized):

    @dataclass
    class Parameters:
        seq_count: int = Defaults.SEQ_COUNT
        seq_length: int = Defaults.SEQ_LENGTH
        t: float = 0
        r: float = Defaults.R

    class _Uniforms(Uniforms):
        seq_count: u32 = Defaults.SEQ_COUNT
        seq_length: u32 = Defaults.SEQ_LENGTH
        t: f32 = 0
        r: f32 = Defaults.R

    def __init__(self, name='particles'):
        super().__init__(name)
        self.uvs = None
        self.shader_file='particles.wgsl'
        self.shader = self.read_shader(self.shader_file)

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

        self.pipeline = device.create_compute_pipeline(
            label=self.make_label('pipeline'),
            layout='auto',
            compute=wgpu.ProgrammableStage(
                module=shader_module,
            ),
        )

        self.uv_bind_group = device.create_bind_group(
            label=self.make_label('uv bind group'),
            layout=self.pipeline.get_bind_group_layout(0),
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self.uvs.resource_descriptor(),
                ),
            ],
        )
        self.instantiate_uniforms_bind_group(device, 1)

        self.pass_descriptor = wgpu.ComputePassDescriptor(
            label=self.make_label('compute pass'),
        )

    def execute(self, device, encoder):

        uniforms = self._Uniforms(
            seq_count=self._parameters.seq_count,
            seq_length=self._parameters.seq_length,
            t=self._parameters.t,
            r=self._parameters.r,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())

        workgroup_count = ceil(self._parameters.seq_count / WORKGROUP_SIZE)
        cpass = encoder.begin_compute_pass(**self.pass_descriptor)
        cpass.set_pipeline(self.pipeline)
        cpass.set_bind_group(0, self.uv_bind_group)
        cpass.set_bind_group(1, self.uniforms_bind_group)
        cpass.dispatch_workgroups(workgroup_count)
        cpass.end()
