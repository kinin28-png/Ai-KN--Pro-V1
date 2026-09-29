# Ai-KN--Pro-V1
## AI KN បកប្រែនិងបង្កើតសម្លេង (AI Khmer Dubbing & Voiceover Studio Pro-V1)

កម្មវិធី AI សម្រាប់បម្លែងវីដេអូទៅជាអក្សរ (Speech-to-Text / SRT), បញ្ចូលសំឡេងនិយាយស្វ័យប្រវត្តិតាមតួអង្គ (AI Video Dubbing / Voiceover), និង Text-to-Speech (TTS) ជាភាសាខ្មែរ និងអង់គ្លេស។

---

## 🌟 លក្ខណៈពិសេសសំខាន់ៗ (Features)

### 1. 🎥 Video / Link to SRT
- អាចបញ្ចូល Link វីដេអូពី YouTube, Web ឬជ្រើសរើសឯកសារវីដេអូក្នុងកុំព្យូទ័រ
- បម្លែងសំឡេងក្នុងវីដេអូទៅជា Subtitle (.SRT) ដោយប្រើ **OpenAI Whisper AI**
- កំណត់ម៉ូឌែល Whisper (Tiny, Base, Small, Medium)
- កំណត់ភាសាស្វ័យប្រវត្តិ (Auto Detect) ឬជ្រើសរើសភាសាជាក់លាក់

### 2. 🎬 SRT to Voice (បញ្ចូលសំឡេងតាមតួអង្គ)
- **Video Preview ស៊ីគ្នាជាមួយ Subtitle:** មើលវីដេអូ និងពេលវេលាជាក់ស្តែង
- **Synchronized Original Audio:** ស្តាប់សំឡេងដើមនៃឈុតនីមួយៗបានច្បាស់ល្អ
- **Auto Detect សំឡេងតួអង្គ (Male/Female):** AI វិភាគកម្រិត Pitch (F0) នៃសំឡេងដើម ដើម្បីកំណត់សំឡេងតួអង្គប្រុស ឬស្រីដោយស្វ័យប្រវត្តិ
- ជ្រើសរើសសំឡេងតួអង្គខ្មែរ (Piseth, Sreymom) ឬសំឡេងបរទេស
- Render ចេញជាសំឡេងនិយាយតម្រង់តាម Timecode នៃវីដេអូដើម (.MP3)

### 3. 📝 Text to Voice (អានអត្ថបទភ្លាមៗ)
- វាយ ឬ Paste អត្ថបទជាភាសាខ្មែរ
- ជ្រើសរើសសំឡេងប្រុស (Piseth) ឬសំឡេងស្រី (Sreymom)
- កែតម្រូវល្បឿននិយាយ (Speed Slider)
- ចុចស្តាប់ភ្លាមៗ (Play Now) ឬ Export ជាឯកសារ .MP3

---

## 🚀 របៀបដំឡើង និងដំណើរការ (Installation & Usage)

### ១. Clone Repository
```bash
git clone https://github.com/kinin28-png/Ai-KN--Pro-V1.git
cd "Ai-KN--Pro-V1"
```

### ២. បង្កើត Virtual Environment
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
```

### ៣. ដំឡើងបណ្ណាល័យចាំបាច់ (Install Requirements)
```bash
pip install -r requirements.txt
```

> **ចំណាំ:** កម្មវិធីតម្រូវឱ្យមាន `ffmpeg` ដំឡើងក្នុងប្រព័ន្ធកុំព្យូទ័រ (System PATH) សម្រាប់ដំណើរការ Whisper, PyDub និង OpenCV។

### ៤. បើកដំណើរការកម្មវិធី
```bash
python app.py
```

---

## 🛠️ បច្ចេកវិទ្យាប្រើប្រាស់ (Tech Stack)
- **GUI Framework:** CustomTkinter, Tkinter
- **Speech-to-Text:** OpenAI Whisper
- **Voice Synthesis:** Edge-TTS (Microsoft Neural Voices)
- **Audio Processing:** PyDub, SoundFile, NumPy
- **Video & Vision:** OpenCV (cv2), Pillow (PIL)
- **Downloader:** yt-dlp
