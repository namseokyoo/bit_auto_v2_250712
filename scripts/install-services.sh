#!/bin/bash

# Quantum Trading System - Systemd Service Installation Script

set -e

echo "========================================"
echo "Installing Quantum Trading System Services"
echo "========================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}[!]${NC} Please run with sudo: sudo $0"
    exit 1
fi

# Stop existing processes
echo -e "${GREEN}[✓]${NC} Stopping existing processes..."
pkill -f quantum_trading || true
pkill -f dashboard.py || true
sleep 2

# Copy service files
echo -e "${GREEN}[✓]${NC} Installing service files..."
cp /opt/bit_auto_v2_250712/config/systemd/quantum-trading.service /etc/systemd/system/
cp /opt/bit_auto_v2_250712/config/systemd/quantum-dashboard.service /etc/systemd/system/

# Reload systemd
echo -e "${GREEN}[✓]${NC} Reloading systemd daemon..."
systemctl daemon-reload

# Enable services
echo -e "${GREEN}[✓]${NC} Enabling services for auto-start..."
systemctl enable quantum-trading.service
systemctl enable quantum-dashboard.service

# Start services
echo -e "${GREEN}[✓]${NC} Starting services..."
systemctl start quantum-trading.service
sleep 5
systemctl start quantum-dashboard.service

# Check status
echo -e "${GREEN}[✓]${NC} Checking service status..."
echo ""
echo "Quantum Trading Service:"
systemctl status quantum-trading.service --no-pager | head -n 5
echo ""
echo "Dashboard Service:"
systemctl status quantum-dashboard.service --no-pager | head -n 5

echo ""
echo "========================================"
echo -e "${GREEN}Installation Complete!${NC}"
echo "========================================"
echo ""
echo "Services are now installed and running."
echo "They will automatically start on system boot."
echo ""
echo "Useful commands:"
echo "  View logs:        sudo journalctl -u quantum-trading -f"
echo "  Restart trading:  sudo systemctl restart quantum-trading"
echo "  Stop trading:     sudo systemctl stop quantum-trading"
echo "  Service status:   sudo systemctl status quantum-trading"
echo ""
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):8080/"
echo "========================================="