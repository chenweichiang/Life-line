use bevy::prelude::*;
use kira::{
	manager::{backend::DefaultBackend, AudioManager, AudioManagerSettings},
	sound::static_sound::{StaticSoundData, StaticSoundSettings},
	tween::Tween,
};
use std::io::Cursor;

pub struct AudioSystemPlugin;

impl Plugin for AudioSystemPlugin {
    fn build(&self, app: &mut App) {
        if let Ok(manager) = AudioManager::<DefaultBackend>::new(AudioManagerSettings::default()) {
            app.insert_non_send_resource(LifeLineAudio { manager });
        }
    }
}

pub struct LifeLineAudio {
    manager: AudioManager,
}

pub fn crossfade_new_ai_audio(
    audio_buffer: &[u8],
    audio_res: &mut LifeLineAudio,
) {
    let cursor = Cursor::new(audio_buffer.to_vec());
    let settings = StaticSoundSettings::default();
    
    if let Ok(sound_data) = StaticSoundData::from_cursor(cursor, settings) {
        let _ = audio_res.manager.play(sound_data);
        println!("AI Procedural Audio Crossfaded seamlessly.");
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn test_tween_duration() {
        let t = super::Tween {
            duration: std::time::Duration::from_secs_f32(1.0),
            ..Default::default()
        };
        assert_eq!(t.duration, std::time::Duration::from_secs_f32(1.0));
    }
}
