"""
Life Line Vision AI — 真正的 SDXL + LoRA 生成引擎
訓練完成的 Lifeline.safetensors 已接入，系統正式從 Procedural 替代品升級為 AI 大腦。
仍保留 Procedural fallback 以備模型載入失敗時使用。
"""
from fastapi import FastAPI
from pydantic import BaseModel
import os
import glob
import random
import base64
from io import BytesIO
import numpy as np
from PIL import Image

app = FastAPI(title="Life Line Vision AI (SDXL + LoRA)")

# === 路徑設定 ===
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 支援外掛環境變數，解決 App Bundle 內部重新命名的問題
MODEL_BASE = os.environ.get("LIFELINE_MODEL_DIR")
if not MODEL_BASE or not os.path.exists(MODEL_BASE):
    MODEL_BASE = os.path.join(PROJECT_ROOT, "ai_models")
    
LORA_PATH = os.path.join(MODEL_BASE, "loras", "output", "Lifeline.safetensors")
SOURCE_IMAGES_DIR = os.path.join(PROJECT_ROOT, "source images")

# === 資料模型 ===
class EmotionVector(BaseModel):
    intensity: float
    color_tone: str
    flow: str
    custom_prompt: str = ""  # 自訂 prompt（留空則自動組合）
    lora_scale: float = 0.85  # Lifeline LoRA 影響力（0.0~1.0，0.85 為風格與構圖多樣性的最佳平衡）
    num_steps: int = 0       # 推論步數（0=自動計算）
    guidance_scale: float = 0.0  # Guidance（0=自動計算）


# === 載入 SDXL + LoRA 模型 ===
pipe = None

def load_model():
    """載入 SDXL 基底模型並融合訓練好的 LoRA 權重"""
    global pipe
    try:
        import torch
        from diffusers import StableDiffusionXLPipeline

        print(f"🧠 Loading SDXL base model...")
        pipe = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float32,
            use_safetensors=True,
        )

        from diffusers import LCMScheduler
        print(f"🚀 Injecting LCMScheduler for extreme acceleration...")
        pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)

        print(f"⚡ Loading LCM-LoRA weights...")
        pipe.load_lora_weights("latent-consistency/lcm-lora-sdxl", adapter_name="lcm")

        print(f"🎨 Loading Lifeline LoRA weights from: {LORA_PATH}")
        pipe.load_lora_weights(LORA_PATH, adapter_name="lifeline", use_safetensors=True)
        # 初始設定 adapters
        pipe.set_adapters(["lcm", "lifeline"], adapter_weights=[1.0, 0.85])

        # Apple M4 Max MPS 加速
        if torch.backends.mps.is_available():
            pipe = pipe.to("mps")
            print("⚡ Using Apple MPS (Metal Performance Shaders)")
        else:
            pipe = pipe.to("cpu")
            print("⚠️ MPS not available, using CPU")

        # 記憶體優化
        pipe.enable_attention_slicing()
        print("✅ SDXL + LoRA model ready!")

    except Exception as e:
        print(f"❌ Model load failed: {e}")
        print("⚠️ Falling back to Procedural Tech Art Engine")
        pipe = None


