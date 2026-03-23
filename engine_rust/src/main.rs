use bevy::prelude::*;
use bevy::window::PrimaryWindow;
use bevy::render::mesh::{Indices, PrimitiveTopology, Mesh};
use bevy::render::render_asset::RenderAssetUsages;
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use base64::{engine::general_purpose, Engine as _};
use image::GenericImageView;

const GRID_STEP: u32 = 1;

fn main() {
    App::new()
        .add_plugins(DefaultPlugins.set(WindowPlugin {
            primary_window: Some(Window {
                title: "Life Line — Living Painting (Metal GPU)".into(),
                resolution: (1280.0, 900.0).into(),
                ..default()
            }),
            ..default()
        }))
        .add_systems(Startup, setup)
        .add_systems(Update, (mouse_interaction, animate_particles))
        .run();
}

#[derive(Serialize)]
struct EmotionVector { intensity: f32, color_tone: String, flow: String }

#[derive(Deserialize)]
struct VisionResponse { image_base64: String, prompt: String }

/// 單一粒子的 CPU 端資料
struct ParticleData {
    original_pos: Vec3,
    velocity: Vec3,
    color: [f32; 4],
}

/// 持有整個粒子雲的 Resource
#[derive(Resource)]
struct ParticleCloud {
    particles: Vec<ParticleData>,
    mesh_handle: Handle<Mesh>,
}

/// 滑鼠世界座標
#[derive(Resource, Default)]
struct MouseWorld {
    pos: Vec3,
    active: bool,
}


fn setup(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {

    // 相機
    commands.spawn(Camera3dBundle {
        transform: Transform::from_xyz(0.0, 0.0, 110.0).looking_at(Vec3::ZERO, Vec3::Y),
        ..default()
    });

    // 取得 AI 圖片
    println!("🧠 Contacting AI Vision Engine (SDXL + LoRA)...");
    let req = EmotionVector { intensity: 0.8, color_tone: "warm".into(), flow: "chaotic".into() };
    let client = Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .unwrap();

    println!("⏳ Waiting for AI to paint...");
    let res = client.post("http://127.0.0.1:8001/generate_vision")
        .json(&req).send().and_then(|r| r.json::<VisionResponse>());

    let (positions, colors) = match res {
        Ok(resp) => {
            println!("🎨 Received! Engine: {}", resp.prompt);
            if let Ok(bytes) = general_purpose::STANDARD.decode(&resp.image_base64) {
                if let Ok(img) = image::load_from_memory(&bytes) {
                    image_to_points(&img)
                } else { generate_test_points() }
            } else { generate_test_points() }
        }
        Err(_) => {
            println!("⚠️ API not available, using test pattern");
            generate_test_points()
        }
    };

    println!("🚀 Creating single mesh with {} vertices...", positions.len());

    // 建立單一 Mesh — 所有粒子都是這個 mesh 的頂點
    let mut mesh = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default());

    // 每個粒子是一個極小的三角形 (Billboard)
    let particle_size = 0.15;
    let mut all_positions: Vec<[f32; 3]> = Vec::with_capacity(positions.len() * 3);
    let mut all_colors: Vec<[f32; 4]> = Vec::with_capacity(positions.len() * 3);
    let mut all_normals: Vec<[f32; 3]> = Vec::with_capacity(positions.len() * 3);

    for (i, pos) in positions.iter().enumerate() {
        let c = colors[i];
        // 每個粒子 = 1 個三角形（3 頂點）
        all_positions.push([pos[0] - particle_size, pos[1] - particle_size, pos[2]]);
        all_positions.push([pos[0] + particle_size, pos[1] - particle_size, pos[2]]);
        all_positions.push([pos[0], pos[1] + particle_size, pos[2]]);
        all_colors.push(c);
        all_colors.push(c);
        all_colors.push(c);
        all_normals.push([0.0, 0.0, 1.0]);
        all_normals.push([0.0, 0.0, 1.0]);
        all_normals.push([0.0, 0.0, 1.0]);
    }

    mesh.insert_attribute(Mesh::ATTRIBUTE_POSITION, all_positions);
    mesh.insert_attribute(Mesh::ATTRIBUTE_COLOR, all_colors);
    mesh.insert_attribute(Mesh::ATTRIBUTE_NORMAL, all_normals);

    let mesh_handle = meshes.add(mesh);

    // 建立粒子資料
    let particle_data: Vec<ParticleData> = positions.iter().enumerate().map(|(i, p)| {
        ParticleData {
            original_pos: Vec3::new(p[0], p[1], p[2]),
            velocity: Vec3::ZERO,
            color: colors[i],
        }
    }).collect();

    // Spawn 整個粒子雲為「單一 Entity」
    commands.spawn(PbrBundle {
        mesh: mesh_handle.clone(),
        material: materials.add(StandardMaterial {
            unlit: true,
            double_sided: true,
            base_color: Color::WHITE,
            ..default()
        }),
        ..default()
    });

    commands.insert_resource(ParticleCloud {
        particles: particle_data,
        mesh_handle,
    });
    commands.insert_resource(MouseWorld::default());

    println!("✅ Single-mesh particle cloud ready! {} particles, 1 draw call", positions.len());
}

