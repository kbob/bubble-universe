"""
    WGSL types.

    Define scalar, vector, and matrix types matching the types of wgsl.
    These are immutable.

    Define `Uniforms`, a superclass that allows easy definition of
    uniform buffers.  Example:

        class MyUniforms(Uniforms):
            scale: vec2f = (1, 1)
            brightness: f32 = 1
            index: u32

        # Instantiate into a Python object
        my_uniforms = MyUniforms(index=3)

        # Create WGPU uniform buffer
        my_u_buffer = MyUniforms.create_buffer(device,
            visibility=Vertex | Fragment)

        # Update values
        my_uniforms.scale = (1.4, 1.4)

        # send to GPU
        my_uniforms.write_buffer(device, my_u_buffer)


    NOTE: bool, f16 and matNxN are not implemented yet.
"""

from collections import namedtuple
from dataclasses import dataclass
from functools import cache
from inspect import get_annotations, isfunction, ismethod
import re

import numpy as np
from wgpu import BufferUsage

__all__ = [
    'f32',
    'i32',
    'u32',
    'vec2f',
    'vec3f',
    'vec4f',
    'vec2u',
    'vec3u',
    'vec4u',
    'Uniforms'
    ]

def camel_to_snake(name):
    return re.sub(r'(?!^)(?=[A-Z])', '_', name).lower()

assert camel_to_snake('camelCaseName') == 'camel_case_name'
assert camel_to_snake('PascalCaseName') == 'pascal_case_name'


class _classproperty:
    def __init__(self, f):
        self.f = f
    def __get__(self, obj, owner):
        return self.f(owner)

class _WgslType: pass


class f32(float, _WgslType):
    bytes = 4
    align = 4
    dtype = 'f4'

class i32(int, _WgslType):
    bytes = 4
    align = 4
    dtype = 'i4'

class u32(int, _WgslType):
    bytes = 4
    align = 4
    dtype = 'u4'

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


class _Vector(tuple, _WgslType):

    def __new__(cls, *args):
        # print(f'    {args = !r}')
        # print(f'    {len(args) = }')

        arg_tuple = tuple(args)
        assert len(arg_tuple) == cls.len, f'{cls.__name__} must have length {cls.len}'
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
    scalar_type = f32
    len = 2
    align = 2 * f32.align

class vec3f(_Vector):
    scalar_type = f32
    len = 3
    align = 4 * f32.align       # !!!

class vec4f(_Vector):
    scalar_type = f32
    len = 4
    align = 4 * f32.align

class vec2u(_Vector):
    scalar_type = u32
    len = 2
    align = 2 * u32.align

class vec3u(_Vector):
    scalar_type = u32
    len = 3
    align = 4 * u32.align       # !!!

class vec4u(_Vector):
    scalar_type = u32
    len = 4
    align = 4 * u32.align

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

# verbose = False


class _FieldInfo(namedtuple('_FieldInfo', 'name offset bytes align')):
    pass


class UniformMeta(type):

    def __new__(cls, *args, **kwargs):
        """Create a Uniforms class.  Give it dataclass behavior."""
        # if verbose:
        #     print(f'UniformMeta.__new__')
        #     print(f'    {cls = }')
        #     print(f'    {args = }')
        #     print(f'    {kwargs = }')
        cls_obj = super().__new__(cls, *args, **kwargs)
        # if verbose:
        #     print(f'    {cls_obj = }')

        # Specify kw_only, otherwise dataclass forces fields without
        # default values to the front of the struct.
        return dataclass(cls_obj, kw_only=True)

    def __init__(self, name, bases, namespace, **kwargs):

        """
            Create a Uniforms class.  Verify that all annotated fields
            have a WGSL type.
        """

        # print(f'UniformMeta.__init__')
        # print(f'    {self = }')
        # print(f'    {name = }')
        # print(f'    {len(kwargs) = }')

        annotations = get_annotations(self)
        # if verbose:
        #     print(f'    {annotations = }')
        for (f, t) in annotations.items():
            assert issubclass(t, _WgslType), f'uniform field {f!r} must be a WGSL type'

        for f in self.__dict__:
            if f.startswith('__'):
                continue
            # print(f'    {f = }')
            # print(f'    {self.__dict__[f] = }')
            if isfunction(self.__dict__[f]):
                continue
            if isinstance(self.__dict__[f], classmethod):
                continue
            if isinstance(self.__dict__[f], _classproperty):
                continue
            assert f in annotations, f'uniform field {f!r} must have a type annotation'

        r = super().__init__(name, bases, namespace, **kwargs)
        # if verbose:
        #     print(f'    {r = }')
        return r

