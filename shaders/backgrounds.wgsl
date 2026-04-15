const INV_PHI: f32 = (sqrt(5f) - 1f) / 2f;
const BORDER: f32 = 0.1;        // duplicated from constants.py
const TAU: f32 = radians(360f);

struct Uniforms {
    theme: u32,
    t: f32,
    viewport_size: vec2u,
};

@group(0) @binding(0) var<uniform> uniforms: Uniforms;

struct InterStage {
    @builtin(position) position: vec4f,
    @location(0) texcoord: vec2f,
    @location(1) xy: vec2f,
};

@vertex fn vertex_shader(
    @builtin(vertex_index) vertex_index: u32,
) -> InterStage {

    let U = uniforms;

    var corners = array<vec2f, 3>(
        vec2f(-1f, -1f),
        vec2f(-1f,  3f),
        vec2f( 3f, -1f),
    );

    let w = f32(U.viewport_size[0]);
    let h = f32(U.viewport_size[1]);
    var scale: vec2f;
    if h > w {
        // portrait
        scale = vec2f(1f, h / w);
    } else {
        // landscape
        scale = vec2f(w / h, 1f);
    }
    scale /= 0.9;

    let pos = corners[vertex_index];
    let xy = pos * scale;

    var out: InterStage;
    out.position = vec4f(pos, 0f, 1f);
    out.texcoord = pos * vec2f(0.5, -0.5) + vec2f(0.5);
    out.xy = xy;
    return out;
}

@fragment fn fragment_shader(
    in: InterStage,
) -> @location(0) vec4f {

    let U = uniforms;

    if U.theme == 6u {
        return oscope_background(in);
    }
    // if U.theme == 5u {
    //     return bone_background(in);
    // }
    if U.theme == 4u {
        return easter_background(in);
    }
    if U.theme == 3u {
        return fiesta_background(in);
    }
    if U.theme == 2u {
        return midnight_background(in);
    }
    if U.theme == 1u {
        return vapor_background(in);
    }
    // Use classic for 0u and any unknown themes too.
    return classic_background(in);
}


// //  //   //    //     //      //       //        //         //
// Classic Theme

fn classic_background(in: InterStage) -> vec4f {
    return vec4f(0f, 0f, 0f, 1f);
}


// //  //   //    //     //      //       //        //         //
// Vapor Theme

fn vapor_background(in: InterStage) -> vec4f {

    let U = uniforms;

    const PINK = vec3f(1f, 0f, 0.75);
    const LIGHT_BLUE = vec3f(0.3, 0.5, 1f);
    const DARK_BLUE = vec3f(0.02, 0f, 0.10);
    const SILVER = vec3f(0.5);

    const HORIZON_Y = 0.2;
    const HORIZON_THICKNESS = 0.01;
    const FLOOR_FADE_H = 0.1;

    let x = in.xy.x;
    let y = in.xy.y;

    // What we're doing
    // in bubble: darker dark blue
    // around bubble: pink glow
    // sky: dark blue gradient fade to lighter blue to pink
    // horizon line: light blue
    // floor:
    //     dark blue
    //     light blue hlines
    //     light blue vlines
    //     light blue glow around lines
    //     distance fade to silver

    var color: vec3f;
    if y > HORIZON_Y {
        // sky
        let sky_gradient = min(1f, y - HORIZON_Y);
        color = mix(5f * DARK_BLUE, DARK_BLUE, sky_gradient);
        // sunset (pink)
        let sunset_mix = pow(min(1f, (y - HORIZON_Y) * 4f), 0.5);
        color = mix(PINK, 1.5 * color, sunset_mix);
    } else if (y > HORIZON_Y - HORIZON_THICKNESS) {
        // horizon
        color = LIGHT_BLUE;
    } else {
        // floor
        color = DARK_BLUE;

        // grid
        // perspective coord
        let py = y - HORIZON_Y;
        let p = vec3f(x / py, 0f, 3f / py - 15f * U.t);

        // vlines
        let vl_dist = abs(p.x - round(p.x));
        let vline_mix =
            0.94 * smoothstep(0.005, 0f, vl_dist)
            + 0.06 * smoothstep(0.15, 0f, vl_dist);
        color = mix(color, LIGHT_BLUE, vline_mix);

        // hlines
        let hl_dist = abs(p.z - round(p.z));
        let hl_thickness = max(0.2 * (py + 1f), 0.01);
        let hline_mix =
            0.94 * smoothstep(hl_thickness, 0f, hl_dist)
            + 0.06 * smoothstep(0.15, 0f, hl_dist);
        color = mix(color, LIGHT_BLUE, hline_mix);

        // floor distance fade
        let fade_y = (y + FLOOR_FADE_H) / HORIZON_Y;
        let floor_fade = pow(clamp(fade_y, 0f, 1f), 1.5);
        color = mix(color, SILVER, floor_fade);
    }

    let r2 = dot(in.xy, in.xy);
    if r2 < 1f {
        // in the bubble
        color = 0.3 * DARK_BLUE;
    } else {
        // apply bubble glow.
        // bubble glow is oval.
        let glow_size = 0.2 + 0.3 * x * x;
        let bubble_glow = 0.3 * smoothstep(1f + glow_size, 1f - glow_size, r2);
        color = mix(color, PINK, bubble_glow);
    }

    return vec4f(color, 1f);
}


