@echo off
set VENV_DIR=venv

:: Check if the virtual environment exists by looking for the activate script
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment. Please ensure Python is installed and in your system PATH.
        pause
        exit /b 1
    )
    
    echo [INFO] Activating virtual environment...
    call "%VENV_DIR%\Scripts\activate.bat"
    
    @REM echo [INFO] Upgrading pip...
    @REM python -m pip install --upgrade pip
    
    echo [INFO] Installing requirements...
    .\venv\Scripts\pip.exe install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install requirements.
        pause
        exit /b 1
    )
    echo [INFO] Setup complete!
) else (
    echo [INFO] Activating existing virtual environment...
    call "%VENV_DIR%\Scripts\activate.bat"
)

echo [INFO] Starting NIR Tracker Server...
python server.py

pause
