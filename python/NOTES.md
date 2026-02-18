Adding HDR

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
