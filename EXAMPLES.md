# Examples

Things that would be good to visualize

R = 0.5 +/- 0.01

Single sequence

Single particle per sequence

# Glowing Sheets Thing

    At start:
    r = 1.0

    At frame 180:
    fade colormap to Fiesta
    particle_size = 1
    trail_persistence = 0.9
    bloom_amount = 0.07

# Nonuniform I Values

Group particle sequences into clusters.  In particles.wgsl, change this.
Vary `k1` and `k2` as desired.

    -    let fi = f32(i);
    +    ket k1 = 0.005;
    +    let k2 = 40f;
    +    let fi = f32(i) * k1 + floor(f32(i) / k2);

# Smokerings thing

 - theme bone
 - seq count: 20
 - seq length 10
 - trail persistence 0.99 - 0.992
 - trail diffusion 1.0

 Also: this one has more "turbulence"

  - theme: bone
  - seq_count: 8
  - seq_length: 20
  - particle size: 2
  - trail persistence: 0.99
  - trail diffusion: 1

# Colored Smoke

    bubbler.update_parameters(
        theme=Theme.TRIAD,
        seq_count=24,
        seq_length=80,
        speed=0.9,
        particle_size=4,
        trail_persistence=0.995,
        trail_diffusion=1.0,
    )

# Fine detail thing

### parameters

  - seq_count = 25 * 120  # 3000
  - seq_length = 100
  - speed = 0.8
  - particle_size = 0.707
  - trail_persistence = 0.8
  - trail_diffusion = 0
  - theme = Triad

        bubbler.update_parameters(
            seq_count=3000,
            speed=0.080,
            s=0.004,
            s_blocks=120,

            theme=Theme.TRIAD,
            particle_size=0.7,
            trail_persistence=0.80,
        )
      
### `colors.wgsl`

  - HUE_SPREAD = 0.2

### `particles.wgsl`

  - `let fi = 0.004 * f32(i) + 1 * floor(f32(i / 25));`

# Another triad moiré variant

  - seq_count = 400
  - speed = TAU / 25
  - particle_size = 1
  - trail_persistence = 0.97

##### `colors.wgsl`

  - HUE_SPREAD = 0.2

##### `particles.wgsl`

  - `let fi = 0.004 * f32(i) + 0 * floor(f32(i / 40));`

# Another another...

This is [&#x1F9F5;32](https://makertube.net/w/nHS1HyY1gGMCvDdGMzX8x8).

 - theme = triad (Classic, midnight, and oscilloscope look good, too.)
 - seq_count = 400
 - speed = TAU / 24
 - particle_size = 1
 - trail_persistence = 0.97

##### `colors.wgsl`

  - HUE_SPREAD = 0.2

##### `particles.wgsl`

  - `let fi = 0.004 * f32(i);`

        bubbler.update_parameters(
            seq_count=400,
            speed=0.251,
            s=0.004,

            theme=Theme.TRIAD,
            particle_size=1.0,
            trail_persistence=0.97,
        )
