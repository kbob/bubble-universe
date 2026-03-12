// Three shaders used by the light bloom pipeline:
//  - ds:  downsampler
//  - us:  upsampler
//  - usm: upsample mixer

struct DSUniforms {
    viewport_size: vec2f,
};

struct USUniforms {
    filter_radius: vec2f,
};

struct USMUniforms {
    filter_radius: vec2f,
    bloom_strength: f32,
};

@group(0) @binding(0) var in_color: texture_2d<f32>;
@group(0) @binding(1) var in_sampler: sampler;
@group(2) @binding(0) var in_blur: texture_2d<f32>;
@group(2) @binding(1) var in_blur_sampler: sampler;

@group(1) @binding(0) var<uniform> ds_uniforms: DSUniforms;
@group(1) @binding(0) var<uniform> us_uniforms: USUniforms;
@group(1) @binding(0) var<uniform> usm_uniforms: USMUniforms;

// All three shaders use the same interstage variables.
struct InterStage {
    @builtin(position) position: vec4f,
    @location(0) texcoord: vec2f,
};

// All three shaders use the same vertex shader.
@vertex fn vertex_shader(
    @builtin(vertex_index) vertex_index: u32,
) -> InterStage {

    var pos = array<vec2f, 3>(
        vec2f(-1.0, -1.0),
        vec2f(-1.0,  3.0),
        vec2f( 3.0, -1.0),
    );

    let xy = pos[vertex_index];
    var out: InterStage;
    out.position = vec4f(xy, 0.0, 1.0);
    out.texcoord = xy * vec2f(0.5, -0.5) + vec2f(0.5);
    return out;
}

@fragment fn downsampler_fragment_shader(
    in: InterStage
) -> @location(0) vec4f {
    let U = ds_uniforms;
    let C = in_color;
    let S = in_sampler;
    let x = in.texcoord.x;
    let y = in.texcoord.y;
    let dx = 1.0 / U.viewport_size[0];
    let dy = 1.0 / U.viewport_size[1];
    let a = textureSample(C, S, vec2f(x - 2. * dx, y + 2. * dy)).rgb;
    let b = textureSample(C, S, vec2f(x,           y + 2. * dy)).rgb;
    let c = textureSample(C, S, vec2f(x + 2. * dx, y + 2. * dy)).rgb;

    let d = textureSample(C, S, vec2f(x - 2. * dx, y          )).rgb;
    let e = textureSample(C, S, vec2f(x,           y          )).rgb;
    let f = textureSample(C, S, vec2f(x + 2. * dx, y          )).rgb;

    let g = textureSample(C, S, vec2f(x - 2. * dx, y - 2. * dy)).rgb;
    let h = textureSample(C, S, vec2f(x,           y - 2. * dy)).rgb;
    let i = textureSample(C, S, vec2f(x + 2. * dx, y - 2. * dy)).rgb;

    let j = textureSample(C, S, vec2f(x -      dx, y +      dy)).rgb;
    let k = textureSample(C, S, vec2f(x +      dx, y +      dy)).rgb;
    let l = textureSample(C, S, vec2f(x -      dx, y -      dy)).rgb;
    let m = textureSample(C, S, vec2f(x +      dx, y -      dy)).rgb;

    // accumulate components from small to large, preserve precision
    var downsample: vec3f = vec3f(0.0);
    downsample += 0.03125 * (a + c + g + i);
    downsample += 0.0625  * (b + d + f + h);
    downsample += 0.125   * (j + k + l + m);
    downsample += 0.125   * e;

    return vec4f(downsample.rgb, 1.0);
}

fn blurred(T: texture_2d<f32>, S: sampler, x: f32, y: f32, dx: f32, dy: f32) -> vec3f {

    let a = textureSample(T, S, vec2f(x - dx, y + dy)).rgb;
    let b = textureSample(T, S, vec2f(x     , y + dy)).rgb;
    let c = textureSample(T, S, vec2f(x + dx, y + dy)).rgb;

    let d = textureSample(T, S, vec2f(x - dx, y     )).rgb;
    let e = textureSample(T, S, vec2f(x     , y     )).rgb;
    let f = textureSample(T, S, vec2f(x + dx, y     )).rgb;

    let g = textureSample(T, S, vec2f(x - dx, y - dy)).rgb;
    let h = textureSample(T, S, vec2f(x     , y - dy)).rgb;
    let i = textureSample(T, S, vec2f(x + dx, y - dy)).rgb;

    var sum: vec3f = vec3f(0.0);
    sum += 0.0625 * (a + c + g + i);
    sum += 0.125  * (b + d + f + h);
    sum += 0.5    * (e);
    return sum;
}

@fragment fn upsampler_fragment_shader(
    in: InterStage
) -> @location(0) vec4f {
    let U = us_uniforms;
    let C = in_color;
    let S = in_sampler;
    let x = in.texcoord.x;
    let y = in.texcoord.y;
    let dx = U.filter_radius.x;
    let dy = U.filter_radius.y;
    let upsample = blurred(C, S, x, y, dx, dy);

    return vec4f(upsample.rgb, 1.0);
}

@fragment fn upsample_mixer_fragment_shader(
    in: InterStage
) -> @location(0) vec4f {
    let U = usm_uniforms;
    let C = in_color;
    let CS = in_sampler;
    let B = in_blur;
    let BS = in_blur_sampler;
    let xy = in.texcoord;
    let x = xy.x;
    let y = xy.y;
    let dx = U.filter_radius.x;
    let dy = U.filter_radius.y;
    let a = textureSample(C, CS, xy);
    let b = blurred(B, BS, x, y, dx, dy);
    var mx = mix(a.rgb, b.rgb, U.bloom_strength);

    // // uncomment to turn the particles black
    // mx *= smoothstep(-0.1, 0.0, -(a.r + a.g + a.b));

    // // uncomment out to make the particles disappear
    // mx = b * U.bloom_strength;

    return vec4f(mx, 1.0);
}
