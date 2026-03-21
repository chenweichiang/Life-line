# Life Line 視覺藝術風格解析與 LoRA 訓練策略

## 一、 原始圖像風格深度解析 (Visual Style Analysis)
透過分析 `source images` 目錄下的 23 張作品，我已經完全掌握了圖像的藝術 DNA，總結出以下核心視覺特徵：

1. **媒材與質地 (Medium & Texture)**：
   * 在帶有明顯**粗糙顆粒感的水彩紙（Textured Watercolor Paper）**上作畫。
   * 結合了「水彩的暈染/半透明疊加」與「細密簽字筆/墨水的清晰線條」。

2. **筆觸與線條結構 (Brushstrokes & Line Art)**：
   * **波浪狀連續線條 (Undulating Continuous Lines)**：如同等高線、水流、或木紋般的連續細線，營造出強烈的流動感。
   * **節奏性短筆觸 (Rhythmic Dashed Strokes)**：大量使用虛線、短點、或是如魚群/葉片狀的短促筆觸，這些短筆觸順著原本的長線條流動，產生空間的層次與密度。
   * **有機幾何 (Organic Geometry)**：形狀多為細胞狀 (Cellular)、神經元、或是生物組織的切面，沒有銳利的幾何直線。

3. **色彩計畫 (Color Palette)**：
   * 具有極高辨識度的**大地/自然色系 (Earthy & Organic Tones)**。
   * 核心色票包含：**赭黃色 (Ochre)、芥末黃 (Mustard)、橄欖綠 (Olive Green)、鐵鏽紅 (Rust Red)、赤陶色 (Terracotta)**。
   * 線條常使用淡淡的灰藍色或深褐色來勾勒邊界。

4. **視覺感受 (Visual Feeling)**：
   * 充滿生命力 (Vibrant, Biological)，如同微觀世界下的細胞分裂，或是宏觀視角下的風流動場 (Wind Currents)。這完美呼應了「Life Line (生命脈絡)」的專案主題。

---

## 二、 LoRA 訓練與標註策略 (Training Strategy)

為確保 AI 能夠 100% 繼承上述所有細節，我們將採用以下訓練設定：

### 1. 影像預處理 (Preprocessing)
* 將 23 張圖片按照紙張紋理方向進行無失真的 `1024x1024` (SDXL) 或 `512x512` 切割與縮放。
* 保留紙張邊緣與留白，讓 AI 學習到「這是一張畫在實體紙上的作品」，而不只是純粹的圖形。

### 2. 觸發詞與提示詞標註 (Captioning)
所有圖片的 `.txt` 標註檔案，必須強制包含這段核心提示詞基礎，讓 AI 將這些語意與您的畫風死死綁定：
> `lifeline_art_style, watercolor and ink on textured paper, organic flowing lines, rhythmic dashed brushstrokes, earthy tones, ochre, olive green, rust red, abstract biological, fluid motion.`

### 3. Hyperparameters (訓練參數)
* **模型選擇**：建議基於 **SDXL 1.0** 進行訓練，因其對「線條質地」與「水彩暈染感」的還原度遠高於 SD 1.5。
* **Network Rank (Dim)**：設定為 `64` 或 `128`。因為筆畫的隨機性與細節（虛線的排列）非常豐富，需要較高的維度來記憶這些微小的筆觸特徵。
* **Learning Rate**：針對藝術風格，建議使用較低的學習率 `1e-4` 搭配 `cosine_with_restarts` 的 Scheduler，避免模型發生「色塊崩壞（Burn/Fried）」的過度訓練。
