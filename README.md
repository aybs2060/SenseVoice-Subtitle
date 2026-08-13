# SenseVoice 透明桌面即時字幕 (SenseVoice-Subtitle)

基於 FunASR / SenseVoiceSmall 的 Windows 透明桌面即時語音辨識字幕工具。

## 🌟 功能特點

- **桌面透明字幕**：懸浮於螢幕上方的透明字幕視窗。
- **即時麥克風辨識**：支援麥克風即時語音轉文字。
- **免安裝隨開即用**：提供打包好的 Windows `.exe` 可執行檔，無需配置 Python 環境。

---

## 📥 免安裝版下載與使用 (For Users)

如果您不需要修改程式碼，只想直接使用本工具：

1. 前往本專案右側的 **[Releases 頁面](https://github.com/aybs2060/SenseVoice-Subtitle/releases)**。
2. 下載最新的 `SenseVoiceSubtitle.zip`。
3. 解壓縮後，直接雙擊執行 `SenseVoiceSubtitle.exe` 即可開始使用！

---

## 🛠️ 開發者環境建置 (For Developers)

如果您想自行修改或重新打包：

1. **安裝依賴**
   ```bash
   pip install -r requirements.txt
   ```

2. **執行程式**
   ```bash
   python gui_subtitle.py
   ```

3. **打包 EXE**
   ```bash
   python build_exe.py
   ```
