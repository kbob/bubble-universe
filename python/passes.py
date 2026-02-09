from abc import ABC, abstractmethod
import os.path

class LabelMaker:
    def __init__(self, base):
        self.base = base
    def shader_label(self):
        return f'{self.base} shader'
    def buffer_layout_label(self, buf_name):
        return f'{self.base} {buf_name} buffer'
    def bind_group_label(self, group_name):
        return f'{self.base} {group_name} buffer'
    def pipeline_layout_label(self):
        return f'{self.base} pipeline layout'
    def pipeline_label(self):
        return f'{self.base} pipeline'
    def compute_pass_descriptor_label(self):
        return f'{self.base} compute pass descriptor'

class Pass(ABC):
    """Base class for compute and render passes"""

    def __init__(self, name):
        self.dymo = LabelMaker(name)

    @abstractmethod
    def instantiate(self):
        ...

    def read_shader(self, filename):
        """ return contents of a file in the shaders directory """
        up = os.path.dirname
        path = os.path.join(up(up(__file__)), 'shaders', filename)
        with open(path) as f:
            return f.read()


class ComputePass(Pass):
    ...

class RenderPass(Pass):
    ...
