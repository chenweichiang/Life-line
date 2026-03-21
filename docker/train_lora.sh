#!/bin/bash
# 這裡是給 Kohya_ss 訓練 SDXL LoRA 的執行腳本
# 建議您透過 Docker 掛載 bmaltais/kohya_ss 或直接使用本機訓練環境執行

export MODEL_NAME="stabilityai/stable-diffusion-xl-base-1.0"
export TRAIN_DIR="../ai_models/loras"
export OUTPUT_DIR="${TRAIN_DIR}/output"
export DATASET_CONFIG="${TRAIN_DIR}/dataset_config.toml"

echo "啟動 Life Line LoRA 模型訓練 (SDXL)..."
mkdir -p "$OUTPUT_DIR"

# 若您有安裝 accelerate，請在前面加上 `accelerate launch`
python3 sdxl_train_network.py \
  --pretrained_model_name_or_path=$MODEL_NAME \
  --dataset_config=$DATASET_CONFIG \
  --output_dir=$OUTPUT_DIR \
  --output_name="Lifeline" \
  --save_model_as="safetensors" \
  --prior_loss_weight=1.0 \
  --max_train_epochs=10 \
  --learning_rate=1e-4 \
  --optimizer_type="AdamW8bit" \
  --xformers \
  --mixed_precision="fp16" \
  --save_precision="fp16" \
  --network_module="networks.lora" \
  --network_dim=128 \
  --network_alpha=64 \
  --resolution="1024,1024" \
  --lr_scheduler="cosine_with_restarts"

echo "訓練結束，權重檔已儲存至 $OUTPUT_DIR/Lifeline.safetensors"
