#!/bin/bash
# setup-ttyd.sh — Install and configure ttyd for read-only tmux viewing
#
# Exposes the tg-bridge tmux session via a web terminal on port 7681.
# Read-only mode (-R) so viewers cannot send input.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="${SCRIPT_DIR}/com.ttyd.plist"
PLIST_DST="${HOME}/Library/LaunchAgents/com.ttyd.plist"
PORT=7681

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

echo ""

# 2. Ensure tmux session exists (warn if not)
if command -v tmux &>/dev/null; then
    if tmux has-session -t tg-bridge 2>/dev/null; then
        echo "✅ tmux session 'tg-bridge' exists"
    else
        echo "⚠️  tmux session 'tg-bridge' does not exist yet."
        echo "   ttyd will wait for it. Create it with: tmux new-session -d -s tg-bridge"
    fi
else
    echo "⚠️  tmux is not installed. Install with: brew install tmux"
fi

echo ""

# 3. Unload existing plist if loaded
if launchctl list com.ttyd &>/dev/null 2>&1; then
    echo "🔄 Unloading existing com.ttyd agent..."
    launchctl unload "${PLIST_DST}" 2>/dev/null || true
fi

# 4. Copy plist and load
echo "📋 Installing launchd plist..."
mkdir -p "${HOME}/Library/LaunchAgents"
cp "${PLIST_SRC}" "${PLIST_DST}"

echo "🚀 Loading com.ttyd agent..."
launchctl load "${PLIST_DST}"

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
echo "Log file: /tmp/ttyd.log"
echo ""
echo "To stop:  launchctl unload ~/Library/LaunchAgents/com.ttyd.plist"
echo "To start: launchctl load ~/Library/LaunchAgents/com.ttyd.plist"
