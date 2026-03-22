#!/bin/bash
# Life Line — 一鍵安裝腳本
# 安裝 Python 環境 + 依賴 + 編譯 SwiftUI App

set -e

echo "╔════════════════════════════════════════════╗"
echo "║   🎨 Life Line — AI 藝術生成器 安裝程式     ║"
echo "╚════════════════════════════════════════════╝"
echo ""

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# === 1. 檢查系統需求 ===
echo "🔍 檢查系統需求..."

# macOS 版本
macos_version=$(sw_vers -productVersion)
echo "  macOS: $macos_version"

# Apple Silicon
arch=$(uname -m)
if [ "$arch" != "arm64" ]; then
    echo "❌ 此專案需要 Apple Silicon (M1/M2/M3/M4)"
    exit 1
fi
echo "  架構: $arch ✅"

# Python
if command -v python3 &>/dev/null; then
    py_version=$(python3 --version 2>&1)
    echo "  Python: $py_version ✅"
else
    echo "❌ 需要 Python 3.10+。請先安裝："
    echo "   brew install python@3.11"
    exit 1
fi

# Rust
if command -v rustc &>/dev/null; then
    rust_version=$(rustc --version)
    echo "  Rust: $rust_version ✅"
else
    echo "⚠️  Rust 未安裝（粒子引擎需要）"
    echo "   安裝: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
fi

# Swift
if command -v swift &>/dev/null; then
    swift_version=$(swift --version 2>&1 | head -1)
    echo "  Swift: $swift_version ✅"
else
    echo "❌ 需要 Swift（Xcode Command Line Tools）"
    echo "   安裝: xcode-select --install"
    exit 1
fi

# Git LFS
if command -v git-lfs &>/dev/null; then
    echo "  Git LFS: 已安裝 ✅"
else
    echo "📦 安裝 Git LFS..."
    brew install git-lfs
    git lfs install
fi

echo ""

# === 2. 下載 LFS 檔案（LoRA 模型） ===
echo "📥 下載 AI 模型（如果需要）..."
cd "$PROJECT_ROOT"
git lfs pull

if [ -f "ai_models/loras/output/Lifeline.safetensors" ]; then
    model_size=$(du -h ai_models/loras/output/Lifeline.safetensors | cut -f1)
    echo "  Lifeline.safetensors: $model_size ✅"
else
    echo "❌ LoRA 模型未找到。請確認 git lfs pull 成功。"
    exit 1
fi

echo ""

# === 3. 建立 Python 虛擬環境 ===
echo "🐍 設定 Python 環境..."
cd "$PROJECT_ROOT/api_vision_python"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "  建立虛擬環境 ✅"
fi

source .venv/bin/activate

# 安裝依賴
echo "  安裝 Python 套件（首次可能需要幾分鐘）..."
pip install --quiet --upgrade pip
pip install --quiet fastapi uvicorn torch diffusers transformers accelerate safetensors Pillow numpy opencv-python-headless

echo "  Python 環境就緒 ✅"
deactivate

echo ""

# === 4. 編譯 SwiftUI App ===
echo "🔨 編譯 SwiftUI App..."
cd "$PROJECT_ROOT/app_macos"
swift build -c release 2>&1 | tail -3

echo "  SwiftUI App 編譯完成 ✅"

echo ""

# === 5. 建立 .app Bundle ===
echo "📦 打包 .app..."
APP_DIR="$PROJECT_ROOT/build/LifeLine.app"
CONTENTS="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES"

# 複製二進位
cp "$PROJECT_ROOT/app_macos/.build/release/LifeLine" "$MACOS_DIR/"

# Info.plist
cat > "$CONTENTS/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>LifeLine</string>
    <key>CFBundleIdentifier</key>
    <string>art.lifeline.generator</string>
    <key>CFBundleName</key>
    <string>Life Line</string>
    <key>CFBundleDisplayName</key>
    <string>Life Line — AI 藝術生成器</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
</dict>
</plist>
PLIST

echo "  LifeLine.app 打包完成 ✅"

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║             ✅ 安裝完成！                   ║"
echo "╠════════════════════════════════════════════╣"
echo "║                                            ║"
echo "║  啟動方式：                                 ║"
echo "║  1. 終端機: ./run.sh                       ║"
echo "║  2. 雙擊:   build/LifeLine.app             ║"
echo "║                                            ║"
echo "║  首次啟動需等待 SDXL 模型載入（約 60 秒）     ║"
echo "║                                            ║"
echo "╚════════════════════════════════════════════╝"
