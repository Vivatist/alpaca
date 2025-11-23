#!/bin/bash
# ALPACA RAG Control Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
MAIN_PY="$PROJECT_DIR/main.py"
PID_FILE="/tmp/alpaca_rag.pid"

case "$1" in
    start)
        echo "🚀 Starting ALPACA RAG..."
        cd "$PROJECT_DIR"
        nohup "$VENV_PYTHON" "$MAIN_PY" > /tmp/alpaca_rag.log 2>&1 &
        sleep 2
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            echo "✅ ALPACA RAG started (PID: $PID)"
            echo "   Logs: tail -f /tmp/alpaca_rag.log"
        else
            echo "❌ Failed to start"
        fi
        ;;
    
    stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            echo "⏹️  Stopping ALPACA RAG (PID: $PID)..."
            kill $PID 2>/dev/null
            sleep 2
            if ps -p $PID > /dev/null 2>&1; then
                echo "⚠️  Process didn't stop gracefully, forcing..."
                kill -9 $PID 2>/dev/null
            fi
            rm -f "$PID_FILE"
            echo "✅ Stopped"
        else
            echo "❌ ALPACA RAG is not running (no PID file)"
        fi
        ;;
    
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    
    status)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p $PID > /dev/null 2>&1; then
                echo "✅ ALPACA RAG is running (PID: $PID)"
                echo "   Logs: tail -f /tmp/alpaca_rag.log"
            else
                echo "❌ PID file exists but process is dead (PID: $PID)"
                echo "   Run: rm $PID_FILE"
            fi
        else
            echo "⚪ ALPACA RAG is not running"
        fi
        ;;
    
    logs)
        tail -f /tmp/alpaca_rag.log
        ;;
    
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start ALPACA RAG in background"
        echo "  stop    - Stop ALPACA RAG"
        echo "  restart - Restart ALPACA RAG"
        echo "  status  - Check if ALPACA RAG is running"
        echo "  logs    - Show live logs"
        exit 1
        ;;
esac
