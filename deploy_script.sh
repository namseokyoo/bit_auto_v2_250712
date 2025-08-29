#!/bin/bash
# Compatibility shim: older workflows call deploy_script.sh
# This script forwards to deploy.sh
set -e
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
exec bash "$SCRIPT_DIR/deploy.sh"
