#!/usr/bin/env bash
# lib/backend.sh — backend lifecycle

backend_running() {
    curl -sf "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1
}

start_backend() {
    if backend_running; then
        return 0  # sudah running, silent
    fi

    PYTHONPATH="$BACKEND_DIR" "$VENV_PYTHON" "$BACKEND_DIR/main.py" >> "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$BACKEND_PID_FILE"
    BACKEND_OWNED=true

    for i in $(seq 1 20); do
        sleep 0.5
        if backend_running; then
            return 0
        fi
        if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
            echo "minimal: backend crashed. Last log:" >&2
            tail -20 "$BACKEND_LOG" >&2
            rm -f "$BACKEND_PID_FILE"
            return 1
        fi
        if [ "$i" -eq 20 ]; then
            kill "$BACKEND_PID" 2>/dev/null || true
            rm -f "$BACKEND_PID_FILE"
            echo "minimal: backend failed to start within 10s. Check $BACKEND_LOG" >&2
            return 1
        fi
    done
}

stop_backend() {
    if [ "$BACKEND_OWNED" = true ] && [ -f "$BACKEND_PID_FILE" ]; then
        local pid
        pid=$(cat "$BACKEND_PID_FILE")
        kill "$pid" 2>/dev/null || true
        rm -f "$BACKEND_PID_FILE"
    fi
}

