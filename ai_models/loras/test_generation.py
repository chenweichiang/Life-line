import torch
from diffusers import StableDiffusionXLImg2ImgPipeline, StableDiffusionXLPipeline
import os

LORA_PATH = "output/Lifeline.safetensors"
BASE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
OUTPUT_IMG = "test_output.jpg"

def main():
    if not os.path.exists(LORA_PATH):
        print(f"錯誤：找不到訓練好的 LoRA 權重檔: {LORA_PATH}")
        print("請先執行 ../../docker/train_lora.sh 來進行訓練。")
        return

    print("載入基礎模型與 LoRA 權重...")
    # 使用 MPS (Mac) 或 CUDA
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用裝置: {device}")

    pipe = StableDiffusionXLPipeline.from_pretrained(
        BASE_MODEL, torch_dtype=torch.float16 if device != "cpu" else torch.float32
    ).to(device)

    # 載入我們微調的 LoRA
    pipe.load_lora_weights(LORA_PATH)
    
    prompt = "lifeline_art_style, watercolor and ink on textured paper, organic flowing lines, rhythmic dashed brushstrokes, earthy tones, ochre, olive green, rust red, abstract biological, fluid motion"
    
    print("開始生成測試圖像...")
    # 生成測試圖片
    image = pipe(
        prompt=prompt,
        num_inference_steps=30,
        guidance_scale=7.5,
    ).images[0]

    image.save(OUTPUT_IMG)
    print(f"✅ 生成完畢！測試圖片已儲存至: {OUTPUT_IMG}")
    print("請打開這張圖片，確認：")
    print("1. 大地色系與橄欖綠是否準確？")
    print("2. 點狀短筆觸與波浪長線條的流動感是否還原？")
    print("3. 水彩紙的粗糙質地是否被保留？")

if __name__ == "__main__":
    main()
