"""
    WGSL (WebGPU Shading Language) types.

    Define data types convenient to use with WGSL shaders.

    This module defines most of WGSL's scalar types and also
    allows convenient declaration of WGSL uniform buffers.

    These types have class properties:
    bytes -- size in bytes
    align -- WGSL alignment requirement in bytes
    dtype -- a numpy-compatible dtype specification

    Vector types also have these.
    len -- length in elements (e.g., vec3i.len is 3)
    scalar_type -- its elements' type (e.g., vec3f.scalar_type is f32)

    These types are immutable.

    The f16, bool, and matrix types aren't impemented (yet?)
"""

from dataclasses import dataclass
from functools import cache
from inspect import get_annotations, isfunction, ismethod
from typing import NamedTuple

import numpy as np

__all__ = [
    'f32',
    'i32',
    'u32',

    'vec2f',
    'vec3f',
    'vec4f',
    'vec2i',
    'vec3i',
    'vec4i',
    'vec2u',
    'vec3u',
    'vec4u',

    'Uniforms'
    ]


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Utilities

class _classproperty:
    def __init__(self, f):
        self.f = f
    def __get__(self, obj, owner):
        return self.f(owner)


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Base

class _WgslType: pass


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## The Scalara

class f32(float, _WgslType):
    """A WGSL 32 bit floating point number"""
    bytes = 4
    align = 4
    dtype = 'f4'

class i32(int, _WgslType):
    """A WGSL 32 bit signed integer"""
    bytes = 4
    align = 4
    dtype = 'i4'

class u32(int, _WgslType):
    """A WGSL 32 bit unsigned integer"""
    bytes = 4
    align = 4
    dtype = 'u4'

## Scalar unit tests

x = f32(4)
assert x == 4.0
assert isinstance(x, f32)
assert x.bytes == 4
assert x.align == 4
assert x.dtype == 'f4'

x = u32(4.4)
assert x == 4
assert isinstance(x, u32)

del x

## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## The Vectors

class _Vector(tuple, _WgslType):

    def __new__(cls, *args):
        arg_tuple = tuple(args)
        assert len(arg_tuple) == cls.len, \
            f'{cls.__name__} must have length {cls.len}'
        typed_args = tuple(cls.scalar_type(a) for a in args)
        r = super().__new__(cls, typed_args)
        return r

    @_classproperty
    def bytes(self):
        return self.len * self.scalar_type.bytes

    @_classproperty
    def dtype(self):
        return (self.scalar_type.dtype, (self.len, ))

class vec2f(_Vector):
    """A two element vector of floats"""
    scalar_type = f32
    len = 2
    align = 2 * f32.align

class vec3f(_Vector):
    """A three element vector of floats"""
    scalar_type = f32
    len = 3
    align = 4 * f32.align       # !!!

class vec4f(_Vector):
    """A four element vector of floats"""
    scalar_type = f32
    len = 4
    align = 4 * f32.align

class vec2i(_Vector):
    """A two element vector of signed ints"""
    scalar_type = i32
    len = 2
    align = 2 * i32.align

class vec3i(_Vector):
    """A three element vector of signed ints"""
    scalar_type = i32
    len = 3
    align = 4 * i32.align       # !!!

class vec4i(_Vector):
    """A four element vector of signed ints"""
    scalar_type = i32
    len = 4
    align = 4 * i32.align

class vec2u(_Vector):
    """A two element vector of unsigned ints"""
    scalar_type = u32
    len = 2
    align = 2 * u32.align

class vec3u(_Vector):
    """A three element vector of unsigned ints"""
    scalar_type = u32
    len = 3
    align = 4 * u32.align       # !!!

class vec4u(_Vector):
    """A four element vector of unsigned ints"""
    scalar_type = u32
    len = 4
    align = 4 * u32.align

# Vector Unit Tests

v = vec2f(3, 4)
assert v == (3, 4)
assert isinstance(v[1], f32)
assert isinstance(v, vec2f)
assert vec2f.bytes == 8
assert v.bytes == 8
assert v.align == 8
assert v.dtype == vec2f.dtype == ('f4', (2, ))

v = vec2f(3, '4')
assert isinstance(v[1], f32)
assert v[1] == 4

v = vec3f(3, 4, 5)
assert v == (3, 4, 5)

v = vec4f(3, 4, 5, 6)
assert v == (3, 4, 5, 6)
assert vec4f.bytes == 16

v = vec2u(3.3, 4.4)
assert v == (3, 4)
assert isinstance(v[1], u32)
assert isinstance(v, vec2u)

v = vec3u(3.3, 4.4, 5.5)
assert v == (3, 4, 5)
assert isinstance(v[0], int)
assert isinstance(v[0], u32)
assert isinstance(v, vec3u)

del v


## ##  ##   ##    ##     ##      ##       ##      ##     ##    ##   ##  ## ##
## Uniforms

class _FieldInfo(NamedTuple):
    name: str
    offset: int
    bytes: int
    align: int

