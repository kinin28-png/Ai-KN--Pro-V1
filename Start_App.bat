@echo off
chcp 65001 >nul
title AI KN បញ្ចូលសំឡេង Pro-V1

echo ========================================================
echo   AI KN បញ្ចូលសំឡេង Pro-V1 (Voiceover Studio)
echo ========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo កំពុងបើកដំណើរការកម្មវិធី...
    start "" ".venv\Scripts\pythonw.exe" app.py
) else (
    echo រកមិនឃើញ .venv! កំពុងដំណើរការជាមួយ Python ក្នុងម៉ាស៊ីន...
    python app.py
)
