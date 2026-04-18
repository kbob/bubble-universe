// Particle Motion Shader

// For the coefficients alpha, see
// "The Unreasonable Efectiveness of Quasirandom Sequences"
// https://extremelearning.com.au/unreasonable-effectiveness-of-quasirandom-sequences/

struct Uniforms {
    seq_count: u32,
    seq_length: u32,
    t: f32,                     // time
    r: f32,                     // magic number
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
    var u: f32 = 0f;
    var v: f32 = 0f;
    var x: f32 = 0f;

    let tau = 6.283185307179586;
    let alpha = vec2f(0.7548776662466927, 0.5698402909980532);

    // Start each sequence at a quasirandom position.
    let init = (U.t / tau + alpha * fi) % 1f;
    let r = 2f * sqrt(init[0]);
    let theta = tau * init[1];

    u = r * sin(theta);
    v = r * cos(theta);
    x = u + U.t;
    u = sin(fi + v) + sin(U.r * fi + x);
    v = cos(fi + v) + cos(U.r * fi + x);
    x = u + U.t;

    uvs[i * U.seq_length] = vec2f(u, -v);
    for (var j = 1u; j < U.seq_length; j++) {

      u = sin(fi + v) + sin(U.r * fi + x);
      v = cos(fi + v) + cos(U.r * fi + x);
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
