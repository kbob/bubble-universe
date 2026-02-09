from abc import ABC, abstractmethod
from functools import reduce
import operator

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

class UniformBuffer(Resource):

    def __init__(self, name, data_class):
        super().__init__(name)
        self.data_class = data_class
        self.buffer = None

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


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Texture

class Texture(Resource):
    ...

class Sampler(Resource):
    ...
