#!/bin/bash

# Remote deployment execution script
# Run this locally to deploy to Oracle server

echo "======================================"
echo "🚀 Remote Deployment to Oracle Server"
echo "======================================"
echo ""

# Server details
SERVER_IP="158.180.82.112"
SERVER_USER="ubuntu"
SSH_KEY_PATH="/Users/namseokyoo/project/bit_auto_v2_250712/ssh-key-2025-07-14.key"

# Check if SSH key exists
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "❌ SSH key not found at $SSH_KEY_PATH"
    echo "Please specify the correct path to your SSH key"
    exit 1
fi

echo "📡 Connecting to Oracle server..."
echo "Server: $SERVER_USER@$SERVER_IP"
echo ""

# Execute deployment script on remote server
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY_PATH" "$SERVER_USER@$SERVER_IP" << 'ENDSSH'
echo "Connected to Oracle server"
echo "Starting deployment..."

# Navigate to project directory
cd /opt/bit_auto_v2_250712 || {
    echo "Creating project directory..."
    sudo mkdir -p /opt/bit_auto_v2_250712
    sudo chown ubuntu:ubuntu /opt/bit_auto_v2_250712
    cd /opt/bit_auto_v2_250712
    
    # Clone repository if not exists
    if [ ! -d ".git" ]; then
        git clone https://github.com/namseokyoo/bit_auto_v2_250712.git .
    fi
}

# Pull latest code
echo "Pulling latest code..."
git pull origin main

# Make deployment script executable
chmod +x deploy_quantum.sh

# Run deployment script
echo "Running deployment script..."
./deploy_quantum.sh

ENDSSH

echo ""
echo "======================================"
echo "✅ Remote deployment completed!"
echo "======================================"
echo ""
echo "You can now access:"
echo "  🌐 Dashboard: http://$SERVER_IP:8080/"
echo "  🔍 Health Check: http://$SERVER_IP:8080/health"
echo ""
echo "To check logs on server:"
echo "  ssh -i $SSH_KEY_PATH $SERVER_USER@$SERVER_IP"
echo "  tail -f /opt/bit_auto_v2_250712/logs/quantum_trading.log"
echo "======================================"