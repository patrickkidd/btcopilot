#!/bin/bash
# Stop Flask server(s)
# Usage: flask_stop.sh [port]
#   If port is specified, stops server on that port
#   If no port specified, stops all servers in range 5555-5565

if [ -n "$1" ]; then
    # Stop specific port
    PORT=$1
    if lsof -ti:$PORT >/dev/null 2>&1; then
        lsof -ti:$PORT | xargs kill -9 2>/dev/null
        echo "Flask server stopped on port $PORT"
    else
        echo "No server running on port $PORT"
    fi
else
    # Stop all Flask servers in range
    STOPPED=0
    for PORT in {5555..5565}; do
        if lsof -ti:$PORT >/dev/null 2>&1; then
            lsof -ti:$PORT | xargs kill -9 2>/dev/null
            echo "Flask server stopped on port $PORT"
            STOPPED=1
        fi
    done

    if [ $STOPPED -eq 0 ]; then
        echo "No Flask servers running"
    fi
fi