// //  //   //    //     //      //       //        //         //
// Midnight Theme

fn midnight_background(in: InterStage) -> vec4f {
    let U = uniforms;

    // Bubble threshold.  Slightly inside the bubble and blurred.
    const IN_RADIUS = 0.87;
    const OUT_RADIUS = 0.97;
    let r2 = dot(in.xy, in.xy);
    let ir2 = IN_RADIUS * IN_RADIUS;
    let or2 = OUT_RADIUS * OUT_RADIUS;
    let circle_mix = smoothstep(ir2, or2, r2);

    // Generate mist noise.
    // Inside the bubble, it has three octaves.
    // Outside, it has four octaves (more detail) and is brighter.
    // The mist is more wide than tall.
    const MIST_SCALE = vec2f(0.35, 2.5);
    let st = in.xy;
    let pos = st * MIST_SCALE;
    let alpha = U.t;
    let n_base = (
        0.5 * srnoise2(pos, 2f * alpha)
        + 0.25 * srnoise2(2f * pos, 2f * alpha)
        + 0.125 * srnoise2(4f * pos, 4f * alpha)
    );
    let n_in = n_base - 0.1;
    let n_out = (
        n_base
        + 0.0625 * srnoise2(8f * pos, 8f * alpha)
        + 0.04 * srnoise2(16f * pos, 16f * alpha)
    );

    // Condition the noise.  Give it black areas, then brighten it.
    const MIST_DARKEN = 0.15;
    const MIST_GAIN = 2f;
    let cn_in = MIST_GAIN * max(0f, n_in - MIST_DARKEN);
    let cn_out = MIST_GAIN * max(0f, n_out - MIST_DARKEN);

    // Color the mist.
    // Inside the bubble, it's pure blue.
    // Outside, it's blue, and the wisps are tinged purple.
    let c_in = vec3f(0f, 0f, 0.1 * cn_in);
    let c_out = vec3f(0.03 * (cn_out - cn_in), 0f, 0.2 * cn_out);

    let color = mix(c_in, c_out, circle_mix);
    return vec4f(color, 1f);
}


// //  //   //    //     //      //       //        //         //
// Fiesta Theme


fn rfract(x: f32) -> f32 {
    // rounded fractional part
    return x - round(x);
}

