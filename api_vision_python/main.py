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
LORA_PATH = os.path.join(PROJECT_ROOT, "ai_models", "loras", "output", "Lifeline.safetensors")
SOURCE_IMAGES_DIR = os.path.join(PROJECT_ROOT, "source images")

# === 資料模型 ===
class EmotionVector(BaseModel):
    intensity: float
    color_tone: str
    flow: str
    custom_prompt: str = ""  # 自訂 prompt（留空則自動組合）


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

        print(f"🎨 Fusing LoRA weights from: {LORA_PATH}")
        pipe.load_lora_weights(LORA_PATH)
        pipe.fuse_lora()

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

    # 推論步數隨強度動態調整
    num_steps = int(15 + vector.intensity * 15)  # 15~30 步

    print(f"🎲 Seed: {seed}")
    print(f"🎨 Generating with prompt: {base_prompt[:100]}...")

    image = pipe(
        prompt=base_prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=num_steps,
        guidance_scale=7.0 + vector.intensity * 3.0,  # 7~10
        width=1024,
        height=1024,
        generator=generator,
        cross_attention_kwargs={"scale": 0.4},  # 降低 LoRA 影響力，釋放構圖多樣性
    ).images[0]

    # 轉 Base64
    buffered = BytesIO()
    image.save(buffered, format="JPEG", quality=90)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# === Procedural Fallback (保留) ===
def procedural_generation(vector: EmotionVector) -> str:
    """OpenCV 程序化生成 (當 AI 模型無法載入時的備援)"""
    import cv2

    image_paths = glob.glob(os.path.join(SOURCE_IMAGES_DIR, "*.jpg"))
    if not image_paths:
        raise Exception("Cannot find source images.")

    img_path = random.choice(image_paths)
    img = cv2.imread(img_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    h, w, _ = img.shape
    size = 1024
    if h > size and w > size:
        y = random.randint(0, h - size)
        x = random.randint(0, w - size)
        img = img[y:y+size, x:x+size]
    else:
        img = cv2.resize(img, (size, size))

    xs, ys = np.meshgrid(np.arange(size), np.arange(size))
    freq = 0.05 if vector.flow == "chaotic" else 0.005
    amp = 150.0 * vector.intensity + 10.0

    x_noise = np.random.normal(0, 5 * vector.intensity, (size, size))
    y_noise = np.random.normal(0, 5 * vector.intensity, (size, size))

    x_displace = np.sin(ys * freq) * amp + x_noise
    y_displace = np.cos(xs * freq) * amp + y_noise

    map_x = np.float32(xs + x_displace)
    map_y = np.float32(ys + y_displace)

    warped = cv2.remap(img, map_x, map_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101)

    if vector.intensity < 0.4:
        warped = cv2.GaussianBlur(warped, (15, 15), 0)

    pil_img = Image.fromarray(warped)
    buffered = BytesIO()
    pil_img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# === API 端點 ===
@app.on_event("startup")
async def startup_event():
    """伺服器啟動時自動載入模型"""
    load_model()


@app.post("/generate_vision")
def generate_vision(vector: EmotionVector):
    print(f"📨 Received: {vector}")

    if pipe is not None:
        # 使用真正的 AI 大腦
        try:
            img_str = ai_generation(vector)
            return {
                "image_base64": img_str,
                "prompt": "SDXL + Lifeline LoRA (AI Brain)",
            }
        except Exception as e:
            print(f"AI generation failed: {e}, falling back to procedural")

    # Fallback: 程序化引擎
    try:
        img_str = procedural_generation(vector)
        return {
            "image_base64": img_str,
            "prompt": "Procedural Fallback (OpenCV Engine)",
        }
    except Exception as e:
        print(f"All generation failed: {e}")
        return {"image_base64": "", "prompt": "Error"}