# === AI 生成 ===
def ai_generation(vector: EmotionVector) -> str:
    """使用訓練好的 LoRA 模型進行風格化生圖（每次隨機種子 + 隨機修飾詞）"""
    import torch

    # 隨機種子
    seed = random.randint(0, 2**32 - 1)
    if torch.backends.mps.is_available():
        generator = torch.Generator("mps").manual_seed(seed)
    else:
        generator = torch.Generator("cpu").manual_seed(seed)

    # 如果有自訂 prompt，直接使用
    if vector.custom_prompt:
        base_prompt = f"lifeline_art_style, {vector.custom_prompt}"
    else:
        base_prompt = "lifeline_art_style, flowing organic lines, "

        if vector.flow == "chaotic":
            base_prompt += "dynamic energetic strokes, vibrant contrast, turbulent flow, "
        else:
            base_prompt += "calm serene brushwork, gentle gradients, peaceful rhythm, "

        tone_map = {
            "warm": "warm earthy ochre tones, amber light, golden hues",
            "cool": "cool blue-grey tones, misty atmosphere, silver light",
            "earthy": "deep earth tones, olive green, raw sienna, natural pigments",
        }
        base_prompt += tone_map.get(vector.color_tone, tone_map["warm"])

    # 隨機藝術修飾詞 — 每次生成增加變化
    modifiers = [
        "dense layered textures", "ethereal transparent washes",
        "bold impasto strokes", "delicate ink-like lines",
        "deep saturated pigments", "luminous translucent layers",
        "raw expressive marks", "meditative repetitive patterns",
        "dramatic chiaroscuro", "soft diffused atmosphere",
        "fractured geometric forms", "fluid watercolor bleeding",
    ]
    base_prompt += ", " + ", ".join(random.sample(modifiers, 2))

    negative_prompt = "photorealistic, 3d render, text, watermark, blurry, low quality"

    # 推論步數：使用者指定 > 自動計算 (LCM 加速，8~12 步確保 Lifeline 紋理完整成形)
    num_steps = vector.num_steps if vector.num_steps > 0 else int(8 + vector.intensity * 4)
    # Guidance scale：使用者指定 > 自動計算 (2.0~4.0 讓 LoRA 風格充分表達)
    guidance = vector.guidance_scale if vector.guidance_scale > 0 else 2.0 + vector.intensity * 2.0
    # LoRA scale
    lora_scale = max(0.0, min(1.0, vector.lora_scale))
    
    # 動態設定多重 LoRA 權重
    pipe.set_adapters(["lcm", "lifeline"], adapter_weights=[1.0, lora_scale])

    print(f"🎲 Seed: {seed}")
    print(f"🎨 Prompt: {base_prompt[:80]}...")
    print(f"🚀 LCM Accelerated - Steps: {num_steps} | Guidance: {guidance:.1f} | Lifeline LoRA: {lora_scale:.2f}")

    image = pipe(
        prompt=base_prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=num_steps,
        guidance_scale=guidance,
        width=1024,
        height=1024,
        generator=generator,
    ).images[0]

    # 轉 Base64
    buffered = BytesIO()
    image.save(buffered, format="JPEG", quality=90)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# === Procedural Fallback (保留) ===
def procedural_generation(vector: EmotionVector) -> str:
    """Numpy/SciPy 程序化生成 (當 AI 模型無法載入時的備援，無 cv2 依賴)"""
    from scipy.ndimage import map_coordinates, gaussian_filter

    image_paths = glob.glob(os.path.join(SOURCE_IMAGES_DIR, "*.jpg"))
    if not image_paths:
        raise Exception("Cannot find source images.")

    img_path = random.choice(image_paths)
    pil_img = Image.open(img_path).convert("RGB")
    
    w, h = pil_img.size
    size = 1024
    if h > size and w > size:
        y = random.randint(0, h - size)
        x = random.randint(0, w - size)
        pil_img = pil_img.crop((x, y, x + size, y + size))
    else:
        pil_img = pil_img.resize((size, size), Image.Resampling.BICUBIC)

    img_arr = np.array(pil_img).astype(np.float32)

    xs, ys = np.meshgrid(np.arange(size), np.arange(size))
    freq = 0.05 if vector.flow == "chaotic" else 0.005
    amp = 150.0 * vector.intensity + 10.0

    x_noise = np.random.normal(0, 5 * vector.intensity, (size, size))
    y_noise = np.random.normal(0, 5 * vector.intensity, (size, size))

    x_displace = np.sin(ys * freq) * amp + x_noise
    y_displace = np.cos(xs * freq) * amp + y_noise

    map_x = np.clip(xs + x_displace, 0, size - 1)
    map_y = np.clip(ys + y_displace, 0, size - 1)

    # 分別對 RGB 進行像素映射變形
    warped_r = map_coordinates(img_arr[:, :, 0], [map_y, map_x], order=1, mode='reflect')
    warped_g = map_coordinates(img_arr[:, :, 1], [map_y, map_x], order=1, mode='reflect')
    warped_b = map_coordinates(img_arr[:, :, 2], [map_y, map_x], order=1, mode='reflect')
    warped = np.stack([warped_r, warped_g, warped_b], axis=-1)

    if vector.intensity < 0.4:
        # 模糊化以表達平靜
        warped[:, :, 0] = gaussian_filter(warped[:, :, 0], sigma=3.0)
        warped[:, :, 1] = gaussian_filter(warped[:, :, 1], sigma=3.0)
        warped[:, :, 2] = gaussian_filter(warped[:, :, 2], sigma=3.0)

    final_img = Image.fromarray(warped.astype(np.uint8))
    buffered = BytesIO()
    final_img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# === API 端點 ===
@app.on_event("startup")
async def startup_event():
    """伺服器啟動時自動載入模型"""
    load_model()


# === 輸出路徑設定 ===
AI_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "ai_output")
os.makedirs(AI_OUTPUT_DIR, exist_ok=True)

