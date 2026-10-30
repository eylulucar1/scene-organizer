@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0main.py"
) else if exist "C:\msys64\ucrt64\bin\pythonw.exe" (
    start "" "C:\msys64\ucrt64\bin\pythonw.exe" "%~dp0main.py"
) else (
    echo Python was not found. Install Python and its dependencies from requirements.txt.
    pause
)