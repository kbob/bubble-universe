import passes
import resources

class RenderGraph:

    def __init__(self, device, passes):
        self.passes = passes

        # Find and instantiate all bound resources
        self.resources = {}
        for pass_ in passes:
            for b in pass_.bindings():
                resource = b.resource
                assert resource, f"pass '{pass_.name}' is missing resource '{b.name}'"
                if resource not in self.resources:
                    self.resources[resource] = resource.instantiate(device)

        # Instantiate all passes
        self.passes = {}
        for pass_ in passes:
            self.passes[pass_] = pass_.instantiate(device)

    def execute(self, device):

        encoder = device.create_command_encoder(
            label='rendergraph command encoder'
        )
        for pass_ in self.passes:
            pass_.execute(device, encoder)
        command_buffer = encoder.finish()
        device.queue.submit([command_buffer])