class _UniformsMeta(type):

    def __new__(cls, *args, **kwargs):
        """Create a Uniforms class.  Give it dataclass behavior."""
        cls_obj = super().__new__(cls, *args, **kwargs)

        # Specify kw_only, otherwise dataclass forces fields without
        # default values to the front of the struct.
        return dataclass(cls_obj, kw_only=True)

    def __init__(self, name, bases, namespace, **kwargs):

        """Create a Uniforms class.  Verify that all annotated fields
           have a WGSL type.
        """
        annotations = get_annotations(self)
        for (f, t) in annotations.items():
            assert issubclass(t, _WgslType), \
                f'uniform field {f!r} must be a WGSL type'

        for f in self.__dict__:
            if f.startswith('__'):
                continue
            if isfunction(self.__dict__[f]):
                continue
            if isinstance(self.__dict__[f], classmethod):
                continue
            if isinstance(self.__dict__[f], _classproperty):
                continue
            assert f in annotations, \
                f'uniform field {f!r} must have a type annotation'

        r = super().__init__(name, bases, namespace, **kwargs)
        return r

class Uniforms(metaclass=_UniformsMeta):

    """An abstract class that allows easy definition of uniform buffers.

    Example:

        class MyUniforms(Uniforms):
            scale: vec2f = (1, 1)
            brightness: f32 = 1
            index: u32  # no default value

    A Uniforms subclass is a dataclass (as defined in Python's
    standard library), so it has dataclass's behaviors.  Example:

        # Instantiate into a Python object
        my_uniforms = MyUniforms(index=3)
        my_uniforms = MyUniforms(index=4, scale=[2, 3])

        # print(my_uniforms)
        MyUniforms(scale=(2.0, 3.0), brightness=1.0, index=4)

    A Uniforms subclass enforces things.

      - Fields must be annoated as WGSL types (scalars and vectors)
      - Fields can only contain the declared types; values are coerced
        to the right type on initialization and assignment

    Uniforms subclasses have the same bytes and dtypes properties
    described above.

    Additional behavior:

      - create_buffer(device, **kwargs) - tell a wgpu device to
        create a buffer that matches the struct definition

        For example,

            MyUniforms.create_buffer(device)

        is equivalent to

            device.create_buffer(
                label='my_uniforms buffer',
                size=16,
                usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
            )

        You can override the `label`, `size`, and `usage` parameters
        with keyword args.

      - as_data() - emit a numpy structured array with the correct binary
        layout to write to the GPU

    A Uniforms

        # Create WGPU uniform buffer
        my_u_buffer = MyUniforms.create_buffer(device,
            visibility=Vertex | Fragment)

        # Update values
        my_uniforms.scale = (1.4, 1.4)

        # send to GPU
        my_uniforms.write_buffer(device, my_u_buffer)
"""

    def __setattr__(self, name, value):
        # set a field.  Coerce the new value to the field's type.

        annotations = get_annotations(type(self))
        assert name in annotations, \
            f'unknown field {name!r} in {type(self).__name__}'

        # ugly hack: if setting a vector, unpack its args
        def cast(name, value):
            anno = annotations[name]
            if hasattr(anno, 'scalar_type'):
                return anno(*value)
            return anno(value)

        cast_value = cast(name, value)
        super().__setattr__(name, cast_value)

    @_classproperty
    @cache
    def _field_info(cls):
        info = []
        offset = 0
        align = None
        for (fname, fclass) in get_annotations(cls).items():
            bytes = fclass.bytes
            align = fclass.align
            offset += (align - offset) % align
            info += [_FieldInfo(fname, offset, bytes, align)]
            offset += bytes
        return tuple(info)

    @_classproperty
    @cache
    def bytes(cls):
        info = cls._field_info
        if info:
            return info[-1].offset + info[-1].bytes
        else:
            return 0

    @_classproperty
    @cache
    def dtype(cls):
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

    def as_data(self):
        """Return a data object with GPU-compatible binary layout."""

        data = np.zeros((), dtype=self.dtype)
        for info in self._field_info:
            data[info.name] = getattr(self, info.name)
        return data

# Uniforms unit tests

class Test(Uniforms):
    index: u32 = 42
    ix2: u32 = 42 / 4
    p3: vec3u = (4.4, 3.3, 2.2)
    pt: vec4f = (1, 2, 3, 4.4)

test = Test()
assert test.index == 42
assert test.pt == (1, 2, 3, 4.4)
assert type(test.index) is u32
assert type(test.pt) is vec4f
assert test._field_info[0].offset == 0
assert Test._field_info[1].offset == 4
assert test._field_info[2].offset == 16
assert Test._field_info[3].offset == 32
assert test.bytes == 48
assert test.dtype == [
    ('index',    'u4'),
    ('ix2',      'u4'),
    ('_filler1', 'i1', (8, )),
    ('p3',       'u4', (3, )),
    ('_filler2', 'i1', (4, )),
    ('pt',       'f4', (4, ))
    ]

test = Test(pt=(5.5, 6.6, 7.7, 8.8))
assert test.index == 42
assert test.pt == (5.5, 6.6, 7.7, 8.8)
assert type(test.index) is u32
assert type(test.pt) is vec4f

test.index = 5.5
assert test.index == 5
assert test.pt == (5.5, 6.6, 7.7, 8.8)
assert type(test.index) is u32
assert type(test.pt) is vec4f

data = test.as_data()
assert np.all(data['p3'] == test.p3)

del Test, test
