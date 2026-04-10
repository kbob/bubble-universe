const INV_PHI: f32 = (sqrt(5.0) - 1.0) / 2.0;

struct Uniforms {
    seq_count: u32,
    seq_length: u32,
    theme: u32,
    t: f32,
};

@group(0) @binding(0) var<uniform> uniforms: Uniforms;

struct InterStage {
    @builtin(position) position: vec4f,
    @location(0) texcoord: vec2f,
};

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

@fragment fn fragment_shader(
    in: InterStage,
) -> @location(0) vec4f {

    let U = uniforms;

    if U.theme == 6u {
        return oscope_color(in);
    }
    if U.theme == 5u {
        return bone_color(in);
    }
    if U.theme == 4u {
        return easter_color(in);
    }
    if U.theme == 3u {
        return fiesta_color(in);
    }
    if U.theme == 2u {
        return midnight_color(in);
    }
    if U.theme == 1u {
        return vapor_color(in);
    }
    // Use classic for 0u and any unknown themes too.
    return classic_color(in);
}

fn classic_color(in: InterStage) -> vec4f {
    let r = in.texcoord.x * (200.0 / 255.0);
    let g = in.texcoord.y * (200.0 / 255.0);
    let b = 99.0 / 255.0;
    let a = 1.0;
    return vec4f(r, g, b, a);
}

fn vapor_color(in: InterStage) -> vec4f {
    let h = 0.6 + 0.4 * in.texcoord.x;
    let s = 0.8;
    let v = 0.5 + 1.0 * in.texcoord.y;
    let a = 1.0;
    return vec4f(hsv_to_rgb(h, s, v), a);
}

fn midnight_color(in: InterStage) -> vec4f {
    let r = 0.005 * in.texcoord.x * in.texcoord.y;
    let g = 0.0;
    let b = 0.2 + 0.6 * in.texcoord.y;
    let a = 1.0;
    return vec4f(r, g, b, a);
}

fn fiesta_color(in: InterStage) -> vec4f {
    let U = uniforms;
    let i = i32(in.texcoord.x * f32(U.seq_length) + 0.5);
    let h = (INV_PHI * f32(i)) % 1.0;
    let s = 1.0;
    let v = 1.0;
    let a = 1.0;
    return vec4f(hsv_to_rgb(h, s, v), a);
}

fn easter_color(in: InterStage) -> vec4f {
    let U = uniforms;

    let grass = in.texcoord.y < 0.2;
    if grass {
        return vec4f(0.0, 0.3, 0.0, 1.0);
    } else {
        let i = i32(in.texcoord.x * f32(U.seq_length) + 0.5);
        let h = (INV_PHI * f32(i)) % 1.0;
        let s = 0.7;
        let v = 1.0;
        let a = 1.0;
        return vec4f(hsv_to_rgb(h, s, v), a);
    }
}

fn bone_color(in: InterStage) -> vec4f {
    let h = 0.1 + 0.2 * in.texcoord.x;
    let s = 0.4 * in.texcoord.y;
    let v = 0.6 + 0.3 * in.texcoord.y;
    let a = 1.0;
    return vec4f(hsv_to_rgb(h, s, v), a);
}

fn oscope_color(in: InterStage) -> vec4f {
    let r = 0.0;
    let g = 0.1875;   // 12/64
    let b = 0.015625; // 1/64
    let a = 1.0;
    return vec4f(r, g, b, a);
}

fn hsv_to_rgb(h: f32, s: f32, v: f32) -> vec3f {
    if s == 0.0 {
        return vec3f(v);
    }
    var i = i32(h * 6.0);
    let f = (h * 6.0) - f32(i);
    let p = v * (1.0 - s);
    let q = v * (1.0 - s * f);
    let t = v * (1.0 - s * (1.0 - f));
    i %= 6;
    if i == 0 {
        return vec3f(v, t, p);
    }
    if i == 1 {
        return vec3f(q, v, p);
    }
    if i == 2 {
        return vec3f(p, v, t);
    }
    if i == 3 {
        return vec3f(p, q, v);
    }
    if i == 4 {
        return vec3f(t, p, v);
    }
    if i == 5 {
        return vec3f(v, p, q);
    }
    return vec3f(0.0);
}