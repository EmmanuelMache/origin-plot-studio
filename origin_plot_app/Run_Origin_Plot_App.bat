@echo off
cd /d "%~dp0"
rem Look whether the Python packages are there, without loading them (quick). Install them only if one is missing.
py -3 -c "import importlib.util as u,sys; sys.exit(any(u.find_spec(m) is None for m in ('win32com','pandas','openpyxl','numpy','matplotlib','xlrd','PySide6')))" 1>nul 2>nul
if errorlevel 1 (
  echo Installing the Python packages this app needs. This happens once and takes a few minutes...
  py -3 -m pip install --quiet --no-warn-script-location pywin32 pandas openpyxl numpy matplotlib xlrd python-calamine PySide6
  if errorlevel 1 (
    echo.
    echo Python was not found or the packages could not be installed.
    echo Install Python 3 from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then run this file again.
    pause
    exit /b 1
  )
)
rem Start the app without a console window and close this one at once.
rem If the app cannot start, it shows a message and writes startup_error.txt in this folder.
where pyw 1>nul 2>nul
if errorlevel 1 (
  py -3 start.pyw %*
  if errorlevel 1 pause
) else (
  start "" pyw -3 start.pyw %*
)
