#!/bin/bash
# Life Line — DMG 打包腳本
# 將 SwiftUI App + Python 環境 + AI 模型打包成自足的 .dmg
# 使用者只需：下載 DMG → 拖入 Applications → 雙擊使用

set -e

echo "╔════════════════════════════════════════════════╗"
echo "║  🎨 Life Line — DMG 打包工具                    ║"
echo "╚════════════════════════════════════════════════╝"
echo ""

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
APP_DIR="$BUILD_DIR/LifeLine.app"
CONTENTS="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
DMG_NAME="LifeLine-v1.0.0"
DMG_PATH="$BUILD_DIR/$DMG_NAME.dmg"

# 清理
rm -rf "$APP_DIR" "$DMG_PATH"
mkdir -p "$MACOS_DIR" "$RESOURCES"

# ═══════════════════════════════════
# 1. 編譯 SwiftUI App (Release)
# ═══════════════════════════════════
echo "🔨 [1/6] 編譯 SwiftUI App..."
cd "$PROJECT_ROOT/app_macos"
swift build -c release 2>&1 | grep -E "(Build|error|warning:)" || true

BINARY="$PROJECT_ROOT/app_macos/.build/release/LifeLine"
if [ ! -f "$BINARY" ]; then
    echo "❌ 編譯失敗"
    exit 1
fi

cp "$BINARY" "$MACOS_DIR/"
echo "  ✅ Binary 複製完成"

# ═══════════════════════════════════
# 2. 建立 Info.plist
# ═══════════════════════════════════
echo "📋 [2/6] 建立 Info.plist..."
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
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.graphics-design</string>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsLocalNetworking</key>
        <true/>
    </dict>
</dict>
</plist>
PLIST
echo "  ✅ Info.plist 完成"

# ═══════════════════════════════════
# 3. 複製 Python 環境
# ═══════════════════════════════════
echo "🐍 [3/6] 複製 Python 環境..."
VENV_SRC="$PROJECT_ROOT/api_vision_python/.venv"

if [ ! -d "$VENV_SRC" ]; then
    echo "❌ Python venv 不存在: $VENV_SRC"
    exit 1
fi

# 複製整個 venv
cp -R "$VENV_SRC" "$RESOURCES/python"

# 修正 shebang 和路徑（使相對化）
# Python venv 的 bin 內的腳本有硬編碼路徑，需要修正
PYTHON_BIN="$RESOURCES/python/bin"
if [ -f "$PYTHON_BIN/python3" ]; then
    # 建立 activate 替代（不需要 source activate 因為直接呼叫 python3）
    echo "  複製 venv 完成"
else
    echo "  ⚠️ 找不到 python3，嘗試建立 symlink..."
    # 找到實際的 python3
    REAL_PYTHON=$(which python3)
    ln -sf "$REAL_PYTHON" "$PYTHON_BIN/python3"
fi

# 清理不需要的檔案節省空間
echo "  清理快取..."
find "$RESOURCES/python" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$RESOURCES/python" -name "*.pyc" -delete 2>/dev/null || true
find "$RESOURCES/python" -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true
find "$RESOURCES/python" -name "test_*" -delete 2>/dev/null || true

PYTHON_SIZE=$(du -sh "$RESOURCES/python" | cut -f1)
echo "  ✅ Python 環境: $PYTHON_SIZE"

# ═══════════════════════════════════
# 4. 複製 API 程式碼
# ═══════════════════════════════════
echo "📦 [4/6] 複製 API 程式碼..."
mkdir -p "$RESOURCES/api"
cp "$PROJECT_ROOT/api_vision_python/main.py" "$RESOURCES/api/"

# 複製 requirements 作為文件
cp "$PROJECT_ROOT/api_vision_python/requirements.txt" "$RESOURCES/api/" 2>/dev/null || true
echo "  ✅ API 程式碼複製完成"

# ═══════════════════════════════════
# 5. 複製 AI 模型
# ═══════════════════════════════════
echo "🧠 [5/6] 複製 AI 模型..."
mkdir -p "$RESOURCES/models/loras/output"

MODEL_SRC="$PROJECT_ROOT/ai_models/loras/output/Lifeline.safetensors"
if [ -f "$MODEL_SRC" ]; then
    cp "$MODEL_SRC" "$RESOURCES/models/loras/output/"
    MODEL_SIZE=$(du -h "$MODEL_SRC" | cut -f1)
    echo "  ✅ Lifeline.safetensors: $MODEL_SIZE"
else
    echo "  ⚠️ 模型檔案未找到（使用者需手動放置）"
fi

# 複製原始素材（for procedural fallback）
if [ -d "$PROJECT_ROOT/source images" ]; then
    cp -R "$PROJECT_ROOT/source images" "$RESOURCES/source_images" 2>/dev/null || true
    echo "  ✅ 原始素材複製完成"
fi

# ═══════════════════════════════════
# 6. 清除 extended attributes 後建立 DMG
# ═══════════════════════════════════
echo "🧹 [6/6] 清除 xattr 並建立 DMG..."
# 關鍵修復：iCloud Drive 的 fileprovider 與 provenance 屬性
# 會導致 macOS Gatekeeper 將 App 標記為「已損毀」
xattr -cr "$APP_DIR"
echo "  ✅ 已清除所有 extended attributes"

# 計算 App 大小
APP_SIZE=$(du -sm "$APP_DIR" | cut -f1)
DMG_SIZE=$((APP_SIZE + 50))  # 額外 50MB buffer

echo "  App 大小: ${APP_SIZE}MB"
echo "  DMG 大小: ${DMG_SIZE}MB"

# 建立暫時目錄
DMG_TEMP="$BUILD_DIR/dmg_temp"
rm -rf "$DMG_TEMP"
mkdir -p "$DMG_TEMP"

# 使用 ditto --norsrc 複製（不帶 resource fork / xattr）
ditto --norsrc "$APP_DIR" "$DMG_TEMP/LifeLine.app"

# 雙重保險：再次清除 staging 裡所有 xattr
xattr -cr "$DMG_TEMP/LifeLine.app"
echo "  ✅ staging 目錄已清除所有 xattr"

# 建立 Applications 捷徑
ln -s /Applications "$DMG_TEMP/Applications"

# 建立 DMG
hdiutil create -volname "Life Line" \
    -srcfolder "$DMG_TEMP" \
    -ov -format UDZO \
    "$DMG_PATH" \
    2>&1 | grep -v "^$"

# 清理
rm -rf "$DMG_TEMP"

DMG_FINAL_SIZE=$(du -h "$DMG_PATH" | cut -f1)

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║              ✅ DMG 打包完成！                  ║"
echo "╠════════════════════════════════════════════════╣"
echo "║                                                ║"
echo "║  📦 檔案: build/$DMG_NAME.dmg                  ║"
echo "║  💾 大小: $DMG_FINAL_SIZE                       ║"
echo "║                                                ║"
echo "║  使用者操作：                                    ║"
echo "║  1. 雙擊 DMG 掛載                               ║"
echo "║  2. 拖 Life Line 到 Applications                ║"
echo "║  3. 從 Launchpad 開啟                            ║"
echo "║                                                ║"
echo "╚════════════════════════════════════════════════╝"
