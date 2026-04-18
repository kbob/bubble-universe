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
