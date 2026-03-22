use bevy::{
    prelude::*,
    render::{
        extract_resource::{ExtractResource, ExtractResourcePlugin},
        render_graph::{Node, NodeRunError, RenderGraphContext, RenderLabel, RenderGraph},
        render_resource::*,
        renderer::{RenderContext, RenderDevice},
        Render, RenderApp, RenderSet,
    },
};
use bytemuck::{Pod, Zeroable};
use std::borrow::Cow;

pub const MAX_PARTICLES: usize = 1_000_000;

// =========================================================
// GPU 資料結構（必須與 WGSL struct 完全對齊）
// =========================================================

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
pub struct Particle {
    pub pos: [f32; 3],      pub _pad1: f32,
    pub vel: [f32; 3],      pub _pad2: f32,
    pub color: [f32; 4],
    pub target_pos: [f32; 3], pub _pad3: f32,
    pub target_color: [f32; 4],
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable, Resource, ExtractResource)]
pub struct SimParams {
    pub mouse_pos: [f32; 3],
    pub delta_time: f32,
    pub mouse_active: u32,
    pub repulsion_radius: f32,
    pub repulsion_force: f32,
    pub recovery_force: f32,
}

impl Default for SimParams {
    fn default() -> Self {
        Self {
            mouse_pos: [0.0; 3],
            delta_time: 0.016,
            mouse_active: 0,
            repulsion_radius: 15.0,
            repulsion_force: 50.0,
            recovery_force: 2.0,
        }
    }
}

// =========================================================
// 粒子 Buffer（MainWorld → RenderWorld 用 Extract）
// =========================================================

#[derive(Resource)]
pub struct GpuParticleBuffers {
    pub storage_buffer: Buffer,
    pub particle_count: u32,
}

/// CPU 端的初始粒子資料（在 main.rs 中設定，透過 Extract 傳給 RenderApp）
#[derive(Resource, Clone, ExtractResource)]
pub struct InitialParticleData {
    pub particles: Vec<Particle>,
}

// =========================================================
// Plugin
// =========================================================

pub struct GpuParticlePlugin;

impl Plugin for GpuParticlePlugin {
    fn build(&self, app: &mut App) {
        app.add_plugins(ExtractResourcePlugin::<SimParams>::default())
           .add_plugins(ExtractResourcePlugin::<InitialParticleData>::default())
           .init_resource::<SimParams>();
    }

    fn finish(&self, app: &mut App) {
        let Ok(render_app) = app.get_sub_app_mut(RenderApp) else { return };
        render_app
            .init_resource::<ParticlePipeline>()
            .add_systems(Render, prepare_bind_group.in_set(RenderSet::Prepare));

        let mut graph = render_app.world.resource_mut::<RenderGraph>();
        graph.add_node(ParticleComputeLabel, ParticleComputeNode::default());
    }
}

// =========================================================
// Compute Pipeline
// =========================================================

#[derive(Debug, Hash, PartialEq, Eq, Clone, RenderLabel)]
pub struct ParticleComputeLabel;

#[derive(Resource)]
pub struct ParticlePipeline {
    pub compute_pipeline_id: CachedComputePipelineId,
    pub bind_group_layout: BindGroupLayout,
}

