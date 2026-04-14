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
}

// //  //   //    //     //      //       //        //         //

const luminance_weights = vec3f(0.2126, 0.7152, 0.0722);
const white = 4.0;
const boost = 4.0;

fn luminance(c: vec3f) -> f32 {
    return dot(c, luminance_weights);
}

fn saturation(c: vec3f) -> f32 {
    let mn = min(min(c.r, c.g), c.b);
    let mx = max(max(c.r, c.g), c.b);
    if mx == 0.0 {
        return 0.0;
    }
    return (mx - mn) / mx;
}

fn reinhard_luminance_tone_map(c: vec3f) -> vec3f {
    let l = luminance(c);
    if l == 0.0 {
        return c;
    }
    let numerator = l * (1.0 + (l * (1.0 / (white * white))));
    let denominator = l + (1.0 / boost);
    return c * (numerator / denominator);
}

fn saturation_luminance_tone_map(c: vec3f) -> vec3f {
    let l = luminance(c);
    let s = saturation(c);
    let rhl = reinhard_luminance_tone_map(c);

    return mix(rhl, c, 0.5 * s);
}

@fragment fn fragment_shader(
    in: InterStage
) -> @location(0) vec4f {
    // return test(in);

    var pixel = textureSample(in_color, in_sampler, in.texcoord);
    if dot(pixel.rgb, pixel.rgb) == 0f {
        // pixel = test(in);
    }

    // let unmapped_rgb = pixel.rgb + test(in).rgb;
    let unmapped_rgb = pixel.rgb;
    // let mapped_rgb = reinhard_luminance_tone_map(unmapped_rgb);
    let mapped_rgb = saturation_luminance_tone_map(unmapped_rgb);
    return vec4f(mapped_rgb, pixel.a);
}

fn test(in: InterStage) -> vec4f {
    let st = in.texcoord;
    let pos = st * vec2f(2f, 8.0);

    let xy = vec2f(2.5, 2.0) * in.texcoord - vec2f(1.25, 1.0);
    let r2 = dot(xy, xy);

    // let n = noise2d(pos);
    // return vec4f(n, n, n, 1.0);

    // var n = 0.0;
    // var sc1 = 0.5;
    // var sc2 = 1.0;
    // for (var i = 0u; i < 3u; i++) {
    //     n += sc1 * noise2d(sc2 * pos);
    //     sc1 *= 0.5;
    //     sc2 *= 2.0;
    // }
    // return vec4f(n, n, n, 1.0);

    let n1 = (
        0.5 * noise2d(pos)
        + 0.25 * noise2d(2.0 * pos)
    );
    let n2 = (
        n1
        + 0.125 * noise2d(4.0 * pos)
        + 0.0625 * noise2d(8.0 * pos)
        // + 0.0625 * noise2d(16.0 * pos)
    );
    let th = 0.3;
    let m = 1.0 / (1.0 - th);
    let nn1 = m * max(0.0, n1 - th);
    let nn2 = m * max(0.0, n2 - th);
    let c_in = vec3f(0.0, 0.0, 0.1 * nn1);
    let c_out = vec3f(0.005 * n1, 0.0, 0.2 * nn2);
    // let c_in = vec3f(0.0, 0.0, nn1);
    // let c_out = vec3f(0.01 * n1, 0.0, nn2);
    let color = mix(c_in, c_out, smoothstep(0.87 * 0.87, 0.97 * 0.97, r2));
    return vec4f(color, 1.0);
}

fn noise2d(st: vec2f) -> f32 {
    let i = floor(st);
    let f = fract(st);

    let a = rand2d(i);
    let b = rand2d(i + vec2f(1.0, 0.0));
    let c = rand2d(i + vec2f(0.0, 1.0));
    let d = rand2d(i + vec2f(1.0, 1.0));
    
    let u = smoothstep(vec2f(0.0), vec2f(1.0), f);

    return mix(a, b, u.x) +
        (c - a) * u.y * (1.0 - u.x) +
        (d - b) * u.x * u.y;
}

fn rand2d(st: vec2f) -> f32 {
    return fract(sin(dot(st, vec2(12.9898, 78.2323))) * 43758.5453123);
}
