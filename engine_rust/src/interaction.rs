use bevy::prelude::*;
use bevy::window::PrimaryWindow;
use bevy::render::camera::RenderTarget;

pub struct InteractionPlugin;

impl Plugin for InteractionPlugin {
    fn build(&self, app: &mut App) {
        app.insert_resource(MouseWorldState::default())
           .add_systems(Update, update_mouse_world_position);
    }
}

// 供 Compute Shader 讀取的滑鼠資源
#[derive(Resource, Default, Debug)]
pub struct MouseWorldState {
    pub position: Vec3,
    pub active: u32,
    pub intensity: f32, // 計算滑鼠移動的劇烈程度
    last_position: Vec3,
}

fn update_mouse_world_position(
    q_window: Query<&Window, With<PrimaryWindow>>,
    q_camera: Query<(&Camera, &GlobalTransform)>,
    mut state: ResMut<MouseWorldState>,
    time: Res<Time>,
) {
    let Ok(window) = q_window.get_single() else { return };
    let Ok((camera, camera_transform)) = q_camera.get_single() else { return };

    if let Some(cursor_pos) = window.cursor_position() {
        // 將螢幕 2D 座標轉換為世界 3D 座標 (假設 Z 平面在 0)
        if let Some(ray) = camera.viewport_to_world(camera_transform, cursor_pos) {
            let distance = ray.intersect_plane(Vec3::ZERO, Plane3d::new(Vec3::Z));
            if let Some(dist) = distance {
                let world_pos = ray.get_point(dist);
                state.active = 1;
                
                // 計算強度 (速度)
                let velocity = (world_pos - state.last_position).length() / time.delta_seconds();
                state.intensity = velocity.clamp(0.0, 50.0);
                
                state.last_position = world_pos;
                state.position = world_pos;
                return;
            }
        }
    }
    state.active = 0;
    state.intensity *= 0.9; // 滑鼠離開時急遽降溫
}
