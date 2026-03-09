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


class Binding(NamedTuple):
    """A wgpu binding used by a pass"""
    group_binding: tuple[int, int] | None # None for non-wgpu passes
    name: str
    resource: resources.Resource
    access: Access

    @property
    def group(self):
        return self.group_binding[0]

    @property
    def binding(self):
        return self.group_binding[1]


class Attachment(NamedTuple):
    """A render pass's attachment (drawing texture)"""
    name: str
    resource: resources.Texture
    clear_value: tuple[int, int, int, int] = (0, 0, 0, 1)
    blend: BlendMode = BlendMode.COPY
    load_op: str = 'clear'


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

    def instantiate_bind_groups(self, device):
        bindings = [r for r in self.resources() if isinstance(r, Binding)]
        groups = [r.group for r in bindings]
        group_count = max(groups) + 1

        self.bind_groups = [
            self._create_bind_group(
                device,
                [b for b in bindings if b.group == i],
            )
            for i in range(group_count)
        ]
        return self

    def rebind_group(self, device, name):
        bindings = [r for r in self.resources() if isinstance(r, Binding)]
        binding = [b for b in bindings if b.name == name][0]
        group = binding.group
        self.bind_groups[group] = self._create_bind_group(
            device,
            [b for b in bindings if b.group == group],
        )
        return self

    def _create_bind_group(self, device, bindings):
        if bindings:
            group = bindings[0].group
            assert all(b.group == group for b in bindings)
            return device.create_bind_group(
                label=self.make_label(f'bind group'),
                layout=self.pipeline.get_bind_group_layout(group),
                entries=[
                    wgpu.BindGroupEntry(
                        binding=b.binding,
                        resource=b.resource.resource_descriptor(),
                    )
                    for b in bindings
                ]
            )
        else:
            return None

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
    
    def instantiate_pipeline(self, device, shader_module):
        self.pipeline = device.create_compute_pipeline(
            label=self.make_label('pipeline'),
            layout='auto',
            compute=wgpu.ProgrammableStage(
                module=shader_module,
            ),
        )
        return self

    def instantiate_pass_descriptor(self):
        self.pass_descriptor = wgpu.ComputePassDescriptor(
            label=self.make_label('compute pass'),
        )
        return self

    def encode_compute_pass(self, encoder, workgroup_count):
        cpass = encoder.begin_compute_pass(**self.pass_descriptor)
        cpass.set_pipeline(self.pipeline)
        for (i, bg) in enumerate(self.bind_groups):
            if bg:
                cpass.set_bind_group(i, bg)
        cpass.dispatch_workgroups(workgroup_count)
        cpass.end()
        return self


class RenderPass(Pass):

    def instantiate_pipeline(
        self,
        device,
        shader_module,
        vertex_entry=None,
        fragment_entry=None,
    ):
        self.pipeline = device.create_render_pipeline(
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
        return self

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
        return self

    def _color_attachments(self):
        return [
            # Nobody is overriding these defaults yet.
            wgpu.RenderPassColorAttachment(
                clear_value=(0, 0, 0, 1),
                load_op=r.load_op,
                store_op='store',
                view=...,
            )
            for r in self.resources()
            if isinstance(r, Attachment)
        ]

    def encode_render_pass_draw(self, encoder, vertex_count):
        rpass = encoder.begin_render_pass(**self.pass_descriptor)
        rpass.set_pipeline(self.pipeline)
        # rpass.set_bind_group(0, self.input_bind_group)
        for (i, bg) in enumerate(self.bind_groups):
            if bg:
                rpass.set_bind_group(i, bg)
        rpass.draw(vertex_count)
        rpass.end()


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
