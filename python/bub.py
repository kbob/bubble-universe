#!/usr/bin/env python3

from dataclasses import dataclass
from math import ceil, cos, sin, tau
import os.path
import re

import wgpu
from rendercanvas.auto import RenderCanvas, loop

from wgsl_types import *


# Internal/performance constants
CANVAS_SIZE = (675, 540)
MAX_FPS = 60                # FPS = frames/second
MAX_SEQ_COUNT = 200
MAX_SEQ_LENGTH = 200
BORDER = 0.1                    # fraction of viewport size
BLEND_MODE = 'blend'            # 'add' or 'blend'
WORKGROUP_SIZE = 64             # defined in compute shader(s)


class Defaults:
    SEQ_COUNT = 200
    SEQ_LENGTH = 200
    SPEED = 0.5                 # radians/sec
    R = tau / 235               # radians
    PARTICLE_SIZE = 3           # pixels normalized to CANVAS_SIZE


particle_shader_source = ''' /* WGSL */
// parameters
//  m, n, t, r
//  output buffer
//  uv: array<vec2f, m * n>;

struct Uniforms {
    seq_count: u32,
    seq_length: u32,
    t: f32,                     // time
    r: f32,                     // magic number
};

@group(0) @binding(0) var<storage, read_write> uvs: array<vec2f>;
@group(1) @binding(0) var<uniform> uniforms: Uniforms;

@compute @workgroup_size(64)
fn compute_shader(@builtin(global_invocation_id) id: vec3u) {

  let U = uniforms;

  let i = id.x;
  if i < U.seq_count {
    let fi = f32(i);
    var u: f32 = 0.0;
    var v: f32 = 0.0;
    var x: f32 = 0.0;

    uvs[i * U.seq_length] = vec2f(u, v);
    for (var j = 1u; j < U.seq_length; j++) {

      u = sin(fi + v) + sin(U.r * fi + x);
      v = cos(fi + v) + cos(U.r * fi + x);
      x = u + U.t;
      uvs[i * U.seq_length + j] = vec2f(u, -v);
    }
  }
}
'''

drawing_shader_source = ''' /* WGSL */
    struct Uniforms {
    particle_size: vec2f,
    scale: vec2f,
    seq_count: u32,
    seq_length: u32,
    };

    @group(0) @binding(0) var<storage, read> uv_buffer: array<vec2f>;
    @group(1) @binding(0) var<uniform> uniforms: Uniforms;

    struct InterStage {
    @builtin(position) pos: vec4f,
    @location(0) @interpolate(flat) ij: vec2u,
    @location(1) @interpolate(perspective) pt: vec2f,
    };

    // Vertex Shader
    //  - call 6 times per particle; emits a quad.

    @vertex fn vertex_shader(
    @builtin(vertex_index) vertex_index : u32
    ) -> InterStage {

    let U = uniforms;

    let points = array<vec2f, 6>(
        vec2f(-1.0, -1.0),
        vec2f( 1.0, -1.0),
        vec2f(-1.0,  1.0),
        vec2f(-1.0,  1.0),
        vec2f( 1.0, -1.0),
        vec2f( 1.0,  1.0),
    );

    let uv_index = vertex_index / 6u;
    let k = vertex_index % 6u;
    let i = uv_index / U.seq_length;
    let j = uv_index % U.seq_length;
    let ij = vec2u(i, j);
    let uv = uv_buffer[uv_index];
    let pt = points[k];
    let xy = U.scale * uv + U.particle_size * pt;

    var out: InterStage;
    out.pos = vec4f(xy, 0.0, 1.0);
    out.ij = ij;
    out.pt = pt;

    return out;
    }

    // Fragment Shader
    //  - trims particle to a circle, transparent near edges
    //  - color is rgb(i, j, 99)

    @fragment fn fragment_shader(in: InterStage) -> @location(0) vec4f {

    let U = uniforms;

    // i is the sequence number,
    // j is the sequence position

    let i = in.ij[0];
    let j = in.ij[1];
    let r = f32(i) / f32(U.seq_count) * 200.0 / 255.0;
    let g = f32(j) / f32(U.seq_length) * 200.0 / 255.0;
    let b = 99.0 / 255.0;

    let rad2 = dot(in.pt, in.pt);
    var a = (1.0 - rad2);
    // a *= 1 - (U.particle_size[1] * 28);
    if a < 0.01 {
        a = 0.0;
        discard;
    }

    return vec4f(r*a, g*a, b*a, a);
    }
'''


@dataclass
class BubblerParameters:
    seq_count: int = Defaults.SEQ_COUNT
    seq_length: int = Defaults.SEQ_LENGTH
    speed: float = Defaults.SPEED
    r: float = Defaults.R
    particle_size = Defaults.PARTICLE_SIZE

    def calc_dt(self, fps):
        return self.speed / fps


