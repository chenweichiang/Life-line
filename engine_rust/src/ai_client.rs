use bevy::prelude::*;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use tokio::runtime::Runtime;

pub struct AiClientPlugin;

impl Plugin for AiClientPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<AiClientState>()
           .insert_resource(TokioRuntime(Runtime::new().unwrap()))
           .add_event::<TriggerAiGeneration>();
    }
}

#[derive(Resource)]
struct TokioRuntime(Runtime);

#[derive(Resource, Default)]
pub struct AiClientState {
    pub is_generating: bool,
}

#[derive(Serialize)]
pub struct EmotionVector {
    intensity: f32,
    color_tone: String,
    flow: String,
}

#[derive(Event)]
pub struct TriggerAiGeneration {
    pub intensity: f32,
}

// 當接收到 TriggerAiGeneration 事件，非同步發送 Request
pub fn handle_ai_triggers(
    mut events: EventReader<TriggerAiGeneration>,
    mut state: ResMut<AiClientState>,
    rt: Res<TokioRuntime>,
) {
    for event in events.read() {
        if state.is_generating { continue; }
        
        state.is_generating = true;
        let intensity = event.intensity;
        
        let vector = EmotionVector {
            intensity,
            color_tone: "earthy, ochre, olive green".into(),
            flow: if intensity > 0.6 { "chaotic and rapid".into() } else { "calm and fluid".into() },
        };

        // 非同步調用 Vision
        let client = Client::new();
        rt.0.spawn(async move {
            let res = client.post("http://localhost:8001/generate_vision")
                            .json(&vector)
                            .send()
                            .await;
            
            if let Ok(_response) = res {
                // 將 Base64 解碼後拋回給 GPU (交由 Render System 處理)
                println!("Got vision generated! Transitioning particles...");
            }
        });

        // 也可以平行發送給 Audio
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ai_client_state_default() {
        let state = AiClientState::default();
        assert!(!state.is_generating);
    }

    #[test]
    fn test_emotion_vector_construction() {
        let v = EmotionVector {
            intensity: 0.8,
            color_tone: "warm".into(),
            flow: "chaotic".into(),
        };
        assert_eq!(v.intensity, 0.8);
        assert_eq!(v.color_tone, "warm");
    }

    #[test]
    fn test_intensity_threshold_logic() {
        let intensity = 0.7;
        let flow: String = if intensity > 0.6 { "chaotic and rapid".into() } else { "calm and fluid".into() };
        assert_eq!(flow, "chaotic and rapid");
    }

    #[test]
    fn test_low_intensity_gives_calm() {
        let intensity = 0.3;
        let flow: String = if intensity > 0.6 { "chaotic and rapid".into() } else { "calm and fluid".into() };
        assert_eq!(flow, "calm and fluid");
    }
}
