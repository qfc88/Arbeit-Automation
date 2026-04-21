#!/bin/bash

# Install Job Scraper as systemd service on Ubuntu Server
# This creates a system service that starts automatically on boot

echo "⚙️  Installing Job Scraper as systemd service"
echo "=============================================="
echo ""

# Get script directory (absolute path)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME=$(whoami)

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please do not run this script as root (sudo)"
    echo "   Run as regular user: ./install_systemd.sh"
    exit 1
fi

echo "📍 Installation details:"
echo "   User: $USER_NAME"
echo "   Project directory: $SCRIPT_DIR"
echo "   Service name: job-scraper-scheduler"
echo ""

# Create systemd service file
SERVICE_FILE="/tmp/job-scraper-scheduler.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Job Scraper Scheduler (2 AM Vietnam Time)
After=network.target docker.service
Wants=docker.service
Requires=network.target

[Service]
Type=simple
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$SCRIPT_DIR
Environment=PATH=/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin
Environment=PYTHONPATH=$SCRIPT_DIR/src
ExecStart=/usr/bin/python3 $SCRIPT_DIR/scripts/schedule_scraper.py
Restart=always
RestartSec=30
StandardOutput=append:$SCRIPT_DIR/data/logs/systemd.log
StandardError=append:$SCRIPT_DIR/data/logs/systemd.log

# Resource limits
MemoryMax=4G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
EOF

echo "📝 Created service configuration:"
cat "$SERVICE_FILE"
echo ""

# Install the service
echo "🔧 Installing systemd service..."
sudo mv "$SERVICE_FILE" /etc/systemd/system/job-scraper-scheduler.service
sudo systemctl daemon-reload

echo "✅ Service installed"
echo ""

# Enable and start service
read -p "Do you want to enable and start the service now? [Y/n]: " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo "🚀 Enabling and starting service..."
    sudo systemctl enable job-scraper-scheduler.service
    sudo systemctl start job-scraper-scheduler.service
    echo "✅ Service enabled and started"
else
    echo "⏭️  Service installed but not started"
fi

echo ""
echo "🎉 Systemd Service Installation Complete!"
echo "========================================="
echo ""
echo "📋 Service Management Commands:"
echo ""
echo "   Check status:"
echo "   sudo systemctl status job-scraper-scheduler"
echo ""
echo "   Start service:"
echo "   sudo systemctl start job-scraper-scheduler"
echo ""
echo "   Stop service:"
echo "   sudo systemctl stop job-scraper-scheduler"
echo ""
echo "   Restart service:"
echo "   sudo systemctl restart job-scraper-scheduler"
echo ""
echo "   Enable auto-start on boot:"
echo "   sudo systemctl enable job-scraper-scheduler"
echo ""
echo "   Disable auto-start:"
echo "   sudo systemctl disable job-scraper-scheduler"
echo ""
echo "   View logs:"
echo "   journalctl -u job-scraper-scheduler -f"
echo "   tail -f $SCRIPT_DIR/data/logs/systemd.log"
echo "   tail -f $SCRIPT_DIR/data/logs/scheduler.log"
echo ""
echo "   Remove service:"
echo "   sudo systemctl stop job-scraper-scheduler"
echo "   sudo systemctl disable job-scraper-scheduler"
echo "   sudo rm /etc/systemd/system/job-scraper-scheduler.service"
echo "   sudo systemctl daemon-reload"
echo ""
echo "🕐 The service will run daily at 2:00 AM Vietnam time (UTC+7)"
echo "📝 Logs are written to: $SCRIPT_DIR/data/logs/"
echo "🔄 Service will auto-restart if it crashes"
echo "🚀 Service will auto-start on system boot"