class ParticleUniforms(Uniforms):
    seq_count: u32 = Defaults.SEQ_COUNT
    seq_length: u32 = Defaults.SEQ_LENGTH
    t: f32
    r: f32 = Defaults.R

class DrawingUniforms(Uniforms):
    particle_size: vec2f = (Defaults.PARTICLE_SIZE / CANVAS_SIZE[1], ) * 2
    scale: vec2f = (1, 1)
    seq_count: u32 = Defaults.SEQ_COUNT
    seq_length: u32 = Defaults.SEQ_LENGTH


def create_shader_from_string(device, string, **kwargs):
    assert 'label' in kwargs
    kwargs['code'] = string
    return device.create_shader_module(**kwargs)


def camel_to_snake(name):
    return re.sub(r'(?!^)(?=[A-Z])', '_', name).lower()

assert camel_to_snake('camelCaseName') == 'camel_case_name'
assert camel_to_snake('PascalCaseName') == 'pascal_case_name'

def create_uniform_buffer(device, uniforms_type):
    return device.create_buffer(
        label=f'{camel_to_snake(uniforms_type.__name__)}',
        size=uniforms_type.bytes,
        usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
    )

def choose_blend_mode():
    if BLEND_MODE == 'add':
        return wgpu.BlendState(
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
        )
    elif BLEND_MODE == 'blend':
        return wgpu.BlendState(
            color=wgpu.BlendComponent(
                operation='add',
                src_factor='one',
                dst_factor='one-minus-src-alpha',
            ),
            alpha=wgpu.BlendComponent(
                operation='add',
                src_factor='one',
                dst_factor='one-minus-src-alpha',
            ),
        )
    else:
        assert False, f'unknown BLEND_MODE of {BLEND_MODE!r}'

