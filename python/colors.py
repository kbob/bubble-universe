from dataclasses import dataclass
from enum import StrEnum
import enum

from constants import *
from parameterized import ParameterizedMixIn
from passes import Access, Attachment, Binding, RenderPass
from wgsl_types import *


class Theme(StrEnum):
    CLASSIC = 'Classic'
    VAPOR = 'Vapor'
    MIDNIGHT = 'Midnight'
    FIESTA = 'Fiesta'
    EASTER = 'Easter'
    BONE = 'Bone'
    OSCOPE = 'Oscilloscope'
    TRIAD = 'Triad'

    @classmethod
    def from_string(cls, s):
        try:
            return cls(s)
        except ValueError:
            sl = s.lower()
            for m in cls:
                if sl == m.lower():
                    return m
            assert False, f'Unknown {cls.__name__} {s!r}'

    @classmethod
    def from_int(cls, n):
        return list(cls)[n]

    def __int__(self):
        return list(type(self)).index(self)

    @enum.property
    def colors_animated(self):
        return self in {self.TRIAD}
    
    @enum.property
    def background_animated(self):
        return self in {self.VAPOR, self.MIDNIGHT, self.FIESTA, self.TRIAD}

vapor = Theme.VAPOR
assert vapor == Theme.from_string('vAPoR')
assert vapor == Theme.VAPOR
assert int(vapor) == 1
assert Theme.from_int(1) == vapor
assert Theme('Vapor') == vapor
assert not vapor.colors_animated
assert vapor.background_animated


class ColormapPass(RenderPass, ParameterizedMixIn):

    @dataclass
    class Parameters:
        seq_count: u32 = Defaults.SEQ_COUNT
        seq_length: u32 = Defaults.SEQ_LENGTH
        theme: Theme = Theme(Defaults.THEME)
        t: float = 0

    class _Uniforms(Uniforms):
        seq_count: u32 = Defaults.SEQ_COUNT
        seq_length: u32 = Defaults.SEQ_LENGTH
        theme: u32 = int(Theme(Defaults.THEME))
        t: f32 = 0

    def __init__(self, name='colors'):
        super().__init__(name)
        self.colormap = None
        self._enabled = True
        self.shader_file = 'colors.wgsl'
        self.shader = self.read_shader(self.shader_file)

    def enable(self):
        self._enabled = True

    def update_parameters(self, **kwargs):
        if 'theme' in kwargs and kwargs['theme'] != self._parameters.theme:
            self._enabled = True
        super().update_parameters(**kwargs)

    def resources(self):
        assert self.colormap is not None
        assert self.uniform_buffer is not None
        return [
            Binding((0, 0), 'uniforms', self.uniform_buffer, Access.RO),
            Attachment('colormap_output', self.colormap),
        ]

    def attach_colormap_output(self, colormap):
        self.colormap = colormap
        return self

    def instantiate(self, device):
        assert self.colormap is not None
        assert self.uniform_buffer is not None

        shader_module = device.create_shader_module(
            label=self.make_label(f'shader {self.shader_file}'),
            code=self.shader,
        )        

        self.instantiate_pipeline(device, shader_module)
        self.instantiate_bind_groups(device)
        self.instantiate_pass_descriptor()

    def execute(self, device, encoder):

        if not self._enabled:
            return
        if not self._parameters.theme.colors_animated:
            self._enabled = False

        # Get the output texture.
        current_texture = self.colormap.current_texture()
        current_view = self.colormap.current_view()

        # Update the output view
        self.pass_descriptor.color_attachments[0].view = current_view

        uniforms = self._Uniforms(
            seq_count=self._parameters.seq_count,
            seq_length=self._parameters.seq_length,
            theme=int(self._parameters.theme),
            t=self._parameters.t,
        )
        self.uniform_buffer.write_buffer(device, uniforms.as_data())

        vertex_count = 3
        self.encode_render_pass_draw(encoder, vertex_count)
