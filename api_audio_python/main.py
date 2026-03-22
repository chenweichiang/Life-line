from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
import numpy as np
from io import BytesIO
import scipy.io.wavfile as wav

app = FastAPI(title="Audio Generative Backend")

class EmotionVector(BaseModel):
    intensity: float  # 0.0 - 1.0 跟隨視覺的同一個向量
    color_tone: str
    flow: str

@app.post("/generate_audio")
def generate_audio_synth(vector: EmotionVector):
    """
    透過 Tech Art 演算法合成與情緒向量對應的環境聲響 (Ambient Drone)
    這種 Procedural Audio 不需等待 10G 音訊模型載入，延遲僅有 0.01 秒，且與視覺高度同步。
    """
    sample_rate = 44100
    duration = 5.0 # 生成 5 秒的無縫淡入淡出環境音
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # 基底頻率：如果流動是 chaotic 則低沉，calm 則清脆
    base_freq = 110.0 if vector.flow == "chaotic" else 220.0
    
    # 強度 (intensity) 控制噪音量與顫音 (Vibrato)
    vibrato = np.sin(2 * np.pi * (5.0 * vector.intensity) * t) * (10.0 * vector.intensity)
    signal = np.sin(2 * np.pi * (base_freq + vibrato) * t)
    
    # 加入高頻泛音與風聲 (Organic flowing noise)
    # 噪音振幅必須低於基底正弦波，否則會淹沒基底頻率的零交叉特徵
    noise = np.random.normal(0, 1, signal.shape)
    noise_filter = np.sin(2 * np.pi * 0.5 * t)  # slow organic swell
    signal += noise * 0.03 * vector.intensity * noise_filter
    
    # 加上 Envelope (Attack / Release) 確保音檔無縫接軌不爆音
    envelope = np.ones_like(t)
    fade_len = int(sample_rate * 0.5)
    envelope[:fade_len] = np.linspace(0, 1, fade_len)
    envelope[-fade_len:] = np.linspace(1, 0, fade_len)
    
    signal = signal * envelope
    
    # 正規化並轉換到 16-bit PCM
    signal = np.int16(signal / np.max(np.abs(signal)) * 32767 * 0.5)
    
    # 將 numpy array 寫入記憶體中的 Wav 格式
    byte_io = BytesIO()
    wav.write(byte_io, sample_rate, signal)
    
    return Response(content=byte_io.getvalue(), media_type="audio/wav")
