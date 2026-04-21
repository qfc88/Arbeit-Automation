#!/bin/bash

# Job Scraper Scheduler for Ubuntu Server
# Runs the scraper at 2 AM Vietnam time when job websites open back up

echo "🚀 Starting Job Scraper Scheduler for 2 AM Vietnam time..."
echo "📍 Running on Ubuntu Server"
echo "Press Ctrl+C to stop the scheduler"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install Python package if not available
install_python_package() {
    local package=$1
    echo "📦 Checking for Python package: $package"
    
    if ! python3 -c "import $package" >/dev/null 2>&1; then
        echo "⬇️  Installing $package..."
        pip3 install --user $package || {
            echo "❌ Failed to install $package with pip3, trying with sudo..."
            sudo pip3 install $package
        }
    else
        echo "✅ $package is already installed"
    fi
}

# Check system requirements
echo "🔍 Checking system requirements..."

# Check Python
if ! command_exists python3; then
    echo "❌ Python3 is not installed. Please install it:"
    echo "   sudo apt update && sudo apt install -y python3 python3-pip"
    exit 1
fi

# Check Docker
if ! command_exists docker; then
    echo "❌ Docker is not installed. Please install it:"
    echo "   curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh"
    echo "   sudo usermod -aG docker \$USER"
    echo "   # Then logout and login again"
    exit 1
fi

# Check Docker Compose
if ! command_exists docker-compose && ! docker compose version >/dev/null 2>&1; then
    echo "❌ Docker Compose is not installed. Please install it:"
    echo "   sudo apt install -y docker-compose"
    echo "   # Or use: pip3 install docker-compose"
    exit 1
fi

# Check if user is in docker group
if ! groups $USER | grep -q docker; then
    echo "⚠️  User $USER is not in docker group. You may need to run with sudo or add user to docker group:"
    echo "   sudo usermod -aG docker $USER"
    echo "   # Then logout and login again"
    echo ""
fi

# Install required Python packages
install_python_package "schedule"

# Check if data/logs directory exists
echo "📁 Creating required directories..."
mkdir -p data/logs
chmod 755 data/logs

# Set up timezone if not already set (optional)
echo "🌍 Current system timezone:"
timedatectl 2>/dev/null || date

# Make the Python script executable
chmod +x scripts/schedule_scraper.py

# Start the scheduler
echo "⏰ Starting Python scheduler..."
echo "📝 Logs will be written to: data/logs/scheduler.log"
echo "🔄 The scheduler will run daily at 2:00 AM Vietnam time (UTC+7)"
echo ""

# Use nohup to run in background if requested
if [[ "$1" == "background" || "$1" == "daemon" ]]; then
    echo "🔧 Starting scheduler in background mode..."
    nohup python3 scripts/schedule_scraper.py > data/logs/scheduler_console.log 2>&1 &
    SCHEDULER_PID=$!
    echo "✅ Scheduler started with PID: $SCHEDULER_PID"
    echo "📝 Console output: data/logs/scheduler_console.log"
    echo "📝 Application logs: data/logs/scheduler.log"
    echo ""
    echo "To stop the scheduler:"
    echo "   kill $SCHEDULER_PID"
    echo "   # Or find it with: ps aux | grep schedule_scraper"
    echo ""
    echo "To monitor logs:"
    echo "   tail -f data/logs/scheduler.log"
    echo "   tail -f data/logs/scheduler_console.log"
else
    # Run in foreground
    python3 scripts/schedule_scraper.py
fi