def _save_to_ai_output(img_base64: str, label: str) -> str:
    """將生成的圖片自動存檔至 ai_output 資料夾"""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{label}.jpg"
    filepath = os.path.join(AI_OUTPUT_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(base64.b64decode(img_base64))
    print(f"💾 Saved: {filepath}")
    return filename


@app.post("/generate_vision")
def generate_vision(vector: EmotionVector):
    print(f"📨 Received: {vector}")

    if pipe is not None:
        # 使用真正的 AI 大腦
        try:
            img_str = ai_generation(vector)
            saved = _save_to_ai_output(img_str, "sdxl")
            return {
                "image_base64": img_str,
                "prompt": "SDXL + Lifeline LoRA (AI Brain)",
                "saved_file": saved,
            }
        except Exception as e:
            print(f"AI generation failed: {e}, falling back to procedural")

    # Fallback: 程序化引擎
    try:
        img_str = procedural_generation(vector)
        saved = _save_to_ai_output(img_str, "procedural")
        return {
            "image_base64": img_str,
            "prompt": "Procedural Fallback (SciPy Engine)",
            "saved_file": saved,
        }
    except Exception as e:
        import traceback
        with open("/tmp/lifeline_py_error.log", "a") as f:
            f.write(f"All generation failed: {e}\n{traceback.format_exc()}\n")
        print(f"All generation failed: {e}")
        return {"image_base64": "", "prompt": "Error"}


from fastapi import BackgroundTasks
import uuid
from datetime import datetime


def _run_vector_generation_task(vector: EmotionVector, task_id: str, output_svg: str):
    """
    向量生成任務：SDXL + LoRA → raster → VTracer → SVG
    
    比起 SDS 微分優化法（15 分鐘），這套管線：
    1. 用 SDXL + LCM + LoRA 生成高品質 raster（~4s）→ 保持美學並極速生成
    2. 用 VTracer（Rust 引擎）即時將 raster 轉為 SVG（~1-2s）
    
    總計 < 10 秒即出向量圖。
    """
    try:
        import vtracer

        if pipe is None:
            print(f"[{task_id}] SDXL model not loaded, cannot generate.")
            return
        
        # ── Step 1: SDXL + LoRA 生成 Raster ──
        print(f"[{task_id}] Step 1/2: Generating raster with SDXL + LoRA...")
        img_base64 = ai_generation(vector)
        
        # 存入 ai_output 作為中間產物
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raster_filename = f"{timestamp}_{task_id}_raster.jpg"
        raster_path = os.path.join(AI_OUTPUT_DIR, raster_filename)
        with open(raster_path, "wb") as f:
            f.write(base64.b64decode(img_base64))
        print(f"[{task_id}] Raster saved: {raster_path}")
        
        # ── Step 2: VTracer 向量化 ──
        print(f"[{task_id}] Step 2/2: Vectorizing with VTracer...")
        vtracer.convert_image_to_svg_py(
            raster_path,
            output_svg,
            colormode='color',
            mode='spline',           # 平滑曲線（符合 Lifeline 的有機線條美學）
            color_precision=6,       # 色階精度（6 = 64 色，好的平衡點）
            filter_speckle=4,        # 過濾 4px 以下雜點
            corner_threshold=60,     # 角偵測閾值
            path_precision=3,        # SVG 路徑座標精度
        )
        
        svg_size_kb = os.path.getsize(output_svg) / 1024
        print(f"[{task_id}] ✅ SVG generated: {output_svg} ({svg_size_kb:.0f} KB)")
        
    except Exception as e:
        print(f"[{task_id}] Vector generation failed: {e}")
        import traceback
        traceback.print_exc()


@app.post("/task/generate_svg")
def generate_svg_task(vector: EmotionVector, background_tasks: BackgroundTasks):
    """
    生成向量圖（SVG）：
    SDXL + LCM 生成 raster → VTracer 即時描邊 → 高品質 SVG
    
    預計耗時 < 10 秒。
    """
    task_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{task_id}_vector.svg"
    filepath = os.path.join(AI_OUTPUT_DIR, filename)
    
    print(f"📨 Task Received [{task_id}]: SVG Vector Generation (SDXL → VTracer)")
    background_tasks.add_task(_run_vector_generation_task, vector, task_id, filepath)
    
    return {
        "task_id": task_id,
        "status": "processing",
        "expected_output": filepath,
        "message": "Vector generation started (SDXL-LCM + VTracer). Should complete in 5~10 seconds.",
    }

