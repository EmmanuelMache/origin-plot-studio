@echo off
rem Installs the Python packages XRD Scan Generator needs (once).
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt
if errorlevel 1 (echo. & echo Installation failed: see the messages above. & pause & exit /b 1)
echo.
echo Done. Start the program with "Start XRD Scan Generator.bat".
pause
