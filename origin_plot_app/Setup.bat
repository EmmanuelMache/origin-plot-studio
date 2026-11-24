@echo off
title Origin Plot Studio - Setup
cd /d "%~dp0"
rem Setup needs Python. If it is there, the installer window opens and this window closes.
where py 1>nul 2>nul
if errorlevel 1 goto nopython
where pyw 1>nul 2>nul
if errorlevel 1 (
  py -3 setup.pyw
) else (
  start "" pyw -3 setup.pyw
)
exit /b 0

:nopython
echo.
echo  Origin Plot Studio needs Python 3, which is not on this computer yet.
echo.
where winget 1>nul 2>nul
if errorlevel 1 goto manual
set /p ANSWER= Install Python now with Windows' own installer (winget)? [Y/N] 
if /i not "%ANSWER%"=="Y" goto manual
winget install -e --id Python.Python.3.12 --scope user
echo.
echo  When Python is installed, close this window and double-click Setup.bat again.
pause
exit /b 0

:manual
echo  Install Python 3 from https://www.python.org/downloads/
echo  (tick "Add python.exe to PATH" in its first window), then double-click Setup.bat again.
echo.
pause
exit /b 1