fn fiesta_background(in: InterStage) -> vec4f {

    let U = uniforms;

    const STRING_COUNT: f32 = 4.5;
    const FLAG_COUNT: f32 = 5f;
    const DROOP_K = 0.8;

    let x = in.xy.x;
    let y = in.xy.y;

    // iy divides the viewport into horizontal bands, one per flag string.
    // fy goes from 0..1 in each band.
    let sy = y / 2.2 * f32(STRING_COUNT);
    let iy = floor(sy);
    let fy = sy - iy;

    // sx shifts and scales x in each horizontal band.
    // ix divides the bands into flag segments (arcs).
    // fx goes from 0..1 in each segment.
    let sx = 0.55 * (x + INV_PHI * iy);
    let ix = round(sx);
    let fx = sx - ix;

    // flag is a different integer for each flag in a row
    let flag = round(sx * FLAG_COUNT);

    // iv - a different xy for each flag segment.
    // noise -- low frequency simplex noise value for each flag segment.
    // cn (conditioned noise) -- noise scaled to 0.7 .. 1.3 (approx.)
    let iv = vec2f(ix, iy);
    let noise =
        srnoise2(iv, U.t)
        + 0.5 * srnoise2(iv * 0.5, 2f * U.t)
        + 0.25 * srnoise2(iv * 0.25, 4f * U.t)
        ;
    let cn = 1f + 0.3 * (noise - 0.5);

    // segment_droop - how far each flag segment droops.
    // droop_y - y coordinage of the invisible string
    //           (0 = band bottom, 1 = band top)
    let segment_droop = cn * DROOP_K;
    let droop_y = (cosh(2f * fx * segment_droop) - cosh(segment_droop)) + 1f;

    // Is this fragment part of the sky or a flag?
    var in_sky: bool = false;
    if fy > droop_y || fy < droop_y - 0.5 {
        // between flag strings
        in_sky = true;
    }
    if abs(sx * FLAG_COUNT - flag) > 0.42 {
        // between flags on string
        in_sky = true;
    }
    if fract(sx * 50f + 0.7) < 0.4 && fract((fy - droop_y) * 15f) < 0.4 {
        // holes in flags
        in_sky = true;
    } 

    // in_bubble - 1 inside the bubble, 0 outside
    let in_bubble = smoothstep(1.05, 1f, dot(in.xy, in.xy));

    // calculate colors
    // The small constants are to keep the strings from being similar.
   let flag_hue = fract(INV_PHI * (iy + 0.123) * (flag + 0.456));
    let flag_color = hsv_to_rgb(flag_hue, 1f, 1f);
    let sky_color = hsv_to_rgb(
        0.667,                  // blue
        mix(1f, 0.5, in.texcoord.y), // fade pure blue -> light blue
        1f,
    );

    // In the bubble, darken the sky more than the flags.
    var color: vec3f;
    if in_sky {
        color = mix(sky_color, vec3f(0f), 0.9 * in_bubble);
    } else {
        color = mix(flag_color, vec3f(0f), 0.8 * in_bubble);
    }
    return vec4f(color, 1f);
}


// //  //   //    //     //      //       //        //         //
// Easter Theme

fn easter_background(in: InterStage) -> vec4f {

    let U = uniforms;

    let blend = smoothstep(0.3, 0.7, in.texcoord.x);
    let grass = smoothstep(0.15, 0.1, 1f - in.texcoord.y);
    let in_bubble = smoothstep(1.05, 1f, dot(in.xy, in.xy));


    let grass_hsv = vec3f(0.333, 1f, 0.3);

    var h = mix(0.2, 0.5, blend);
    var s = 0.6;
    var v = 0.7;

    h = mix(h, grass_hsv.r, grass);
    s = mix(s, grass_hsv.g, grass);
    v = mix(v, grass_hsv.b, grass);

    let color = mix(hsv_to_rgb(h, s, v), vec3f(0f), 0.9 * in_bubble);
    return vec4f(color, 1f);
}


// //  //   //    //     //      //       //        //         //
// Bone Theme

fn bone_background(in: InterStage) -> vec4f {
    return vec4f(0f, 0f, 0f, 1f);
    let h = 0.1 + 0.15 * in.texcoord.x;
    let s = 0.4 * in.texcoord.y;
    let v = 0.6 + 0.3 * in.texcoord.y;
    let a = 1f;
    return vec4f(hsv_to_rgb(h, s, v), a);
}


// //  //   //    //     //      //       //        //         //
// Oscilloscope Theme

const OSCOPE_LINE_WIDTH = 0.003;
const OSCOPE_HALF_LINE_WIDTH = OSCOPE_LINE_WIDTH * 0.5;
const OSCOPE_BG_COLOR = vec3f(0.05);
const OSCOPE_LINE_COLOR = vec3f(0.2);
const OSCOPE_VDIV_COUNT: u32 = 10;

fn oscope_in_line(x: f32, line: f32) -> f32 {
    return
        smoothstep(line - OSCOPE_HALF_LINE_WIDTH, line, x) -
        smoothstep(line, line + OSCOPE_HALF_LINE_WIDTH, x);
}

