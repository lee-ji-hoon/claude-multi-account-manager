#!/bin/bash
# setup-ttyd.sh — Install and configure ttyd as a read-only web terminal.
#
# Backend is auto-detected (herdr → tmux) and can be forced with TTYD_BACKEND.
#
# Why this is configurable now (measured 2026-08-07):
#   The previous version hardcoded `tmux attach -t tg-bridge`. On a machine that had
#   migrated to herdr, that session did not exist — so the web terminal exposed a dead
#   screen. Worse, before the tmux cleanup the session only contained Claude Code
#   processes stuck for 26 days on the startup "do you trust these settings" dialog,
#   so the page had been showing nothing useful for a long time without anyone noticing.
#
#   The `-R` flag was also dropped: it does not exist in ttyd 1.7.x
#   (`ttyd: invalid option -- R`). Read-only is the default there and `-W/--writable`
#   is what opts into writing. ttyd only warns and keeps running, so this went unnoticed.
#
# The plist is generated here rather than copied from a static file, so the launch
# command and this script can never drift apart.

set -euo pipefail

PLIST_DST="${HOME}/Library/LaunchAgents/com.ttyd.plist"
PORT="${TTYD_PORT:-7681}"

echo "=== ttyd Setup ==="
echo ""

# 1. Check if ttyd is installed
if command -v ttyd &>/dev/null; then
    echo "✅ ttyd is already installed: $(which ttyd)"
else
    echo "📦 Installing ttyd via Homebrew..."
    if ! command -v brew &>/dev/null; then
        echo "❌ Homebrew is not installed. Please install it first:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    brew install ttyd
    echo "✅ ttyd installed: $(which ttyd)"
fi
TTYD_BIN="$(command -v ttyd)"

echo ""

# 2. Decide which multiplexer to expose.
#    TTYD_BACKEND=herdr | tmux | custom
#    TTYD_COMMAND=<full command> overrides everything (backend=custom).
BACKEND="${TTYD_BACKEND:-}"
if [[ -z "${BACKEND}" ]]; then
    if command -v herdr &>/dev/null; then
        BACKEND="herdr"
    else
        BACKEND="tmux"
    fi
fi

TMUX_SESSION="${TTYD_TMUX_SESSION:-tg-bridge}"
ATTACH_ARGS=()

case "${BACKEND}" in
    herdr)
        if ! command -v herdr &>/dev/null; then
            echo "❌ TTYD_BACKEND=herdr but herdr was not found on PATH."
            exit 1
        fi
        ATTACH_ARGS=("$(command -v herdr)")
        echo "🧭 Backend: herdr (attaches the persistent session)"
        echo "   ⚠️  herdr has no read-only attach mode. ttyd itself is read-only, so"
        echo "      keystrokes are blocked, but a browser client still negotiates a PTY"
        echo "      size — that may reflow your live pane layout. If it does, point this"
        echo "      at a dedicated session instead:"
        echo "        TTYD_COMMAND=\"\$(command -v herdr) --session web\" $0"
        ;;
    tmux)
        if ! command -v tmux &>/dev/null; then
            echo "⚠️  tmux is not installed. Install with: brew install tmux"
        elif tmux has-session -t "${TMUX_SESSION}" 2>/dev/null; then
            echo "✅ tmux session '${TMUX_SESSION}' exists"
        else
            echo "⚠️  tmux session '${TMUX_SESSION}' does not exist yet."
            echo "   ttyd will wait for it. Create it with: tmux new-session -d -s ${TMUX_SESSION}"
        fi
        ATTACH_ARGS=("$(command -v tmux || echo /usr/bin/tmux)" "attach" "-t" "${TMUX_SESSION}")
        echo "🧭 Backend: tmux (session '${TMUX_SESSION}')"
        ;;
    custom) ;;
    *)
        echo "❌ Unknown TTYD_BACKEND='${BACKEND}' (expected: herdr | tmux | custom)"
        exit 1
        ;;
esac

if [[ -n "${TTYD_COMMAND:-}" ]]; then
    # shellcheck disable=SC2206 # intentional word split: user supplies a command line
    ATTACH_ARGS=(${TTYD_COMMAND})
    echo "🧭 Backend: custom — ${TTYD_COMMAND}"
fi

if [[ ${#ATTACH_ARGS[@]} -eq 0 ]]; then
    echo "❌ No attach command resolved. Set TTYD_COMMAND explicitly."
    exit 1
fi

echo ""

# 3. Unload existing agent if loaded
if launchctl list com.ttyd &>/dev/null 2>&1; then
    echo "🔄 Unloading existing com.ttyd agent..."
    launchctl bootout "gui/$(id -u)/com.ttyd" 2>/dev/null \
        || launchctl unload "${PLIST_DST}" 2>/dev/null \
        || true
fi

# 4. Generate the plist. Read-only is ttyd's default — do NOT pass -R (invalid in 1.7.x)
#    and do NOT pass -W unless you actually want viewers to type.
echo "📋 Writing launchd plist..."
mkdir -p "${HOME}/Library/LaunchAgents"
{
    printf '<?xml version="1.0" encoding="UTF-8"?>\n'
    printf '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    printf '<plist version="1.0">\n<dict>\n'
    printf '  <key>Label</key><string>com.ttyd</string>\n'
    printf '  <key>ProgramArguments</key>\n  <array>\n'
    printf '    <string>%s</string>\n' "${TTYD_BIN}" "-p" "${PORT}"
    for arg in "${ATTACH_ARGS[@]}"; do
        printf '    <string>%s</string>\n' "${arg}"
    done
    printf '  </array>\n'
    printf '  <key>RunAtLoad</key><true/>\n'
    printf '  <key>KeepAlive</key><true/>\n'
    printf '  <key>StandardOutPath</key><string>/tmp/ttyd.log</string>\n'
    printf '  <key>StandardErrorPath</key><string>/tmp/ttyd.log</string>\n'
    printf '</dict>\n</plist>\n'
} > "${PLIST_DST}"

if command -v plutil &>/dev/null; then
    plutil -lint "${PLIST_DST}" >/dev/null || { echo "❌ Generated plist is invalid"; exit 1; }
fi

echo "🚀 Loading com.ttyd agent..."
launchctl bootstrap "gui/$(id -u)" "${PLIST_DST}" 2>/dev/null \
    || launchctl load "${PLIST_DST}"

echo ""

# 5. Verify
sleep 1
if launchctl list com.ttyd &>/dev/null 2>&1; then
    echo "✅ com.ttyd agent is running"
else
    echo "⚠️  com.ttyd agent may not have started. Check: launchctl list com.ttyd"
fi

echo ""
echo "=== Access ==="
echo "  Local:   http://localhost:${PORT}"
echo "  Network: http://$(hostname):${PORT}"
echo ""
echo "  Note: ttyd binds all interfaces by default. Put it behind Tailscale serve or"
echo "        pass -i 127.0.0.1 via TTYD_COMMAND if LAN exposure is not wanted."
echo ""
echo "Log file: /tmp/ttyd.log"
echo ""
echo "To stop:  launchctl bootout gui/\$(id -u)/com.ttyd"
echo "To start: launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.ttyd.plist"
