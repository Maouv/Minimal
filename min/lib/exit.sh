#!/usr/bin/env bash
# lib/exit.sh — cleanup dan exit screen

cleanup() {
    local exit_code=$?

    # Restore terminal — opentui pakai alternate screen buffer
    printf "\033[?1049l" >/dev/tty 2>/dev/null || true
    printf "\033[?47l"   >/dev/tty 2>/dev/null || true
    tput rmcup           2>/dev/null || true

    stop_backend

    # Baca session ID yang ditulis TUI
    if [ -f "$MINIMAL_SESSION_FILE" ]; then
        MINIMAL_SESSION_ID=$(cat "$MINIMAL_SESSION_FILE")
        rm -f "$MINIMAL_SESSION_FILE"
    fi

    # Exit screen
    printf "\n"
    printf "  ▄▄▄▄▄▄▄ ✦ ▄▄▄▄ ✦ ▄▄▄▄▄▄▄ ▄▄▄▄ ▄\n"
    printf "  █░░█░░█ ▄ █░░█ ▄ █░░█░░█ █░░█ █\n"
    printf "  █  █  █ █ █  █ █ █  █  █ █▀▀█ █\n"
    printf "  ▀  ▀  ▀ ▀ ▀  ▀ ▀ ▀  ▀  ▀ ▀  ▀ ▀▀▀\n"
    printf "\n"
    printf "  PID: %s  •  session: %s\n" "${BACKEND_PID:-—}" "${MINIMAL_SESSION_ID:-unknown}"
    printf "\n"

    exit $exit_code
}