fn oscope_background(in: InterStage) -> vec4f {
    let U = uniforms;
    let r2 = dot(in.xy, in.xy);
    let left_margin: f32 = BORDER * f32(U.viewport_size.x) / 2f;
    let top_margin: f32 = BORDER * f32(U.viewport_size.y) / 2f;
    let right_margin: f32 = (2f - BORDER) * f32(U.viewport_size.x) / 2f;
    let bottom_margin: f32 = (2f - BORDER) * f32(U.viewport_size.y) / 2f;

    var color = OSCOPE_BG_COLOR;

    var marks: f32 = 0f;

    // vline
    let x = in.position.x;
    let y = in.position.y;
    let gcoord = (2f * in.texcoord - 1f) / (1f - BORDER);

    if y >= top_margin && y <= bottom_margin {
        var gx = gcoord.x;
        if abs(gx) < 0.1 {
            gx /= 5f;
        }
        let vline = round(gcoord.x * 5f) / 5f;
        marks = max(marks, oscope_in_line(gx, vline));
    }

    // hline
    if x >= left_margin && x <= right_margin {
        var gy = gcoord.y;
        if abs(gy) < 0.1 {
            gy /= 5f;
        }
        let hline = round(gcoord.y * 4f) / 4f;
        marks = max(marks, oscope_in_line(gy, hline));
    }

    color = mix(OSCOPE_BG_COLOR, OSCOPE_LINE_COLOR, marks);
    return vec4f(color, 1f);
}


// //  //   //    //     //      //       //        //         //
// Noise
//
// This section is under the following license.
//
// psrdnoise (c) 2021 Stefan Gustavson and Ian McEwan
// Published under the MIT license.
// https://github.com/stegu/psrdnoise/

// Say hello to our old friend, the "mod289" function!
// WGSL has no mod(), and "%" is "remainder", not proper modulo.
fn mod289v3f(x: vec3<f32>) -> vec3<f32> {
	return x - floor(x / 289.0) * 289.0;
}

fn psrnoise2(x: vec2<f32>, p: vec2<f32>, alpha: f32) -> f32
{
	var uv: vec2<f32>;
	var f0: vec2<f32>;
	var i0: vec2<f32>;
	var i1: vec2<f32>;
	var i2: vec2<f32>;
	var o1: vec2<f32>;
	var v0: vec2<f32>;
	var v1: vec2<f32>;
	var v2: vec2<f32>;
	var x0: vec2<f32>;
	var x1: vec2<f32>;
	var x2: vec2<f32>;
	
	uv = vec2<f32>(x.x+x.y*0.5, x.y); // So far, so good
	i0 = floor(uv);  // modf() is not a modulo operation!
	f0 = uv - i0;
	o1 = select(vec2<f32>(0.0,1.0), vec2<f32>(1.0, 0.0), f0.x > f0.y);
	i1 = i0 + o1;
	i2 = i0 + vec2<f32>(1.0, 1.0);
	v0 = vec2<f32>(i0.x - i0.y*0.5, i0.y);
	v1 = vec2<f32>(v0.x + o1.x - o1.y*0.5, v0.y + o1.y);
	v2 = vec2<f32>(v0.x + 0.5, v0.y + 1.0);
	x0 = x - v0;
	x1 = x - v1;
	x2 = x - v2;

	var iu: vec3<f32>;
	var iv: vec3<f32>;
	var xw: vec3<f32>;
	var yw: vec3<f32>;

	if(any(p > vec2<f32>(0.0, 0.0)))
	{
		xw = vec3<f32>(v0.x, v1.x, v2.x);
		yw = vec3<f32>(v0.y, v1.y, v2.y);
		if(p.x > 0.0) {
			xw = xw - floor(vec3<f32>(v0.x, v1.x, v2.x) / p.x) * p.x;
		}
		if(p.y > 0.0) {
			yw = yw - floor(vec3<f32>(v0.y, v1.y, v2.y) / p.y) * p.y;
		}
	iu = floor(xw + 0.5*yw + 0.5);
	iv = floor(yw + 0.5);
	} else {
		iu = vec3<f32>(i0.x, i1.x, i2.x);
		iv = vec3<f32>(i0.y, i1.y, i2.y);
	}

	var hash: vec3<f32>;
	var psi: vec3<f32>;
	var gx: vec3<f32>;
	var gy: vec3<f32>;
	var g0: vec2<f32>;
	var g1: vec2<f32>;
	var g2: vec2<f32>;

	hash = mod289v3f(iu);
	hash = mod289v3f((hash*51.0 + 2.0)*hash + iv);
	hash = mod289v3f((hash*34.0 + 10.0)*hash);
	psi = hash*0.07482 + alpha;
	gx = cos(psi);
	gy = sin(psi);
	g0 = vec2<f32>(gx.x, gy.x);
	g1 = vec2<f32>(gx.y, gy.y);
	g2 = vec2<f32>(gx.z, gy.z);

	var w: vec3<f32>;
	var w2: vec3<f32>;
	var w4: vec3<f32>;
	var gdotx: vec3<f32>;
	var n: f32;

	w = 0.8 - vec3<f32>(dot(x0, x0), dot(x1, x1), dot(x2, x2));
	w = max(w, vec3<f32>(0.0, 0.0, 0.0));
	w2 = w*w;
	w4 = w2*w2;
	gdotx = vec3<f32>(dot(g0, x0), dot(g1, x1), dot(g2, x2));
	n = dot(w4, gdotx);

	return 10.9*n;
}

