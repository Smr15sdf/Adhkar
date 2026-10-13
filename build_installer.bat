@echo off
cd /d "%~dp0"
echo ===== Step 1/3: building Adhkar.exe =====
python -m pip install -r requirements.txt
if errorlevel 1 goto err
python -m PyInstaller --noconsole --onefile --clean --name Adhkar --icon assets\icon.ico --collect-data tzdata --add-data "fonts;fonts" --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtPdf adhkar_app.py
if errorlevel 1 goto err
if not exist "dist\Adhkar.exe" goto err
echo.
echo ===== Step 2/3: looking for Inno Setup =====
call :findiscc
if defined ISCC goto compile
echo Inno Setup 6 was not found.
where winget >nul 2>&1
if errorlevel 1 goto manual
choice /m "Install Inno Setup now using winget"
if errorlevel 2 goto manual
winget install -e --id JRSoftware.InnoSetup
call :findiscc
if defined ISCC goto compile
:manual
echo.
echo Please install Inno Setup 6 from https://jrsoftware.org/isdl.php
echo then run this file again.
pause
exit /b 1
:compile
echo.
echo ===== Step 3/3: building the installer =====
"%ISCC%" adhkar_setup.iss
if errorlevel 1 goto err
echo.
echo DONE. Your installer is: installer_output\Adhkar_Setup.exe
pause
exit /b 0
:findiscc
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
exit /b 0
:err
echo.
echo ERROR: something failed. Send the message above to Claude.
pause
exit /b 1
