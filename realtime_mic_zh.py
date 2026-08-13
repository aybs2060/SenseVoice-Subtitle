import os
import sys

# 確保在 Windows CP950/Big5 主控台下可正常輸出 UTF-8 中文與 Emoji
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import queue
import time
import argparse
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("[提示] 未偵測到 sounddevice 套件，請使用 venv 環境執行。")

# 全域音訊佇列
audio_queue = queue.Queue()

def audio_callback(indata, frames, time_info, status):
    """麥克風輸入回呼函式，將錄製到的音訊存入 queue"""
    if status:
        print(f"狀態警示: {status}", file=sys.stderr)
    audio_queue.put(indata.copy())

def get_relative_model_path(model_arg):
    """將模型路徑轉為相對路徑，避免 Windows C++ SentencePiece 中文路徑 Bug"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    if os.path.exists(os.path.join(base_dir, "models", "SenseVoiceSmall")):
        return os.path.join("models", "SenseVoiceSmall")
    elif os.path.exists(os.path.join(base_dir, "model")):
        return "model"
    elif os.path.exists(model_arg):
        return os.path.relpath(model_arg, base_dir)
        
    return model_arg

def clean_sensevoice_text(raw_text):
    """清理 SenseVoice 標記標籤 (例如 <|zh|><|NEUTRAL|><|Speech|><|woitn|>)"""
    import re
    if not raw_text:
        return ""
    text = re.sub(r"<\|.*?\|>", "", raw_text).strip()
    return text

def start_realtime_transcription(model_arg="models/SenseVoiceSmall", chunk_duration=3.0, language="auto"):
    model_path = get_relative_model_path(model_arg)
    print(f"正在從本地載入 SenseVoice全精度模型 (FP32, quantize=False): {model_path} ...")

    model = None
    try:
        from funasr_onnx import SenseVoiceSmall
        # 第一點：全精度 SenseVoice-Small 模型 (quantize=False)
        model = SenseVoiceSmall(model_path, quantize=False)
        print("✅ 成功載入全精度 SenseVoice-Small ONNX 引擎！")
    except Exception as e:
        print(f"ONNX 引擎載入備用方案中 ({e})...")
        try:
            from funasr import AutoModel
            model = AutoModel(model="SenseVoiceSmall", model_path=model_path, disable_update=True)
            print("✅ 成功載入 FunASR PyTorch 引擎！")
        except Exception as ex:
            print(f"[錯誤] 模型載入失敗: {ex}")
            return

    sample_rate = 16000
    chunk_samples = int(sample_rate * chunk_duration)
    
    print("\n" + "="*50)
    print(f"🎙️ 麥克風即時語音辨識已啟動 (模型: SenseVoiceSmall 全精度版)")
    print("👉 請對著麥克風開始說話（按下 Ctrl+C 可停止）...")
    print("="*50 + "\n")

    audio_buffer = np.array([], dtype=np.float32)

    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='float32', callback=audio_callback):
            while True:
                # 從佇列取出錄音片段
                while not audio_queue.empty():
                    chunk = audio_queue.get()
                    audio_buffer = np.append(audio_buffer, chunk.flatten())

                # 當緩衝區音訊達到指定長度 (如 3 秒) 時進行語音辨識
                if len(audio_buffer) >= chunk_samples:
                    segment = audio_buffer[:chunk_samples]
                    # 保留最後 0.5 秒音訊重疊，確保句子連續性
                    overlap = int(sample_rate * 0.5)
                    audio_buffer = audio_buffer[chunk_samples - overlap:]

                    # 音量能量簡單判定 (能量太低視為靜音)
                    rms = np.sqrt(np.mean(segment**2))
                    if rms < 0.005:
                        continue

                    try:
                        if hasattr(model, "__call__") and type(model).__name__ == "SenseVoiceSmall":
                            res = model(segment, language=language)
                            if res and len(res) > 0:
                                text = clean_sensevoice_text(res[0])
                        else:
                            res = model.generate(input=segment, language=language, use_itn=True)
                            if res and len(res) > 0:
                                text = clean_sensevoice_text(res[0].get("text", ""))

                        if text:
                            timestamp = time.strftime("%H:%M:%S")
                            print(f"[{timestamp}] 🗣️  {text}")

                    except Exception as err:
                        print(f"辨識出錯: {err}")

                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[停止] 即時語音辨識已停止。")
    except Exception as e:
        print(f"\n[錯誤] 執行即時語音辨識時出錯: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SenseVoice 即時麥克風語音辨識工具")
    parser.add_argument("--model", type=str, default="models/SenseVoiceSmall", help="指定模型路徑")
    parser.add_argument("--chunk", type=float, default=3.0, help="語音採樣視窗長度（秒，預設: 3.0）")
    parser.add_argument("--lang", type=str, default="auto", help="語言設定 (預設: auto)")
    
    args = parser.parse_args()
    start_realtime_transcription(model_arg=args.model, chunk_duration=args.chunk, language=args.lang)
