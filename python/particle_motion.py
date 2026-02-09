import wgpu

from constants import *
from passes import ComputePass
from wgsl_types import *

class ParticleMotionUniforms(Uniforms):
    seq_count: u32 = Defaults.SEQ_COUNT
    seq_length: u32 = Defaults.SEQ_LENGTH
    t: f32 = 0
    r: f32 = Defaults.R

class ParticleMotionPass(ComputePass):

    def __init__(self, name='particles'):
        super().__init__(name)
        self.uvs = None
        self.uniforms = ParticleMotionUniforms()
        self.shader = self.read_shader('particles.wgsl')

    def bind_uvs(self, buffer):
        self.uvs = buffer

    def instantiate(self, device):
        assert self.shader
        assert self.uvs

        shader_module = device.create_shader_module(
            code=self.shader,
        )

        uv_layout = device.create_bind_group_layout(
            label=self.dymo.buffer_layout_label('uv'),
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
            label=self.dymo.buffer_layout_label('uniforms'),
            entries=[
                wgpu.BindGroupLayoutEntry(
                    binding=1,
                    visibility=wgpu.ShaderStage.COMPUTE,
                    buffer=wgpu.BufferBindingLayout(
                        type='uniform',
                    ),
                ),
            ],
        )

        self.uv_bind_group = device.create_bind_group(
            label=self.dymo.bind_group_label('uv'),
            layout=uv_layout,
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=wgpu.BufferBinding(
                        buffer=self.uvs,
                    ),
                ),
            ],
        )

        self.uniforms_bind_group = device.bind

        pipeline_layout=device.create_pipeline_layout(
            label=self.dymo.pipeline_layout_label(),
            bind_group_layouts=[
                uv_layout,
                uniforms_layout,
            ]
        )

        self.pipeline = device.create_compute_pipeline(
            label=self.dymo.pipeline_label(),
            layout=pipeline_layout,
            compute=wgpu.ProgrammableStage(
                module=shader_module,
            ),
        )

        self.pass_descriptor = wgpu.ComputePassDescriptor(
            label=self.dymo.compute_pass_descriptor_label(),
        )
