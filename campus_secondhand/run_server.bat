@echo off
cd /d "%~dp0"
set PYTHON_EXE=C:\Users\11447\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" -B app.py
) else (
  python -B app.py
)
