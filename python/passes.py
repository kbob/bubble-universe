from abc import abstractmethod
from enum import Enum
import os.path
from typing import NamedTuple

import resources


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

    @abstractmethod
    def instantiate(self):
        ...

    @abstractmethod
    def bindings(self):
        ...

    def make_label(self, tag):
        """naming: one of the two Karlton-hard CS problems"""
        return f'{self.name} {tag}'

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
