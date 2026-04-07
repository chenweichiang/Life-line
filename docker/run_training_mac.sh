#!/bin/bash
set -e

echo "開始準備 Mac 本機 M4 Max (MPS) 訓練環境..."

cd /Users/chenweichiang/Documents/Developer/life_line/ai_models

if [ ! -d "kohya_ss" ]; then
    echo "正在下載 Kohya_ss..."
    git clone --recursive https://github.com/bmaltais/kohya_ss.git
fi

cd kohya_ss
git submodule update --init --recursive

if [ ! -d "venv_310" ]; then
    echo "安裝 Astral UV 以部署獨立的 Python 3.10 (解決 Python 3.14 scipy 編譯錯誤)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
    
    echo "正在建立 Python 3.10 虛擬環境..."
    uv venv --python 3.10 venv_310
fi

source venv_310/bin/activate

echo "正在使用 uv 極速安裝相依套件 (Mac MPS 專用)..."
# 解除牽制
python3 -c "import re; bad=['tensorflow', 'xformers', 'bitsandbytes']; open('req_clean.txt', 'w').writelines([re.split(r'[=<>~]', line)[0]+'\n' for line in open('requirements_macos_arm64.txt') if not any(b in line for b in bad)])"

uv pip install torch torchvision --upgrade
uv pip install -r req_clean.txt --index-strategy unsafe-best-match
uv pip install accelerate transformers diffusers safetensors einops huggingface_hub typing_extensions scipy --index-strategy unsafe-best-match

export MODEL_NAME="stabilityai/stable-diffusion-xl-base-1.0"
export TRAIN_DIR="/Users/chenweichiang/Documents/Developer/life_line/ai_models/loras"
export OUTPUT_DIR="${TRAIN_DIR}/output"
export DATASET_CONFIG="${TRAIN_DIR}/dataset_config.toml"

echo "啟動 Life Line LoRA 模型訓練 (SDXL on M4 Max)..."
mkdir -p "$OUTPUT_DIR"

# 針對 Mac (Apple Silicon) 的參數調整：
# - 移除 --xformers (NVIDIA 特有)
# - optimizer 改回原生的 AdamW
python3 sd-scripts/sdxl_train_network.py \
  --pretrained_model_name_or_path=$MODEL_NAME \
  --dataset_config=$DATASET_CONFIG \
  --output_dir=$OUTPUT_DIR \
  --output_name="Lifeline" \
  --save_model_as="safetensors" \
  --prior_loss_weight=1.0 \
  --max_train_epochs=10 \
  --learning_rate=1e-4 \
  --optimizer_type="AdamW" \
  --save_precision="fp16" \
  --network_module="networks.lora" \
  --network_dim=64 \
  --network_alpha=32 \
  --resolution="1024,1024" \
  --lr_scheduler="cosine_with_restarts"

echo "訓練結束，權重檔已儲存至 $OUTPUT_DIR/Lifeline.safetensors"