/// 追蹤滑鼠世界座標
fn mouse_interaction(
    mut mouse: ResMut<MouseWorld>,
    q_window: Query<&Window, With<PrimaryWindow>>,
    q_camera: Query<(&Camera, &GlobalTransform)>,
) {
    let Ok(window) = q_window.get_single() else { return };
    let Ok((camera, cam_tf)) = q_camera.get_single() else { return };

    if let Some(cursor) = window.cursor_position() {
        if let Some(ray) = camera.viewport_to_world(cam_tf, cursor) {
            if let Some(d) = ray.intersect_plane(Vec3::ZERO, Plane3d::new(Vec3::Z)) {
                mouse.pos = ray.get_point(d);
                mouse.active = true;
                return;
            }
        }
    }
    mouse.active = false;
}

/// 每幀更新粒子物理 + 回寫 Mesh 頂點
fn animate_particles(
    mut cloud: ResMut<ParticleCloud>,
    mouse: Res<MouseWorld>,
    time: Res<Time>,
    mut meshes: ResMut<Assets<Mesh>>,
) {
    let dt = time.delta_seconds();
    let mouse_pos = mouse.pos;
    let mouse_active = mouse.active;
    let repulsion_radius_sq: f32 = 50.0 * 50.0;
    let particle_size = 0.15;

    let mesh_handle = cloud.mesh_handle.clone();
    let particles = &mut cloud.particles;
    let t = time.elapsed_seconds();

    // 更新物理
    for p in particles.iter_mut() {
        let ox = p.original_pos.x;
        let oy = p.original_pos.y;

        // ====== 流動目標：粒子的歸宿隨時間漂移 ======
        let drift_x = (oy * 0.02 + t * 0.3).sin() * 8.0
                     + (ox * 0.015 + t * 0.2).cos() * 5.0;
        let drift_y = (ox * 0.025 + t * 0.25).cos() * 6.0
                     + (oy * 0.01 + t * 0.35).sin() * 4.0;
        let drift_z = ((ox + oy) * 0.01 + t * 0.4).sin() * 3.0;

        let target = Vec3::new(
            ox + drift_x,
            oy + drift_y,
            p.original_pos.z + drift_z,
        );

        // 向漂移目標的柔和拉力
        let to_target = target - (p.original_pos + p.velocity * dt);
        p.velocity += to_target * 2.0 * dt;

        // ====== 滑鼠排斥力 ======
        if mouse_active {
            let cur_x = p.original_pos.x + p.velocity.x * dt;
            let cur_y = p.original_pos.y + p.velocity.y * dt;
            let dx = cur_x - mouse_pos.x;
            let dy = cur_y - mouse_pos.y;
            let dist_sq = dx * dx + dy * dy;
            if dist_sq < repulsion_radius_sq && dist_sq > 0.0001 {
                let dist = dist_sq.sqrt();
                let force = (50.0 - dist) / 50.0;
                let inv = 1.0 / dist;
                p.velocity.x += dx * inv * force * 2000.0 * dt;
                p.velocity.y += dy * inv * force * 2000.0 * dt;
                p.velocity.z += force * 800.0 * dt;
            }
        }

        p.velocity *= 0.96;
    }

    // 回寫到 Mesh 頂點 Buffer
    if let Some(mesh) = meshes.get_mut(&mesh_handle) {
        let mut new_positions: Vec<[f32; 3]> = Vec::with_capacity(particles.len() * 3);

        for p in particles.iter() {
            let x = p.original_pos.x + p.velocity.x * dt;
            let y = p.original_pos.y + p.velocity.y * dt;
            let z = p.original_pos.z + p.velocity.z * dt;

            new_positions.push([x - particle_size, y - particle_size, z]);
            new_positions.push([x + particle_size, y - particle_size, z]);
            new_positions.push([x, y + particle_size, z]);
        }

        mesh.insert_attribute(Mesh::ATTRIBUTE_POSITION, new_positions);
    }
}

