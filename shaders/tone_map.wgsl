@group(0) @binding(0) var in_color: texture_2d<f32>;
@group(0) @binding(1) var in_sampler: sampler;

struct InterStage {
    @builtin(position) position: vec4f,
    @location(0) texcoord: vec2f,
};

@vertex fn vertex_shadder(
    @builtin(vertex_index) vertex_index: u32,
) -> InterStage {

    let pos: array<vec2f, 3> = array<vec2f, 3>(
        vec2f(-1.0, -1.0),
        vec2f(-1.0,  3.0),
        vec2f( 3.0, -1.0),
    );

    let xy = pos[vertex_index];

    var out: InterStage;
    out.position = vec4f(xy, 0.0, 1.0);
    out.texcoord = xy * vec2f(0.5, -0.5) + vec2f(0.5);
    return out;
};

// //  //   //    //     //      //       //        //         //

const luminance_weights = vec3f(0.2126, 0.7152, 0.0722);
const white = 4.0;
const boost = 4.0;

// fn lerp3f(frac: f32, a: vec3f, b: vec3f) -> vec3f {
//     return frac * b + (1 - frac) * a;
// };

fn luminance(c: vec3f) -> f32 {
    return dot(c, luminance_weights);
};

fn saturation(c: vec3f) -> f32 {
    // let avg = 0.333 * (c.r + c.g + c.b);
    let mn = min(min(c.r, c.g), c.b);
    let mx = max(max(c.r, c.g), c.b);
    if mx == 0.0 {
        return 0.0;
    }
    return (mx - mn) / mx;
    // return (mx - avg) / mx;
};

fn reinhard_luminance_tone_map(c: vec3f) -> vec3f {
    let l = luminance(c);
    if l == 0.0 {
        return c;
    }
    let numerator = l * (1.0 + (l * (1.0 / (white * white))));
    let denominator = l + (1.0 / boost);
    return c * (numerator / denominator);
};

fn saturation_luminance_tone_map(c: vec3f) -> vec3f {
    let l = luminance(c);
    let s = saturation(c);
    let rhl = reinhard_luminance_tone_map(c);

    // return lerp3f(s, rhl, c);
    return mix(rhl, c, 0.5 * s);
}

@fragment fn fragment_shader(
    in: InterStage
) -> @location(0) vec4f {
    let pixel = textureSample(in_color, in_sampler, in.texcoord);
    let unmapped_rgb = pixel.rgb;
    // let mapped_rgb = reinhard_luminance_tone_map(unmapped_rgb);
    let mapped_rgb = saturation_luminance_tone_map(unmapped_rgb);
    return vec4f(mapped_rgb, pixel.a);
};
