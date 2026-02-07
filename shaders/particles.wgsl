// parameters
//  m, n, t, r
//  output buffer
//  uv: array<vec2f, m * n>;

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

  let U = uniforms;

  let i = id.x;
  if i < U.seq_count {
    let fi = f32(i);
    var u: f32 = 0.0;
    var v: f32 = 0.0;
    var x: f32 = 0.0;

    uvs[i * U.seq_length] = vec2f(u, v);
    for (var j = 1u; j < U.seq_length; j++) {

      u = sin(fi + v) + sin(U.r * fi + x);
      v = cos(fi + v) + cos(U.r * fi + x);
      x = u + U.t;
      uvs[i * U.seq_length + j] = vec2f(u, -v);
    }
  }
}
