@echo off
echo Starting Laser Marking System...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

REM Check if required packages are installed
echo Checking dependencies...
python main.py --check-deps
if %errorlevel% neq 0 (
    echo.
    echo Installing required packages...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Error: Failed to install required packages
        pause
        exit /b 1
    )
)

REM Setup environment
echo Setting up environment...
python main.py --setup-env

REM Start the application
echo.
echo Starting Laser Marking System...
python main.py

pause