# Notes on Work in Progress

Nothing here is definite.  These are my thoughts as I figure out
what I'm doing.

Most recent notes are on top.

## Bloom, 2nd Try

*This is on hold.  float16 looks okay for now.*

To work with float32 textures, it needs to have two sets of buffers:
one set gets downsampled into, and the other gets upsample-added.
I *think* the Upsampler and UpsampleMixer would become identical,
just different gains.

The `BloomSubgraph` should build an actual subgraph, with one
`Downsampler` and one `Upsampler` instance for each MIP level.

Construct the subgraph in BloomSubgraph constructor.

    class BloomSubgraph:

        def __init__(self):
            self.input = None
            self.output = None
            self._parameters = ...
            self.downsample_textures = [...]
            self.upsample_textures = [...]
            self.downsamplers = [...]
            self.upsamplers = [...]

        def bindings(self):
            ... # input, output, downsample and upsample textures

        def instantiate(self, device):
            self.graph = RenderGraph(downsampler + upsamplers, ...)

--------

## Architecture Changes

## Resizing

Viewport resizing is very ad-hoc.  I should figure out which textures
need to be resized and which passes need to rebind them.

I kind of want to put an annotation in `resources` that says which
resources are affected if the color attachment changes size.  Then
RenderGraph can walk the graph, resize and rebind as needed.

There are weird cases,though. For example, `Bloomer` might want to
change the MIP depth when resized.

For now, I'll have Bubbler resize passes explicitly and Bloomer
will resize its resources and subpasses.

But there should be a "rebuild bind group if changed" thing.
Imagine a `resource_changed` method which calls a `binding_changed`
or `attachment_changed`.  They rebuild the bind group/color attachment.

 1. Split bindings into bindings and attachments.
 2. Write Pass.create_bind_group_entry().
 

## Resources, Bindings, Attachments

Should distinguish between bindings and attachments.
the `bindings` method should be renamed `resources` and return
a list containing both bindings and attachments.

The `resources` (*nee* `bindings`) method of passes has enough
information to create the bind groups.  The passes could become
more declarative.

It would be awesome if `resources` became totally declarative.

    class MyPass(RenderPass):
        class Resources:
            uvs: Buffer
            decal: Texture
            color: Attachment
            depth: Attachment

... or something.

### Strategy

  * rename `bindings()` to `resources()`

  * Define Attachment class.  Move color attachments to it.

  * Add info to attachments to create the `RenderPassColorAttachment`.
     - blend mode, default = replace
     - clear_value, default = (0, 0, 0, 1)

  * Refactor color attachment initialization out of
    `.instantiate()` methods

  * add info to Binding and do likewise.



## `update_parameters`

*This is done.*

The `update_parameters` method could be moved into `Pass`.  It can
get everything it needs from the `self.Parameters` subclass's
annotations.

--------

## Bloom

https://learnopengl.com/Guest-Articles/2022/Phys.-Based-Bloom


    constants:
        MIP_LEVELS = 5

    defaults:
        BLUR_AMOUNT = 0.1  # turn these up a lot for debugging
        BLUR_SIZE = 0.005

    parameters:
        mip_levels = 5
        blur_amount
        blur_size

    bindings:
        input
        output_color

    initialize:
        # Construct framebuffers, textures
        size = output.size
        mip_textures = [
            Texture(size / 2, ...),
            Texture(size / 4, ...),
        ]
        downsample = RenderPass(...)
        upsample = RenderPass(...)
        upsample_mix = RenderPass(...)

    execute:
        src = input
        ping, pong = mip_textures

        # recursively downsample

        for i in range(MIP_LEVELS):
            downsample.update_parameters(size = 2**(-i - 1))
            downsample.bind_input(src)
            downsample.bind_output(ping)
            downsample.execute()
            src = ping
            ping, pong = pong, ping # ping-pong the ping pong pair.
        # Now pong has the smallest mip

        # recursively upsample

        upsample.update_parameters(
            blur_radius=parameters.blur_radius,
        )
        for i in range(MIP_LEVELS, 1, -1):
            upsample.update_parameters(size=2**-i)
            upsample.bind_input(src)
            upsample.bind_output(ping)
            upsample.execute()
            src = ping
            ping, pong = pong, ping # ping-pong the ping pong pair.

        # last upsample pass also mixes into the destination buffer
        upsample_mix.update_parameters(
            blur_amount=parameters.blur_amount,
            blur_radius=parameters.blur_radius,
        )
        upsample_mix.bind_image_input(input)
        upsample_mix.bind_blur_input(src)
        upsample_mix.bind_output_color(output_color)
        upsample_mix.execute()


