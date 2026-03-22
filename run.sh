#!/bin/bash
# Life Line — 快速啟動腳本
# 同時啟動 Python AI 後端 + SwiftUI App

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "🎨 Life Line — AI 藝術生成器"
echo ""

# 啟動 Python API（背景）
echo "🧠 啟動 AI 後端..."
cd "$PROJECT_ROOT/api_vision_python"
source .venv/bin/activate
uvicorn main:app --port 8001 --host 127.0.0.1 --timeout-keep-alive 120 &
API_PID=$!
echo "  API PID: $API_PID"

# 等待 API 就緒
echo "⏳ 等待模型載入..."
for i in $(seq 1 45); do
    if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/docs 2>/dev/null | grep -q "200"; then
        echo "  ✅ 模型已就緒！"
        break
    fi
    printf "  載入中 (%d/45)...\r" "$i"
    sleep 2
done

echo ""

# 啟動 SwiftUI App
echo "🖥️  啟動 App..."
if [ -f "$PROJECT_ROOT/build/LifeLine.app/Contents/MacOS/LifeLine" ]; then
    open "$PROJECT_ROOT/build/LifeLine.app"
elif [ -f "$PROJECT_ROOT/app_macos/.build/release/LifeLine" ]; then
    "$PROJECT_ROOT/app_macos/.build/release/LifeLine" &
else
    cd "$PROJECT_ROOT/app_macos"
    swift run &
fi

APP_PID=$!

echo "  App 已啟動"
echo ""
echo "📌 按 Ctrl+C 關閉所有服務"

# 捕捉退出信號，清理程序
cleanup() {
    echo ""
    echo "🛑 關閉服務..."
    kill $API_PID 2>/dev/null
    kill $APP_PID 2>/dev/null
    echo "  已關閉"
}

trap cleanup EXIT INT TERM

# 等待前景程序
wait
