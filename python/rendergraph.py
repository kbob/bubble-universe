import passes
import resources


frame = 0

class RenderGraph:

    def __init__(self, device, passes, external_resources=[]):

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

    def execute(self, device):
        global frame

        encoder = device.create_command_encoder(
            label='rendergraph command encoder'
        )
        for pass_ in self.passes:
            pass_.execute(device, encoder)
        frame += 1
        command_buffer = encoder.finish()
        device.queue.submit([command_buffer])
