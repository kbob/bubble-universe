import passes
import resources


frame = 0

class RenderGraph:

    def __init__(self, device, passes):

        # Find and instantiate all bound resources
        resources = {}
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

    def execute(self, device):
        global frame

        encoder = device.create_command_encoder(
            label='rendergraph command encoder'
        )
        for pass_ in self.passes:
            from light_bloom import BloomSubgraph
            from copier import CopyPass
            # print(f'{frame = }')
            # if isinstance(pass_, BloomSubgraph):
            #     if frame % 2 == 0:
            #         # print('    no bloom')
            #         continue
            if isinstance(pass_, CopyPass):
                # from constants import MAX_FPS
                # if frame % (2 * MAX_FPS) < MAX_FPS:
                    # print('    no copy')
                    continue
            pass_.execute(device, encoder)
        frame += 1
        command_buffer = encoder.finish()
        device.queue.submit([command_buffer])
