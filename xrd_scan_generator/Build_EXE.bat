@echo off
rem Builds dist\XRD Scan Generator\XRD Scan Generator.exe (no console window).
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -m pip install -r requirements.txt pyinstaller
%PY% -m PyInstaller --noconfirm --clean xrd_scan_generator.spec
if errorlevel 1 (echo. & echo Build failed: see the messages above. & pause & exit /b 1)
echo.
echo Built: dist\XRD Scan Generator\XRD Scan Generator.exe
pause
