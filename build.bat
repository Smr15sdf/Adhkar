@echo off
cd /d "%~dp0"
echo ===== Installing requirements =====
python -m pip install -r requirements.txt
if errorlevel 1 goto err
echo.
echo ===== Building EXE =====
python -m PyInstaller --noconsole --onefile --clean --name Adhkar --icon assets\icon.ico --collect-data tzdata --add-data "fonts;fonts" --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtPdf adhkar_app.py
if errorlevel 1 goto err
echo.
echo DONE. Your file is: dist\Adhkar.exe
pause
exit /b 0
:err
echo.
echo ERROR: something failed. Send the message above to Claude.
pause
exit /b 1
