from abc import ABC, abstractmethod
from functools import reduce
import operator
import re

import wgpu

import wgsl_types


class _classproperty:
    def __init__(self, f):
        self.f = f
    def __get__(self, obj, owner):
        return self.f(owner)


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Resource
## abstract base for resource classes

class Resource(ABC):

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def instantiate(self, device):
        ...

    @abstractmethod
    def resource_descriptor(self):
        ...

    def make_label(self, tag):
        return f'{self.name} {tag}'


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## StorageBuffer

class StorageBuffer(Resource):

    def __init__(self, name, type_, shape, writable=False):
        super().__init__(name)
        assert issubclass(type_, wgsl_types._WgslType)
        self.type = type_
        self.shape = shape
        self.is_writable = writable
        self.buffer = None

    @property
    def bytes(self):
        def prod(iterable):
            return reduce(operator.mul, iterable, 1)
        return self.type.align * prod(self.shape)

    def instantiate(self, device):
        if self.buffer is None:
            usage = wgpu.BufferUsage.STORAGE
            if self.is_writable:
                usage |= wgpu.BufferUsage.COPY_DST
            self.buffer = device.create_buffer(
                label=self.make_label('storage buffer'),
                size=self.bytes,
                usage=usage,
            )
        return self.buffer

    def resource_descriptor(self):
        assert self.buffer is not None
        return self.buffer


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Uniforms

class UniformBuffer(Resource):

    def __init__(self, name, data_class):
        super().__init__(name)
        assert issubclass(data_class, wgsl_types.Uniforms)
        self.data_class = data_class
        self.buffer = None

    def instantiate(self, device):
        if self.buffer is None:
            self.buffer = device.create_buffer(
                label=self.make_label('buffer'),
                size=self.data_class.bytes,
                usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
            )
        return self.buffer

    def resource_descriptor(self):
        assert self.buffer is not None
        return self.buffer

    def write_buffer(self, device, data):
        assert self.buffer is not None
        device.queue.write_buffer(
            self.buffer,
            0,                  # buffer offset
            memoryview(data),
            0,                  # data offset
        )


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Texture
#
# Expose a tiny subset of wgpu's texture capabilities.  As more
# is needed, I'll expand the API.

class Texture(Resource):

    def __init__(
        self,
        name,
        format,
        shape,
        bindable_as_texture=True,
        readable=False,
        writable=False,
        renderable=False,
    ):
        super().__init__(name)
        assert re.match(r'[rgba]{4}8', format)
        assert len(shape) == 3, 'shape must be (width, height, #channels)'
        self.format = format
        self.shape = shape
        self.is_bindable_as_texture=bindable_as_texture
        self.is_readable = readable
        self.is_writable = writable
        self.is_renderable = renderable
        self.texture = None
        self.view = None

    def instantiate(self, device):
        if self.texture is None:
            usage = 0
            assert self.is_bindable_as_texture
            if self.is_bindable_as_texture:
                usage |= wgpu.TextureUsage.TEXTURE_BINDING
            if self.is_readable:
                usage |= wgpu.TextureUsage.COPY_SRC
            if self.is_writable:
                usage |= wgpu.TextureUsage.COPY_DST
            if self.is_renderable:
                usage |= wgpu.TextureUsage.RENDER_ATTACHMENT
            assert usage & wgpu.TextureUsage.TEXTURE_BINDING
            self.texture = device.create_texture(
                label=self.make_label('texture'),
                size=self.shape[:2],
                format=self.format,
                usage=usage,
            )
            self.view = self.texture.create_view(
                label=self.make_label('texture view'),
            )
        return self.texture

    def resize(self, device, size):
        # destroy texture
        # create texture
        # create view
        self.texture.destroy()
        self.shape = (*size, self.shape[2])
        self.texture = None
        self.instantiate(device)


    def resource_descriptor(self):
        assert self.texture is not None
        assert self.view is not None
        return self.view

    def current_texture(self):
        assert self.texture is not None
        return self.texture

    def current_view(self):
        assert self.texture is not None
        assert self.view is not None
        return self.view

    def current_size(self):
        return self.current_texture().size[:2]

    def write_texture(self, device, data):
        assert self.texture is not None
        data_view = memoryview(data)
        device.queue.write_texture(
            destination=wgpu.TexelCopyTextureInfo(
                texture=self.texture,
            ),
            data=data_view,
            data_layout=wgpu.TexelCopyBufferLayout(
                bytes_per_row=data_view.strides[0],
            ),
            size=data_view.nbytes,
        )


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## CanvasTexture
#
# Ties a RenderCanvas into the pipeline.

class CanvasTexture(Texture):

    def __init__(self, name, context, format):

        assert re.match(r'[rgba]{4}8', format)
        shape = context.physical_size + (4, )
        super().__init__(name, format, shape, writable=True)
        self.context = context   

    def instantiate(self, device):
        assert self.context is not None
        return 'placeholder - canvas requires no instantiation'
    
    def resource_descriptor(self):
        assert self.context is not None
        return 'placeholder - current view is found at execute time'

    def current_texture(self):
        assert self.context is not None
        return self.context.get_current_texture()

    def current_view(self):
        assert self.context is not None
        txt = self.context.get_current_texture()
        if txt != self.texture:
            self.texture = txt
            self.view = txt.create_view()
        return self.view

    def write_texture(self, device, data):
        raise NotImplementedError('Canvas does not support direct write')


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Sampler

class Sampler(Resource):
    
    def __init__(self, name):
        super().__init__(name)
        self.sampler = None

    def instantiate(self, device):
        if self.sampler is None:
            self.sampler = device.create_sampler(
                label=self.name,
            )
        return self.sampler

    def resource_descriptor(self):
        assert self.sampler is not None
        return self.sampler