class Uniforms(metaclass=UniformMeta):

    def __setattr__(self, name, value):
        """ set a field.  Coerce the new value to the field's type. """

        annotations = get_annotations(self.__class__)
        assert name in annotations, f'unknown field {name!r} in {self.__class__.__name__}'
#         print(f'__setattr__')
# #        print(f'    {self = }')
#         print(f'    {name = }, {value = }')

        # ugly hack: if setting a vector, unpack its args
        def cast(name, value):
            # print(f'    cast({name=}, {value=})')
            # print(f'        {annotations[name] = }')
            # print(f'        {hasattr(annotations[name], 'scalar_type') = }')
            anno = annotations[name]            
            if hasattr(anno, 'scalar_type'):
                # print(f'        has scalar_type')
                return anno(*value)
            return anno(value)

        cast_value = cast(name, value)
        # if verbose:
        #     print(f'setattr({name}, {value}) => {cast_value}')
        super().__setattr__(name, cast_value)


    @_classproperty
    @cache
    def _field_info(cls):
        info = []
        offset = 0
        align = None
        for (fname, fclass) in get_annotations(cls).items():
            # print(f'iteration')
            bytes = fclass.bytes
            align = fclass.align
            # print(f'    {bytes = }, {align = }')
            # print(f'    A: {offset = }')
            offset += (align - offset) % align
            # print(f'     B: {offset = }')
            info += [_FieldInfo(fname, offset, bytes, align)]
            offset += bytes
            # print(f'     C: {offset = }')
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
        # print(f'{cls.__name__}.dtype')
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

    @classmethod
    def create_buffer(cls, device, **kwargs):

        kwargs.setdefault('label', f'{camel_to_snake(cls.__name__)} buffer')
        kwargs.setdefault('size', cls.bytes)
        kwargs.setdefault('usage', BufferUsage.UNIFORM | BufferUsage.COPY_DST)

        # print(f'{kwargs = }')
        return device.create_buffer(**kwargs)

    def as_data(self):
        data = np.zeros((), dtype=self.dtype)
        for info in self._field_info:
            data[info.name] = getattr(self, info.name)
        return data

        # Build a dtype
        # Allocate a memory using the dtype
        # fill with zeroes
        # offset = 0
        # for a in annotations:
        #   copy a.bytes bytes in at offset
        #   offset += a.align

        # What's the memory?  

class Test(Uniforms):
    index: u32 = 42
    ix2: u32 = 42 / 4
    p3: vec3u = (4.4, 3.3, 2.2)
    pt: vec4f = (1, 2, 3, 4.4)

test = Test()
# print(test)
assert test.index == 42
assert test.pt == (1, 2, 3, 4.4)
assert type(test.index) is u32
assert type(test.pt) is vec4f
# print('\n'.join(str(o) for o in test._field_info))
assert test._field_info[0].offset == 0
assert Test._field_info[1].offset == 4
assert test._field_info[2].offset == 16
assert Test._field_info[3].offset == 32
assert test.bytes == 48
# print(test.dtype)
assert test.dtype == [
    ('index',    'u4'),
    ('ix2',      'u4'),
    ('_filler1', 'i1', (8, )),
    ('p3',       'u4', (3, )),
    ('_filler2', 'i1', (4, )),
    ('pt',       'f4', (4, ))
    ]

test = Test(pt=(5.5, 6.6, 7.7, 8.8))
# print(test)
assert test.index == 42
assert test.pt == (5.5, 6.6, 7.7, 8.8)
assert type(test.index) is u32
assert type(test.pt) is vec4f

test.index = 5.5
# print(test)
assert test.index == 5
assert test.pt == (5.5, 6.6, 7.7, 8.8)
assert type(test.index) is u32
assert type(test.pt) is vec4f

data = test.as_data()
assert np.all(data['p3'] == test.p3)

del test
