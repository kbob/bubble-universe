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
        super().__init__()
        self.name = name

        # If subclass has a _Uniforms member, create a uniforms buffer.
        if hasattr(type(self), '_Uniforms'):
            U = type(self)._Uniforms
            self.uniform_buffer = resources.UniformBuffer(
                name=f'{name} uniforms',
                data_class=U,
            )

    @abstractmethod
    def bindings(self):
        ...

    @abstractmethod
    def instantiate(self, driver):
        ...

    def resize(self, device, new_size):
        print(f'resize not handled by pass {self.name}')
        return self

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

    def instantiate_uniforms_bind_group(self, device, layout, binding=0):
        """
        create self.uniforms_bind_group.
        If `layout` is a number, it's used as the group number for auto layout,
        otherwise it's used as a bind group layout.
        """
        if isinstance(layout, int):
            layout = self.pipeline.get_bind_group_layout(layout)
        self.uniforms_bind_group = device.create_bind_group(
            label=self.make_label('uniforms bind group'),
            layout=layout,
            entries=[
                wgpu.BindGroupEntry(
                    binding=binding,
                    resource=self.uniform_buffer.resource_descriptor(),
                ),
            ],
        )

class ComputePass(Pass):
    ...

class RenderPass(Pass):

    # @abstractmethod
    # def bind_color_output(self, tex):
    #     ...

    def create_pipeline(
        self,
        device,
        shader_module,
        vertex_entry=None,
        fragment_entry=None,
        blend=None,
    ):
        return device.create_render_pipeline(
            label=self.make_label('pipeline'),
            layout='auto',
            vertex=wgpu.VertexState(
                module=shader_module,
                entry_point=vertex_entry,
            ),
            fragment=wgpu.FragmentState(
                module=shader_module,
                entry_point=fragment_entry,
                targets=[
                    wgpu.ColorTargetState(
                        blend=blend,
                        format=self.output.format,
                    ),
                ],
            ),
        )

class Subgraph(Pass):

    """
        A RenderGraph node
        that does not encapsulate a wgpu pipeline-render pass.
    """

    # required:
    # bindings(self)
    # instantiate(self, device)
    # execute(self, device, encoder)

    # optional:
    # _Parameters
    # __init__(self, ...)
    # resize(self, device, size)

    def instantiate_subgraph(self, device, passes, external_resources):

        # Find and instantiate all bound resources
        resources = {r: None for r in external_resources}
        for pass_ in passes:
            for b in pass_.bindings():
                resource = b.resource
                assert resource, (f'pass {pass_.name!r} '
                                  f'is missing resource {b.name!r}')
                if resource not in resources:
                    resources[resource] = resource.instantiate(device)

        # Instantiate all passes
        self.passes = {}
        for pass_ in passes:
            self.passes[pass_] = pass_.instantiate(device)
