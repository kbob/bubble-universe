// Particle Motion Shader

// For the coefficients alpha, see
// "The Unreasonable Efectiveness of Quasirandom Sequences"
// https://extremelearning.com.au/unreasonable-effectiveness-of-quasirandom-sequences/

struct Uniforms {
    seq_count: u32,
    seq_length: u32,
    s_blocks: u32,
    r: f32,                     // magic number
    s: f32,                     // more magic number
    t: f32,                     // time
};

@group(0) @binding(0) var<storage, read_write> uvs: array<vec2f>;
@group(1) @binding(0) var<uniform> uniforms: Uniforms;

@compute @workgroup_size(64)
fn compute_shader(@builtin(global_invocation_id) id: vec3u) {

  // rectangular_grid(id);
  // return;

  let U = uniforms;

  let i = id.x;
  if i < U.seq_count {
    let fi = f32(i);
    let b_size = U.seq_count / U.s_blocks;
    let r = U.r * U.s;
    let s = U.s + f32(i / b_size * b_size);
    var u: f32 = 0f;
    var v: f32 = 0f;
    var x: f32 = 0f;

    let tau = 6.283185307179586;
    let alpha = vec2f(0.7548776662466927, 0.5698402909980532);

    // Start each sequence at a quasirandom position.
    let init = (U.t / tau + alpha * U.s * fi) % 1f;
    let rad = 2f * sqrt(init[0]);
    let theta = tau * init[1];

    u = rad * sin(theta);
    v = rad * cos(theta);
    x = u + U.t;
    u = sin(s * fi + v) + sin(r * fi + x);
    v = cos(s * fi + v) + cos(r * fi + x);
    x = u + U.t;

    uvs[i * U.seq_length] = vec2f(u, -v);
    for (var j = 1u; j < U.seq_length; j++) {

      u = sin(s * fi + v) + sin(r * fi + x);
      v = cos(s * fi + v) + cos(r * fi + x);
      x = u + U.t;
      uvs[i * U.seq_length + j] = vec2f(u, -v);
    }
  }
}

fn rectangular_grid(id: vec3u) {

  let U = uniforms;

  let i: u32 = id.x;
  let fi: f32 = f32(i);
  let u: f32 = fi / f32(U.seq_count - 1) * 4f - 2f;
  if i < U.seq_count {
    for (var j = 0u; j < U.seq_length; j++) {
      let v: f32 = f32(j) / f32(U.seq_length - 1) * 4f - 2f;
      uvs[i * U.seq_length + j] = vec2f(u, v);
    }
  }
}
