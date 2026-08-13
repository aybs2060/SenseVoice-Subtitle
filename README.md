# SenseVoice & Paraformer-zh 桌面透明即時字幕

基於 FunASR 的 Windows 透明桌面即時語音辨識字幕工具。提供多語言版 (SenseVoice) 與 純中文精準增強版 (Paraformer-zh)。

## 🌟 功能特點

- **桌面透明字幕**：懸浮於螢幕上方的透明字幕視窗。
- **即時麥克風辨識**：支援麥克風即時語音轉文字。
- **雙模型支援**：
  - **SenseVoiceSmall**：支援多國語言（中、英、日、韓、粵語）識別。
  - **Paraformer-zh**：專為中文/普通話優化，中文錯別字率更低、斷詞更精準。

---

## 📥 免安裝版下載與使用 (For Users)

如果您不需要修改程式碼，只想直接使用：

1. 前往本專案右側的 **[Releases 頁面](https://github.com/aybs2060/SenseVoice-Subtitle/releases)**。
2. 下載最新的 `.zip` 壓縮包（可選擇 SenseVoice 多語言版或 Paraformer-zh 中文精準版）。
3. 解壓縮後，雙擊執行 `.exe` 檔即可開始使用！

---

## 🛠️ 開發者環境建置 (For Developers)

### 執行 SenseVoice 多語言版
```bash
python gui_subtitle.py
```

### 執行 Paraformer-zh 中文精準版
```bash
python gui_paraformer_subtitle.py
```

### 打包成 EXE 檔
- 打包 SenseVoice：`python build_exe.py`
- 打包 Paraformer-zh：`python build_paraformer_exe.py`
