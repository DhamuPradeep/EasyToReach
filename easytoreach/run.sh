#!/usr/bin/env bash
# Startup script for EasyToReach WhatsApp CRM & Marketing Platform
cd "$(dirname "$0")"

PORT=5050

echo "=========================================================="
echo " EasyToReach: Multi-Tenant WhatsApp CRM for Textile Shops"
echo "=========================================================="

# Free port 5050 if already in use by a previous instance
PID=$(lsof -ti tcp:$PORT 2>/dev/null || fuser $PORT/tcp 2>/dev/null)
if [ ! -z "$PID" ]; then
    echo "Freeing port $PORT from existing process ($PID)..."
    kill -9 $PID 2>/dev/null || true
    sleep 1
fi

python3 database.py
exec python3 app.py
