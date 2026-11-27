@echo off
cd /d "%~dp0"
rem This file starts the app. It installs NOTHING: the Python packages are installed by Setup.bat, which shows
rem what it installs (the tested versions listed in requirements.lock) and waits for you to press Install.
rem Here it is only looked whether the packages are there, without loading them (quick).
py -3 -c "import importlib.util as u,sys; sys.exit(any(u.find_spec(m) is None for m in ('win32com','pandas','openpyxl','numpy','matplotlib','scipy','PySide6')))" 1>nul 2>nul
if errorlevel 1 goto notready
rem Start the app without a console window and close this one at once.
rem If the app cannot start, it shows a message and writes startup_error.txt in this folder.
where pyw 1>nul 2>nul
if errorlevel 1 (
  py -3 start.pyw %*
  if errorlevel 1 pause
) else (
  start "" pyw -3 start.pyw %*
)
exit /b 0

:notready
echo.
echo  Origin Plot Studio cannot start yet: Python 3, or one of the Python packages it needs, is not installed.
echo.
echo  Nothing is installed from here. Run Setup.bat in this folder: it shows each step, installs the
echo  tested package versions listed in requirements.lock, and needs no administrator rights.
echo.
set ANSWER=
set /p ANSWER= Open Setup now? [Y/N] 
if /i "%ANSWER%"=="Y" call "%~dp0Setup.bat"
exit /b 1
