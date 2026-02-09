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
        device,
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

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cache, reduce
from inspect import get_annotations, isfunction
import operator
import os.path
from typing import NamedTuple

import numpy as np
import wgpu

import wgsl_types
from wgsl_types import *
del Uniforms                    # we define a better Uniforms


class _classproperty:
    def __init__(self, f):
        self.f = f
    def __get__(self, obj, owner):
        return self.f(owner)


class Resource(ABC):

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def resource_descriptor(self):
        ...

    def make_label(self, tag):
        return f'{self.name} {tag}'


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## StorageBuffer

class StorageBuffer(Resource):

    def __init__(self, name, type_, shape):
        super().__init__(name)
        # print(f'StorageBuffer({name=}, {type_=}, {shape=})')
        assert issubclass(type_, wgsl_types._WgslType)
        self.type = type_
        self.shape = shape
        self.buffer = None

    @property
    def bytes(self):
        def prod(iterable):
            return reduce(operator.mul, iterable, 1)
        return self.type.align * prod(self.shape)

    def instantiate(self, device):
        print(f'StorageBuffer {self.name} instantiate')
        if self.buffer is None:
            self.buffer = device.create_buffer(
                label=self.make_label('storage buffer'),
                size=self.bytes,
                usage=wgpu.BufferUsage.STORAGE,
            )
        return self.buffer

    def resource_descriptor(self):
        assert self.buffer is not None
        return wgpu.BufferBinding(
            buffer=self.buffer,
        )


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Uniforms

# Bah.  I need to split the uniform concept into two separate classes.abs
# Uniforms the automated data marshalling thing is one complete thing,
# and Uniforms the GPU resource is another.  (Utadmt and UtGr for short.)
#
# Utgr should reference a Utadmt, and Utqr should be able to write a Utadmt
# to a buffer.  Utadmt is a passive data container, it just has magic
# conversion properties.
#
# But which one keeps the "Uniforms" name?
#
#   Qption: Utadmt is Uniforms, and Utgr is UniformBuffer.
#
#   Option: Utgr is Uniforms, and Utadmt 

# class _FieldInfo(NamedTuple):
#     name: str
#     offset: int
#     bytes: int
#     align: int

# class _UniformsMeta(type):

#     def __new__(cls, *args, **kwargs):
#         """Create a Uniforms class.  Give it dataclass behavior."""
#         cls_obj = super().__new__(cls, *args, **kwargs)

#         # Specify kw_only, otherwise dataclass forces fields without
#         # default values to the front of the struct.
#         return dataclass(cls_obj, kw_only=True, repr=False)

#     def __init__(self, name, bases, namespace, **kwargs):

#         """Create a Uniforms class.  Verify that all annotated fields
#            have a WGSL type.
#         """
#         annotations = get_annotations(self)
#         for (f, t) in annotations.items():
#             assert issubclass(t, wgsl_types._WgslType), \
#                 f'uniform field {f!r} must be a WGSL type'

#         for f in self.__dict__:
#             if f.startswith('__'):
#                 continue
#             if isfunction(self.__dict__[f]):
#                 continue
#             if isinstance(self.__dict__[f], classmethod):
#                 continue
#             if isinstance(self.__dict__[f], _classproperty):
#                 continue
#             assert f in annotations, \
#                 f'uniform field {f!r} must have a type annotation'

#         r = super().__init__(name, bases, namespace, **kwargs)
#         return r

