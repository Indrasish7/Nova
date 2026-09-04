@echo off
title Nova AI Launcher (Administrator)
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% == 0 (
    echo [Nova] Running with Administrator privileges.
    echo [Nova] Starting Nova AI Launcher...
    .venv\Scripts\python.exe main.py
) else (
    echo [Nova] Requesting Administrator privileges (UAC)...
    powershell -Command "Start-Process cmd -ArgumentList '/k \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)
