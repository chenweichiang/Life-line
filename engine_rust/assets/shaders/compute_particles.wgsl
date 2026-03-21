struct Particle {
    pos: vec3<f32>,
    vel: vec3<f32>,
    color: vec4<f32>,
    target_pos: vec3<f32>, // 從 AI 影像取得的目標還原位置
    target_color: vec4<f32>, // 從 AI 影像取得的目標顏色
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

    // 1. 滑鼠排斥力 (Mouse Repulsion)
    if (params.mouse_active == 1u) {
        let dir = p.pos - params.mouse_pos;
        let dist = length(dir);
        if (dist < params.repulsion_radius && dist > 0.01) {
            let force = (params.repulsion_radius - dist) / params.repulsion_radius;
            // 距離越近，排斥力越強
            p.vel += normalize(dir) * force * params.repulsion_force * params.delta_time;
        }
    }

    // 2. 復原力 (Recovery back to actual image structure)
    let to_target = p.target_pos - p.pos;
    let dist_to_target = length(to_target);
    if (dist_to_target > 0.0) {
        // 向目標位置的拉力，讓被推開的粒子會慢慢彈回原本的形狀
        p.vel += to_target * params.recovery_force * params.delta_time;
    }

    // 3. 阻力與速度更新
    p.vel *= 0.95; // 阻尼 Damping
    p.pos += p.vel * params.delta_time;

    // 4. 更新顏色 (漸變至新的目標顏色)
    p.color = mix(p.color, p.target_color, 2.0 * params.delta_time);

    // 寫回 Buffer
    particles[index] = p;
}
