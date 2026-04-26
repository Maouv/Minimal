#!/usr/bin/env bash
# lib/init.sh — minimal --init

cmd_init() {
    check_dep python3
    check_dep bun

    echo "minimal: initializing..." >&2

    if [ ! -x "$VENV_PYTHON" ]; then
        echo "minimal: creating venv at $VENV_DIR ..." >&2
        python3 -m venv "$VENV_DIR"
    else
        echo "minimal: venv already exists" >&2
    fi

    echo "minimal: installing backend deps..." >&2
    "$VENV_DIR/bin/pip" install -q --upgrade pip
    "$VENV_DIR/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"

    echo "minimal: installing TUI deps..." >&2
    cd "$TUI_DIR" && bun install --silent

    LOCAL_BIN="$HOME/.local/bin"
    mkdir -p "$LOCAL_BIN"
    LINK="$LOCAL_BIN/minimal"
    if [ -L "$LINK" ] || [ -f "$LINK" ]; then
        echo "minimal: launcher already linked" >&2
    else
        ln -sf "$SCRIPT_DIR/minimal" "$LINK"
        echo "minimal: linked $LINK" >&2
        case ":$PATH:" in
            *":$LOCAL_BIN:"*) ;;
            *)
                echo ""
                echo "  ⚠  Add this to your shell rc:"
                echo "     export PATH=\"\$HOME/.local/bin:\$PATH\""
                echo ""
                ;;
        esac
    fi

    echo "" >&2
    echo "minimal: done! Run: minimal" >&2
    echo "minimal: credential setup akan muncul otomatis saat pertama kali jalan" >&2
}

