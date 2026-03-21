// Vertex shader
struct Particle {
    pos: vec3<f32>,
    vel: vec3<f32>,
    color: vec4<f32>,
    target_pos: vec3<f32>,
    target_color: vec4<f32>,
};

@group(0) @binding(0) var<storage, read> particles: array<Particle>;

struct VertexOutput {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) color: vec4<f32>,
};

struct CameraUniform {
    view_proj: mat4x4<f32>,
};
@group(1) @binding(0) var<uniform> camera: CameraUniform;

@vertex
fn vs_main(
    @builtin(vertex_index) vertex_index: u32,
    @builtin(instance_index) instance_index: u32,
) -> VertexOutput {
    var out: VertexOutput;
    
    let p = particles[instance_index];
    
    // 簡單的 Billboard 粒子展開 (這裡簡化為點，實際可展開成 Quad)
    // 假設我們渲染 Point Topology
    let world_pos = vec4<f32>(p.pos, 1.0);
    out.clip_position = camera.view_proj * world_pos;
    
    // 發光效果：顏色的 Alpha 可以用來控制 Glow
    out.color = p.color;
    
    return out;
}

// Fragment shader
@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    // 圓形粒子遮罩
    // let coord = in.uv * 2.0 - 1.0;
    // if dot(coord, coord) > 1.0 { discard; }
    
    return in.color;
}
