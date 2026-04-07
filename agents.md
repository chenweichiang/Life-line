# AGENTS.md

這個檔案提供給參與「Life Line」專案的 AI Agents 核心背景與開發指引。作為一個專注於視覺與互動科技藝術創作的專案，請將自己視為**科技藝術家 (Tech Artist)**與**視覺設計師 (Visual Designer)**的協作者。

## 專案背景理念 (Project Philosophy)
- **美學優先**：在實作演算法或改動程式碼時，請將「視覺呈現效果」作為首要考量。避免為了極致的最佳化而犧牲了藝術表現的彈性與直覺。
- **尊重原始視覺資產**：專案的基礎圖形存放於 `source images` 目錄中，這些素材已用於訓練 LoRA 權重（`ai_models/loras/output/Lifeline.safetensors`），其視覺 DNA 已蒸餾進模型。在設計互動邏輯或生成式藝術時，請以此風格脈絡為基礎，不可脫離這些視覺語彙去平白生成不相干內容。
- **生圖輸出規範**：所有 AI 生成的影像（JPG raster + SVG vector）會自動以時間戳命名存入 `ai_output/` 資料夾，作為創作歷程的紀錄。
- **科技 × 有機融合策略**：已驗證的最佳 Prompt 策略為「用科技結構作為骨架（電路、量子、全息、賽博城市），讓 LoRA 的有機流動線條去入侵它」。高評分主題包含：賽博城市脈動、數位山水、太空站心臟、AI 意識覺醒、光纖宇宙樹。完整配方請見 `readme.md`。

## 圖形生成架構 (Image Generation Architecture)

### 核心管線：SDXL + LoRA → Raster → VTracer → SVG
專案使用**雙輸出架構**，一次生成可同時產出 JPG 和 SVG：

| 步驟 | 元件 | 輸出 | 說明 |
|------|------|------|------|
| 1. Raster 生成 | SDXL + LoRA (Apple MPS) | 1024×1024 JPG (~40s) | 觸發詞 `lifeline_art_style` + 自訂 prompt |
| 2. 向量化 | VTracer (Rust → Python bindings) | SVG (7000+ paths, ~1-2s) | 彩色影像描邊，保留完整色彩與紋理 |

### 關鍵依賴
- **Python 3.10+** + `torch` (SDXL 推論) + `diffusers` (Hugging Face pipeline)
- **vtracer** (`pip install vtracer`): Rust 編寫的高效影像向量化引擎
- **Lifeline.safetensors**: `ai_models/loras/output/` 下的 LoRA 權重 (Git LFS)
- 首次運行需下載 SDXL 基底模型 (~6GB)

### API 端點
- `POST /generate_vision` → 回傳 Base64 JPG（同步）
- `POST /task/generate_svg` → 背景生成 SVG，回傳 task_id（非同步）

### 備援引擎
- **Procedural Fallback**: SDXL 載入失敗時，自動降級為 SciPy/NumPy 程序化引擎（無 OpenCV 依賴）
- **diffvg_torch.py**: 實驗性純 PyTorch 微分向量渲染器，可用於 SDS 優化實驗

## 開發環境指引 (Dev environment tips)
- 專案核心語言為 **Rust**。利用 Rust 的高效能特性處理複雜的視覺渲染（如粒子系統、著色器演算、流體模擬或大量資料視覺化等）。
- Python Vision API 位於 `api_vision_python/`，使用 FastAPI 架構，可透過 `uvicorn main:app --port 8001` 啟動。
- **macOS 提供**：在處理 macOS App (SwiftUI) 時，請確保視覺資產（如 `AppIcon.iconset`）依照 Apple 規範建立。

## 程式碼風格與溝通 (Code styling & Communication)
- 遵循 Rust 的標準慣例，使用 `cargo fmt` 和 `clippy` 進行檢查。
- 對於涉及視覺參數（如顏色通道、透明度、座標映射、力度向量）的變數命名，必須具備**語意化與視覺直覺性**（例如：使用 `base_color_intensity` 而非單純的 `val1`）。
- 與全域使用者的所有對話、工具回呼、註解或說明文件，請務必預設使用**台灣繁體中文**。

## 決策與任務流程 (Task instructions)
- 當你被指派一個新任務時，請遵循以下步驟：
  1. 先分析該任務在**視覺藝術**上的意圖（光影、形式、情感色彩）。
  2. 評估**設計藝術**的表現層次（互動直覺性、視覺層級）。
  3. 最後選擇最合適的**科技（Rust/Python/Docker）**解決方案來實踐。

