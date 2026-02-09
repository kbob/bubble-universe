from abc import abstractmethod
# from collections import namedtuple
from enum import Enum
import os.path
from typing import NamedTuple

import resources


class LabelMaker:
    def __init__(self, base):
        self.base = base
    def shader_label(self):
        return f'{self.base} shader'
    def bind_group_layout_label(self, group_name):
        return f'{self.base} {group_name} bind group layout'
    def bind_group_label(self, group_name):
        return f'{self.base} {group_name} buffer'
    def pipeline_layout_label(self):
        return f'{self.base} pipeline layout'
    def pipeline_label(self):
        return f'{self.base} pipeline'
    def compute_pass_descriptor_label(self):
        return f'{self.base} compute pass descriptor'


# class Binding(namedtuple('Binding', 'name resource access')):
#     """A resource used by a pass"""
#     ...

class Access(Enum):
    RO = 'ro'
    RW = 'rw'

class Binding(NamedTuple):
    """A resource used by a pass"""
    name: str
    resource: resources.Resource
    access: Access

class Pass:
    """Base class for compute and render passes"""

    def __init__(self, name):
        self.name = name
        self.dymo = LabelMaker(name)

    @abstractmethod
    def instantiate(self):
        ...

    @abstractmethod
    def bindings(self):
        ...

    def read_shader(self, filename):
        """return contents of a file in the shaders directory"""
        up = os.path.dirname
        path = os.path.join(up(up(__file__)), 'shaders', filename)
        with open(path) as f:
            return f.read()


class ComputePass(Pass):
    ...

class RenderPass(Pass):
    ...
