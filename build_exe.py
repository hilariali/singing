import os
import subprocess
import sys

def build():
    print("--- 開始打包 卡拉OK神 ---")
    
    # Ensure dependencies are installed
    print("正在檢查/安裝必要依賴 (eel, yt-dlp, requests, bottle, pyinstaller)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "eel", "yt-dlp", "requests", "bottle", "pyinstaller"])

    # PyInstaller command
    # --onefile: Bundle into a single executable
    # --noconsole: Don't show terminal window
    # --add-data: Include the 'web' folder
    # --name: Executable name
    # --clean: Clean cache
    
    # Windows uses ; as separator for add-data, Linux/Mac uses :
    sep = ';' if os.name == 'nt' else ':'
    
    cmd = [
        "python", "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        f"--add-data=web{sep}web",
        "--name=karaoke-shen",
        "main.py"
    ]
    
    # Try using an icon if it exists (ideally .ico)
    # Since we only have .svg, we might skip icon for now or just let PyInstaller handle it
    
    print(f"執行命令: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print("\n--- 打包完成！ ---")
        print("您可以在 'dist' 資料夾中找到 'karaoke-shen.exe'")
    except subprocess.CalledProcessError as e:
        print(f"\n打包失敗: {e}")

if __name__ == "__main__":
    build()
