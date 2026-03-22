// Life Line — GPU Render Shader (Instanced Billboard 粒子)
// 每個粒子以 instance_index 從 Storage Buffer 讀取位置與顏色
// 使用 6 個頂點展開成 Billboard Quad

struct Particle {
    pos: vec3<f32>,
    _pad1: f32,
    vel: vec3<f32>,
    _pad2: f32,
    color: vec4<f32>,
    target_pos: vec3<f32>,
    _pad3: f32,
    target_color: vec4<f32>,
};

struct CameraUniform {
    view_proj: mat4x4<f32>,
};

@group(0) @binding(0) var<storage, read> particles: array<Particle>;
@group(1) @binding(0) var<uniform> camera: CameraUniform;

struct VertexOutput {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) color: vec4<f32>,
    @location(1) uv: vec2<f32>,
};

@vertex
fn vs_main(
    @builtin(vertex_index) vertex_index: u32,
    @builtin(instance_index) instance_index: u32,
) -> VertexOutput {
    var out: VertexOutput;
    let p = particles[instance_index];

    // Billboard Quad: 2 個三角形 = 6 個頂點
    var offsets = array<vec2<f32>, 6>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>( 1.0, -1.0),
        vec2<f32>(-1.0,  1.0),
        vec2<f32>(-1.0,  1.0),
        vec2<f32>( 1.0, -1.0),
        vec2<f32>( 1.0,  1.0),
    );
    let offset = offsets[vertex_index];
    let size = 0.15; // 粒子大小

    let world_pos = vec4<f32>(
        p.pos.x + offset.x * size,
        p.pos.y + offset.y * size,
        p.pos.z,
        1.0
    );

    out.clip_position = camera.view_proj * world_pos;
    out.color = p.color;
    out.uv = offset * 0.5 + 0.5;

    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    // 圓形粒子遮罩 + 柔和邊緣
    let coord = in.uv * 2.0 - 1.0;
    let dist_sq = dot(coord, coord);
    if (dist_sq > 1.0) { discard; }

    // 柔和的圓形發光效果
    let alpha = 1.0 - dist_sq * 0.5;
    return vec4<f32>(in.color.rgb * alpha, in.color.a * alpha);
}