fn srnoise2(x: vec2<f32>, alpha: f32) -> f32
{
	var uv: vec2<f32>;
	var f0: vec2<f32>;
	var i0: vec2<f32>;
	var i1: vec2<f32>;
	var i2: vec2<f32>;
	var o1: vec2<f32>;
	var v0: vec2<f32>;
	var v1: vec2<f32>;
	var v2: vec2<f32>;
	var x0: vec2<f32>;
	var x1: vec2<f32>;
	var x2: vec2<f32>;
	
	uv = vec2<f32>(x.x+x.y*0.5, x.y);
	i0 = floor(uv);
	f0 = uv - i0;
	o1 = select(vec2<f32>(0.0,1.0), vec2<f32>(1.0, 0.0), f0.x > f0.y);
	i1 = i0 + o1;
	i2 = i0 + vec2<f32>(1.0, 1.0);
	v0 = vec2<f32>(i0.x - i0.y*0.5, i0.y);
	v1 = vec2<f32>(v0.x + o1.x - o1.y*0.5, v0.y + o1.y);
	v2 = vec2<f32>(v0.x + 0.5, v0.y + 1.0);
	x0 = x - v0;
	x1 = x - v1;
	x2 = x - v2;

	var iu: vec3<f32>;
	var iv: vec3<f32>;

	iu = vec3<f32>(i0.x, i1.x, i2.x);
	iv = vec3<f32>(i0.y, i1.y, i2.y);

	var hash: vec3<f32>;
	var psi: vec3<f32>;
	var gx: vec3<f32>;
	var gy: vec3<f32>;
	var g0: vec2<f32>;
	var g1: vec2<f32>;
	var g2: vec2<f32>;

	hash = mod289v3f(iu);
	hash = mod289v3f((hash*51.0 + 2.0)*hash + iv);
	hash = mod289v3f((hash*34.0 + 10.0)*hash);
	psi = hash*0.07482 + alpha;
	gx = cos(psi);
	gy = sin(psi);
	g0 = vec2<f32>(gx.x, gy.x);
	g1 = vec2<f32>(gx.y, gy.y);
	g2 = vec2<f32>(gx.z, gy.z);

	var w: vec3<f32>;
	var w2: vec3<f32>;
	var w4: vec3<f32>;
	var gdotx: vec3<f32>;
	var n: f32;

	w = 0.8 - vec3<f32>(dot(x0, x0), dot(x1, x1), dot(x2, x2));
	w = max(w, vec3<f32>(0.0, 0.0, 0.0));
	w2 = w*w;
	w4 = w2*w2;
	gdotx = vec3<f32>(dot(g0, x0), dot(g1, x1), dot(g2, x2));
	n = dot(w4, gdotx);

	return 10.9*n;
}


// //  //   //    //     //      //       //        //         //
// Utilities

fn hsv_to_rgb(h: f32, s: f32, v: f32) -> vec3f {
    if s == 0f {
        return vec3f(v);
    }
    let hm = h - floor(h);
    var i = i32(hm * 6f);
    let f = (hm * 6f) - f32(i);
    let p = v * (1f - s);
    let q = v * (1f - s * f);
    let t = v * (1f - s * (1f - f));
    // i %= 6;
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
    return vec3f(0f);
}
