import os
import sys
import re
import time
import queue
import numpy as np

# 確保控制台與 GUI UTF-8 輸出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QFont, QColor, QMouseEvent, QPainter, QBrush

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

def get_relative_model_path():
    """取得 SenseVoiceSmall 模型路徑，自動相容 PyInstaller 打包與普通執行"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', base_dir)
        exe_dir = os.path.dirname(sys.executable)
        candidates = [
            os.path.join(meipass, "models", "SenseVoiceSmall"),
            os.path.join(exe_dir, "_internal", "models", "SenseVoiceSmall"),
            os.path.join(exe_dir, "models", "SenseVoiceSmall"),
            os.path.join(exe_dir, "model"),
            "models/SenseVoiceSmall",
            "model"
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    return os.path.relpath(p, os.getcwd())
                except Exception:
                    return p

    if os.path.exists(os.path.join(base_dir, "models", "SenseVoiceSmall")):
        return "models/SenseVoiceSmall"
    elif os.path.exists(os.path.join(base_dir, "model")):
        return "model"
    return "models/SenseVoiceSmall"

def clean_sensevoice_text(raw_text):
    """清理 SenseVoice 標記標籤"""
    if not raw_text:
        return ""
    text = re.sub(r"<\|.*?\|>", "", raw_text).strip()
    return text


class ASRWorkerThread(QThread):
    """背景語音辨識執行緒 (流式即時輸出 Streaming Mode, language='auto')"""
    text_recognized = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_running = True

    def run(self):
        model_path = get_relative_model_path()
        print(f"🎙️ 載入全精度 SenseVoice-Small 模型 ({model_path}, quantize=False)...")
        
        model = None
        # 1. 載入全精度 SenseVoice-Small ONNX 引擎 (quantize=False)
        try:
            from funasr_onnx import SenseVoiceSmall
            model = SenseVoiceSmall(model_path, quantize=False)
            print("✅ 成功載入全精度 SenseVoice-Small ONNX 流式引擎！")
        except Exception as e:
            print(f"funasr_onnx 載入失敗 ({e})，嘗試使用 FunASR 原生引擎...")
            try:
                from funasr import AutoModel
                model = AutoModel(model="SenseVoiceSmall", model_path=model_path, disable_update=True)
                print("✅ 成功載入 FunASR PyTorch 引擎！")
            except Exception as ex:
                print(f"[錯誤] 模型載入失敗: {ex}")
                self.text_recognized.emit("❌ 模型載入失敗，請確認模型檔案完整。")
                return

        sample_rate = 16000
        step_samples = int(sample_rate * 0.5)   # 每 0.5 秒進行一次流式動態更新
        max_samples = int(sample_rate * 3.5)    # 滑動視窗最大長度 3.5 秒
        audio_buffer = np.array([], dtype=np.float32)
        silence_count = 0

        try:
            with sd.InputStream(samplerate=sample_rate, channels=1, dtype='float32', callback=audio_callback):
                while self.is_running:
                    while not audio_queue.empty():
                        chunk = audio_queue.get()
                        audio_buffer = np.append(audio_buffer, chunk.flatten())

                    # 當累積音訊達到 0.5 秒時觸發流式更新
                    if len(audio_buffer) >= step_samples:
                        # 保持最大 3.5 秒上下文視窗
                        if len(audio_buffer) > max_samples:
                            audio_buffer = audio_buffer[-max_samples:]

                        # 檢測最新片段音量 (RMS)
                        recent_chunk = audio_buffer[-step_samples:]
                        rms = np.sqrt(np.mean(recent_chunk**2))

                        if rms < 0.004:
                            silence_count += 1
                            # 連續靜音超過 1.2 秒則自動清空視窗，開啟下一句
                            if silence_count >= 3:
                                audio_buffer = np.array([], dtype=np.float32)
                                silence_count = 0
                            time.sleep(0.05)
                            continue

                        silence_count = 0
                        text = ""
                        # 語言設定改為自動 (language='auto')
                        if hasattr(model, "__call__") and type(model).__name__ == "SenseVoiceSmall":
                            res = model(audio_buffer, language="auto")
                            if res and len(res) > 0:
                                text = clean_sensevoice_text(res[0])
                        else:
                            res = model.generate(input=audio_buffer, language="auto", use_itn=True)
                            if res and len(res) > 0:
                                text = clean_sensevoice_text(res[0].get("text", ""))

                        if text:
                            print(f"🗣️ [流式即時] {text}")
                            self.text_recognized.emit(text)

                    time.sleep(0.05)

        except Exception as e:
            print(f"錄音與流式辨識過程出錯: {e}")

    def stop(self):
        self.is_running = False
        self.wait()


class TransparentSubtitleWindow(QWidget):
    """桌面透明即時字幕浮動視窗 GUI"""

    def __init__(self):
        super().__init__()
        self.old_pos = None
        self.font_size = 24
        self.init_ui()

        # 啟動背景 ASR 語音辨識執行緒 (流式模式)
        self.asr_thread = ASRWorkerThread()
        self.asr_thread.text_recognized.connect(self.update_subtitle)
        self.asr_thread.start()

    def init_ui(self):
        # 設定視窗名稱 (使其出現在 Alt+Tab 切換選單中)
        self.setWindowTitle("字幕")

        # 設定無邊框、永遠置頂、可出現在 Alt+Tab 的標準 Window 視窗類型
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # 主要版面配置
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 10, 15, 10)

        # 頂部控制欄（可調整字體大/小、關閉）
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("字幕")
        title_label.setStyleSheet("color: rgba(255, 255, 255, 180); font-size: 12px; background: transparent;")
        
        btn_font_dec = QPushButton("A-")
        btn_font_dec.setFixedSize(26, 22)
        btn_font_dec.setStyleSheet("""
            QPushButton { background-color: rgba(255,255,255,40); color: white; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: rgba(255,255,255,80); }
        """)
        btn_font_dec.clicked.connect(self.decrease_font_size)

        btn_font_inc = QPushButton("A+")
        btn_font_inc.setFixedSize(26, 22)
        btn_font_inc.setStyleSheet("""
            QPushButton { background-color: rgba(255,255,255,40); color: white; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: rgba(255,255,255,80); }
        """)
        btn_font_inc.clicked.connect(self.increase_font_size)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 22)
        btn_close.setStyleSheet("""
            QPushButton { background-color: rgba(235, 64, 52, 180); color: white; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: rgba(255, 0, 0, 220); }
        """)
        btn_close.clicked.connect(self.close)

        top_bar.addWidget(title_label)
        top_bar.addStretch()
        top_bar.addWidget(btn_font_dec)
        top_bar.addWidget(btn_font_inc)
        top_bar.addWidget(btn_close)

        # 字幕顯示 Label
        self.label_subtitle = QLabel("🎤 正在準備麥克風流式語音辨識...")
        self.label_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_subtitle.setWordWrap(True)
        self.update_label_font()

        # 字幕陰影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 255))
        shadow.setOffset(2, 2)
        self.label_subtitle.setGraphicsEffect(shadow)

        main_layout.addLayout(top_bar)
        main_layout.addWidget(self.label_subtitle)
        self.setLayout(main_layout)

        # 初始大小與位置 (放置於螢幕中下方)
        screen = QApplication.primaryScreen().geometry()
        window_width = 850
        window_height = 140
        x = (screen.width() - window_width) // 2
        y = screen.height() - window_height - 100
        self.setGeometry(x, y, window_width, window_height)

    def paintEvent(self, event):
        """繪製半透明黑圓角背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 黑色半透明背景 (Alpha: 140)
        painter.setBrush(QBrush(QColor(0, 0, 0, 140)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

    def update_label_font(self):
        """更新字體樣式與大小"""
        font = QFont("Microsoft JhengHei", self.font_size, QFont.Weight.Bold)
        self.label_subtitle.setFont(font)
        self.label_subtitle.setStyleSheet("color: #FFFFFF; background: transparent;")

    def increase_font_size(self):
        if self.font_size < 40:
            self.font_size += 2
            self.update_label_font()

    def decrease_font_size(self):
        if self.font_size > 14:
            self.font_size -= 2
            self.update_label_font()

    def update_subtitle(self, text):
        """更新字幕文字"""
        self.label_subtitle.setText(text)

    # 支援滑鼠按住拖曳移動視窗
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.old_pos = None

    def closeEvent(self, event):
        """關閉視窗時優雅停止語音辨識執行緒"""
        if hasattr(self, 'asr_thread') and self.asr_thread.isRunning():
            self.asr_thread.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = TransparentSubtitleWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
