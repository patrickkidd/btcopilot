#!/bin/bash
lsof -ti:5555 | xargs kill -9 2>/dev/null && echo "Flask server stopped" || echo "No server running"
