#!/bin/bash

# Test Job Scraper immediately on Ubuntu Server
# Runs the scraper right now instead of waiting for 2 AM

echo "🧪 Testing Job Scraper immediately (not waiting for 2 AM)"
echo "📍 Running on Ubuntu Server"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Quick system check
echo "🔍 Quick system check..."

if ! command_exists python3; then
    echo "❌ Python3 not found. Please install it first."
    exit 1
fi

if ! command_exists docker; then
    echo "❌ Docker not found. Please install it first."
    exit 1
fi

# Install schedule if needed
if ! python3 -c "import schedule" >/dev/null 2>&1; then
    echo "📦 Installing schedule package..."
    pip3 install --user schedule || sudo pip3 install schedule
fi

# Create logs directory
mkdir -p data/logs

# Make script executable
chmod +x scripts/schedule_scraper.py

# Run test immediately
echo "🚀 Running test scrape immediately..."
echo "📝 Logs: data/logs/scheduler.log"
echo ""

python3 scripts/schedule_scraper.py test