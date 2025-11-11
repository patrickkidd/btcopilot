#!/bin/bash
# Flask server management script for btcopilot training app

PORT=5555

case "$1" in
  start)
    echo "Starting Flask server on port $PORT with auto-auth..."
    FLASK_APP=btcopilot.app:create_app \
    FLASK_CONFIG=development \
    FLASK_DEBUG=1 \
    FLASK_AUTO_AUTH_USER=patrickkidd+unittest@gmail.com \
    uv run flask run -p $PORT &
    echo "Server started (PID: $!)"
    ;;

  stop)
    echo "Stopping Flask server on port $PORT..."
    lsof -ti:$PORT | xargs kill -9 2>/dev/null && echo "Server stopped" || echo "No server running on port $PORT"
    ;;

  restart)
    $0 stop
    sleep 2
    $0 start
    ;;

  status)
    PID=$(lsof -ti:$PORT 2>/dev/null)
    if [ -n "$PID" ]; then
      echo "Server is running (PID: $PID)"
    else
      echo "Server is not running"
    fi
    ;;

  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