/// 將 AI 圖片轉換為頂點陣列
fn image_to_points(img: &image::DynamicImage) -> (Vec<[f32; 3]>, Vec<[f32; 4]>) {
    let (w, h) = img.dimensions();
    let xo = w as f32 / 2.0;
    let yo = h as f32 / 2.0;
    let scale = 0.12;
    let mut positions = Vec::new();
    let mut colors = Vec::new();

    for y in (0..h).step_by(GRID_STEP as usize) {
        for x in (0..w).step_by(GRID_STEP as usize) {
            let px = img.get_pixel(x, y);
            if px[0] < 30 && px[1] < 30 && px[2] < 30 { continue; }

            let r = px[0] as f32 / 255.0;
            let g = px[1] as f32 / 255.0;
            let b = px[2] as f32 / 255.0;
            let z = (px[0] as f32 - 128.0) * 0.05;

            positions.push([(x as f32 - xo) * scale, -(y as f32 - yo) * scale, z]);
            colors.push([r, g, b, 1.0]);
        }
    }
    (positions, colors)
}

/// 備用測試圖案
fn generate_test_points() -> (Vec<[f32; 3]>, Vec<[f32; 4]>) {
    let mut positions = Vec::new();
    let mut colors = Vec::new();
    for y in -50..50 {
        for x in -60..60 {
            let r = (x + 60) as f32 / 120.0;
            let g = (y + 50) as f32 / 100.0;
            positions.push([x as f32 * 0.5, y as f32 * 0.5, 0.0]);
            colors.push([r, g, 0.5, 1.0]);
        }
    }
    (positions, colors)
}

#[cfg(test)]
mod tests {
    use super::*;
    use image::{RgbaImage, DynamicImage};
    use serde_json::json;

    #[test]
    fn test_emotion_vector_serialization() {
        let ev = EmotionVector {
            intensity: 0.8,
            color_tone: "warm".to_string(),
            flow: "chaotic".to_string(),
        };
        let j = serde_json::to_string(&ev).unwrap();
        assert!(j.contains(r#""intensity":0.8"#));
        assert!(j.contains(r#""color_tone":"warm""#));
        assert!(j.contains(r#""flow":"chaotic""#));
    }

    #[test]
    fn test_vision_response_deserialization() {
        let j = json!({
            "image_base64": "SGVsbG8=",
            "prompt": "Test Prompt"
        });
        let vr: VisionResponse = serde_json::from_value(j).unwrap();
        assert_eq!(vr.image_base64, "SGVsbG8=");
        assert_eq!(vr.prompt, "Test Prompt");
    }

    #[test]
    fn test_generate_test_points() {
        let (positions, colors) = generate_test_points();
        // 100 * 120 = 12000 點
        assert_eq!(positions.len(), 12000);
        assert_eq!(colors.len(), 12000);
        
        // 確保範圍與顏色格式正確
        let first_pos = positions[0];
        assert!(first_pos[0] >= -30.0 && first_pos[0] <= 30.0); // 因為 x 範圍是 -60 到 60，乘以 0.5
        
        let first_color = colors[0];
        assert!(first_color[3] == 1.0); // Alpha 應該為 1.0
    }

    #[test]
    fn test_image_to_points_black_ignored() {
        // 建立 4x4 的全黑影像
        let img = RgbaImage::new(4, 4);
        let dynamic_img = DynamicImage::ImageRgba8(img);
        
        let (pos, _colors) = image_to_points(&dynamic_img);
        // 全黑點應該被忽略
        assert_eq!(pos.len(), 0);
    }

    #[test]
    fn test_image_to_points_colors_parsed() {
        // 建立包含色彩的影像
        let mut img = RgbaImage::new(2, 2);
        img.put_pixel(0, 0, image::Rgba([255, 128, 64, 255]));
        img.put_pixel(1, 1, image::Rgba([10, 10, 10, 255])); // 黑點應忽略（<30）
        
        let dynamic_img = DynamicImage::ImageRgba8(img);
        let (pos, colors) = image_to_points(&dynamic_img);
        
        assert_eq!(pos.len(), 1); // 只有一個非黑點
        assert_eq!(colors.len(), 1);
        
        // 檢查顏色正規化 (R: 255/255=1.0, G: 128/255=0.5, B: 64/255=0.25)
        let c = colors[0];
        assert!((c[0] - 1.0).abs() < 0.01);
        assert!((c[1] - 0.501).abs() < 0.01); // 128/255 ≒ 0.5019
        assert!((c[2] - 0.25).abs() < 0.01); // 64/255 ≒ 0.2509
        assert_eq!(c[3], 1.0);
    }
}
