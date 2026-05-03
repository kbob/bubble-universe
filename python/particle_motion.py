from dataclasses import dataclass

from constants import *
from math import ceil
from parameterized import ParameterizedMixIn
from passes import Access, Binding, ComputePass
from resources import StorageBuffer, UniformBuffer
from wgsl_types import *


class ParticleMotionPass(ComputePass, ParameterizedMixIn):

    @dataclass
    class Parameters:
        seq_count: int = Defaults.SEQ_COUNT
        seq_length: int = Defaults.SEQ_LENGTH
        s_blocks: int = Defaults.S_BLOCKS
        r: float = Defaults.R
        s: float = Defaults.S
        t: float = 0

    class _Uniforms(Uniforms):
        seq_count: u32 = Defaults.SEQ_COUNT
        seq_length: u32 = Defaults.SEQ_LENGTH
        s_blocks: u32 = Defaults.S_BLOCKS
        r: f32 = Defaults.R
        s: f32 = Defaults.S
        t: f32 = 0

    def __init__(self, name='particles'):
        super().__init__(name)
        self.uvs = None
        self.shader_file='particles.wgsl'
        self.shader = self.read_shader(self.shader_file)

    def resources(self):
        assert self.uvs is not None
        assert self.uniform_buffer is not None
        return [
            Binding((0, 0), 'uv', self.uvs, Access.WO),
            Binding((1, 0), 'uniforms', self.uniform_buffer, Access.RO),
        ]

    def bind_uvs(self, buffer):
        self.uvs = buffer
        return self

    def instantiate(self, device):
        assert self.shader
        assert self.uvs is not None

        shader_module = device.create_shader_module(
            label=self.make_label(f'shader {self.shader_file}'),
            code=self.shader,
        )

        self.instantiate_pipeline(device, shader_module)
        self.instantiate_bind_groups(device)
        self.instantiate_pass_descriptor()

    def execute(self, device, encoder):

        uniforms = self._Uniforms(
            seq_count=self._parameters.seq_count,
            seq_length=self._parameters.seq_length,
            s_blocks=self._parameters.s_blocks,
            r=self._parameters.r,
            s=self._parameters.s,
            t=self._parameters.t,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())

        workgroup_count = ceil(self._parameters.seq_count / WORKGROUP_SIZE)
        self.encode_compute_pass(encoder, workgroup_count)
