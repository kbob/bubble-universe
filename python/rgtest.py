from collections.abc import Mapping, MutableSequence
from inspect import get_annotations
from itertools import chain
from typing import NamedTuple

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

def short_repr(obj, n=40):
    r = repr(obj)
    if len(r) > n:
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
        i_lines = [f'    {i}' for i in i_lines]
        lines += i_lines
    lines += [']']
    return lines

def mapping_lines(map):
    lines = [f'{map.__class__.__name__}(']
    for (key, value) in map.items():
        v_lines = object_lines(value)
        v_lines[0] = f'    {key}=' + v_lines[0]
        v_lines[-1] += ','
        for i in range(1, len(v_lines)):
            v_lines[i] = '    ' + v_lines[i]
        lines += v_lines
    lines += [')']
    return lines

def call_lines(call):
    if not call.args and not call.kwargs:
        return [f'{call.name}()']
    lines = [f'{call.name}(']
    for arg in call.args:
        a_lines = object_lines(arg)
        a_lines = [f'    {l}' for l in a_lines]
        a_lines[-1] += ','
        lines += a_lines
    for (arg, value) in call.kwargs.items():
        v_lines = object_lines(value)
        v_lines[0] = f'    {arg}=' + v_lines[0]
        v_lines[1:] = [f'    {l}' for l in v_lines[1:]]
        v_lines[-1] += ','
        lines += v_lines
    lines += [')']
    return lines

def print_object(obj, indent=''):
    print('\n'.join(object_lines(obj)))

stri = 'This is a longer string than I want to see.'
stru = {'one': 1, 'two': 2}
lis = [stru, stri]
sls = {'list': lis}
call = CallRecord('function', (123, stri), {'stru': stru})
# print_object(str)
# print_object(stru)
# print_object([1, 2])
# print_object(lis)
# print_object(sls)
# print_object(call)
# exit()

class CallLogger:

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def log(*args, **kwargs):
            self.calls.append(CallRecord(name, args, kwargs))
            return f'result from {name}'
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
# exit()


class TestPass(passes.ComputePass):

    def __init__(self, name):
        super().__init__(name)
        self.output = None

    def bind_output(self, out):
        self.output = out
        return self

    def bindings(self):
        return [
            passes.Binding('output', self.output, passes.Access.RW)
        ]

    def instantiate(self, device):
        device.instantiate_pass(self.name)

buffer = resources.StorageBuffer('my storage buffer', vec2f, (2, 2))
tp = TestPass('my test pass')
tp.bind_output(buffer)

device = CallLogger()
rg = rendergraph.RenderGraph(device, [tp])
# device.print_calls(multiline=True)
# exit()

uv_buffer = resources.StorageBuffer('uv', vec2f, (200, 200))
rp = particle_motion.ParticleMotionPass()
rp.bind_uvs(uv_buffer)

device = CallLogger()
rg = rendergraph.RenderGraph(device, [rp])
device.print_calls(multiline=True)
print_object(rp.pass_descriptor)
