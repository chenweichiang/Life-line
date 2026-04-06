"""
vector_optimizer.py — SDS 導引向量場雕刻器
Life Line 專案核心：以 Score Distillation Sampling 驅動貝茲曲線的梯度下降

這支程式是整個 VectorFusion 管線的心臟。它做的事情是：
  1. 在畫布上播撒 N 條隨機的貝茲曲線（種子）
  2. 透過純 PyTorch 微分渲染器將曲線畫成像素
  3. 將像素影像餵入 SDXL + Lifeline LoRA 計算 SDS Loss
  4. 梯度一路從 UNet 的噪聲預測反推回每條曲線的控制點座標
  5. 迭代數百次，曲線逐漸被雕刻成具有 Lifeline 美學的有機向量圖形

最終產出：一張由真實 SVG 路徑碼構成的純向量圖形，
可在任何解析度下無損縮放，也可直接載入 Rust/Bevy 做即時動畫。

改用 diffvg_torch（純 PyTorch）替代 pydiffvg（C++ 擴展），
徹底消除跨平台編譯障礙。
"""
import os
import torch
import torch.nn.functional as F
import random
import time

# 使用我們的純 PyTorch 渲染引擎，而非 C++ 版本的 pydiffvg
import diffvg_torch


def sds_loss(unet, vae, text_embeddings, rendered_image, scheduler, device):
    """
    Score Distillation Sampling Loss (VectorFusion / DreamFusion)
    
    核心思想：
      - 將渲染出的 512x512 RGB 像素編碼至 VAE latent space
      - 加入隨機時間步長的高斯噪聲
      - 讓 UNet 預測「這張圖的噪聲方向」
      - SDS 梯度 = w(t) × (預測噪聲 - 實際噪聲)
      - 這個梯度會被 autograd 傳遞回渲染器，再傳遞至曲線控制點
    
    rendered_image: [H, W, 3] float32, 0~1 — 由 diffvg_torch 渲染的 RGB 影像
    """
    # 轉成 SDXL 預期的格式 [-1, 1] & NCHW
    image = rendered_image * 2.0 - 1.0
    image = image.unsqueeze(0).permute(0, 3, 1, 2)  # [1, 3, H, W]
    
    with torch.no_grad():
        # 編碼至 latent（半精度節省記憶體）
        latents = vae.encode(image.to(torch.float16)).latent_dist.sample()
        latents = latents * vae.config.scaling_factor
        
        # 隨機時間步長 — 避免過早或過晚的雜訊等級
        t = torch.randint(
            int(scheduler.config.num_train_timesteps * 0.05),
            int(scheduler.config.num_train_timesteps * 0.95),
            (1,), device=device, dtype=torch.long
        )
        
        # 加入噪聲
        noise = torch.randn_like(latents)
        latents_noisy = scheduler.add_noise(latents, noise, t)
        
        # Classifier-free guidance：uncond + cond
        latent_model_input = torch.cat([latents_noisy] * 2)
        latent_model_input = scheduler.scale_model_input(latent_model_input, t)
        
        # UNet 預測噪聲
        noise_pred = unet(
            latent_model_input, t, encoder_hidden_states=text_embeddings
        ).sample
    
    # CFG 合成
    noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
    guidance_scale = 7.5
    noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_text - noise_pred_uncond)
    
    # SDS 梯度：w(t) × (ε_pred - ε)
    w = (1 - scheduler.alphas_cumprod[t])
    grad = w * (noise_pred - noise)
    
    # Trick: 建立一個假 loss，使得 autograd 回傳 SDS 梯度到渲染圖像
    loss = torch.sum(latents * grad.detach())
    return loss


