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
    """取得 Paraformer-zh 模型路徑，自動相容 PyInstaller 打包與普通執行"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', base_dir)
        exe_dir = os.path.dirname(sys.executable)
        candidates = [
            os.path.join(meipass, "models", "paraformer-zh"),
            os.path.join(exe_dir, "_internal", "models", "paraformer-zh"),
            os.path.join(exe_dir, "models", "paraformer-zh"),
            "models/paraformer-zh",
            "paraformer-zh"
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    return os.path.relpath(p, os.getcwd())
                except Exception:
                    return p

    if os.path.exists(os.path.join(base_dir, "models", "paraformer-zh")):
        return os.path.join(base_dir, "models", "paraformer-zh")
    return "paraformer-zh"

def clean_paraformer_text(raw_text):
    """清理標點與無用標記"""
    if not raw_text:
        return ""
    text = re.sub(r"<\|.*?\|>", "", raw_text).strip()
    return text


class ParaformerASRWorkerThread(QThread):
    """背景語音辨識執行緒 (Paraformer-zh 原生中文引擎)"""
    text_recognized = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_running = True

    def run(self):
        model_path = get_relative_model_path()
        print(f"🎙️ 載入 Paraformer-zh 中文語音辨識模型 ({model_path})...")
        
        model = None
        # 載入 FunASR Paraformer-zh 原生中文引擎
        try:
            from funasr import AutoModel
            model = AutoModel(model="paraformer-zh", disable_update=True)
            print("✅ 成功載入 Paraformer-zh 中文語音辨識引擎！")
        except Exception as e:
            print(f"[錯誤] Paraformer-zh 模型載入失敗: {e}")
            self.text_recognized.emit("❌ Paraformer 模型載入失敗，請確認網路或模型檔案。")
            return

        sample_rate = 16000
        step_samples = int(sample_rate * 0.5)   # 每 0.5 秒滑動更新
        max_samples = int(sample_rate * 3.5)    # 最大上下文視窗 3.5 秒
        audio_buffer = np.array([], dtype=np.float32)
        silence_count = 0

        try:
            with sd.InputStream(samplerate=sample_rate, channels=1, dtype='float32', callback=audio_callback):
                while self.is_running:
                    while not audio_queue.empty():
                        chunk = audio_queue.get()
                        audio_buffer = np.append(audio_buffer, chunk.flatten())

                    # 當累積音訊達到 0.5 秒時觸發辨識
                    if len(audio_buffer) >= step_samples:
                        if len(audio_buffer) > max_samples:
                            audio_buffer = audio_buffer[-max_samples:]

                        # 檢測音量 RMS
                        recent_chunk = audio_buffer[-step_samples:]
                        rms = np.sqrt(np.mean(recent_chunk**2))

                        if rms < 0.004:
                            silence_count += 1
                            if silence_count >= 3:
                                audio_buffer = np.array([], dtype=np.float32)
                                silence_count = 0
                            time.sleep(0.05)
                            continue

                        silence_count = 0
                        text = ""
                        res = model.generate(input=audio_buffer, batch_size_s=300, use_itn=True)
                        if res and len(res) > 0:
                            raw = res[0].get("text", "") if isinstance(res[0], dict) else str(res[0])
                            text = clean_paraformer_text(raw)

                        if text:
                            print(f"🗣️ [Paraformer 中文即時] {text}")
                            self.text_recognized.emit(text)

                    time.sleep(0.05)

        except Exception as e:
            print(f"錄音與語音辨識過程出錯: {e}")

    def stop(self):
        self.is_running = False
        self.wait()


class ParaformerTransparentSubtitleWindow(QWidget):
    """Paraformer 中文桌面透明即時字幕浮動視窗 GUI"""

    def __init__(self):
        super().__init__()
        self.old_pos = None
        self.font_size = 24
        self.init_ui()

        # 啟動背景 ASR 語音辨識執行緒
        self.asr_thread = ParaformerASRWorkerThread()
        self.asr_thread.text_recognized.connect(self.update_subtitle)
        self.asr_thread.start()

    def init_ui(self):
        self.setWindowTitle("Paraformer 中文桌面字幕")

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 10, 15, 10)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Paraformer 中文專用字幕")
        title_label.setStyleSheet("color: rgba(0, 210, 255, 220); font-weight: bold; font-size: 12px; background: transparent;")
        
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

        self.label_subtitle = QLabel("🎤 正在準備 Paraformer 中文語音辨識模型...")
        self.label_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_subtitle.setWordWrap(True)
        self.update_label_font()

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 255))
        shadow.setOffset(2, 2)
        self.label_subtitle.setGraphicsEffect(shadow)

        main_layout.addLayout(top_bar)
        main_layout.addWidget(self.label_subtitle)
        self.setLayout(main_layout)

        screen = QApplication.primaryScreen().geometry()
        window_width = 850
        window_height = 140
        x = (screen.width() - window_width) // 2
        y = screen.height() - window_height - 100
        self.setGeometry(x, y, window_width, window_height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(0, 0, 0, 140)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

    def update_label_font(self):
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
        self.label_subtitle.setText(text)

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
        if hasattr(self, 'asr_thread') and self.asr_thread.isRunning():
            self.asr_thread.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = ParaformerTransparentSubtitleWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
