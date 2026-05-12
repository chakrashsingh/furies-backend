#!/bin/bash
# Run this every time you want to start Furies:
#   ./start.sh

source venv/bin/activate
echo "🔥 Starting Furies..."
echo "   API docs → http://localhost:8000/docs"
echo "   Press Ctrl+C to stop"
echo ""
uvicorn main:app --reload --host 0.0.0.0 --port 8000