def run_optimization(pipe, prompt, output_svg_path, num_steps=200,
                     num_paths=150, canvas_size=512):
    """
    主渲染優化迴圈 — 讓 AI 一筆一筆地在虛空中雕繪線條
    
    pipe: SDXL + LoRA pipeline
    prompt: 引導生成的文字描述
    output_svg_path: SVG 輸出路徑
    num_steps: 優化迭代次數
    num_paths: 初始曲線數量
    canvas_size: 畫布邊長（像素）
    """
    device = pipe.device
    
    print(f"🎭 初始化 {num_paths} 條貝茲曲線在 {canvas_size}x{canvas_size} 畫布上...")
    shapes, shape_groups = diffvg_torch.initialize_random_paths(
        num_paths=num_paths, canvas_size=canvas_size, device=device
    )
    
    # 設定 Adam 優化器 — 分別控制不同類型參數的學習率
    points_vars = [shape.points for shape in shapes]
    color_vars = [group.stroke_color for group in shape_groups]
    width_vars = [shape.stroke_width for shape in shapes]
    
    optimizer = torch.optim.Adam([
        {'params': points_vars, 'lr': 1.0},       # 控制點位移：大步長
        {'params': color_vars,  'lr': 0.01},       # 顏色微調：小步長
        {'params': width_vars,  'lr': 0.1},        # 線寬：中步長
    ])
    
    print(f"🧠 預編碼文字嵌入... (Prompt: {prompt[:60]}...)")
    
    # 預先編碼 text embeddings，迴圈中不再重複計算
    with torch.no_grad():
        text_inputs = pipe.tokenizer(
            prompt, padding="max_length",
            max_length=pipe.tokenizer.model_max_length,
            truncation=True, return_tensors="pt"
        )
        text_embeddings = pipe.text_encoder(
            text_inputs.input_ids.to(device)
        )[0]
        
        uncond_inputs = pipe.tokenizer(
            "", padding="max_length",
            max_length=pipe.tokenizer.model_max_length,
            return_tensors="pt"
        )
        uncond_embeddings = pipe.text_encoder(
            uncond_inputs.input_ids.to(device)
        )[0]
        
        text_embeddings = torch.cat([uncond_embeddings, text_embeddings])
    
    print(f"🚀 開始 SDS 向量雕刻... ({num_steps} iterations)")
    start_time = time.time()
    
    for step in range(num_steps):
        optimizer.zero_grad()
        
        # ── 1. 渲染：向量 → 像素 ──
        img = diffvg_torch.render_paths_soft(
            shapes, shape_groups, canvas_size, device=device
        )
        
        # 合成背景（白色底）
        bg = torch.ones(canvas_size, canvas_size, 3, device=device)
        rgb = img[:, :, 3:4] * img[:, :, :3] + bg * (1 - img[:, :, 3:4])
        
        # ── 2. AI SDS Loss ──
        loss = sds_loss(
            pipe.unet, pipe.vae, text_embeddings,
            rgb, pipe.scheduler, device
        )
        
        # ── 3. 反向傳播 → 雕刻曲線 ──
        loss.backward()
        optimizer.step()
        
        # ── 4. 邊界約束 ──
        with torch.no_grad():
            for group in shape_groups:
                group.stroke_color.data.clamp_(0.0, 1.0)
            for shape in shapes:
                shape.stroke_width.data.clamp_(0.5, 10.0)
                # 防止控制點飛出畫布太遠
                shape.points.data.clamp_(-canvas_size * 0.1,
                                          canvas_size * 1.1)
        
        if step % 50 == 0:
            elapsed = time.time() - start_time
            per_step = elapsed / (step + 1)
            remaining = per_step * (num_steps - step - 1)
            print(f"  🔄 Iteration {step}/{num_steps} | "
                  f"Loss: {loss.item():.4f} | "
                  f"已耗時: {elapsed:.0f}s | "
                  f"預估剩餘: {remaining:.0f}s")
    
    total_time = time.time() - start_time
    print(f"\n✅ 優化完成！總耗時 {total_time:.1f} 秒 ({total_time/60:.1f} 分鐘)")
    
    # 匯出 SVG
    diffvg_torch.save_svg(output_svg_path, canvas_size, shapes, shape_groups)
    print(f"💾 SVG 已儲存: {output_svg_path}")
    
    return output_svg_path
