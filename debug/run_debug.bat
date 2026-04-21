@echo off
echo 🚀 Starting Local Debugging Session
echo ====================================

echo 📋 Activating conda environment py11...
call conda activate py11

echo 📁 Setting working directory...
cd /d "C:\Users\Wow\Task\Scrape\job-scraper"

echo 🔍 Checking Python environment...
python --version
echo.

echo 📦 Installing/checking Playwright browsers...
python -m playwright install chromium --with-deps

echo.
echo 🛠️ Debug Configuration:
echo - headless=False (browser will be visible)
echo - batch_size=2 (small batches)
echo - max_jobs_per_session=10 (limited for debugging)
echo - logging=DEBUG (verbose output)
echo.

echo 🏃 Starting automation pipeline in DEBUG mode...
echo Press Ctrl+C to stop
echo.

python scripts/run_automated_pipeline.py

echo.
echo 🏁 Debug session completed.
pause