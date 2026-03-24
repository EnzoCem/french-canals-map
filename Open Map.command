#!/bin/bash
# Double-click this file to open the French Canals Map locally
cd "$(dirname "$0")"

# Kill any previous instance on port 8765
lsof -ti:8765 | xargs kill -9 2>/dev/null

# Start local server in background
python3 -m http.server 8765 &
SERVER_PID=$!

# Wait for server to start
sleep 1

# Open in browser
open "http://localhost:8765/french_canals_map.html"

echo "French Canals Map is running at http://localhost:8765/french_canals_map.html"
echo "Press Ctrl+C to stop the server when done."

# Keep script running so server stays alive; clean up on exit
trap "kill $SERVER_PID 2>/dev/null" EXIT
wait $SERVER_PID
