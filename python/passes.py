from abc import ABC, abstractmethod
from enum import Enum
from inspect import get_annotations
import os.path
from typing import NamedTuple

import resources
import wgpu


class Access(Enum):
    RO = 'ro'
    RW = 'rw'
    WO = 'wo'


class BlendMode(Enum):
    ADD = 'add'
    BLEND = 'blend'
    COPY = 'copy'

    @property
    def blend(self):
        if self == self.ADD:
            return wgpu.BlendState(
                color=wgpu.BlendComponent(
                    operation='add',
                    src_factor='one',
                    dst_factor='one',
                ),
                alpha=wgpu.BlendComponent(
                    operation='add',
                    src_factor='one',
                    dst_factor='one',
                ),
            )
        if self == self.BLEND:
            return wgpu.BlendState(
                color=wgpu.BlendComponent(
                    operation='add',
                    src_factor='one',
                    dst_factor='one-minus-src-alpha',
                ),
                alpha=wgpu.BlendComponent(
                    operation='add',
                    src_factor='one',
                    dst_factor='one-minus-src-alpha',
                ),
            )
        if self == self.COPY:
            return None # use wgpu default
        raise NotImplementedError(f'no blend mode defined for {self}')


class Attachment(NamedTuple):
    """A render pass's attachment (drawing texture)"""
    name: str
    resource: resources.Texture
    clear_value: tuple[int, int, int, int] = (0, 0, 0, 1)
    blend: BlendMode = BlendMode.COPY


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
    def resources(self):
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
    
    def instantiate_pass_descriptor(self):
        self.pass_descriptor = wgpu.ComputePassDescriptor(
            label=self.make_label('compute pass'),
        )


class RenderPass(Pass):

    def instantiate_pipeline(
        self,
        device,
        shader_module,
        vertex_entry=None,
        fragment_entry=None,
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
                # No depth/stencil targets yet
                targets=self._color_targets()
            ),
        )

    def _color_targets(self):
        return [
            wgpu.ColorTargetState(
                blend=r.blend.blend,
                format=r.resource.format,
            )
            for r in self.resources()
            if isinstance(r, Attachment)
        ]

    def instantiate_pass_descriptor(self):
        self.pass_descriptor = wgpu.RenderPassDescriptor(
            label=self.make_label('render pass'),
            color_attachments=self._color_attachments(),
        )

    def _color_attachments(self):
        return [
            # Nobody is overriding these defaults yet.
            wgpu.RenderPassColorAttachment(
                clear_value=(0, 0, 0, 1),
                load_op='clear',
                store_op='store',
                view=...,
            )
            for r in self.resources()
            if isinstance(r, Attachment)
        ]


class Subgraph(Pass):

    """
        A RenderGraph node that is another RenderGraph.
    """

    # required members:
    #   resources(self)
    #   instantiate(self, device)
    #   execute(self, device, encoder)

    # optional members:
    # _Parameters
    #   __init__(self, ...)
    #   resize(self, device, size)

    def instantiate_subgraph(self, device, passes, external_resources):

        # Find and instantiate all bound resources
        resources = {r: None for r in external_resources}
        for pass_ in passes:
            for r in pass_.resources():
                resource = r.resource
                assert resource, (f'pass {pass_.name!r} '
                                  f'is missing resource {r.name!r}')
                if resource not in resources:
                    resources[resource] = resource.instantiate(device)

        # Instantiate all passes
        self.passes = {}
        for pass_ in passes:
            self.passes[pass_] = pass_.instantiate(device)
