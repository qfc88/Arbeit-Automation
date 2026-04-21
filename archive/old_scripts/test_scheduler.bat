@echo off
echo Testing Job Scraper immediately (not waiting for 2 AM)...
echo.

cd /d "%~dp0"

REM Activate conda environment if available
if exist "C:\ProgramData\anaconda3\condabin\activate.bat" (
    echo Activating conda environment py11...
    call C:\ProgramData\anaconda3\condabin\activate.bat py11
)

REM Install schedule library if not available
python -c "import schedule" 2>nul || (
    echo Installing required schedule library...
    pip install schedule
)

REM Run test immediately
python scripts/schedule_scraper.py test

pause