class Bubbler:

    def __init__(self):
        self._time = 0

    def inc_time(self, dt):
        assert -tau < dt < tau
        self._time += dt
        if self._time < 0:
            self._time += tau
        if self._time >= tau:
            self._time -= tau

    def init_graphics(self, device, output_format):
        self._device = device

        # create shader modules
        # particle_shader = create_shader_from_file(device, 'particles.wgsl')
        # drawing_shader = create_shader_from_file(device, 'draw.wgsl')
        particle_shader = create_shader_from_string(
            device,
            particle_shader_source,
            label='particle shader',
        )
        drawing_shader = create_shader_from_string(
            device,
            drawing_shader_source,
            label='drawing shader',
        )

        # create buffers
        uv_bytes = MAX_SEQ_COUNT * MAX_SEQ_LENGTH * vec2f.bytes
        self._uv_buffer = device.create_buffer(
            label='uv buffer',
            size=uv_bytes,
            usage=wgpu.BufferUsage.STORAGE,
        )

        self._pu_buffer = create_uniform_buffer(device, ParticleUniforms)
        self._du_buffer = create_uniform_buffer(device, DrawingUniforms)

        # create bind group layouts
        uv_rw_layout = device.create_bind_group_layout(
            label='uv rw bind group layout',
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
        uv_ro_layout = device.create_bind_group_layout(
            label='uv ro bind group layout',
            entries=[
                wgpu.BindGroupLayoutEntry(
                    binding=0,
                    visibility=wgpu.ShaderStage.VERTEX,
                    buffer=wgpu.BufferBindingLayout(
                        type='read-only-storage',
                    ),
                ),
            ],
        )
        pu_layout = device.create_bind_group_layout(
            label='pu bind group layout',
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
        du_layout = device.create_bind_group_layout(
            label='du bind group layout',
            entries=[
                wgpu.BindGroupLayoutEntry(
                    binding=0,
                    visibility=(wgpu.ShaderStage.VERTEX |
                                wgpu.ShaderStage.FRAGMENT),
                    buffer=wgpu.BufferBindingLayout(
                        type='uniform',
                    ),
                ),
            ],
        )

        # create bind groups
        self._uv_rw_bind_group = device.create_bind_group(
            label='uv rw bind group',
            layout=uv_rw_layout,
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self._uv_buffer,
                ),
            ],
        )
        self._uv_ro_bind_group = device.create_bind_group(
            label='uv re bind group',
            layout=uv_ro_layout,
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self._uv_buffer,
                ),
            ],
        )
        self._pu_bind_group = device.create_bind_group(
            label='pu bind group',
            layout=pu_layout,
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self._pu_buffer,
                ),
            ],
        )
        self._du_bind_group = device.create_bind_group(
            label='du bind group',
            layout=du_layout,
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=self._du_buffer,
               ),
            ],
        )

        # Create pipeline layouts

        pp_layout = device.create_pipeline_layout(
            label='pp layout',
            bind_group_layouts=[
                uv_rw_layout,
                pu_layout,
            ],
        )
        dp_layout = device.create_pipeline_layout(
            label='dp layout',
            bind_group_layouts=[
                uv_ro_layout,
                du_layout,
            ],
        )

        # Create pipelines
        self._particle_pipeline = device.create_compute_pipeline(
            label='particle pipeline',
            layout=pp_layout,
            compute=wgpu.ProgrammableStage(
                module=particle_shader,
            ),
        )
        self._drawing_pipeline = device.create_render_pipeline(
            label='drawing pipeline',
            layout=dp_layout,
            vertex=wgpu.VertexState(
                module=drawing_shader,
            ),
            fragment=wgpu.FragmentState(
                module=drawing_shader,
                targets=[
                    wgpu.ColorTargetState(
                        blend=choose_blend_mode(),
                        format=output_format,
                    ),
                ],
            ),
        )

        # Partially create the drawing pass descriptor
        self._drawing_pass_desc = wgpu.RenderPassDescriptor(
            label='drawing pass',
            color_attachments=[
                wgpu.RenderPassColorAttachment(
                    clear_value=(0, 0, 0, 1),
                    load_op='clear',
                    store_op='store',
                    view=...,           # set in draw_frame()
                ),
            ],
        )

    def draw_frame(self, parameters, output_texture):
        device = self._device

        def adjust_for_aspect(x):
            w, h = output_texture.width, output_texture.height
            assert w != 0 and h != 0
            if h > w:
                return (x, x * w / h)
            else:
                return (x * h / w, x)

        # Set the particle pass's uniforms
        pu_uniforms = ParticleUniforms(
            seq_count = parameters.seq_count,
            seq_length = parameters.seq_length,
            t=self._time,
            r=parameters.r,
        )
        device.queue.write_buffer(self._pu_buffer, 0, pu_uniforms.as_data())

        # Set the drawing pass's uniforms
        du_uniforms = DrawingUniforms(
            particle_size=adjust_for_aspect(
                parameters.particle_size / CANVAS_SIZE[1],
            ),
            scale=adjust_for_aspect((1 - BORDER) / 2),
            seq_count=parameters.seq_count,
            seq_length=parameters.seq_length,
        )
        device.queue.write_buffer(self._du_buffer, 0, du_uniforms.as_data())

        # Create a command encoder
        encoder = device.create_command_encoder(label='the encoder')

        # Add the particle compute pass to the encoder
        workgroup_count = ceil(parameters.seq_count / WORKGROUP_SIZE)
        particle_pass = encoder.begin_compute_pass(label='particle pass')
        particle_pass.set_pipeline(self._particle_pipeline)
        particle_pass.set_bind_group(0, self._uv_rw_bind_group)
        particle_pass.set_bind_group(1, self._pu_bind_group)
        particle_pass.dispatch_workgroups(workgroup_count)
        particle_pass.end()

        # patch in the output texture
        out_view = output_texture.create_view()
        drawing_pass_kwargs = dict(self._drawing_pass_desc)
        drawing_pass_kwargs['color_attachments'][0].view = out_view

        # Add the drawing render pass to the encoder
        vertex_count = parameters.seq_count * parameters.seq_length * 6
        drawing_pass = encoder.begin_render_pass(**drawing_pass_kwargs)
        drawing_pass.set_pipeline(self._drawing_pipeline)
        drawing_pass.set_bind_group(0, self._uv_ro_bind_group)
        drawing_pass.set_bind_group(1, self._du_bind_group)
        drawing_pass.draw(vertex_count)
        drawing_pass.end()

        command_buffer = encoder.finish()
        device.queue.submit([command_buffer])


def run_app():
    adapter = wgpu.gpu.request_adapter_sync()
    device = adapter.request_device_sync()

    canvas = RenderCanvas(
        size=CANVAS_SIZE,
        title='Bubble Universe',
        update_mode='continuous',
        max_fps=MAX_FPS,
        )
    context = canvas.get_wgpu_context()
    preferred_format = context.get_preferred_format(adapter)
    context.configure(device=device, format=preferred_format)

    bubbler = Bubbler()
    bubbler.init_graphics(device, preferred_format)
    parameters = BubblerParameters()

    def draw_frame():
        dest_texture = context.get_current_texture()
        bubbler.draw_frame(parameters, dest_texture)
        bubbler.inc_time(parameters.calc_dt(MAX_FPS))

    canvas.request_draw(draw_frame)

    loop.run()


if __name__ == '__main__':
    run_app()