impl FromWorld for ParticlePipeline {
    fn from_world(world: &mut World) -> Self {
        let render_device = world.resource::<RenderDevice>();

        let bind_group_layout = render_device.create_bind_group_layout(
            "particle_bind_group_layout",
            &[
                // @binding(0) — particle storage buffer (read_write)
                BindGroupLayoutEntry {
                    binding: 0,
                    visibility: ShaderStages::COMPUTE,
                    ty: BindingType::Buffer {
                        ty: BufferBindingType::Storage { read_only: false },
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                // @binding(1) — SimParams uniform
                BindGroupLayoutEntry {
                    binding: 1,
                    visibility: ShaderStages::COMPUTE,
                    ty: BindingType::Buffer {
                        ty: BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
            ],
        );

        let shader = world.resource::<AssetServer>().load("shaders/compute_particles.wgsl");
        let pipeline_cache = world.resource::<PipelineCache>();

        let compute_pipeline_id = pipeline_cache.queue_compute_pipeline(ComputePipelineDescriptor {
            label: Some(Cow::from("particle_compute_pipeline")),
            layout: vec![bind_group_layout.clone()],
            shader,
            shader_defs: vec![],
            entry_point: Cow::from("main"),
            push_constant_ranges: vec![],
        });

        Self { compute_pipeline_id, bind_group_layout }
    }
}

// =========================================================
// Bind Group 每幀準備
// =========================================================

#[derive(Resource)]
pub struct ParticleBindGroup {
    pub bind_group: BindGroup,
    pub particle_count: u32,
}

fn prepare_bind_group(
    mut commands: Commands,
    pipeline: Res<ParticlePipeline>,
    render_device: Res<RenderDevice>,
    sim_params: Res<SimParams>,
    initial_data: Option<Res<InitialParticleData>>,
    existing_buffers: Option<Res<GpuParticleBuffers>>,
) {
    // 如果 GPU buffer 還不存在且有初始資料，就建立它
    if existing_buffers.is_none() {
        let Some(data) = initial_data else { return };
        let count = data.particles.len() as u32;

        let storage_buffer = render_device.create_buffer_with_data(&BufferInitDescriptor {
            label: Some("particle_storage_buffer"),
            contents: bytemuck::cast_slice(&data.particles),
            usage: BufferUsages::STORAGE | BufferUsages::COPY_DST,
        });

        commands.insert_resource(GpuParticleBuffers {
            storage_buffer,
            particle_count: count,
        });
        println!("🎮 GPU Buffer created: {} particles uploaded to Metal", count);
    }

    let Some(buffers) = existing_buffers.or_else(|| None) else { return };

    // 每幀更新 SimParams uniform
    let uniform_buffer = render_device.create_buffer_with_data(&BufferInitDescriptor {
        label: Some("sim_params_uniform"),
        contents: bytemuck::cast_slice(&[*sim_params]),
        usage: BufferUsages::UNIFORM | BufferUsages::COPY_DST,
    });

    let bind_group = render_device.create_bind_group(
        "particle_bind_group",
        &pipeline.bind_group_layout,
        &BindGroupEntries::sequential((
            buffers.storage_buffer.as_entire_binding(),
            uniform_buffer.as_entire_binding(),
        )),
    );

    commands.insert_resource(ParticleBindGroup {
        bind_group,
        particle_count: buffers.particle_count,
    });
}

// =========================================================
// Compute Node（每幀在 GPU 上運行物理模擬）
// =========================================================

#[derive(Default)]
pub struct ParticleComputeNode;

impl Node for ParticleComputeNode {
    fn run(
        &self,
        _graph: &mut RenderGraphContext,
        render_context: &mut RenderContext,
        world: &World,
    ) -> Result<(), NodeRunError> {
        let pipeline_cache = world.resource::<PipelineCache>();
        let pipeline = world.resource::<ParticlePipeline>();

        if let Some(compute_pipeline) = pipeline_cache.get_compute_pipeline(pipeline.compute_pipeline_id) {
            if let Some(bind_group) = world.get_resource::<ParticleBindGroup>() {
                let mut pass = render_context
                    .command_encoder()
                    .begin_compute_pass(&ComputePassDescriptor {
                        label: Some("particle_compute_pass"),
                        ..default()
                    });

                pass.set_pipeline(compute_pipeline);
                pass.set_bind_group(0, &bind_group.bind_group, &[]);
                pass.dispatch_workgroups((bind_group.particle_count / 64) + 1, 1, 1);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::mem;

    #[test]
    fn test_particle_struct_size_is_gpu_aligned() {
        let size = mem::size_of::<Particle>();
        assert_eq!(size % 16, 0);
    }

    #[test]
    fn test_particle_struct_exact_size() {
        assert_eq!(mem::size_of::<Particle>(), 80);
    }

    #[test]
    fn test_sim_params_struct_size_is_gpu_aligned() {
        let size = mem::size_of::<SimParams>();
        assert_eq!(size % 16, 0);
    }

    #[test]
    fn test_sim_params_exact_size() {
        assert_eq!(mem::size_of::<SimParams>(), 32);
    }

    #[test]
    fn test_particle_is_pod_castable() {
        let p = Particle {
            pos: [1.0, 2.0, 3.0], _pad1: 0.0,
            vel: [0.1, 0.2, 0.3], _pad2: 0.0,
            color: [1.0, 0.5, 0.2, 1.0],
            target_pos: [4.0, 5.0, 6.0], _pad3: 0.0,
            target_color: [0.8, 0.6, 0.1, 1.0],
        };
        let bytes: &[u8] = bytemuck::bytes_of(&p);
        assert_eq!(bytes.len(), 80);
    }

    #[test]
    fn test_sim_params_defaults() {
        let p = SimParams::default();
        assert_eq!(p.repulsion_radius, 15.0);
        assert_eq!(p.repulsion_force, 50.0);
        assert_eq!(p.recovery_force, 2.0);
    }

    #[test]
    fn test_workgroup_dispatch_covers_all() {
        let dispatch = (MAX_PARTICLES as u32 / 64) + 1;
        assert!(dispatch * 64 >= MAX_PARTICLES as u32);
    }

    #[test]
    fn test_buffer_byte_size() {
        let size = MAX_PARTICLES * mem::size_of::<Particle>();
        assert_eq!(size, 80_000_000);
        assert!(size < 256_000_000);
    }
}