class UniformBuffer(Resource):

    def __init__(self, name, data_class):
        super().__init__(name)
        self.data_class = data_class
        self.buffer = None

    # # XXX is this needed?
    # @property
    # def bytes(cls):
    #     return self.data_class.bytes
    #     # info = cls._field_info
    #     # if info:
    #     #     return info[-1].offset + info[-1].bytes
    #     # else:
    #     #     return 0

    def instantiate(self, device):
        print(f'instantiating {self.name}')
        # import sys, traceback
        # traceback.print_stack(file=sys.stdout)
        # print('\n')
        if self.buffer is None:
            self.buffer = device.create_buffer(
                label=self.make_label('buffer'),
                size=self.data_class.bytes,
                usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
            )
        return self.buffer

    def resource_descriptor(self):
        assert self.buffer is not None
        return wgpu.BufferBinding(
            buffer=self.buffer,
        )

    # def __setattr__(self, name, value):
    #     # set a field.  Coerce the new value to the field's type.

    #     # print(f'{self.__class__.__name__}.__setattr__({name=}, {value=})')

    #     annotations = get_annotations(self.__class__)
    #     assert name in annotations, \
    #         f'unknown field {name!r} in {self.__class__.__name__}'

    #     # ugly hack: if setting a vector, unpack its args
    #     def cast(name, value):
    #         anno = annotations[name]
    #         if hasattr(anno, 'scalar_type'):
    #             return anno(*value)
    #         return anno(value)

    #     cast_value = cast(name, value)
    #     super().__setattr__(name, cast_value)

    # @_classproperty
    # @cache
    # def _field_info(cls):
    #     info = []
    #     offset = 0
    #     align = None
    #     for (fname, fclass) in get_annotations(cls).items():
    #         bytes = fclass.bytes
    #         align = fclass.align
    #         offset += (align - offset) % align
    #         info += [_FieldInfo(fname, offset, bytes, align)]
    #         offset += bytes
    #     return tuple(info)

    # @_classproperty
    # @cache
    # def dtype(cls):
    #     """Return a numpy dtype definition"""
    #     annotations = get_annotations(cls)
    #     info = cls._field_info
    #     dt = []
    #     end = 0
    #     fillno = 1
    #     for f in info:
    #         if f.offset != end:
    #             # insert filler
    #             dt += [(f'_filler{fillno}', 'i1', (f.offset - end,))]
    #             fillno += 1
    #         f_dtype = annotations[f.name].dtype
    #         if type(f_dtype) is not tuple:
    #             f_dtype = (f_dtype, )
    #         dt += [(f.name, ) + f_dtype]
    #         end = f.offset + f.bytes
    #     return dt

    # def as_data(self):
    #     """Return a data object with GPU-compatible binary layout."""

    #     data = np.zeros((), dtype=self.dtype)
    #     for info in self._field_info:
    #         data[info.name] = getattr(self, info.name)
    #     return data

    @classmethod
    def create_buffer(cls, device, **kwargs):
        """Return a numpy dtype definition"""
        annotations = get_annotations(cls)
        info = cls._field_info
        dt = []
        end = 0
        fillno = 1
        for f in info:
            if f.offset != end:
                # insert filler
                dt += [(f'_filler{fillno}', 'i1', (f.offset - end,))]
                fillno += 1
            f_dtype = annotations[f.name].dtype
            if type(f_dtype) is not tuple:
                f_dtype = (f_dtype, )
            dt += [(f.name, ) + f_dtype]
            end = f.offset + f.bytes
        return dt

# # Uniforms unit tests

# class Test(Uniforms):
#     index: u32 = 42
#     ix2: u32 = 42 / 4
#     p3: vec3u = (4.4, 3.3, 2.2)
#     pt: vec4f = (1, 2, 3, 4.4)

# test = Test()
# assert test.index == 42
# assert test.pt == (1, 2, 3, 4.4)
# assert type(test.index) is u32
# assert type(test.pt) is vec4f
# assert test._field_info[0].offset == 0
# assert Test._field_info[1].offset == 4
# assert test._field_info[2].offset == 16
# assert Test._field_info[3].offset == 32
# assert test.bytes == 48
# assert test.dtype == [
#     ('index',    'u4'),
#     ('ix2',      'u4'),
#     ('_filler1', 'i1', (8, )),
#     ('p3',       'u4', (3, )),
#     ('_filler2', 'i1', (4, )),
#     ('pt',       'f4', (4, ))
#     ]

# test = Test(pt=(5.5, 6.6, 7.7, 8.8))
# assert test.index == 42
# assert test.pt == (5.5, 6.6, 7.7, 8.8)
# assert type(test.index) is u32
# assert type(test.pt) is vec4f

# test.index = 5.5
# assert test.index == 5
# assert test.pt == (5.5, 6.6, 7.7, 8.8)
# assert type(test.index) is u32
# assert type(test.pt) is vec4f

# data = test.as_data()
# assert np.all(data['p3'] == test.p3)

# del Test, test


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Texture

class Texture(Resource):
    ...

class Sampler(Resource):
    ...


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
