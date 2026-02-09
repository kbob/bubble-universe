"""

Just thinking out loud about wgpu modularity.

I'd like to be able to declare a bunch of buffers and a bunch of render
passes and connect them together.


    class ParticleMotionPass(ComputePass):
        ...
    class DrawingPass(RenderPass):
        ...
    class TonemapPass(RenderPass):
        ...


    ParticleMotionPass particle_motion(...)

    # colormap and depth buffer are local to the drawer pass
    DrawingPass drawer(...)
    Texture colormap(...)
    DepthBuffer depth(...)
    connect_input(drawer, colormap, ...)
    connect_in_out(drawer, depth, ...)

    TonemapPass tonemapper(...)

    # uv is written by particle_motion and read by drawing_pass
    StorageBuffer uv(...)
    connect_output(particle_motion, uv, ...)
    connect_input(drawing_pass, uv, ...)

    connect_output(drawer, hdr_pixels, ...)
    connect_input(tonemapper, canvas, ...)

    render_graph = RenderGraph(
        [
            particle_motion,
            drawer,
            tonemapper,
        ],
        ...)

And then at draw_frame time, something like this.

    particle_motion.update_params(...)
    drawer.update_params(...)
    tonemapper.update_params(...)
    # buffers are implicit
    render_graph.execute()


Then I could swap out the draw pass, use a modified particle stream (or a
filter), use dynamic colormap, add/substitute a video to file destinatin, etc.

This kind of looks like what wgpu does with bindings, but could potentially
be less verbose at the expense of some flexibility.

The open question is, how flexible and terse can I make it?

=========

So here's a class hierarchy maybe.

class Resource:         # base class for all resources
class Uniforms(Resource):
class StorageBuffer(Resource):
class VertexBuffer(Resource):
class Texture(Resource):
class CanvasTexture(Texture):
class Sampler(Resource):


class Pass:             # base class for all passes
class ComputePass(Pass):
class ParticleMotionPass(ComputePass): # defines shaders and uniforms
class ColormapPass(ComputePass):
class RenderPass(Pass):
class DrawingPass(RenderPass):
class MaskedDrawingPass(RenderPass): # variant that suppresses some particles
class ToneMappingPass(RenderPass):

========

At init time, the goal is to build wgpu pipeline objects and
Render/ComputePassDescriptor objects (as far as possible).

    trace the graph, find all buffers and textures, create them
    for each graph,
        construct a GPURender/ComputePass

The pipelines will require shader modules, bindings, pipelines, blend modes...

Each pass will have some setters for things that aren't part of the uniforms,
or maybe the passes hide which parameters are uniforms and which are render
pass modifications.

========

The start of the hard work is RenderGraph's constructor.  


========

Bindings should be kept entirely within the compute/render pass objects.
Layouts are there; the shader source is there.

The wgpu pipeline should be Compute/RenderPass class state; the wgpu
compute/renderpass should be instance state.  That way, a pipeline can
be reused in several passes.  The bindings are part of the instance state.

=========

Files

generic WGPU stuff
   wgsl_types.py - scalars, vectors, and matrices
   labels.py - LabelMaker
   resources.py - Resource, Uniforms, StorageBuffer, Texture, Sampler
   passes.py - Pass, ComputePass, RenderPass

bubble universe stuff
   constants.py - limits, sizes, and defaults
   particle_motion.py - ParticleMotion, ParticleMotionUniforms
   drawer.py - Drawer, DrawerUniforms
"""

from abc import ABC
import os.path

import wgpu

from passes import ComputePass
from wgsl_types import Uniforms

class Resource(ABC):

    def __init__(self, name):
        self.dymo = LabelMaker()

    @abstractmethod
    def descriptor(self):
        ...


class StorageBuffer(Resource): ...

    def __init__(self, name, shape):
        super().__init__(name)


    # size
    # write
    # buffer reference

# class Uniforms(Resource): ...

class Texture(Resource): ...

class Sampler(Resource): ...

# class LabelMaker:
#     def __init__(self, base):
#         self.base = base
#     def shader_label(self):
#         return f'{self.base} shader'
#     def buffer_layout_label(self, buf_name):
#         return f'{self.base} {buf_name} buffer'
#     def bind_group_label(self, group_name):
#         return f'{self.base} {group_name} buffer'
#     def pipeline_layout_label(self):
#         return f'{self.base} pipeline layout'
#     def pipeline_label(self):
#         return f'{self.base} pipeline'

# class Pass:
#     """Base class for compute and render passes"""

#     def __init__(self, name):
#         self.dymo = LabelMaker(name)

#     def read_shader(self, filename):
#         """ return contents of a file in the shaders directory """
#         up = os.path.dirname
#         path = os.path.join(up(up(__file__)), 'shaders', filename)
#         with open(path) as f:
#             return f.read()


# class ComputePass(Pass):
#     ...

# class ParticleMotionUniforms(Uniforms):
#     seq_count: u32 = Defaults.SEQ_COUNT
#     seq_length: u32 = Defaults.SEQ_LENGTH
#     t: f32 = 0
#     r: f32 = Defaults.R

# class ParticleMotionPass(ComputePass):

#     def __init__(self, name='particles'):
#         super().__init__(name)
#         self.uvs = None
#         self.uniforms = ParticleMotionUniforms()
#         self.shader = self.read_shader('particles.wgsl')

#     def bind_uvs(self, buffer):
#         self.uvs = buffer

#     def instantiate(self, device):
#         assert self.shader
#         assert self.uvs

#         shader_module = device.create_shader_module(
#             code=self.shader,
#         )

#         uv_layout = device.create_bind_group_layout(
#             label=self.dymo.buffer_layout_label('uv'),
#             entries=[
#                 wgpu.BindGroupLayoutEntry(
#                     binding=0,
#                     visibility=wgpu.ShaderStage.COMPUTE,
#                     buffer=wgpu.BufferBindingLayout(
#                         type='storage',
#                     ),
#                 ),
#             ],
#         )

#         uniforms_layout = device.create_bind_group_layout(
#             label=self.dymo.buffer_layout_label('uniforms'),
#             entries=[
#                 wgpu.BindGroupLayoutEntry(
#                     binding=1,
#                     visibility=wgpu.ShaderStage.COMPUTE,
#                     buffer=wgpu.BufferBindingLayout(
#                         type='uniform',
#                     ),
#                 ),
#             ],
#         )

#         self.uv_bind_group = device.create_bind_group(
#             label=self.dymo.bind_group_label('uv'),
#             layout=uv_layout,
#             entries=[
#                 wgpu.BindGroupEntry(
#                     binding=0,
#                     resource=wgpu.BufferBinding(
#                         buffer=self.uvs,
#                     ),
#                 ),
#             ],
#         )

#         self.uniforms_bind_group = device.bind

#         pipeline_layout=device.create_pipeline_layout(
#             label=self.dymo.pipeline_layout_label(),
#             bind_group_layouts=[
#                 uv_layout,
#                 uniforms_layout,
#             ]
#         )

#         self.pipeline = device.create_compute_pipeline(
#             label=self.dymo.pipeline_label(),
#             layout=pipeline_layout,
#             compute=wgpu.ProgrammableStage(
#                 module=shader_module,
#             ),
#         )

#         self.pass_descriptor = wgpu.ComputePassDescriptor(
#             label=self.dymo.compute_pass_descriptor_label(),
#         )
