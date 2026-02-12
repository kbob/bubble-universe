struct Uniforms {
  particle_size: vec2f,
  scale: vec2f,
  seq_count: u32,
  seq_length: u32,
};

@group(0) @binding(0) var<storage, read> uv_buffer: array<vec2f>;
@group(1) @binding(0) var<uniform> uniforms: Uniforms;

struct InterStage {
  @builtin(position) pos: vec4f,
  @location(0) @interpolate(flat) ij: vec2u,
  @location(1) @interpolate(perspective) pt: vec2f,
};

// Vertex Shader
//  - call 6 times per particle; emits a quad.

@vertex fn vertex_shader(
  @builtin(vertex_index) vertex_index : u32
) -> InterStage {

  let U = uniforms;

  let points = array<vec2f, 6>(
      vec2f(-1.0, -1.0),
      vec2f( 1.0, -1.0),
      vec2f(-1.0,  1.0),
      vec2f(-1.0,  1.0),
      vec2f( 1.0, -1.0),
      vec2f( 1.0,  1.0),
  );

  let uv_index = vertex_index / 6u;
  let k = vertex_index % 6u;
  let i = uv_index % U.seq_length;
  let j = uv_index / U.seq_length;
  let ij = vec2u(i, j);
  let uv = uv_buffer[uv_index];
  let pt = points[k];
  let xy = U.scale * uv + U.particle_size * pt;

  var out: InterStage;
  out.pos = vec4f(xy, 0.0, 1.0);
  out.ij = ij;
  out.pt = pt;

  return out;
}

// Fragment Shader
//  - trims particle to a circle, transparent near edges
//  - color is rgb(i, j, 99)

@fragment fn fragment_shader(in: InterStage) -> @location(0) vec4f {

  let U = uniforms;

  let i = in.ij[0];
  let j = in.ij[1];
  let r = f32(j) / f32(U.seq_length) * 200.0 / 255.0;
  let g = f32(i) / f32(U.seq_count) * 200.0 / 255.0;
  let b = 99.0 / 255.0;

  // j is the sequence number,
  // i is the sequence position

  let rad2 = dot(in.pt, in.pt);
  var a = (1.0 - rad2);
  a *= 1 - (U.particle_size[1] * 28);
  if a < 0.01 {
    a = 0.0;
    discard;
  }

  return vec4f(r*a, g*a, b*a, a);
}
