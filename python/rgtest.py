from collections.abc import Mapping, MutableSequence
from inspect import get_annotations
from itertools import chain
from typing import NamedTuple

import drawer
import passes
import rendergraph
import resources
import wgpu
from wgsl_types import *

import particle_motion

class CallRecord(NamedTuple):
    name: str
    args: str
    kwargs: str
    prefix: str = ''

indent = '  '

def short_repr(obj, n=60):
    r = repr(obj)
    if len(r) > n and 'result' not in r:
        r = r[:n - 3] + '...'
    return r

def object_lines(obj):
    if isinstance(obj, CallRecord):
        return call_lines(obj)
    elif isinstance(obj, MutableSequence):
        return list_lines(obj)
    elif isinstance(obj, Mapping):
        return mapping_lines(obj)
    else:
        return [short_repr(obj)]

def list_lines(lis):
    lines = ['[']
    for item in lis:
        i_lines = object_lines(item)
        i_lines[-1] += ','
        i_lines = [indent + f'{i}' for i in i_lines]
        lines += i_lines
    lines += [']']
    return lines

def mapping_lines(map):
    lines = [f'{type(map).__name__}(']
    for (key, value) in map.items():
        v_lines = object_lines(value)
        v_lines[0] = indent + f'{key}=' + v_lines[0]
        v_lines[-1] += ','
        for i in range(1, len(v_lines)):
            v_lines[i] = indent + v_lines[i]
        lines += v_lines
    lines += [')']
    return lines

def call_lines(call):
    if not call.args and not call.kwargs:
        return [f'{call.name}()']
    lines = [f'{call.name}(']
    for arg in call.args:
        a_lines = object_lines(arg)
        a_lines = [indent + f'{l}' for l in a_lines]
        a_lines[-1] += ','
        lines += a_lines
    for (arg, value) in call.kwargs.items():
        v_lines = object_lines(value)
        v_lines[0] = indent + f'{arg}=' + v_lines[0]
        v_lines[1:] = [indent + f'{l}' for l in v_lines[1:]]
        v_lines[-1] += ','
        lines += v_lines
    lines += [')']
    return lines

def print_object(obj, indent=''):
    print(indent + '\n'.join(object_lines(obj)))

stri = (
    'This is a longer string than I want to see.'
    'Much, much longer.  Maybe even longer than I want to type.'
    )

stru = {'one': 1, 'two': 2}
lis = [stru, stri]
sls = {'list': lis}
call = CallRecord('function', (123, stri), {'stru': stru})
# print_object(stri)
# print_object(stru)
# print_object([1, 2])
# print_object(lis)
# print_object(sls)
# print_object(call)
# exit()


call_stack = []

def record_call(name, args, kwargs, prefix=None):
    rec = CallRecord(name, args, kwargs, prefix)
    for log in call_stack:
        log.append(rec)

def print_calls(calls):
    for (i, call) in enumerate(calls):
        print(f'{call.prefix}: ', end='')
        print_object(call)


class CallLogger:

    def __init__(self, prefix=''):
        # print(f'CL.init({self=}, {prefix=})')
        self.calls = []
        self.prefix=prefix

    def __getattr__(self, name):
        def log(*args, **kwargs):
            prefix = self.prefix
            if prefix: prefix += '.'
            prefix=f'{prefix}{len(self.calls)}'
            rec = CallRecord(name, args, kwargs)
            self.calls.append(rec)
            record_call(name, args, kwargs, prefix)
            note = ''
            if 'label' in kwargs:
                note = f' ({kwargs['label']!r})'
            return CallableString(f'{name} result{note}', prefix=prefix)
        return log

    def print_calls(self, multiline=False):
        def short_repr(obj, n=20):
            r = repr(obj)
            if len(r) > n:
                r = r[:n - 3] + '...'
            return r
        if multiline:
            for (i, call) in enumerate(self.calls):
                print(f'{i}: ', end='')
                print_object(call)
        else:
            for (i, call) in enumerate(self.calls):
                astr = (short_repr(a) for a in call[1])
                kwstr = (f'{k}={short_repr(v)}' for (k, v) in call[2].items())
                allstr = ', '.join(a for a in chain(astr, kwstr))
                print(f'{i}: {call[0]}({allstr})')

class CallableString(str, CallLogger):

    def __new__(cls, value, prefix=''):
        # print(f'CS.new({value=}, {prefix=})')
        return super().__new__(cls, value)

    def __init__(self, value, prefix=''):
        # print(f'CS.init({value=}, {prefix=})')
        super(str, self).__init__(prefix=prefix)

foo = CallableString('foo', prefix='pre>')
# print(f'{foo = }')
# print(f'{type(foo) = }')
# print(f'{foo.prefix = }')
# exit()

del foo


call_stack.append([])
a = CallLogger()
a.method('arg1', 'arg2', kwarg='value')
a.other(1, 2, shoe='buckled')
a.method()
a.long_one(__builtins__, kw=__builtins__)
a.array(
    my_array=[
        'shoe',
        'door',
        'Some days you get the bear, and some days the bear gets you.',
    ],
)
# a.print_calls()
# a.print_calls(multiline=True)
# print_calls(call_stack.pop())
# exit()

call_stack.clear()
del a


class TestPass(passes.ComputePass):

    def __init__(self, name):
        super().__init__(name)
        self.output = None

    def resources(self):
        return [
            passes.Attachment('output', self.output, passes.Access.RW)
        ]

    def bind_output(self, out):
        self.output = out
        return self

    def instantiate(self, device):
        device.instantiate_pass(self.name)

    def execute(self, device, encoder):
        device.execute(f'{self.name}({encoder = })')


buffer = resources.StorageBuffer('my storage buffer', vec2f, (2, 2))
texture = resources.Texture('my texture', 'rgba8unorm', (7, 2, 4))
sampler = resources.Sampler('my sampler')

# Test graph
tp = TestPass('my test pass')
tp.bind_output(buffer)

call_stack.append([])
device = CallLogger()
rg = rendergraph.RenderGraph(device, [tp])
# device.print_calls(multiline=True)
# print_calls(call_stack.pop())
# 

call_stack.clear()
del buffer, texture, sampler, tp, rg

# Minimal real render graph

class FakeCanvas(CallLogger):

    @property
    def physical_size(self):
        return (320, 240)

    def get_physical_size(self):
        return (320, 240)

    def get_preferred_format(self):
        return 'bgra8unorm'


call_stack.append([])
fake_canvas = FakeCanvas()
canvas = resources.CanvasTexture('my canvas', fake_canvas, 'bgra8unorm')
# fake_canvas.print_calls(multiline=True)
# exit()

uv_buffer = resources.StorageBuffer('uv', vec2f, (200, 200))

cp = particle_motion.ParticleMotionPass()
cp.bind_uvs(uv_buffer)

rp = drawer.DrawingPass()
rp.bind_uvs(uv_buffer)
rp.attach_color_output(canvas)

fake_device = CallLogger()
rg = rendergraph.RenderGraph(fake_device, [rp])


print('Graph Initialization Calls')
# fake_device.print_calls(multiline=True)
print_calls(call_stack.pop())
print_object(rp.pass_descriptor)
