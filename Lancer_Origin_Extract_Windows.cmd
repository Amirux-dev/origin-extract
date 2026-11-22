@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
  py -3 -m venv "%~dp0.venv"
  if errorlevel 1 goto error
)
"%~dp0.venv\Scripts\python.exe" -c "import PySide6.QtWidgets, pywinauto, win32clipboard" >nul 2>&1
if errorlevel 1 (
  "%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 goto error
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0lancer_origin_extract.py"
exit /b 0
:error
echo Le lancement a echoue. Verifiez que Python 3.10 ou plus recent est installe.
pause
exit /b 1
