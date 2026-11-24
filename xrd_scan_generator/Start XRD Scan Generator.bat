@echo off
rem Starts XRD Scan Generator without a console window.
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw "%~dp0run.pyw" %* & exit /b)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0run.pyw" %* & exit /b)
echo Python was not found. Install Python 3.9 or newer from https://www.python.org (tick "Add python.exe to PATH"),
echo then double-click Install.bat.
pause
