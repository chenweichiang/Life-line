use bevy::{
    prelude::*,
    render::{
        compute_pipeline::{ComputePipeline, ComputePipelineDescriptor},
        render_resource::*,
        renderer::{RenderDevice, RenderQueue},
        RenderApp, RenderSet,
    },
};
use bytemuck::{Pod, Zeroable};

pub struct RenderSystemPlugin;

impl Plugin for RenderSystemPlugin {
    fn build(&self, app: &mut App) {
        // 因架構龐大，此處先初始化核心資源的佔位
        // TODO: 在 RenderApp 中註冊 Compute 節點
        // let render_app = app.sub_app_mut(RenderApp);
        // render_app.add_systems(Render, queue_bind_groups.in_set(RenderSet::Queue));
    }
}

pub const MAX_PARTICLES: usize = 1_000_000;

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
pub struct Particle {
    pos: [f32; 3],  _pad1: f32,
    vel: [f32; 3],  _pad2: f32,
    color: [f32; 4],
    target_pos: [f32; 3], _pad3: f32,
    target_color: [f32; 4],
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
pub struct SimParams {
    mouse_pos: [f32; 3],
    delta_time: f32,
    mouse_active: u32,
    repulsion_radius: f32,
    repulsion_force: f32,
    recovery_force: f32,
}

// TODO: 將解析好的 Base64 AI 圖像載入成 Bevy Texture
pub fn apply_new_ai_texture() {
    // 將新圖片的像素顏色與座標，寫入 GPU 中粒子的 `target_color` 與 `target_pos`
    // GPU 下一幀就會自動計算力的漸變 (Morphing)
    println!("Applying new AI texture to particle target buffers...");
}
