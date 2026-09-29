import os
import sys
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# កំណត់ PATH ឱ្យស្គាល់ ffmpeg ប្រសិនបើមានក្នុង Folder ជាមួយ App
_app_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
if _app_dir and _app_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _app_dir + os.pathsep + os.environ.get("PATH", "")

import re
import time
import tempfile
import threading
import asyncio
import datetime
import urllib.parse
import winsound
import requests
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import edge_tts
from pydub import AudioSegment
import yt_dlp
import whisper
import cv2
import numpy as np
from PIL import Image

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def get_best_khmer_font():
    """ស្វែងរក Font ភាសាខ្មែរដែលល្អបំផុត និងមានស្រាប់លើកុំព្យូទ័រ"""
    try:
        import tkinter.font as tkfont
        _r = tk.Tk()
        _r.withdraw()
        available = set(tkfont.families())
        _r.destroy()

        candidates = [
            "Khmer OS Battambang",
            "Khmer OS",
            "Kantumruy",
            "Leelawadee UI",
            "Khmer UI",
            "Noto Sans Khmer",
            "DaunPenh",
            "Segoe UI"
        ]
        for c in candidates:
            if c in available:
                return c
    except Exception:
        pass
    return "Khmer OS Battambang"

KHMER_FONT_FAMILY = get_best_khmer_font()
# កំណត់ Font ជាសកលក្នុង CustomTkinter ដើម្បីគាំទ្រអក្សរខ្មែរគ្រប់ Widget ដោយមិនចេញសញ្ញា (?)
ctk.ThemeManager.theme["CTkFont"]["family"] = KHMER_FONT_FAMILY

def add_context_menu(widget):
    """បន្ថែម Right-Click Menu (កាត់, ចម្លង, បិទភ្ជាប់) សម្រាប់ប្រអប់អត្ថបទ"""
    target = getattr(widget, "_entry", getattr(widget, "_textbox", widget))
    menu = tk.Menu(target, tearoff=0)
    menu.add_command(label="កាត់ (Cut)", command=lambda: target.event_generate("<<Cut>>"))
    menu.add_command(label="ចម្លង (Copy)", command=lambda: target.event_generate("<<Copy>>"))
    menu.add_command(label="បិទភ្ជាប់ (Paste)", command=lambda: target.event_generate("<<Paste>>"))
    menu.add_separator()
    def _select_all():
        if hasattr(target, "select_range"):
            target.select_range(0, 'end')
        elif hasattr(target, "tag_add"):
            target.tag_add("sel", "1.0", "end")
    menu.add_command(label="ជ្រើសទាំងអស់ (Select All)", command=_select_all)

    def _show_menu(event):
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    target.bind("<Button-3>", _show_menu)

VOICE_OPTIONS = {
    "សំឡេងប្រុស (Piseth)": "km-KH-PisethNeural",
    "សំឡេងស្រី (Sreymom)": "km-KH-SreymomNeural",
    "English Male (Guy)": "en-US-GuyNeural",
    "English Female (Jenny)": "en-US-JennyNeural"
}

WHISPER_MODELS = {
    "base (លឿន និងសមរម្យ)": "base",
    "tiny (លឿនបំផុត)": "tiny",
    "small (ច្បាស់ល្អ)": "small",
    "medium (ច្បាស់កម្រិតខ្ពស់)": "medium"
}

LANGUAGE_OPTIONS = {
    "ស្វ័យប្រវត្តិ (Auto Detect)": None,
    "English (en)": "en",
    "Khmer (km)": "km",
    "Chinese (zh)": "zh",
    "Thai (th)": "th",
    "Vietnamese (vi)": "vi",
    "French (fr)": "fr",
    "Japanese (ja)": "ja",
    "Korean (ko)": "ko"
}

# ឃ្លាំងរក្សាទុក Whisper Model ក្នុង Memory កុំឱ្យ Reload ច្រើនដង
LOADED_WHISPER_MODELS = {}

def get_whisper_model(model_name="base"):
    if model_name not in LOADED_WHISPER_MODELS:
        LOADED_WHISPER_MODELS[model_name] = whisper.load_model(model_name)
    return LOADED_WHISPER_MODELS[model_name]

def parse_time(time_str):
    # បម្លែងពី HH:MM:SS,mmm ទៅជា milliseconds
    parts = re.split(r'[:,]', time_str)
    h, m, s, ms = map(int, parts)
    return (h * 3600 + m * 60 + s) * 1000 + ms

def format_timestamp(seconds: float):
    # បម្លែង seconds ទៅជា HH:MM:SS,mmm សម្រាប់ SRT
    total_msec = int(round(seconds * 1000))
    hours = total_msec // 3600000
    minutes = (total_msec % 3600000) // 60000
    secs = (total_msec % 60000) // 1000
    msec = total_msec % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{msec:03d}"

def translate_to_khmer(text: str, source: str = 'auto') -> str:
    # បកប្រែអត្ថបទទៅជាភាសាខ្មែរដោយប្រើ dict-chrome-ex របស់ Google
    if not text or not text.strip():
        return text
    # បើជាអក្សរខ្មែរលើសពី 50% រួចហើយ មិនបាច់បកប្រែទៀតទេ
    khmer_chars = len(re.findall(r'[\u1780-\u17ff]', text))
    if khmer_chars > len(text.strip()) * 0.5:
        return text
    
    try:
        url = 'https://translate.googleapis.com/translate_a/single?client=dict-chrome-ex&sl=' + source + '&tl=km&dt=t&q=' + urllib.parse.quote(text)
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=10).json()
        if resp and resp[0]:
            translated = ''.join([part[0] for part in resp[0] if part and part[0]])
            if translated.strip():
                return translated
    except Exception as e:
        print(f"Translation error: {e}")
    return text

def detect_voice_gender(audio_segment):
    """
    វិភាគរលកសំឡេងរកកម្រិតប្រេកង់ Fundamental Frequency (F0)
    ដើម្បីកំណត់ថាតើសំឡេងជា 'សំឡេងប្រុស (Piseth)' (F0 < 165 Hz) ឬ 'សំឡេងស្រី (Sreymom)' (F0 >= 165 Hz)
    """
    if audio_segment is None or len(audio_segment) < 200:
        return None, 0.0

    try:
        # Convert to mono, 16kHz
        chunk = audio_segment.set_channels(1).set_frame_rate(16000)
        samples = np.array(chunk.get_array_of_samples(), dtype=np.float32)
        if len(samples) < 640:
            return None, 0.0

        max_val = np.max(np.abs(samples))
        if max_val > 0:
            samples = samples / max_val

        sr = 16000
        frame_len = 640  # 40ms
        step = 320       # 20ms
        min_lag = int(sr / 350)  # ~45 samples (350 Hz)
        max_lag = int(sr / 75)   # ~213 samples (75 Hz)

        pitches = []
        for i in range(0, len(samples) - frame_len, step):
            frame = samples[i : i + frame_len]
            if np.mean(frame ** 2) < 0.003:
                continue

            frame = frame - np.mean(frame)
            n = len(frame)
            f = np.fft.rfft(frame, n=2 * n)
            acf = np.fft.irfft(f * np.conj(f))[:n]
            if acf[0] <= 0:
                continue

            search_region = acf[min_lag : max_lag]
            if len(search_region) == 0:
                continue

            best_idx = np.argmax(search_region)
            best_lag = min_lag + best_idx
            norm_corr = acf[best_lag] / acf[0]

            if norm_corr > 0.32:
                f0 = sr / best_lag
                pitches.append(f0)

        if not pitches:
            return None, 0.0

        median_f0 = float(np.median(pitches))
        if median_f0 < 165.0:
            return "សំឡេងប្រុស (Piseth)", median_f0
        else:
            return "សំឡេងស្រី (Sreymom)", median_f0
    except Exception as e:
        print("Pitch detection error:", e)
        return None, 0.0

class SubtitleDubberApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI KN - Subtitle Generator & Voice Dubbing Pro")
        self.geometry("1180x820")
        self.minsize(1000, 700)

        self.srt_entries = [] # រក្សាទុកទិន្នន័យបន្ទាត់ SRT សម្រាប់ Tab 2
        self.temp_preview_audio = None
        self.selected_video_path = ""

        # Video & Audio Preview State (សម្រាប់ Tab 2)
        self.video_cap = None
        self.video_preview_path = None
        self.video_audio = None # AudioSegment នៃសំឡេងវីដេអូដើមសម្រាប់ចាក់ & Auto Detect
        self.video_duration_sec = 0.0
        self.video_fps = 25.0
        self.is_video_playing = False
        self.current_video_pos_ms = 0.0
        self.active_subtitle_index = None
        self._updating_slider = False
        self.playback_wall_start = 0.0
        self.playback_pos_start_ms = 0.0
        self.chk_autoplay_orig_var = ctk.BooleanVar(value=True)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # បង្កើត TabView សម្រាប់បែងចែក ៣ មុខងារសំខាន់
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=15)

        self.tab_video2srt = self.tabview.add("🎥 1. Video / Link to SRT")
        self.tab_srt2voice = self.tabview.add("🎬 2. SRT to Voice (តាមតួអង្គ)")
        self.tab_text2voice = self.tabview.add("📝 3. Text to Voice (ភ្លាមៗ)")

        self.setup_video2srt_tab()
        self.setup_srt2voice_tab()
        self.setup_text2voice_tab()

    # =========================================================================
    # ផ្ទាំងទី ១៖ VIDEO / LINK TO SRT
    # =========================================================================
    def setup_video2srt_tab(self):
        # Frame សម្រាប់ជ្រើសរើសប្រភពវីដេអូ
        input_frame = ctk.CTkFrame(self.tab_video2srt)
        input_frame.pack(fill="x", padx=10, pady=10)

        lbl_input_title = ctk.CTkLabel(
            input_frame, 
            text="📥 ជ្រើសរើសវីដេអូក្នុងកុំព្យូទ័រ ឬ បញ្ចូលតំណភ្ជាប់ (Link):",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_input_title.pack(anchor="w", padx=15, pady=(10, 5))

        # ជម្រើសទី ១៖ វីដេអូក្នុងកុំព្យូទ័រ
        file_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        file_row.pack(fill="x", padx=15, pady=5)

        btn_browse_video = ctk.CTkButton(
            file_row, 
            text="📂 ជ្រើសរើសវីដេអូ / សំឡេង", 
            width=180,
            command=self.browse_video_file
        )
        btn_browse_video.pack(side="left", padx=(0, 10))

        self.lbl_selected_video = ctk.CTkLabel(
            file_row, 
            text="មិនទាន់បានជ្រើសរើសឯកសារ", 
            text_color="gray", 
            anchor="w"
        )
        self.lbl_selected_video.pack(side="left", fill="x", expand=True)

        # ជម្រើសទី ២៖ Link វីដេអូ
        url_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        url_row.pack(fill="x", padx=15, pady=5)

        lbl_url = ctk.CTkLabel(url_row, text="🔗 ឬ Link (YouTube/Web):", width=180, anchor="w")
        lbl_url.pack(side="left", padx=(0, 10))

        self.entry_video_url = ctk.CTkEntry(
            url_row, 
            font=ctk.CTkFont(family=KHMER_FONT_FAMILY, size=13),
            placeholder_text="https://www.youtube.com/watch?v=..."
        )
        self.entry_video_url.pack(side="left", fill="x", expand=True)
        add_context_menu(self.entry_video_url)

        # Frame កំណត់ Settings (Whisper Model & Language)
        settings_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        settings_frame.pack(fill="x", padx=15, pady=(10, 15))

        lbl_m = ctk.CTkLabel(settings_frame, text="Whisper AI Model:")
        lbl_m.pack(side="left", padx=(0, 5))

        self.combo_whisper_model = ctk.CTkComboBox(
            settings_frame, 
            values=list(WHISPER_MODELS.keys()), 
            width=190
        )
        self.combo_whisper_model.set("base (លឿន និងសមរម្យ)")
        self.combo_whisper_model.pack(side="left", padx=(0, 20))

        lbl_lang = ctk.CTkLabel(settings_frame, text="ភាសាដើមក្នុងវីដេអូ:")
        lbl_lang.pack(side="left", padx=(0, 5))

        self.combo_whisper_lang = ctk.CTkComboBox(
            settings_frame, 
            values=list(LANGUAGE_OPTIONS.keys()), 
            width=200
        )
        self.combo_whisper_lang.set("ស្វ័យប្រវត្តិ (Auto Detect)")
        self.combo_whisper_lang.pack(side="left")

        # ប៊ូតុងចាប់ផ្តើមបម្លែង
        self.btn_start_v2srt = ctk.CTkButton(
            self.tab_video2srt, 
            text="⚡ ចាប់ផ្តើមបម្លែងវីដេអូទៅជា Subtitle (.SRT)", 
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: threading.Thread(target=self.process_video2srt_thread, daemon=True).start()
        )
        self.btn_start_v2srt.pack(fill="x", padx=10, pady=5)

        # Status & Progress bar
        self.lbl_v2srt_status = ctk.CTkLabel(self.tab_video2srt, text="ត្រៀមរួចរាល់...", text_color="gray")
        self.lbl_v2srt_status.pack(padx=10, pady=(5, 2))

        self.prog_v2srt = ctk.CTkProgressBar(self.tab_video2srt)
        self.prog_v2srt.pack(fill="x", padx=10, pady=(0, 10))
        self.prog_v2srt.set(0)

        # ប្រអប់ Preview SRT Content
        lbl_out = ctk.CTkLabel(self.tab_video2srt, text="📄 លទ្ធផល Subtitle (SRT Preview):", font=ctk.CTkFont(weight="bold"))
        lbl_out.pack(anchor="w", padx=10, pady=(5, 2))

        self.txt_srt_output = ctk.CTkTextbox(self.tab_video2srt, height=220, font=ctk.CTkFont(family=KHMER_FONT_FAMILY, size=13))
        self.txt_srt_output.pack(fill="both", expand=True, padx=10, pady=5)
        add_context_menu(self.txt_srt_output)

        # ប៊ូតុងរក្សាទុក SRT និងបញ្ជូនទៅ Tab 2
        bottom_row = ctk.CTkFrame(self.tab_video2srt, fg_color="transparent")
        bottom_row.pack(fill="x", padx=10, pady=10)

        self.btn_save_srt = ctk.CTkButton(
            bottom_row, 
            text="💾 រក្សាទុកជាឯកសារ .SRT", 
            width=200, 
            command=self.save_generated_srt
        )
        self.btn_save_srt.pack(side="left", padx=5)

        self.btn_send_to_tab2 = ctk.CTkButton(
            bottom_row, 
            text="➡️ បញ្ជូនទៅកាន់ផ្ទាំង 'SRT to Voice' (Dubbing)", 
            width=280,
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            command=self.send_srt_to_dubbing_tab
        )
        self.btn_send_to_tab2.pack(side="right", padx=5)

        self.selected_video_path = ""

    def browse_video_file(self):
        filetypes = [
            ("វីដេអូ ឬ សំឡេង", "*.mp4;*.mkv;*.avi;*.mov;*.flv;*.webm;*.mp3;*.wav;*.m4a;*.aac;*.ogg;*.ts"),
            ("ឯកសារទាំងអស់", "*.*")
        ]
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self.selected_video_path = path
            self.lbl_selected_video.configure(
                text=f"✅ {os.path.basename(path)} ({os.path.getsize(path)/(1024*1024):.1f} MB)", 
                text_color="#4caf50"
            )
            # clear URL if local file is selected
            self.entry_video_url.delete(0, "end")
            # ផ្ទុកចូល Video Preview ក្នុង Tab 2 ផងដែរប្រសិនបើជាវីដេអូ
            ext = os.path.splitext(path)[1].lower()
            if ext in [".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".ts"]:
                self.load_video_for_preview(path)

    def process_video2srt_thread(self):
        url = self.entry_video_url.get().strip()
        local_file = self.selected_video_path

        if not url and (not local_file or not os.path.exists(local_file)):
            messagebox.showwarning("ការជូនដំណឹង", "សូមជ្រើសរើសឯកសារវីដេអូក្នុងកុំព្យូទ័រ ឬ បញ្ចូល Link វីដេអូជាមុនសិន!")
            return

        self.btn_start_v2srt.configure(state="disabled", text="⏳ កំពុងដំណើរការ...")
        self.prog_v2srt.set(0.1)

        temp_audio_file = None
        try:
            # ១. ទាញយកសំឡេងពី Link (បើប្រើ URL)
            if url:
                self.lbl_v2srt_status.configure(text="🌐 កំពុងទាញយកសំឡេងពី Link...", text_color="#2196f3")
                temp_dir = tempfile.gettempdir()
                temp_base = os.path.join(temp_dir, f"ytdl_{int(time.time())}")
                
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': f"{temp_base}.%(ext)s",
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'quiet': True,
                    'no_warnings': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                temp_audio_file = f"{temp_base}.mp3"
                if not os.path.exists(temp_audio_file):
                    raise RuntimeError("មិនអាចទាញយកសំឡេងពី Link បានទេ។ សូមពិនិត្យមើល Link ម្តងទៀត!")
                target_audio = temp_audio_file
            else:
                target_audio = local_file

            self.prog_v2srt.set(0.35)
            self.lbl_v2srt_status.configure(text="🤖 កំពុងផ្ទុក Whisper AI Model...", text_color="#ff9800")
            
            model_key = self.combo_whisper_model.get()
            model_name = WHISPER_MODELS.get(model_key, "base")
            model = get_whisper_model(model_name)

            self.prog_v2srt.set(0.55)
            self.lbl_v2srt_status.configure(text="🎙️ AI កំពុងស្តាប់ និងបង្កើត Subtitle...", text_color="#ff9800")

            lang_key = self.combo_whisper_lang.get()
            selected_lang = LANGUAGE_OPTIONS.get(lang_key, None)

            # Transcribe
            transcribe_args = {
                "verbose": False,
                "task": "transcribe"
            }
            if selected_lang:
                transcribe_args["language"] = selected_lang

            result = model.transcribe(target_audio, **transcribe_args)
            segments = result.get("segments", [])

            # ២. បង្កើត SRT Text
            self.prog_v2srt.set(0.85)
            self.lbl_v2srt_status.configure(text="📝 កំពុងតម្រៀបកាលវិភាគ SRT...", text_color="#ff9800")

            srt_lines = []
            for idx, seg in enumerate(segments, 1):
                start_str = format_timestamp(seg["start"])
                end_str = format_timestamp(seg["end"])
                text = seg["text"].strip()
                srt_lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")

            full_srt = "\n".join(srt_lines)

            # បង្ហាញក្នុងប្រអប់ Textbox
            self.txt_srt_output.delete("0.0", "end")
            self.txt_srt_output.insert("0.0", full_srt)

            self.prog_v2srt.set(1.0)
            self.lbl_v2srt_status.configure(
                text=f"✅ បម្លែងជោគជ័យ! ទទួលបាន {len(segments)} បន្ទាត់ Subtitle", 
                text_color="#4caf50"
            )
            messagebox.showinfo("ជោគជ័យ", f"បានបម្លែងវីដេអូទៅជា SRT ដោយជោគជ័យ!\nចំនួនបន្ទាត់៖ {len(segments)}")

        except Exception as e:
            self.lbl_v2srt_status.configure(text=f"❌ មានកំហុស៖ {str(e)}", text_color="#f44336")
            messagebox.showerror("កំហុស", f"មិនអាចបម្លែងជា SRT បានទេ៖\n{str(e)}")
        finally:
            if temp_audio_file and os.path.exists(temp_audio_file):
                try:
                    os.remove(temp_audio_file)
                except:
                    pass
            self.btn_start_v2srt.configure(state="normal", text="⚡ ចាប់ផ្តើមបម្លែងវីដេអូទៅជា Subtitle (.SRT)")

    def save_generated_srt(self):
        content = self.txt_srt_output.get("0.0", "end").strip()
        if not content:
            messagebox.showwarning("ការជូនដំណឹង", "មិនទាន់មានទិន្នន័យ SRT សម្រាប់រក្សាទុកទេ!")
            return
        
        save_path = filedialog.asksaveasfilename(
            defaultextension=".srt", 
            filetypes=[("SRT Files", "*.srt")]
        )
        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("ជោគជ័យ", f"បានរក្សាទុកឯកសារ SRT នៅ៖\n{save_path}")

    def send_srt_to_dubbing_tab(self):
        content = self.txt_srt_output.get("0.0", "end").strip()
        if not content:
            messagebox.showwarning("ការជូនដំណឹង", "សូមបម្លែងវីដេអូជា SRT ជាមុនសិន ឬ វាយបញ្ចូលទិន្នន័យ SRT!")
            return
        
        # បញ្ចូលទិន្នន័យទៅក្នុង Tab 2
        self.parse_and_display_srt(content, source_name="SRT ពីផ្ទាំងបម្លែងវីដេអូ")

        # ប្រសិនបើមានវីដេអូក្នុង Tab 1 ស្រាប់ ផ្ទុកចូល Video Preview ដោយស្វ័យប្រវត្តិ
        if self.selected_video_path and os.path.exists(self.selected_video_path):
            self.load_video_for_preview(self.selected_video_path)

        self.tabview.set("🎬 2. SRT to Voice (តាមតួអង្គ)")

    # =========================================================================
    # ផ្ទាំងទី ២៖ SRT TO VOICE + VIDEO & AUDIO PREVIEW + AUTO DETECT
    # =========================================================================
    def setup_srt2voice_tab(self):
        # Frame មេ ចែកជា ២ ផ្នែក៖ ខាងឆ្វេង (Video & Audio Preview) និងខាងស្តាំ (Subtitle Entries)
        main_split = ctk.CTkFrame(self.tab_srt2voice, fg_color="transparent")
        main_split.pack(fill="both", expand=True, padx=5, pady=5)

        # -------------------------------------------------------------
        # ផ្នែកខាងឆ្វេង៖ VIDEO & AUDIO PREVIEW & PLAYER CONTROLS
        # -------------------------------------------------------------
        self.left_video_frame = ctk.CTkFrame(main_split, width=430)
        self.left_video_frame.pack(side="left", fill="y", padx=(0, 6), pady=0)
        self.left_video_frame.pack_propagate(False)

        lbl_v_title = ctk.CTkLabel(
            self.left_video_frame, 
            text="🎥 ផ្ទាំងមើលវីដេអូ & សំឡេងដើម (Preview)", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_v_title.pack(anchor="w", padx=12, pady=(10, 4))

        # ប៊ូតុងជ្រើសរើសវីដេអូ និងឈ្មោះឯកសារ
        v_btn_row = ctk.CTkFrame(self.left_video_frame, fg_color="transparent")
        v_btn_row.pack(fill="x", padx=12, pady=2)

        btn_load_v = ctk.CTkButton(
            v_btn_row, 
            text="📂 ជ្រើសរើសវីដេអូ", 
            width=130, 
            command=self.browse_preview_video
        )
        btn_load_v.pack(side="left", padx=(0, 8))

        self.lbl_preview_video_name = ctk.CTkLabel(
            v_btn_row, 
            text="មិនទាន់មានវីដេអូ...", 
            text_color="gray", 
            anchor="w"
        )
        self.lbl_preview_video_name.pack(side="left", fill="x", expand=True)

        # កន្លែងបង្ហាញ Frame វីដេអូ (Video Screen)
        video_box = ctk.CTkFrame(self.left_video_frame, fg_color="#181818", corner_radius=8, height=225)
        video_box.pack(fill="x", padx=12, pady=6)
        video_box.pack_propagate(False)

        self.lbl_video_display = ctk.CTkLabel(
            video_box, 
            text="🎬 មិនទាន់មានវីដេអូ\n\nសូមចុច 'ជ្រើសរើសវីដេអូ' ដើម្បី Preview\nនិងស្តាប់សំឡេងតួអង្គ (ប្រុស ឬ ស្រី)", 
            font=ctk.CTkFont(size=13), 
            text_color="#9e9e9e"
        )
        self.lbl_video_display.pack(fill="both", expand=True, padx=5, pady=5)

        # ពេលវេលា និង Seek Slider
        time_row = ctk.CTkFrame(self.left_video_frame, fg_color="transparent")
        time_row.pack(fill="x", padx=12, pady=(2, 0))

        self.lbl_video_time = ctk.CTkLabel(
            time_row, 
            text="⏱️ 00:00:00 / 00:00:00", 
            font=ctk.CTkFont(size=12, weight="bold"), 
            text_color="#90caf9"
        )
        self.lbl_video_time.pack(side="left")

        self.slider_video_seek = ctk.CTkSlider(
            self.left_video_frame, 
            from_=0, 
            to=100, 
            command=self.on_video_seek_change
        )
        self.slider_video_seek.set(0)
        self.slider_video_seek.pack(fill="x", padx=12, pady=(2, 4))

        # ប៊ូតុងបញ្ជាវីដេអូ (Play ជាមួយសំឡេងដើម, Pause, Step)
        ctrl_row = ctk.CTkFrame(self.left_video_frame, fg_color="transparent")
        ctrl_row.pack(fill="x", padx=12, pady=2)

        btn_seek_bwd = ctk.CTkButton(
            ctrl_row, 
            text="⏪ -3s", 
            width=65, 
            fg_color="#37474f", 
            command=lambda: self.step_video_seconds(-3)
        )
        btn_seek_bwd.pack(side="left", padx=2)

        self.btn_video_play = ctk.CTkButton(
            ctrl_row, 
            text="▶️ Play (មានសំឡេង)", 
            width=100, 
            fg_color="#0288d1", 
            hover_color="#0277bd", 
            command=self.toggle_video_play
        )
        self.btn_video_play.pack(side="left", padx=3, fill="x", expand=True)

        btn_seek_fwd = ctk.CTkButton(
            ctrl_row, 
            text="⏩ +3s", 
            width=65, 
            fg_color="#37474f", 
            command=lambda: self.step_video_seconds(3)
        )
        btn_seek_fwd.pack(side="left", padx=2)

        btn_stop = ctk.CTkButton(
            ctrl_row, 
            text="⏹️ Stop", 
            width=60, 
            fg_color="#c62828", 
            hover_color="#b71c1c", 
            command=self.stop_video_playback
        )
        btn_stop.pack(side="left", padx=2)

        # ឧបករណ៍ជំនួយសំឡេង និង Auto Detect សម្រាប់បន្ទាត់កំពុងជ្រើស
        sound_act_frame = ctk.CTkFrame(self.left_video_frame, fg_color="#212121", corner_radius=6)
        sound_act_frame.pack(fill="x", padx=12, pady=(6, 3))

        lbl_s_title = ctk.CTkLabel(
            sound_act_frame, 
            text="🔊 ពិនិត្យសំឡេង & AI Detect (បន្ទាត់កំពុងមើល)៖", 
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_s_title.pack(anchor="w", padx=10, pady=(5, 3))

        btn_s_row = ctk.CTkFrame(sound_act_frame, fg_color="transparent")
        btn_s_row.pack(fill="x", padx=8, pady=(0, 4))

        btn_listen_current = ctk.CTkButton(
            btn_s_row, 
            text="🎧 ស្តាប់សំឡេងដើម", 
            fg_color="#00695c", 
            hover_color="#004d40", 
            command=self.play_active_subtitle_original_audio
        )
        btn_listen_current.pack(side="left", fill="x", expand=True, padx=2)

        btn_detect_current = ctk.CTkButton(
            btn_s_row, 
            text="⚡ Auto Detect បន្ទាត់នេះ", 
            fg_color="#6a1b9a", 
            hover_color="#4a148c", 
            command=self.auto_detect_single_line_voice
        )
        btn_detect_current.pack(side="right", fill="x", expand=True, padx=2)

        # Checkbox កំណត់ឱ្យចាក់សំឡេងស្វ័យប្រវត្តពេលចុចបន្ទាត់ Subtitle
        chk_autoplay = ctk.CTkCheckBox(
            sound_act_frame, 
            text="ចាក់សំឡេងដើមស្វ័យប្រវត្តិ ពេលចុចមើលបន្ទាត់", 
            variable=self.chk_autoplay_orig_var,
            font=ctk.CTkFont(size=11)
        )
        chk_autoplay.pack(anchor="w", padx=10, pady=(2, 6))

        # ប្រអប់កំណត់តួអង្គបន្ទាត់បច្ចុប្បន្នភ្លាមៗ (1-Click Tagging)
        tag_frame = ctk.CTkFrame(self.left_video_frame, fg_color="#212121", corner_radius=6)
        tag_frame.pack(fill="x", padx=12, pady=(4, 4))

        lbl_tag_title = ctk.CTkLabel(
            tag_frame, 
            text="👤 កំណត់សំឡេងដោយផ្ទាល់ (១ ចុច)៖", 
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_tag_title.pack(anchor="w", padx=10, pady=(5, 3))

        btn_tag_row = ctk.CTkFrame(tag_frame, fg_color="transparent")
        btn_tag_row.pack(fill="x", padx=8, pady=(0, 6))

        btn_tag_male = ctk.CTkButton(
            btn_tag_row, 
            text="👨 ប្រុស (Piseth)", 
            fg_color="#1565c0", 
            hover_color="#0d47a1", 
            command=lambda: self.set_active_row_voice("សំឡេងប្រុស (Piseth)")
        )
        btn_tag_male.pack(side="left", fill="x", expand=True, padx=2)

        btn_tag_female = ctk.CTkButton(
            btn_tag_row, 
            text="👩 ស្រី (Sreymom)", 
            fg_color="#ad1457", 
            hover_color="#880e4f", 
            command=lambda: self.set_active_row_voice("សំឡេងស្រី (Sreymom)")
        )
        btn_tag_female.pack(side="right", fill="x", expand=True, padx=2)

        # ព័ត៌មានជំនួយ និងបន្ទាត់បច្ចុប្បន្ន
        self.lbl_active_hint = ctk.CTkLabel(
            self.left_video_frame, 
            text="💡 ជំនួយ៖ ចុចប៊ូតុង 👁️ នៃបន្ទាត់ Subtitle\nដើម្បីលោតវីដេអូ & ស្តាប់សំឡេងតួអង្គនិយាយ!", 
            font=ctk.CTkFont(size=11), 
            text_color="#90a4ae", 
            justify="left"
        )
        self.lbl_active_hint.pack(anchor="w", padx=12, pady=(4, 6))

        # -------------------------------------------------------------
        # ផ្នែកខាងស្តាំ៖ SUBTITLE ENTRIES & ASSIGNMENTS
        # -------------------------------------------------------------
        self.right_srt_frame = ctk.CTkFrame(main_split, fg_color="transparent")
        self.right_srt_frame.pack(side="right", fill="both", expand=True, padx=(6, 0), pady=0)

        # Toolbar Upload SRT & Translate
        top_srt_row = ctk.CTkFrame(self.right_srt_frame)
        top_srt_row.pack(fill="x", padx=0, pady=(0, 4))

        btn_browse_srt = ctk.CTkButton(
            top_srt_row, 
            text="📂 Upload ឯកសារ .SRT", 
            width=150, 
            command=self.load_srt_file
        )
        btn_browse_srt.pack(side="left", padx=6, pady=6)

        self.lbl_srt_name = ctk.CTkLabel(
            top_srt_row, 
            text="មិនទាន់មានឯកសារ .srt ទេ", 
            text_color="gray", 
            anchor="w"
        )
        self.lbl_srt_name.pack(side="left", padx=5, fill="x", expand=True)

        self.btn_trans_all = ctk.CTkButton(
            top_srt_row, 
            text="🌐 បកប្រែជាភាសាខ្មែរទាំងអស់", 
            width=180, 
            fg_color="#0288d1", 
            hover_color="#0277bd", 
            command=lambda: threading.Thread(target=self.translate_all_entries_thread, daemon=True).start()
        )
        self.btn_trans_all.pack(side="right", padx=6, pady=6)

        # Toolbar កំណត់សំឡេងរហ័ស & AUTO DETECT ទាំងអស់
        quick_voice_frame = ctk.CTkFrame(self.right_srt_frame, fg_color="transparent")
        quick_voice_frame.pack(fill="x", padx=0, pady=2)

        # ប៊ូតុង Auto Detect សំឡេងតួទាំងអស់
        self.btn_auto_detect_all = ctk.CTkButton(
            quick_voice_frame, 
            text="🤖 Auto Detect សំឡេងតួទាំងអស់", 
            width=190, 
            font=ctk.CTkFont(weight="bold"),
            fg_color="#6a1b9a", 
            hover_color="#4a148c",
            command=lambda: threading.Thread(target=self.auto_detect_all_voices_thread, daemon=True).start()
        )
        self.btn_auto_detect_all.pack(side="left", padx=(0, 6))

        btn_all_male = ctk.CTkButton(
            quick_voice_frame, 
            text="👨 ប្រុសទាំងអស់", 
            width=95, 
            fg_color="#37474f", 
            command=lambda: self.set_all_voices("សំឡេងប្រុស (Piseth)")
        )
        btn_all_male.pack(side="left", padx=2)

        btn_all_female = ctk.CTkButton(
            quick_voice_frame, 
            text="👩 ស្រីទាំងអស់", 
            width=95, 
            fg_color="#37474f", 
            command=lambda: self.set_all_voices("សំឡេងស្រី (Sreymom)")
        )
        btn_all_female.pack(side="left", padx=2)

        btn_alternate = ctk.CTkButton(
            quick_voice_frame, 
            text="🔄 ឆ្លាស់គ្នា", 
            width=80, 
            fg_color="#37474f", 
            command=self.set_alternate_voices
        )
        btn_alternate.pack(side="left", padx=2)

        self.lbl_srt_count = ctk.CTkLabel(quick_voice_frame, text="ចំនួនបន្ទាត់៖ 0", text_color="#90caf9")
        self.lbl_srt_count.pack(side="right", padx=5)

        # បញ្ជី Subtitle Entries (Scrollable)
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.right_srt_frame, 
            label_text="បញ្ជី Subtitle (ចុច 👁️ ដើម្បី Preview វីដេអូ & ស្តាប់សំឡេងដើម)"
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=0, pady=4)

        # -------------------------------------------------------------
        # ផ្នែកខាងក្រោមនៃ TAB 2៖ PROGRESS & RENDER BUTTON
        # -------------------------------------------------------------
        self.lbl_dub_status = ctk.CTkLabel(self.tab_srt2voice, text="ត្រៀមរួចរាល់...", text_color="gray")
        self.lbl_dub_status.pack(padx=10, pady=(2, 0))

        self.prog_dub = ctk.CTkProgressBar(self.tab_srt2voice)
        self.prog_dub.pack(fill="x", padx=10, pady=(0, 5))
        self.prog_dub.set(0)

        self.btn_process_srt = ctk.CTkButton(
            self.tab_srt2voice, 
            text="🚀 Render ចេញជាសំឡេងនិយាយតម្រង់តាមពេលវេលា (Export MP3)", 
            height=40, 
            font=ctk.CTkFont(size=14, weight="bold"), 
            command=lambda: threading.Thread(target=self.process_srt_thread, daemon=True).start()
        )
        self.btn_process_srt.pack(fill="x", padx=10, pady=(0, 6))

    # =========================================================================
    # មុខងារគ្រប់គ្រង VIDEO PREVIEW & AUDIO PLAYBACK សម្រាប់ TAB 2
    # =========================================================================
    def browse_preview_video(self):
        filetypes = [
            ("វីដេអូ", "*.mp4;*.mkv;*.avi;*.mov;*.flv;*.webm;*.ts"),
            ("ឯកសារទាំងអស់", "*.*")
        ]
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self.load_video_for_preview(path)

    def load_video_for_preview(self, filepath):
        if not filepath or not os.path.exists(filepath):
            return

        self.stop_video_playback(pause_only=True)
        if self.video_cap:
            try:
                self.video_cap.release()
            except:
                pass
            self.video_cap = None

        safe_path = filepath
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.kernel32.GetShortPathNameW(filepath, buf, 1024) > 0:
                safe_path = buf.value
        except Exception:
            safe_path = filepath

        try:
            cap = cv2.VideoCapture(safe_path)
            if not cap.isOpened():
                cap = cv2.VideoCapture(filepath)

            if not cap.isOpened():
                messagebox.showwarning("កំហុសវីដេអូ", "មិនអាចបើកវីដេអូសម្រាប់ Preview បានទេ។ សូមពិនិត្យទ្រង់ទ្រាយឯកសារ!")
                return

            self.video_cap = cap
            self.video_preview_path = filepath
            fps = cap.get(cv2.CAP_PROP_FPS)
            self.video_fps = fps if (fps and fps > 0) else 25.0
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            self.video_duration_sec = frame_count / self.video_fps if self.video_fps > 0 else 0

            filename = os.path.basename(filepath)
            short_name = (filename[:22] + "...") if len(filename) > 22 else filename
            self.lbl_preview_video_name.configure(text=f"🎬 {short_name}", text_color="#81c784")

            self.slider_video_seek.configure(from_=0, to=max(self.video_duration_sec, 1))
            self.slider_video_seek.set(0)

            # ផ្ទុកសំឡេងដើម (Audio) ពីវីដេអូ សម្រាប់ចាក់ Playback & Auto Detect
            self.video_audio = None
            self.lbl_dub_status.configure(
                text=f"⏳ កំពុងទាញយកសំឡេងដើមពីវីដេអូ {short_name}...", 
                text_color="#ff9800"
            )

            def _load_audio_async():
                try:
                    self.video_audio = AudioSegment.from_file(safe_path)
                    self.lbl_dub_status.configure(
                        text=f"✅ បានផ្ទុកវីដេអូ និងសំឡេងដើមជោគជ័យ ({format_timestamp(self.video_duration_sec)[:8]})",
                        text_color="#4caf50"
                    )
                except Exception as ex:
                    print("Load audio error:", ex)
                    self.video_audio = None
                    self.lbl_dub_status.configure(
                        text=f"⚠️ ផ្ទុកវីដេអូបាន ប៉ុន្តែមិនអាចទាញសំឡេងដើមបានទេ៖ {ex}",
                        text_color="#ffb74d"
                    )

            threading.Thread(target=_load_audio_async, daemon=True).start()

            # បង្ហាញ Frame ដំបូង
            if self.active_subtitle_index is not None and 0 <= self.active_subtitle_index < len(self.srt_entries):
                self.seek_video_ms(self.srt_entries[self.active_subtitle_index]["start"])
            else:
                self.seek_video_ms(0)

        except Exception as e:
            messagebox.showerror("កំហុស", f"មិនអាចដំណើរការវីដេអូ Preview បានទេ៖ {str(e)}")

    def update_video_frame(self, frame=None, current_ms=None):
        if frame is None and self.video_cap and self.video_cap.isOpened():
            ret, frame = self.video_cap.read()
            if not ret:
                self.stop_video_playback(pause_only=True)
                return

        if frame is not None:
            try:
                h, w = frame.shape[:2]
                max_w, max_h = 390, 220
                scale = min(max_w / w, max_h / h)
                target_w = max(1, int(w * scale))
                target_h = max(1, int(h * scale))

                resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
                rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(target_w, target_h))

                self.lbl_video_display.configure(image=ctk_img, text="")
                self.lbl_video_display.image = ctk_img

                if self.video_cap and self.video_cap.isOpened():
                    curr_ms = current_ms if current_ms is not None else self.video_cap.get(cv2.CAP_PROP_POS_MSEC)
                    self.current_video_pos_ms = curr_ms
                    curr_sec = curr_ms / 1000.0

                    self._updating_slider = True
                    self.slider_video_seek.set(curr_sec)
                    self._updating_slider = False

                    curr_str = format_timestamp(curr_sec)[:8]
                    total_str = format_timestamp(self.video_duration_sec)[:8]
                    self.lbl_video_time.configure(text=f"⏱️ {curr_str} / {total_str}")
            except Exception as e:
                print("Update frame error:", e)

    def seek_video_ms(self, pos_ms):
        if not self.video_cap or not self.video_cap.isOpened():
            return
        was_playing = self.is_video_playing
        if was_playing:
            self.stop_video_playback(pause_only=True)

        try:
            self.video_cap.set(cv2.CAP_PROP_POS_MSEC, max(0, pos_ms))
            ret, frame = self.video_cap.read()
            if ret:
                self.update_video_frame(frame, current_ms=pos_ms)
        except Exception as e:
            print("Seek error:", e)

        if was_playing:
            self.start_video_playback()

    def on_video_seek_change(self, value):
        if self._updating_slider:
            return
        sec = float(value)
        self.seek_video_ms(sec * 1000.0)

    def step_video_seconds(self, delta_sec):
        if not self.video_cap or not self.video_cap.isOpened():
            return
        curr_ms = self.current_video_pos_ms
        new_ms = max(0, curr_ms + (delta_sec * 1000.0))
        self.seek_video_ms(new_ms)

    def toggle_video_play(self):
        if not self.video_cap or not self.video_cap.isOpened():
            messagebox.showinfo("ការជូនដំណឹង", "សូមជ្រើសរើសវីដេអូជាមុនសិន!")
            return

        if self.is_video_playing:
            self.stop_video_playback(pause_only=True)
        else:
            self.start_video_playback()

    def start_video_playback(self):
        if not self.video_cap or not self.video_cap.isOpened():
            return

        self.is_video_playing = True
        self.btn_video_play.configure(text="⏸️ Pause", fg_color="#f57c00")

        # ចាក់សំឡេងដើមពីពេលវេលាបច្ចុប្បន្ន
        if self.video_audio is not None:
            try:
                curr_ms = max(0, int(self.current_video_pos_ms))
                if curr_ms < len(self.video_audio):
                    audio_slice = self.video_audio[curr_ms:]
                    temp_wav = os.path.join(tempfile.gettempdir(), f"preview_playback_{int(time.time()*1000)}.wav")
                    audio_slice.export(temp_wav, format="wav")
                    winsound.PlaySound(temp_wav, winsound.SND_ASYNC | winsound.SND_FILENAME)
            except Exception as e:
                print("Audio playback sync error:", e)

        self.playback_wall_start = time.time()
        self.playback_pos_start_ms = self.current_video_pos_ms
        self.video_play_tick()

    def stop_video_playback(self, pause_only=False):
        self.is_video_playing = False
        winsound.PlaySound(None, winsound.SND_PURGE)
        self.btn_video_play.configure(text="▶️ Play (មានសំឡេង)", fg_color="#0288d1")

        if not pause_only and self.video_cap and self.video_cap.isOpened():
            self.seek_video_ms(0)

    def video_play_tick(self):
        if not self.is_video_playing or not self.video_cap or not self.video_cap.isOpened():
            return

        elapsed_ms = (time.time() - self.playback_wall_start) * 1000.0
        target_ms = self.playback_pos_start_ms + elapsed_ms

        if target_ms >= self.video_duration_sec * 1000.0:
            self.stop_video_playback(pause_only=True)
            return

        self.video_cap.set(cv2.CAP_PROP_POS_MSEC, target_ms)
        ret, frame = self.video_cap.read()
        if ret:
            self.update_video_frame(frame, current_ms=target_ms)
            self.after(30, self.video_play_tick)
        else:
            self.stop_video_playback(pause_only=True)

    def play_original_audio_segment(self, start_ms, end_ms):
        """ចាក់សំឡេងដើមនៃបន្ទាត់ Subtitle ជាក់លាក់មួយ"""
        if self.video_audio is None:
            return

        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
            duration = len(self.video_audio)
            s = max(0, int(start_ms))
            e = min(duration, max(s + 500, int(end_ms)))
            if s >= duration or s >= e:
                return

            chunk = self.video_audio[s:e]
            temp_wav = os.path.join(tempfile.gettempdir(), f"orig_chunk_{int(time.time()*1000)}.wav")
            chunk.export(temp_wav, format="wav")
            winsound.PlaySound(temp_wav, winsound.SND_ASYNC | winsound.SND_FILENAME)
        except Exception as e:
            print("Play original audio segment error:", e)

    def play_active_subtitle_original_audio(self):
        """ចាក់សំឡេងដើមនៃបន្ទាត់ Subtitle ដែលកំពុងសកម្ម"""
        if self.active_subtitle_index is None or not (0 <= self.active_subtitle_index < len(self.srt_entries)):
            messagebox.showinfo("ការជូនដំណឹង", "សូមជ្រើសរើសបន្ទាត់ Subtitle ណាមួយជាមុនសិន!")
            return

        if self.video_audio is None:
            messagebox.showwarning("ការជូនដំណឹង", "មិនទាន់មានសំឡេងដើមពីវីដេអូទេ។ សូមជ្រើសរើសវីដេអូជាមុនសិន!")
            return

        item = self.srt_entries[self.active_subtitle_index]
        self.play_original_audio_segment(item["start"], item["end"])

    def auto_detect_single_line_voice(self):
        """Auto Detect សំឡេងតួអង្គ (ប្រុស ឬ ស្រី) សម្រាប់បន្ទាត់ដែលកំពុងសកម្ម"""
        if self.active_subtitle_index is None or not (0 <= self.active_subtitle_index < len(self.srt_entries)):
            messagebox.showinfo("ការជូនដំណឹង", "សូមជ្រើសរើសបន្ទាត់ Subtitle ណាមួយជាមុនសិន!")
            return

        if self.video_audio is None:
            messagebox.showwarning("ការជូនដំណឹង", "មិនទាន់មានសំឡេងដើមពីវីដេអូសម្រាប់វិភាគទេ។ សូមផ្ទុកវីដេអូជាមុនសិន!")
            return

        item = self.srt_entries[self.active_subtitle_index]
        start_ms = item["start"]
        end_ms = item["end"]

        chunk = self.video_audio[start_ms:end_ms]
        voice_res, f0 = detect_voice_gender(chunk)
        if voice_res:
            item["combo"].set(voice_res)
            self.lbl_active_hint.configure(
                text=f"🤖 បាន Detect បន្ទាត់ #{self.active_subtitle_index+1}៖ {voice_res} ({f0:.1f} Hz)",
                text_color="#69f0ae"
            )
            self.lbl_dub_status.configure(
                text=f"🤖 Auto Detect បន្ទាត់ #{self.active_subtitle_index+1}៖ {voice_res} ({f0:.1f} Hz)",
                text_color="#4caf50"
            )
        else:
            self.lbl_dub_status.configure(
                text=f"⚠️ បន្ទាត់ #{self.active_subtitle_index+1} មិនអាចកត់សម្គាល់សំឡេងបានច្បាស់ (ស្ងាត់ ឬតន្ត្រី)",
                text_color="#ffb74d"
            )

    def auto_detect_all_voices_thread(self):
        """Auto Detect សំឡេងតួអង្គ (ប្រុស ឬ ស្រី) សម្រាប់គ្រប់បន្ទាត់ Subtitle ទាំងអស់"""
        if not self.srt_entries:
            messagebox.showwarning("ការជូនដំណឹង", "មិនទាន់មានទិន្នន័យ Subtitle ទេ។ សូម Upload .SRT ជាមុនសិន!")
            return

        if self.video_audio is None:
            messagebox.showwarning("ការជូនដំណឹង", "មិនទាន់មានសំឡេងដើមពីវីដេអូសម្រាប់វិភាគទេ។ សូមជ្រើសរើសវីដេអូជាមុនសិន!")
            return

        self.btn_auto_detect_all.configure(state="disabled", text="⏳ កំពុង Detect...")
        self.prog_dub.set(0)

        male_count = 0
        female_count = 0
        unknown_count = 0
        total = len(self.srt_entries)

        try:
            for idx, item in enumerate(self.srt_entries):
                start_ms = item["start"]
                end_ms = item["end"]
                chunk = self.video_audio[start_ms:end_ms]

                voice_res, f0 = detect_voice_gender(chunk)
                if voice_res:
                    item["combo"].set(voice_res)
                    if "Piseth" in voice_res:
                        male_count += 1
                    else:
                        female_count += 1
                else:
                    unknown_count += 1

                prog = (idx + 1) / total
                self.prog_dub.set(prog)
                self.lbl_dub_status.configure(
                    text=f"🤖 កំពុង Auto Detect សំឡេងតួ... {idx+1}/{total} ({(prog*100):.0f}%) | 👨 {male_count} | 👩 {female_count}",
                    text_color="#ce93d8"
                )

            self.lbl_dub_status.configure(
                text=f"✅ Auto Detect រួចរាល់ {total} បន្ទាត់! (👨 ប្រុស៖ {male_count} | 👩 ស្រី៖ {female_count})",
                text_color="#4caf50"
            )
            messagebox.showinfo(
                "Auto Detect ជោគជ័យ",
                f"បានវិភាគ និងកំណត់សំឡេងតួអង្គដោយស្វ័យប្រវត្តជោគជ័យ!\n\n"
                f"• ចំនួនបន្ទាត់សរុប៖ {total}\n"
                f"• សំឡេងប្រុស (Piseth)៖ {male_count} បន្ទាត់\n"
                f"• សំឡេងស្រី (Sreymom)៖ {female_count} បន្ទាត់\n"
                f"• មិនច្បាស់ (រក្សានៅដដែល)៖ {unknown_count} បន្ទាត់"
            )
        except Exception as e:
            messagebox.showerror("កំហុស", f"មានបញ្ហាក្នុងការ Auto Detect៖ {str(e)}")
        finally:
            self.btn_auto_detect_all.configure(state="normal", text="🤖 Auto Detect សំឡេងតួទាំងអស់")

    def jump_to_subtitle(self, index, start_ms):
        self.active_subtitle_index = index

        # Highlight active row visually
        for i, item in enumerate(self.srt_entries):
            if i == index:
                item["row_frame"].configure(border_width=2, border_color="#00e676")
                item["jump_btn"].configure(fg_color="#00897b")
            else:
                item["row_frame"].configure(border_width=0)
                item["jump_btn"].configure(fg_color="#263238")

        # Update hint text on Left Panel
        current_text = self.srt_entries[index]["entry"].get().strip()
        voice_now = self.srt_entries[index]["combo"].get()
        short_text = (current_text[:28] + '...') if len(current_text) > 28 else current_text
        self.lbl_active_hint.configure(
            text=f"👉 កំពុងមើលបន្ទាត់ #{index+1} [{format_timestamp(start_ms/1000)[:8]}]\nអត្ថបទ៖ \"{short_text}\"\nសំឡេង៖ {voice_now}",
            text_color="#81c784"
        )

        # Seek video to frame
        if self.video_cap and self.video_cap.isOpened():
            if self.is_video_playing:
                self.stop_video_playback(pause_only=True)
            self.seek_video_ms(start_ms)

            # ចាក់សំឡេងដើមនៃបន្ទាត់នេះ ប្រសិនបើបើក Option Auto-play
            if self.chk_autoplay_orig_var.get() and self.video_audio is not None:
                end_ms = self.srt_entries[index]["end"]
                self.play_original_audio_segment(start_ms, end_ms)
        else:
            self.lbl_dub_status.configure(
                text=f"📌 បានជ្រើសបន្ទាត់ #{index+1} [{format_timestamp(start_ms/1000)[:8]}] - ចុច '📂 ជ្រើសរើសវីដេអូ' នៅខាងឆ្វេងដើម្បី Preview",
                text_color="#ffb74d"
            )

    def set_active_row_voice(self, voice_name):
        if self.active_subtitle_index is not None and 0 <= self.active_subtitle_index < len(self.srt_entries):
            item = self.srt_entries[self.active_subtitle_index]
            item["combo"].set(voice_name)
            start_ms = item["start"]
            current_text = item["entry"].get().strip()
            short_text = (current_text[:28] + '...') if len(current_text) > 28 else current_text
            self.lbl_active_hint.configure(
                text=f"✅ បានកំណត់បន្ទាត់ #{self.active_subtitle_index+1} ជា៖ {voice_name}\nអត្ថបទ៖ \"{short_text}\"",
                text_color="#69f0ae"
            )
            self.lbl_dub_status.configure(
                text=f"✅ បន្ទាត់ #{self.active_subtitle_index + 1} ត្រូវបានកំណត់ជា៖ {voice_name}",
                text_color="#4caf50"
            )
        else:
            messagebox.showinfo("ការជូនដំណឹង", "សូមចុចលើប៊ូតុង 👁️ នៃបន្ទាត់ Subtitle ណាមួយជាមុនសិន!")

    def on_closing(self):
        self.is_video_playing = False
        winsound.PlaySound(None, winsound.SND_PURGE)
        if self.video_cap:
            try:
                self.video_cap.release()
            except:
                pass
            self.video_cap = None
        self.destroy()

    def load_srt_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("SRT Files", "*.srt"), ("All Files", "*.*")])
        if not filepath:
            return

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        self.parse_and_display_srt(content, source_name=os.path.basename(filepath))
        # ប្រសិនបើមានជ្រើសរើសវីដេអូក្នុង Tab 1 ស្រាប់ ផ្ទុកចូល Video Preview ដោយស្វ័យប្រវត្តិ
        if not self.video_cap and self.selected_video_path and os.path.exists(self.selected_video_path):
            self.load_video_for_preview(self.selected_video_path)

    def parse_and_display_srt(self, srt_content, source_name="ឯកសារ SRT"):
        self.lbl_srt_name.configure(text=source_name, text_color="#4caf50")

        # សម្អាតចាស់
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.srt_entries.clear()
        self.active_subtitle_index = None

        # Regex រក Timecode និង អត្ថបទ
        pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n([\s\S]*?)(?=\n\s*\d+\s*\n|\Z)')
        matches = pattern.findall(srt_content)

        if not matches:
            # Regex ជំនួសករណី formatting ខុសគ្នាបន្តិច
            pattern_alt = re.compile(r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n([\s\S]*?)(?=\n{2,}|\Z)')
            alt_matches = pattern_alt.findall(srt_content)
            matches = [(str(i+1), m[0], m[1], m[2]) for i, m in enumerate(alt_matches)]

        for idx, start_t, end_t, text in matches:
            clean_text = " ".join([l.strip() for l in text.strip().splitlines() if l.strip()])
            if not clean_text:
                continue

            current_idx = len(self.srt_entries)
            start_ms = parse_time(start_t)
            end_ms = parse_time(end_t)

            row_frame = ctk.CTkFrame(self.scroll_frame)
            row_frame.pack(fill="x", padx=4, pady=3)

            # ប៊ូតុង Jump / Preview វីដេអូ & ស្តាប់សំឡេងដើម
            btn_jump = ctk.CTkButton(
                row_frame, 
                text=f"👁️ #{idx} [{start_t[:8]}]", 
                width=110, 
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#263238",
                hover_color="#37474f",
                command=lambda i=current_idx, s=start_ms: self.jump_to_subtitle(i, s)
            )
            btn_jump.pack(side="left", padx=2)

            # ប្រអប់អត្ថបទ (អាចកែប្រែបាន)
            txt_entry = ctk.CTkEntry(row_frame, font=ctk.CTkFont(family=KHMER_FONT_FAMILY, size=13))
            txt_entry.insert(0, clean_text)
            txt_entry.pack(side="left", padx=3, fill="x", expand=True)
            txt_entry.bind("<FocusIn>", lambda e, i=current_idx, s=start_ms: self.jump_to_subtitle(i, s))
            add_context_menu(txt_entry)

            # Dropdown ជ្រើសរើសសំឡេងតួអង្គ
            combo_voice = ctk.CTkComboBox(
                row_frame, 
                values=list(VOICE_OPTIONS.keys()), 
                width=165
            )
            default_voice = "សំឡេងប្រុស (Piseth)" if current_idx % 2 == 0 else "សំឡេងស្រី (Sreymom)"
            combo_voice.set(default_voice)
            combo_voice.pack(side="left", padx=2)

            # ប៊ូតុង Preview ស្តាប់សំឡេងដើម (Original Voice Snippet)
            btn_play_orig = ctk.CTkButton(
                row_frame, 
                text="🎧 ដើម", 
                width=55,
                font=ctk.CTkFont(size=11),
                fg_color="#37474f",
                hover_color="#455a64",
                command=lambda s=start_ms, e=end_ms: self.play_original_audio_segment(s, e)
            )
            btn_play_orig.pack(side="left", padx=2)

            # ប៊ូតុង Preview ស្តាប់សំឡេង AI (Edge-TTS)
            btn_play_single = ctk.CTkButton(
                row_frame, 
                text="🔊 AI", 
                width=48,
                font=ctk.CTkFont(size=11),
                fg_color="#00695c",
                hover_color="#004d40",
                command=lambda t=txt_entry, c=combo_voice: threading.Thread(
                    target=self.play_single_entry_preview, 
                    args=(t.get().strip(), c.get()), 
                    daemon=True
                ).start()
            )
            btn_play_single.pack(side="left", padx=2)

            self.srt_entries.append({
                "start": start_ms,
                "end": end_ms,
                "start_str": start_t,
                "entry": txt_entry,
                "combo": combo_voice,
                "row_frame": row_frame,
                "jump_btn": btn_jump
            })

        self.lbl_srt_count.configure(text=f"ចំនួនបន្ទាត់៖ {len(self.srt_entries)}")
        if self.srt_entries:
            self.lbl_dub_status.configure(
                text=f"បានផ្ទុក {len(self.srt_entries)} បន្ទាត់។ អ្នកអាចចុច '🤖 Auto Detect សំឡេងតួទាំងអស់' ឬ '🌐 បកប្រែជាភាសាខ្មែរទាំងអស់'។", 
                text_color="#90caf9"
            )
            # លោតទៅកាន់បន្ទាត់ទី ១ ជាស្វ័យប្រវត្តិ
            self.jump_to_subtitle(0, self.srt_entries[0]["start"])

    def set_all_voices(self, voice_name):
        for item in self.srt_entries:
            item["combo"].set(voice_name)

    def set_alternate_voices(self):
        for i, item in enumerate(self.srt_entries):
            voice = "សំឡេងប្រុស (Piseth)" if i % 2 == 0 else "សំឡេងស្រី (Sreymom)"
            item["combo"].set(voice)

    def play_single_entry_preview(self, text, voice_name):
        if not text:
            return
        voice_code = VOICE_OPTIONS.get(voice_name, "km-KH-PisethNeural")
        temp_mp3 = os.path.join(tempfile.gettempdir(), f"preview_{int(time.time()*1000)}.mp3")
        temp_wav = os.path.join(tempfile.gettempdir(), f"preview_{int(time.time()*1000)}.wav")
        try:
            async def _gen():
                comm = edge_tts.Communicate(text, voice_code)
                await comm.save(temp_mp3)
            asyncio.run(_gen())

            if os.path.exists(temp_mp3):
                audio = AudioSegment.from_file(temp_mp3)
                audio.export(temp_wav, format="wav")
                winsound.PlaySound(temp_wav, winsound.SND_ASYNC | winsound.SND_FILENAME)
        except Exception as e:
            print("Preview error:", e)

    def translate_all_entries_thread(self):
        if not self.srt_entries:
            messagebox.showwarning("ការជូនដំណឹង", "សូម Upload ឬបញ្ចូល Subtitle ជាមុនសិន!")
            return

        self.btn_trans_all.configure(state="disabled", text="⏳ កំពុងបកប្រែ...")
        self.prog_dub.set(0)
        total = len(self.srt_entries)

        try:
            for idx, item in enumerate(self.srt_entries):
                current_text = item["entry"].get().strip()
                if current_text:
                    translated = translate_to_khmer(current_text)
                    # Update GUI Entry safely
                    item["entry"].delete(0, "end")
                    item["entry"].insert(0, translated)

                prog = (idx + 1) / total
                self.prog_dub.set(prog)
                self.lbl_dub_status.configure(
                    text=f"🌐 កំពុងបកប្រែជាភាសាខ្មែរ... {idx + 1}/{total} ({(prog*100):.0f}%)",
                    text_color="#0288d1"
                )

            self.lbl_dub_status.configure(text="✅ បានបកប្រែជាភាសាខ្មែរគ្រប់បន្ទាត់រួចរាល់!", text_color="#4caf50")
            messagebox.showinfo("ជោគជ័យ", "បានបកប្រែអត្ថបទទាំងអស់ជាភាសាខ្មែររួចរាល់!")
        except Exception as e:
            messagebox.showerror("កំហុស", f"មានបញ្ហាក្នុងការបកប្រែ៖ {str(e)}")
        finally:
            self.btn_trans_all.configure(state="normal", text="🌐 បកប្រែជាភាសាខ្មែរទាំងអស់")

    def process_srt_thread(self):
        if not self.srt_entries:
            messagebox.showwarning("ការជូនដំណឹង", "សូម Upload ឯកសារ SRT ជាមុនសិន!")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".mp3", 
            filetypes=[("MP3 Files", "*.mp3")]
        )
        if not save_path:
            return

        self.btn_process_srt.configure(state="disabled", text="⏳ កំពុង Render សំឡេង...")
        self.prog_dub.set(0)

        async def generate_chunk(text, voice_code, temp_file):
            communicate = edge_tts.Communicate(text, voice_code)
            await communicate.save(temp_file)

        try:
            total_items = len(self.srt_entries)
            # រយៈពេលសរុបនៃវីដេអូ ឬ Subtitle ចុងក្រោយ
            total_duration = self.srt_entries[-1]["end"] + 4000
            final_audio = AudioSegment.silent(duration=total_duration)

            for i, item in enumerate(self.srt_entries):
                text_to_speak = item["entry"].get().strip()
                if not text_to_speak:
                    continue

                voice_name = item["combo"].get()
                voice_code = VOICE_OPTIONS.get(voice_name, "km-KH-PisethNeural")
                temp_chunk = os.path.join(tempfile.gettempdir(), f"dub_chunk_{i}_{int(time.time())}.mp3")

                self.lbl_dub_status.configure(
                    text=f"🎙️ កំពុងបញ្ចេញសំឡេងបន្ទាត់ទី {i+1}/{total_items} ({voice_name})...",
                    text_color="#ff9800"
                )

                asyncio.run(generate_chunk(text_to_speak, voice_code, temp_chunk))

                if os.path.exists(temp_chunk):
                    chunk_audio = AudioSegment.from_file(temp_chunk)
                    # ដាក់សំឡេងឱ្យចំពេលវេលា Subtitle ដើម
                    final_audio = final_audio.overlay(chunk_audio, position=item["start"])
                    try:
                        os.remove(temp_chunk)
                    except:
                        pass

                self.prog_dub.set((i + 1) / total_items)

            self.lbl_dub_status.configure(text="💾 កំពុង Export ឯកសារ MP3...", text_color="#0288d1")
            final_audio.export(save_path, format="mp3")

            self.prog_dub.set(1.0)
            self.lbl_dub_status.configure(text="✅ Render សំឡេងជោគជ័យពេញលេញ!", text_color="#4caf50")
            
            res = messagebox.askyesno(
                "ជោគជ័យ", 
                f"បានបង្កើតសំឡេង SRT រួចរាល់នៅ៖\n{save_path}\n\nតើអ្នកចង់ចាក់ស្តាប់ភ្លាមៗដែរឬទេ?"
            )
            if res:
                os.startfile(save_path)

        except Exception as e:
            self.lbl_dub_status.configure(text=f"❌ មានកំហុស៖ {str(e)}", text_color="#f44336")
            messagebox.showerror("បញ្ហា", f"កើតមានកំហុសអំឡុងពេល Render៖ {str(e)}")
        finally:
            self.btn_process_srt.configure(
                state="normal", 
                text="🚀 Render ចេញជាសំឡេងនិយាយតម្រង់តាមពេលវេលា (Export MP3)"
            )

    # =========================================================================
    # ផ្ទាំងទី ៣៖ TEXT TO VOICE (បម្លែងជាសំឡេងភ្លាមៗ)
    # =========================================================================
    def setup_text2voice_tab(self):
        lbl = ctk.CTkLabel(
            self.tab_text2voice, 
            text="✍️ វាយ ឬចម្លងអត្ថបទចូល ដើម្បីបម្លែងជាសំឡេងភ្លាមៗ៖", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl.pack(anchor="w", padx=15, pady=(15, 5))

        self.txt_tts_input = ctk.CTkTextbox(self.tab_text2voice, height=220, font=ctk.CTkFont(family=KHMER_FONT_FAMILY, size=13))
        self.txt_tts_input.pack(fill="both", expand=True, padx=15, pady=5)
        self.txt_tts_input.insert("0.0", "សូមស្វាគមន៍មកកាន់ប្រព័ន្ធ AI បញ្ចូលសំឡេងជាភាសាខ្មែរ! អ្នកអាចជ្រើសរើសសំឡេងប្រុស (Piseth) ឬសំឡេងស្រី (Sreymom) ដើម្បីបម្លែងជាសំឡេងនិយាយភ្លាមៗ។")
        add_context_menu(self.txt_tts_input)

        # ប្រអប់កំណត់សំឡេង និងល្បឿន
        settings_box = ctk.CTkFrame(self.tab_text2voice)
        settings_box.pack(fill="x", padx=15, pady=10)

        # ជ្រើសរើសសំឡេង
        lbl_v = ctk.CTkLabel(settings_box, text="ជ្រើសរើសសំឡេង (Voice):", font=ctk.CTkFont(weight="bold"))
        lbl_v.grid(row=0, column=0, padx=15, pady=15, sticky="w")

        self.combo_tts_voice = ctk.CTkComboBox(
            settings_box, 
            values=list(VOICE_OPTIONS.keys()), 
            width=230
        )
        self.combo_tts_voice.set("សំឡេងប្រុស (Piseth)")
        self.combo_tts_voice.grid(row=0, column=1, padx=10, pady=15, sticky="w")

        # ល្បឿនអាន
        self.lbl_speed = ctk.CTkLabel(settings_box, text="ល្បឿននិយាយ៖ ធម្មតា (0%)")
        self.lbl_speed.grid(row=0, column=2, padx=(20, 10), pady=15, sticky="w")

        self.slider_speed = ctk.CTkSlider(
            settings_box, 
            from_=-50, 
            to=50, 
            number_of_steps=20, 
            width=180,
            command=self.on_speed_slider_change
        )
        self.slider_speed.set(0)
        self.slider_speed.grid(row=0, column=3, padx=10, pady=15, sticky="w")

        # Status Label
        self.lbl_tts_status = ctk.CTkLabel(self.tab_text2voice, text="ត្រៀមរួចរាល់...", text_color="gray")
        self.lbl_tts_status.pack(padx=15, pady=2)

        # ប៊ូតុងសកម្មភាព (Play Now, Stop, Export MP3)
        btn_frame = ctk.CTkFrame(self.tab_text2voice, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=10)

        self.btn_tts_play = ctk.CTkButton(
            btn_frame, 
            text="▶️ ស្តាប់សំឡេងភ្លាមៗ (Play Now)", 
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#0288d1",
            hover_color="#0277bd",
            command=lambda: threading.Thread(target=self.play_tts_instant_thread, daemon=True).start()
        )
        self.btn_tts_play.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.btn_tts_stop = ctk.CTkButton(
            btn_frame, 
            text="⏹️ បញ្ឈប់ (Stop)", 
            height=42,
            width=110,
            fg_color="#d32f2f",
            hover_color="#c62828",
            command=self.stop_tts_playback
        )
        self.btn_tts_stop.pack(side="left", padx=5)

        self.btn_tts_export = ctk.CTkButton(
            btn_frame, 
            text="💾 រក្សាទុកជា MP3 (Export)", 
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            command=lambda: threading.Thread(target=self.process_tts_export_thread, daemon=True).start()
        )
        self.btn_tts_export.pack(side="right", fill="x", expand=True, padx=(5, 0))

    def on_speed_slider_change(self, value):
        val = int(value)
        sign = "+" if val > 0 else ""
        self.lbl_speed.configure(text=f"ល្បឿននិយាយ៖ {sign}{val}%")

    def stop_tts_playback(self):
        winsound.PlaySound(None, winsound.SND_PURGE)
        self.lbl_tts_status.configure(text="បានបញ្ឈប់ការចាក់សំឡេង", text_color="gray")

    def play_tts_instant_thread(self):
        text = self.txt_tts_input.get("0.0", "end").strip()
        if not text:
            messagebox.showwarning("ការជូនដំណឹង", "សូមវាយបញ្ចូលអត្ថបទជាមុនសិន!")
            return

        self.btn_tts_play.configure(state="disabled", text="⏳ កំពុងបង្កើតសំឡេង...")
        self.lbl_tts_status.configure(text="🎙️ កំពុងដំណើរការបង្កើតសំឡេង...", text_color="#ff9800")

        temp_mp3 = os.path.join(tempfile.gettempdir(), f"instant_tts_{int(time.time()*1000)}.mp3")
        temp_wav = os.path.join(tempfile.gettempdir(), f"instant_tts_{int(time.time()*1000)}.wav")

        try:
            voice_name = self.combo_tts_voice.get()
            voice_code = VOICE_OPTIONS.get(voice_name, "km-KH-PisethNeural")
            
            speed_val = int(self.slider_speed.get())
            rate_str = f"{'+' if speed_val >= 0 else ''}{speed_val}%"

            async def _run():
                comm = edge_tts.Communicate(text, voice_code, rate=rate_str)
                await comm.save(temp_mp3)

            asyncio.run(_run())

            if os.path.exists(temp_mp3):
                self.lbl_tts_status.configure(text=f"🔊 កំពុងចាក់សំឡេង ({voice_name})...", text_color="#4caf50")
                audio = AudioSegment.from_file(temp_mp3)
                audio.export(temp_wav, format="wav")
                winsound.PlaySound(temp_wav, winsound.SND_ASYNC | winsound.SND_FILENAME)

        except Exception as e:
            self.lbl_tts_status.configure(text=f"❌ កំហុស៖ {str(e)}", text_color="#f44336")
            messagebox.showerror("កំហុស", f"មិនអាចបង្កើតសំឡេងបានទេ៖ {str(e)}")
        finally:
            self.btn_tts_play.configure(state="normal", text="▶️ ស្តាប់សំឡេងភ្លាមៗ (Play Now)")

    def process_tts_export_thread(self):
        text = self.txt_tts_input.get("0.0", "end").strip()
        if not text:
            messagebox.showwarning("ការជូនដំណឹង", "សូមវាយបញ្ចូលអត្ថបទជាមុនសិន!")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".mp3", 
            filetypes=[("MP3 Files", "*.mp3")]
        )
        if not save_path:
            return

        self.btn_tts_export.configure(state="disabled", text="⏳ កំពុងរក្សាទុក...")
        self.lbl_tts_status.configure(text="💾 កំពុងបង្កើត និងរក្សាទុកឯកសារ MP3...", text_color="#ff9800")

        try:
            voice_name = self.combo_tts_voice.get()
            voice_code = VOICE_OPTIONS.get(voice_name, "km-KH-PisethNeural")
            speed_val = int(self.slider_speed.get())
            rate_str = f"{'+' if speed_val >= 0 else ''}{speed_val}%"

            async def run_tts():
                comm = edge_tts.Communicate(text, voice_code, rate=rate_str)
                await comm.save(save_path)

            asyncio.run(run_tts())
            self.lbl_tts_status.configure(text="✅ រក្សាទុក MP3 ជោគជ័យ!", text_color="#4caf50")
            
            res = messagebox.askyesno(
                "ជោគជ័យ", 
                f"បានរក្សាទុកសំឡេងជោគជ័យនៅ៖\n{save_path}\n\nតើអ្នកចង់បើកស្តាប់ភ្លាមៗដែរឬទេ?"
            )
            if res:
                os.startfile(save_path)
        except Exception as e:
            self.lbl_tts_status.configure(text=f"❌ កំហុស៖ {str(e)}", text_color="#f44336")
            messagebox.showerror("បញ្ហា", f"កើតមានកំហុស៖ {str(e)}")
        finally:
            self.btn_tts_export.configure(state="normal", text="💾 រក្សាទុកជា MP3 (Export)")

if __name__ == "__main__":
    app = SubtitleDubberApp()
    app.mainloop()