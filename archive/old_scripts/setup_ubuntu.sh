#!/bin/bash

# Ubuntu Server Setup Script for Job Scraper
# Installs all dependencies and sets up the environment

set -e  # Exit on any error

echo "🐧 Ubuntu Server Setup for Job Scraper"
echo "========================================"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo "📋 Step 1: System Update"
echo "------------------------"
sudo apt update
sudo apt upgrade -y

echo ""
echo "🐍 Step 2: Install Python and pip"
echo "----------------------------------"
if ! command_exists python3; then
    sudo apt install -y python3 python3-pip python3-venv
else
    echo "✅ Python3 already installed: $(python3 --version)"
fi

echo ""
echo "🐳 Step 3: Install Docker"
echo "-------------------------"
if ! command_exists docker; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "✅ Docker installed"
    echo "⚠️  Please logout and login again to use Docker without sudo"
else
    echo "✅ Docker already installed: $(docker --version)"
fi

echo ""
echo "📦 Step 4: Install Docker Compose"
echo "---------------------------------"
if ! command_exists docker-compose && ! docker compose version >/dev/null 2>&1; then
    # Try package manager first
    sudo apt install -y docker-compose || {
        echo "Installing Docker Compose via pip..."
        pip3 install --user docker-compose
        export PATH="$HOME/.local/bin:$PATH"
    }
    echo "✅ Docker Compose installed"
else
    echo "✅ Docker Compose already installed"
fi

echo ""
echo "📚 Step 5: Install Python Dependencies"
echo "-------------------------------------"
pip3 install --user -r requirements.txt
echo "✅ Python dependencies installed"

echo ""
echo "🗂️  Step 6: Setup Directories"
echo "-----------------------------"
mkdir -p data/{input,output,logs,backup,temp}
chmod -R 755 data/
echo "✅ Directory structure created"

echo ""
echo "🔧 Step 7: Make Scripts Executable"
echo "-----------------------------------"
chmod +x scripts/*.py
chmod +x *.sh
echo "✅ Scripts made executable"

echo ""
echo "⏰ Step 8: Setup Timezone (Optional)"
echo "-----------------------------------"
echo "Current timezone: $(timedatectl show --property=Timezone --value 2>/dev/null || echo 'Unknown')"
echo "Current time: $(date)"
echo ""
read -p "Do you want to set timezone to Asia/Ho_Chi_Minh (Vietnam)? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo timedatectl set-timezone Asia/Ho_Chi_Minh
    echo "✅ Timezone set to Vietnam (UTC+7)"
else
    echo "⏭️  Timezone unchanged"
fi

echo ""
echo "🔐 Step 9: Setup Environment"
echo "----------------------------"
if [ ! -f .env ]; then
    cat > .env << EOF
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=job_market_data
DB_USER=jobscraper
DB_PASSWORD=working

# Application Settings
PYTHONPATH=/app/src
PIPELINE_MODE=automated
SCRAPER_HEADLESS=true
SCRAPER_BATCH_SIZE=50
MAX_JOBS_PER_SESSION=2000
ENABLE_DATABASE_LOADING=true
EOF
    echo "✅ Environment file created (.env)"
else
    echo "✅ Environment file already exists"
fi

echo ""
echo "🧪 Step 10: Test Installation"
echo "-----------------------------"
echo "Testing Python imports..."
python3 -c "import schedule, asyncpg, pandas; print('✅ All required packages available')"

echo "Testing Docker..."
if groups $USER | grep -q docker; then
    docker --version && echo "✅ Docker working"
else
    echo "⚠️  Docker installed but user not in docker group. You may need sudo for Docker commands."
    echo "   Run: sudo usermod -aG docker $USER"
    echo "   Then logout and login again"
fi

echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "📋 What's installed:"
echo "   ✅ Python 3 with all dependencies"
echo "   ✅ Docker and Docker Compose"
echo "   ✅ Directory structure"
echo "   ✅ Environment configuration"
echo "   ✅ Executable scripts"
echo ""
echo "🚀 Ready to use:"
echo ""
echo "   Start scheduler (waits for 2 AM Vietnam time):"
echo "   ./start_scheduler.sh"
echo ""
echo "   Run in background:"
echo "   ./start_scheduler.sh background"
echo ""
echo "   Test immediately:"
echo "   ./test_scheduler.sh"
echo ""
echo "   Manual Docker run:"
echo "   docker-compose up -d"
echo ""
echo "📝 Log files:"
echo "   Application logs: data/logs/"
echo "   Docker logs: docker-compose logs -f"
echo ""
echo "🌐 Admin interface:"
echo "   Database: http://localhost:8081"
echo "   Connection: jobscraper / working / job_market_data"
echo ""
if ! groups $USER | grep -q docker; then
    echo "⚠️  IMPORTANT: Please logout and login again to use Docker without sudo"
fi