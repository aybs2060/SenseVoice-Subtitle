import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import subprocess

def build():
    print("=== 開始打包 Paraformer-zh 中文桌面字幕為 .EXE 檔 (無 CMD 視窗) ===")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pyinstaller_bin = os.path.join(base_dir, ".venv", "Scripts", "pyinstaller.exe")
    
    if not os.path.exists(pyinstaller_bin):
        pyinstaller_bin = "pyinstaller"

    cmd = [
        pyinstaller_bin,
        "--noconsole",                   # 隱藏 CMD 控制台視窗
        "--onedir",                      # 目錄模式
        "--name=ParaformerSubtitle",     # 產生的 EXE 名稱
        "-y",
        "gui_paraformer_subtitle.py"
    ]

    print("執行 PyInstaller 打包指令:\n", " ".join(cmd))
    result = subprocess.run(cmd, cwd=base_dir)
    
    if result.returncode == 0:
        exe_path = os.path.join(base_dir, "dist", "ParaformerSubtitle", "ParaformerSubtitle.exe")
        print(f"\n[成功] 打包成功！Paraformer 可執行檔路徑為:\n  {exe_path}")
    else:
        print("\n[失敗] 打包失敗，請檢查 log 輸出。")

if __name__ == "__main__":
    build()
