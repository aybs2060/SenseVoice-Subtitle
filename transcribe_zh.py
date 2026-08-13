import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import argparse
import librosa
import numpy as np

def get_relative_model_path(model_arg):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(base_dir, "models", "SenseVoiceSmall")):
        return os.path.join("models", "SenseVoiceSmall")
    elif os.path.exists(os.path.join(base_dir, "model")):
        return "model"
    elif os.path.exists(model_arg):
        return os.path.relpath(model_arg, base_dir)
    return model_arg

def clean_sensevoice_text(raw_text):
    import re
    if not raw_text:
        return ""
    return re.sub(r"<\|.*?\|>", "", raw_text).strip()

def transcribe_audio(audio_path, model_arg="models/SenseVoiceSmall", language="auto"):
    model_path = get_relative_model_path(model_arg)
    print(f"正在從本地載入 SenseVoice ONNX 模型 ({model_path})...")

    try:
        from funasr_onnx import SenseVoiceSmall
        model = SenseVoiceSmall(model_path, quantize=True)
        print(f"正在轉寫音訊檔案: {audio_path} ...")
        
        result = model(audio_path, language=language)
        text = clean_sensevoice_text(result[0]) if result else ""
        
        print("\n" + "="*40)
        print("辨識結果：")
        print("="*40)
        print(text)
        print("="*40 + "\n")
        return text
    except Exception as e:
        print(f"ONNX 轉寫備用方案 ({e})...")
        try:
            from funasr import AutoModel
            model = AutoModel(model="SenseVoiceSmall", model_path=model_path, disable_update=True)
            res = model.generate(input=audio_path, language=language, use_itn=True)
            text = clean_sensevoice_text(res[0].get("text", "")) if res else ""
            print("\n" + "="*40)
            print("辨識結果：")
            print("="*40)
            print(text)
            print("="*40 + "\n")
            return text
        except Exception as ex:
            print(f"[錯誤] 模型轉寫失敗: {ex}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SenseVoice 中文音訊轉寫工具")
    parser.add_argument("audio", type=str, help="音訊檔案路徑 (wav, mp3, m4a 等)")
    parser.add_argument("--model", type=str, default="models/SenseVoiceSmall", help="指定模型路徑")
    parser.add_argument("--lang", type=str, default="auto", help="語言設定 (預設: auto)")
    
    args = parser.parse_args()
    transcribe_audio(args.audio, model_arg=args.model, language=args.lang)
