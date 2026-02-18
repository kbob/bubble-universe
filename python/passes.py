from abc import ABC, abstractmethod
from enum import Enum
import os.path
from typing import NamedTuple

import resources
import wgpu


class Access(Enum):
    RO = 'ro'
    RW = 'rw'

class Binding(NamedTuple):
    """A resource used by a pass"""
    name: str
    resource: resources.Resource
    access: Access

class Pass(ABC):
    """Base class for compute and render passes"""

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def bindings(self):
        ...

    @abstractmethod
    def instantiate(self, driver):
        ...

    def resize(self, device, new_size):
        print(f'resize not handled by pass {self.name}')
        pass

    @abstractmethod
    def execute(self, device, encoder):
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

    @abstractmethod
    def bind_color_output(self, tex):
        ...

    def create_pipeline(self, device, shader_module, blend=None):
        return device.create_render_pipeline(
            label=self.make_label('pipeline'),
            layout='auto',
            vertex=wgpu.VertexState(
                module=shader_module,
            ),
            fragment=wgpu.FragmentState(
                module=shader_module,
                targets=[
                    wgpu.ColorTargetState(
                        blend=blend,
                        format=self.output.format,
                    ),
                ],
            ),
        )
