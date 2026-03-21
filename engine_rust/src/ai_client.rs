use bevy::prelude::*;

// 發送「情緒向量」給 Python 容器的通訊模組 (Reqwest 非同步客戶端)
pub struct AiClientPlugin;

impl Plugin for AiClientPlugin {
    fn build(&self, app: &mut App) {
        // TODO: 加入發送 HTTP API 的請求列隊系統
    }
}

pub fn trigger_ai_generation(intensity: f32, color_tone: &str, flow: &str) {
    // TODO: 發送 HTTP POST 給 localhost:8001 (Vision API)
    // TODO: 發送 HTTP POST 給 localhost:8002 (Audio API)
    // TODO: 接收 Base64 圖像與 Wav 音檔緩衝
}
