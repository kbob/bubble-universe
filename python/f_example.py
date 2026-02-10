#!/usr/bin/env python3

"""python translation of the first texture example at
   https://webgpufundamentals.org/webgpu/lessons/webgpu-textures.html
"""

import os.path

import numpy as np
from rendercanvas.auto import RenderCanvas, loop
import wgpu


# Internal/performance constants
CANVAS_SIZE = (675, 540)
MAX_FPS = 60                # FPS = frames/second


shader_source = '''
struct InterStage {
    @builtin(position)position: vec4f,
    @location(0) texcoord: vec2f,
};

@vertex fn vertex_shader(
    @builtin(vertex_index) vertex_index: u32
) -> InterStage {
    let pos = array(
        // 1st triangle
        vec2f(0.0, 0.0),        // 1st triangle
        vec2f(1.0, 0.0),
        vec2f(0.0, 1.0),

        vec2f(0.0, 1.0),        // 2nd triangle
        vec2f(1.0, 0.0),
        vec2f(1.0, 1.0),
    );

    var out: InterStage;
    let xy = pos[vertex_index];
    out.position = vec4f(xy, 0.0, 1.0);
    out.texcoord = xy;
    return out;
};

@group(0) @binding(0) var our_sampler: sampler;
@group(0) @binding(1) var our_texture: texture_2d<f32>;

@fragment fn fragemnt_shader(in: InterStage) -> @location(0) vec4f {
    return textureSample(our_texture, our_sampler, in.texcoord);
};
'''

TEXTURE_WIDTH = 5
TEXTURE_HEIGHT = 7
_ = [255,   0,   0, 255]
y = [255, 255,   0, 255]
b = [  0,   0, 255, 255]
texture_data = np.array(
    [
        [b, _, _, _, _,],
        [_, y, y, y, _,],
        [_, y, _, _, _,],
        [_, y, y, _, _,],
        [_, y, _, _, _,],
        [_, y, _, _, _,],
        [_, _, _, _, _,],
    ],
    dtype='uint8',
)
texture_data = texture_data[::-1, ].copy()     # flip it upside down


class Effer:

    def __init__(self):
        self._time = 0

    def init_graphics(self, device, output_format):
        self._device = device

        # create shader module
        shader = device.create_shader_module(
            code=shader_source,
        )

        # create texture and view
        texture = device.create_texture(
            label='yellow F on red',
            size=[TEXTURE_WIDTH, TEXTURE_HEIGHT],
            format='rgba8unorm',
            usage=(wgpu.TextureUsage.TEXTURE_BINDING |
                   wgpu.TextureUsage.COPY_DST),
        )
        texture_view = texture.create_view(
            label='texture view',
            format='rgba8unorm',
            dimension='2d',
            usage=wgpu.TextureUsage.TEXTURE_BINDING,
        )

        device.queue.write_texture(
            destination=wgpu.TexelCopyTextureInfo(
                texture=texture,
            ),
            data=texture_data,
            data_layout=wgpu.TexelCopyBufferLayout(
                bytes_per_row=texture_data.strides[0],
            ),
            size=texture_data.shape[1::-1],
        )

        # create sampler
        sampler = device.create_sampler(
            label='sampler',
        )

        # create pipeline
        self._pipeline = device.create_render_pipeline(
            label='drawing pipeline',
            layout='auto',
            vertex=wgpu.VertexState(
                module=shader,
            ),
            fragment=wgpu.FragmentState(
                module=shader,
                targets=[
                    wgpu.ColorTargetState(
                        format=output_format,
                    ),
                ],
            ),
        )

        # create bind group
        self._bind_group = device.create_bind_group(
            label='the bind group',
            layout=self._pipeline.get_bind_group_layout(0),
            entries=[
                wgpu.BindGroupEntry(
                    binding=0,
                    resource=sampler,
                ),
                wgpu.BindGroupEntry(
                    binding=1,
                    resource=texture_view,
                ),
            ],
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

        # Create a command encoder
        encoder = device.create_command_encoder(label='the encoder')

        # patch in the output texture
        out_view = output_texture.create_view()
        drawing_pass_kwargs = dict(self._drawing_pass_desc)
        drawing_pass_kwargs['color_attachments'][0].view = out_view

        # Add the drawing render pass to the encoder
        vertex_count = 6
        drawing_pass = encoder.begin_render_pass(**drawing_pass_kwargs)
        drawing_pass.set_pipeline(self._pipeline)
        drawing_pass.set_bind_group(0, self._bind_group)
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
        update_mode='ondemand',
        max_fps=MAX_FPS,
        )
    context = canvas.get_wgpu_context()
    preferred_format = context.get_preferred_format(adapter)
    context.configure(device=device, format=preferred_format)

    effer = Effer()
    effer.init_graphics(device, preferred_format)
    parameters = None

    def draw_frame():
        dest_texture = context.get_current_texture()
        effer.draw_frame(parameters, dest_texture)

    canvas.request_draw(draw_frame)

    loop.run()


if __name__ == '__main__':
    run_app()
