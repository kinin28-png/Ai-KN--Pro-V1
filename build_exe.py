import os
import sys
import subprocess

def main():
    print("=== ចាប់ផ្តើមវេចខ្ចប់ Ai KN Pro-V1 ជា File .exe ===")
    
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=Ai_KN_Pro_V1",
        "--onefile",
        "--windowed",
        "--collect-all=customtkinter",
        "--collect-all=whisper",
        "--collect-all=tiktoken",
        "--collect-all=soundfile",
        "--collect-all=edge_tts",
        "--collect-all=yt_dlp",
        "--collect-all=deep_translator",
        "--collect-data=certifi",
        "--copy-metadata=tqdm",
        "--copy-metadata=regex",
        "--copy-metadata=requests",
        "--copy-metadata=packaging",
        "--copy-metadata=filelock",
        "--copy-metadata=numpy",
        "--copy-metadata=torch",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageTk",
        "--hidden-import=cv2",
        "--hidden-import=pydub",
        "--clean",
        "-y",
        "app.py"
    ]
    
    print("Running command:", " ".join(cmd))
    res = subprocess.run(cmd)
    
    if res.returncode == 0:
        exe_path = os.path.abspath(os.path.join("dist", "Ai_KN_Pro_V1.exe"))
        print("\n=== BUILD SUCCESSFUL ===")
        print(f"File .exe ត្រូវបានបង្កើតនៅ៖ {exe_path}")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"ទំហំ File៖ {size_mb:.2f} MB")
    else:
        print(f"\n=== BUILD FAILED (Code {res.returncode}) ===")

if __name__ == "__main__":
    main()
