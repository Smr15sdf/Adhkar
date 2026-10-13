@echo off
cd /d "%~dp0"
if "%~1"=="" goto usage
rem Isolated test mode: separate data folder + fake clock that starts at the given time
set "ADHKAR_DATA_DIR=%TEMP%\adhkar_test_data"
set "ADHKAR_FAKE_NOW=%~1"
echo Data folder : %ADHKAR_DATA_DIR%
echo Fake clock  : %ADHKAR_FAKE_NOW%  (it keeps ticking in real time)
python adhkar_app.py
exit /b 0
:usage
echo Usage:  test_mode.bat 2026-10-11T15:10:00+03:00
echo Pick a time a few minutes BEFORE a prayer pre-notice to watch the full cycle.
echo Tip: open "Prayer times" settings first to see today prayer times, then rerun with a closer time.
pause
exit /b 1
