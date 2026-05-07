@echo off
cd /d "%~dp0"
set PYTHON_EXE=C:\Users\11447\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" init_db.py
) else (
  python init_db.py
)