To encapsulate, I should define a GenericPass hierarchy: has the
same interface as Pass but isn't an actual wgpu compute/render pass.        

    class GenericPass(Pass):  # name TBD
        """A RenderGraph node with bindings that does
           not encapsulate a wgpu pipeline-renderpass.
        """
        # implements bindings, bind_foo, instantiate, execute, resize

GenericPass?  CompositePass?  GraphPass?  Subgraph?

------


## Adding HDR

Use an rgba16float HDR pixel format.

1. shader.  Change definitions and color calculations.
2. HDRdrawingPass.
   - Extra bindings, different texture datatypes.
   - Change blend mode to add
3. Extend Texture as needed.
4. Tone mapping pass.

------


Just thinking out loud about wgpu modularity.

I'd like to be able to declare a bunch of buffers and a bunch of render
passes and connect them together.


    class ParticleMotionPass(ComputePass):
        ...
    class DrawingPass(RenderPass):
        ...
    class TonemapPass(RenderPass):
        ...


    ParticleMotionPass particle_motion(...)

    # colormap and depth buffer are local to the drawer pass
    DrawingPass drawer(...)
    Texture colormap(...)
    DepthBuffer depth(...)
    connect_input(drawer, colormap, ...)
    connect_in_out(drawer, depth, ...)

    TonemapPass tonemapper(...)

    # uv is written by particle_motion and read by drawing_pass
    StorageBuffer uv(...)
    connect_output(particle_motion, uv, ...)
    connect_input(drawing_pass, uv, ...)

    connect_output(drawer, hdr_pixels, ...)
    connect_input(tonemapper, canvas, ...)

    render_graph = RenderGraph(
        device,
        [
            particle_motion,
            drawer,
            tonemapper,
        ],
        ...)


And then at draw_frame time, something like this.

    particle_motion.update_params(...)
    drawer.update_params(...)
    tonemapper.update_params(...)
    # buffers are implicit
    render_graph.execute()


Then I could swap out the draw pass, use a modified particle stream (or a
filter), use dynamic colormap, add/substitute a video to file destinatin, etc.

This kind of looks like what wgpu does with bindings, but could potentially
be less verbose at the expense of some flexibility.

The open question is, how flexible and terse can I make it?

=========

So here's a class hierarchy maybe.

    class Resource:         # base class for all resources
    class Uniforms(Resource):
    class StorageBuffer(Resource):
    class VertexBuffer(Resource):
    class Texture(Resource):
    class CanvasTexture(Texture):
    class Sampler(Resource):

    class Pass:             # base class for all passes
    class ComputePass(Pass):
    class ParticleMotionPass(ComputePass): # defines shaders and uniforms
    class ColormapPass(ComputePass):
    class RenderPass(Pass):
    class DrawingPass(RenderPass):
    class MaskedDrawingPass(RenderPass): # variant that suppresses some particles
    class ToneMappingPass(RenderPass):

========

At init time, the goal is to build wgpu pipeline objects and
Render/ComputePassDescriptor objects (as far as possible).

    trace the graph, find all buffers and textures, create them
    for each graph,
        construct a GPURender/ComputePass

The pipelines will require shader modules, bindings, pipelines, blend modes...

Each pass will have some setters for things that aren't part of the uniforms,
or maybe the passes hide which parameters are uniforms and which are render
pass modifications.

========

The start of the hard work is RenderGraph's constructor.


========

Bindings should be kept entirely within the compute/render pass objects.
Layouts are there; the shader source is there.

The wgpu pipeline should be Compute/RenderPass class state; the wgpu
compute/renderpass should be instance state.  That way, a pipeline can
be reused in several passes.  The bindings are part of the instance state.

=========

Files

generic WGPU stuff
 * wgsl_types.py - scalars, vectors, and matrices
 * labels.py - LabelMaker
 * resources.py - Resource, Uniforms, StorageBuffer, Texture, Sampler
 * passes.py - Pass, ComputePass, RenderPass

bubble universe stuff
 * constants.py - limits, sizes, and defaults
 * particle_motion.py - ParticleMotion, ParticleMotionUniforms
 * drawer.py - Drawer, DrawerUniforms
