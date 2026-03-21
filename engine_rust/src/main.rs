use bevy::prelude::*;

mod interaction;
mod ai_client;
mod audio_system;
mod render_system;

fn main() {
    println!("啟動 Life Line 3D Engine...");
    App::new()
        .add_plugins(DefaultPlugins)
        .add_plugins((
            interaction::InteractionPlugin,
            ai_client::AiClientPlugin,
            audio_system::AudioSystemPlugin,
            render_system::RenderSystemPlugin,
        ))
        .add_systems(Startup, setup)
        .run();
}

fn setup(mut commands: Commands) {
    // 初始化攝影機
    commands.spawn(Camera3dBundle {
        transform: Transform::from_xyz(0.0, 0.0, 5.0).looking_at(Vec3::ZERO, Vec3::Y),
        ..default()
    });
}
