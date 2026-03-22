// Life Line — GPU Compute Shader (100 萬粒子物理模擬)
// 每個 workgroup 處理 64 個粒子

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

struct SimParams {
    mouse_pos: vec3<f32>,
    delta_time: f32,
    mouse_active: u32,
    repulsion_radius: f32,
    repulsion_force: f32,
    recovery_force: f32,
};

@group(0) @binding(0) var<storage, read_write> particles: array<Particle>;
@group(0) @binding(1) var<uniform> params: SimParams;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) global_id: vec3<u32>) {
    let index = global_id.x;
    if (index >= arrayLength(&particles)) {
        return;
    }

    var p = particles[index];

    // 1. 滑鼠排斥力
    if (params.mouse_active == 1u) {
        let dx = p.pos.x - params.mouse_pos.x;
        let dy = p.pos.y - params.mouse_pos.y;
        let dist_sq = dx * dx + dy * dy;
        let radius_sq = params.repulsion_radius * params.repulsion_radius;

        if (dist_sq < radius_sq && dist_sq > 0.0001) {
            let dist = sqrt(dist_sq);
            let force = (params.repulsion_radius - dist) / params.repulsion_radius;
            let inv_dist = 1.0 / dist;
            p.vel.x += dx * inv_dist * force * params.repulsion_force * params.delta_time;
            p.vel.y += dy * inv_dist * force * params.repulsion_force * params.delta_time;
            p.vel.z += force * 80.0 * params.delta_time;
        }
    }

    // 2. 復原力
    let to_target = p.target_pos - p.pos;
    let dist_sq_target = dot(to_target, to_target);
    if (dist_sq_target > 0.01) {
        p.vel += to_target * params.recovery_force * params.delta_time;
    }

    // 3. 阻尼 + 位移
    p.vel *= 0.92;
    p.pos += p.vel * params.delta_time;

    // 4. 顏色漸變
    p.color = mix(p.color, p.target_color, 2.0 * params.delta_time);

    particles[index] = p;
}
