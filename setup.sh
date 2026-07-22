#!/bin/bash
# ============================================================================
#  AKAZA X PROXY  -  One-shot setup script + Bot Manager
#  Run this on your Linux server (or Termux on Android).
#
#  What it does:
#    1. Creates a Python virtual environment (`.venv`)
#    2. Installs all dependencies from requirements.txt
#    3. Asks you for BOT_TOKEN and ADMIN_ID
#    4. Writes them to `.env` (so you don't have to edit code)
#    5. Starts the bot in nohup mode (background, persists after terminal close)
#
#  Usage:
#      bash setup.sh              # Full setup + start
#      bash setup.sh start        # Start bot in background
#      bash setup.sh stop         # Stop the bot
#      bash setup.sh restart      # Restart the bot
#      bash setup.sh status       # Check if bot is running
#      bash setup.sh logs         # View bot logs
#      bash setup.sh kill         # Force-kill all bot processes
#      bash setup.sh auto-restart # Monitor and auto-restart on crash
# ============================================================================
set -e

cd "$(dirname "$0")"

# Color codes (works in most terminals)
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'  # no color

# Configuration
BOT_SCRIPT="AKAZA_X_PROXY_Bot.py"
VENV_PYTHON=".venv/bin/python"
PID_FILE=".bot.pid"
LOG_FILE="bot.log"
NOHUP_LOG="nohup.out"

# ============================================================================
# Helper functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${CYAN}=================================================="
    echo "  AKAZA X PROXY  -  Setup & Bot Manager"
    echo "  v7.0 — Self-contained auto-install"
    echo "  Credit: @akaza_isnt"
    echo -e "==================================================${NC}"
    echo ""
}

get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        echo ""
    fi
}

is_running() {
    local pid=$(get_pid)
    if [ -z "$pid" ]; then
        return 1
    fi
    # Check if process exists
    if kill -0 "$pid" 2>/dev/null; then
        return 0
    else
        # Process doesn't exist anymore, clean up PID file
        rm -f "$PID_FILE"
        return 1
    fi
}

# ============================================================================
# Auto-install helpers  —  detect the OS package manager and install only
# what is missing.  Everything here is idempotent: already-installed tools
# are left untouched (no upgrades), and .venv is never recreated.
# ============================================================================

# Global chosen Python interpreter (set by ensure_python).
PY=""

# Populated by detect_pkg_manager.
PKG_MANAGER=""
SUDO=""

detect_pkg_manager() {
    # Choose sudo only when we are not already root and sudo exists.
    if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        SUDO=""
    fi

    if command -v apt-get >/dev/null 2>&1; then
        PKG_MANAGER="apt"
    elif command -v dnf >/dev/null 2>&1; then
        PKG_MANAGER="dnf"
    elif command -v yum >/dev/null 2>&1; then
        PKG_MANAGER="yum"
    elif command -v pacman >/dev/null 2>&1; then
        PKG_MANAGER="pacman"
    elif command -v apk >/dev/null 2>&1; then
        PKG_MANAGER="apk"
    elif command -v pkg >/dev/null 2>&1 && [ -n "${PREFIX:-}" ]; then
        PKG_MANAGER="termux"   # Termux on Android (no sudo)
        SUDO=""
    else
        PKG_MANAGER=""
    fi
}

# Refresh package indexes once per run (best-effort).
_pkg_updated=""
pkg_update_once() {
    [ -n "$_pkg_updated" ] && return 0
    _pkg_updated="1"
    case "$PKG_MANAGER" in
        apt)    $SUDO apt-get update -y            >/dev/null 2>&1 || true ;;
        pacman) $SUDO pacman -Sy --noconfirm        >/dev/null 2>&1 || true ;;
        apk)    $SUDO apk update                    >/dev/null 2>&1 || true ;;
        termux) pkg update -y                       >/dev/null 2>&1 || true ;;
    esac
}

# pkg_install <space-separated package names> — best-effort, never aborts.
pkg_install() {
    local pkgs="$1"
    [ -z "$pkgs" ] && return 0
    [ -z "$PKG_MANAGER" ] && return 1
    pkg_update_once
    case "$PKG_MANAGER" in
        apt)    $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $pkgs >/dev/null 2>&1 || return 1 ;;
        dnf)    $SUDO dnf install -y $pkgs           >/dev/null 2>&1 || return 1 ;;
        yum)    $SUDO yum install -y $pkgs           >/dev/null 2>&1 || return 1 ;;
        pacman) $SUDO pacman -S --noconfirm --needed $pkgs >/dev/null 2>&1 || return 1 ;;
        apk)    $SUDO apk add $pkgs                  >/dev/null 2>&1 || return 1 ;;
        termux) pkg install -y $pkgs                 >/dev/null 2>&1 || return 1 ;;
        *)      return 1 ;;
    esac
    return 0
}

ensure_python() {
    if command -v python3 >/dev/null 2>&1; then
        PY="python3"
    elif command -v python >/dev/null 2>&1; then
        PY="python"
    fi

    # Already present — never upgrade, just confirm venv support exists.
    if [ -n "$PY" ] && "$PY" -m venv --help >/dev/null 2>&1; then
        return 0
    fi

    # Missing (or missing the venv module) — install it.
    echo -e "${YELLOW}    Python (or its venv module) not found — installing...${NC}"
    case "$PKG_MANAGER" in
        apt)    pkg_install "python3 python3-venv python3-pip" || true ;;
        dnf|yum) pkg_install "python3 python3-pip" || true ;;
        pacman) pkg_install "python python-pip" || true ;;
        apk)    pkg_install "python3 py3-pip" || true ;;
        termux) pkg_install "python" || true ;;
        *)      : ;;
    esac

    if command -v python3 >/dev/null 2>&1; then
        PY="python3"
    elif command -v python >/dev/null 2>&1; then
        PY="python"
    fi

    if [ -z "$PY" ] || ! "$PY" -m venv --help >/dev/null 2>&1; then
        echo -e "${RED}❌ Could not install Python 3 with venv support automatically.${NC}"
        echo "   Install it manually, then re-run:"
        echo "     Ubuntu/Debian:  sudo apt install python3 python3-pip python3-venv"
        echo "     Fedora/RHEL:    sudo dnf install python3 python3-pip"
        echo "     Arch:           sudo pacman -S python python-pip"
        echo "     Alpine:         sudo apk add python3 py3-pip"
        echo "     Termux:         pkg install python"
        exit 1
    fi
}

# Install unrar / p7zip only if the corresponding tool is missing. These are
# optional (archive extraction) — failures are non-fatal.
ensure_system_tools() {
    if ! command -v unrar >/dev/null 2>&1 && ! command -v unar >/dev/null 2>&1; then
        case "$PKG_MANAGER" in
            apt)    pkg_install "unrar" || pkg_install "unar" || true ;;
            dnf|yum) pkg_install "unrar" || pkg_install "unar" || true ;;
            pacman) pkg_install "unrar" || true ;;
            apk)    pkg_install "unrar" || true ;;
            termux) pkg_install "unrar" || true ;;
        esac
    fi
    if ! command -v 7z >/dev/null 2>&1 && ! command -v 7za >/dev/null 2>&1 \
       && ! command -v 7zr >/dev/null 2>&1; then
        case "$PKG_MANAGER" in
            apt)    pkg_install "p7zip-full" || true ;;
            dnf|yum) pkg_install "p7zip p7zip-plugins" || pkg_install "p7zip" || true ;;
            pacman) pkg_install "p7zip" || true ;;
            apk)    pkg_install "p7zip" || true ;;
            termux) pkg_install "p7zip" || true ;;
        esac
    fi
}

_req_hash() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum requirements.txt | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 requirements.txt | awk '{print $1}'
    elif command -v md5sum >/dev/null 2>&1; then
        md5sum requirements.txt | awk '{print $1}'
    else
        echo "nohash"
    fi
}

# ============================================================================
# SETUP Command (Full, self-contained, idempotent)
# ============================================================================

cmd_setup() {
    print_header
    detect_pkg_manager

    # --- Ensure Python (auto-install if missing) ---
    echo -e "${YELLOW}[1/6] Checking Python...${NC}"
    ensure_python
    echo -e "${GREEN}✅ Found: $($PY --version 2>&1)${NC}"
    echo ""

    # --- Ensure archive tools (auto-install if missing) ---
    echo -e "${YELLOW}[2/6] Checking archive tools (unrar / p7zip)...${NC}"
    ensure_system_tools
    echo -e "${GREEN}✅ Archive tools checked${NC}"
    echo ""

    # --- Create virtual environment (only if absent) ---
    echo -e "${YELLOW}[3/6] Virtual environment (.venv)...${NC}"
    local venv_fresh=""
    if [ -d ".venv" ] && [ -x "$VENV_PYTHON" ]; then
        echo -e "${GREEN}✅ .venv already exists — reusing${NC}"
    else
        # A partial/broken .venv would break pip; recreate only in that case.
        [ -d ".venv" ] && rm -rf .venv
        "$PY" -m venv .venv
        venv_fresh="1"
        echo -e "${GREEN}✅ Created .venv${NC}"
    fi
    echo ""

    # --- Install dependencies (only when fresh or requirements changed) ---
    echo -e "${YELLOW}[4/6] Python dependencies...${NC}"
    local req_hash marker
    req_hash="$(_req_hash)"
    marker=".venv/.deps_ok"
    if [ -z "$venv_fresh" ] && [ -f "$marker" ] && [ "$(cat "$marker" 2>/dev/null)" = "$req_hash" ]; then
        echo -e "${GREEN}✅ Dependencies already up to date — skipping${NC}"
    else
        [ -n "$venv_fresh" ] && "$VENV_PYTHON" -m pip install --upgrade pip --quiet
        "$VENV_PYTHON" -m pip install -r requirements.txt --quiet
        echo "$req_hash" > "$marker"
        echo -e "${GREEN}✅ Dependencies installed${NC}"
    fi
    echo ""

    # --- Resolve credentials (env → existing .env → interactive prompt) ---
    echo -e "${YELLOW}[5/6] Configuring credentials...${NC}"
    local token admin current_token current_admin
    token="${BOT_TOKEN:-}"
    admin="${ADMIN_ID:-}"
    [ "$token" = "your_bot_token_here" ] && token=""

    if [ -f ".env" ]; then
        current_token="$(grep '^BOT_TOKEN=' .env | cut -d= -f2- || true)"
        current_admin="$(grep '^ADMIN_ID=' .env | cut -d= -f2- || true)"
        [ -z "$token" ] && token="$current_token"
        [ -z "$admin" ] && admin="$current_admin"
    fi
    [ "$token" = "your_bot_token_here" ] && token=""

    if [ -z "$token" ] || [ -z "$admin" ]; then
        if [ -t 0 ]; then
            echo "  • BOT_TOKEN → from @BotFather   • ADMIN_ID → from @userinfobot"
            [ -z "$token" ] && read -r -p "BOT_TOKEN: " token
            [ -z "$admin" ] && read -r -p "ADMIN_ID: " admin
        else
            echo -e "${RED}❌ BOT_TOKEN / ADMIN_ID not provided and no terminal to prompt.${NC}"
            echo "   Provide them non-interactively, e.g.:"
            echo "     BOT_TOKEN=123:ABC ADMIN_ID=123456789 bash setup.sh"
            echo "   or create a .env file with those two lines, then re-run."
            exit 1
        fi
    fi

    if [ -z "$token" ] || [ -z "$admin" ]; then
        echo -e "${RED}❌ BOT_TOKEN and ADMIN_ID are both required.${NC}"
        exit 1
    fi

    cat > .env <<EOF
# AKAZA X PROXY — auto-generated by setup.sh
BOT_TOKEN=$token
ADMIN_ID=$admin
EOF
    echo -e "${GREEN}✅ Saved to .env${NC}"
    echo ""

    # --- Start the bot in nohup mode (restart if already running) ---
    echo -e "${YELLOW}[6/6] Starting bot in background (nohup mode)...${NC}"
    echo ""

    if is_running; then
        echo -e "${YELLOW}    Bot already running — restarting with new config...${NC}"
        cmd_stop
    fi

    nohup "$VENV_PYTHON" "$BOT_SCRIPT" > "$NOHUP_LOG" 2>&1 &
    local pid=$!
    echo $pid > "$PID_FILE"

    sleep 2

    if is_running; then
        echo -e "${GREEN}✅ Bot started successfully in background!${NC}"
        echo -e "${GREEN}   PID: $pid${NC}"
        echo ""
    else
        echo -e "${RED}❌ Bot failed to start. Check logs:${NC}"
        tail -20 "$NOHUP_LOG"
        exit 1
    fi

    echo ""
    echo -e "${CYAN}=================================================="
    echo -e "${GREEN}  ✅ Setup Complete!${NC}"
    echo -e "${CYAN}==================================================${NC}"
    echo ""
    echo "Bot is running in the background. You can close this terminal."
    echo ""
    echo "Management Commands:"
    echo "  bash setup.sh status      → Check if bot is running"
    echo "  bash setup.sh logs        → View real-time logs"
    echo "  bash setup.sh stop        → Stop the bot"
    echo "  bash setup.sh restart     → Restart the bot"
    echo "  bash setup.sh kill        → Force-kill all bot processes"
    echo "  bash setup.sh auto-restart → Auto-restart on crash"
    echo ""
}

# ============================================================================
# START Command
# ============================================================================

cmd_start() {
    echo ""
    echo -e "${CYAN}=================================================="
    echo "  Starting bot in background..."
    echo -e "==================================================${NC}"
    echo ""
    
    # Check if already running
    if is_running; then
        pid=$(get_pid)
        echo -e "${RED}❌ Bot is already running with PID: $pid${NC}"
        echo ""
        exit 1
    fi
    
    # Check if venv exists
    if [ ! -d ".venv" ]; then
        echo -e "${RED}❌ Virtual environment not found.${NC}"
        echo "Run: bash setup.sh"
        exit 1
    fi
    
    # Check if .env exists
    if [ ! -f ".env" ]; then
        echo -e "${RED}❌ .env configuration file not found.${NC}"
        echo "Run: bash setup.sh"
        exit 1
    fi
    
    # Start bot with nohup
    nohup $VENV_PYTHON "$BOT_SCRIPT" > "$NOHUP_LOG" 2>&1 &
    local pid=$!
    echo $pid > "$PID_FILE"
    
    sleep 2
    
    if is_running; then
        echo -e "${GREEN}✅ Bot started successfully!${NC}"
        echo -e "${GREEN}   PID: $pid${NC}"
        echo -e "${GREEN}   Logs: $NOHUP_LOG${NC}"
        echo ""
        echo "Bot will continue running even after you close this terminal."
        echo ""
    else
        echo -e "${RED}❌ Bot failed to start. Check logs:${NC}"
        tail -20 "$NOHUP_LOG"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# ============================================================================
# STOP Command
# ============================================================================

cmd_stop() {
    echo ""
    echo -e "${CYAN}=================================================="
    echo "  Stopping bot..."
    echo -e "==================================================${NC}"
    echo ""
    
    if ! is_running; then
        echo -e "${RED}❌ Bot is not running.${NC}"
        echo ""
        exit 1
    fi
    
    pid=$(get_pid)
    echo -e "${YELLOW}   Killing process $pid...${NC}"
    
    # Try graceful kill first
    kill "$pid" 2>/dev/null || true
    sleep 2
    
    # If still running, force kill
    if is_running; then
        echo -e "${YELLOW}   Force killing process...${NC}"
        kill -9 "$pid" 2>/dev/null || true
    fi
    
    rm -f "$PID_FILE"
    
    echo -e "${GREEN}✅ Bot stopped.${NC}"
    echo ""
}

# ============================================================================
# RESTART Command
# ============================================================================

cmd_restart() {
    echo ""
    echo -e "${CYAN}=================================================="
    echo "  Restarting bot..."
    echo -e "==================================================${NC}"
    echo ""
    
    if is_running; then
        cmd_stop
    fi
    
    sleep 1
    cmd_start
}

# ============================================================================
# STATUS Command
# ============================================================================

cmd_status() {
    echo ""
    echo -e "${CYAN}=================================================="
    echo "  Bot Status"
    echo -e "==================================================${NC}"
    echo ""
    
    if is_running; then
        pid=$(get_pid)
        echo -e "${GREEN}✅ Bot is RUNNING${NC}"
        echo "   PID: $pid"
        echo ""
        
        # Show process info
        echo "Process info:"
        ps aux | grep "$pid" | grep -v grep || true
        echo ""
        
        # Show recent logs
        echo "Recent logs (last 15 lines):"
        echo "---"
        if [ -f "$NOHUP_LOG" ]; then
            tail -15 "$NOHUP_LOG"
        fi
    else
        echo -e "${RED}❌ Bot is NOT running${NC}"
        echo ""
        echo "Start it with: bash setup.sh start"
    fi
    echo ""
}

# ============================================================================
# LOGS Command
# ============================================================================

cmd_logs() {
    echo ""
    echo -e "${CYAN}=================================================="
    echo "  Bot Logs (Live tail - Ctrl+C to exit)"
    echo -e "==================================================${NC}"
    echo ""
    
    if [ ! -f "$NOHUP_LOG" ]; then
        echo -e "${RED}❌ No logs found yet.${NC}"
        echo ""
        exit 1
    fi
    
    tail -f "$NOHUP_LOG"
}

# ============================================================================
# AUTO-RESTART (auto-restart on crash)
# ============================================================================

cmd_auto_restart() {
    echo ""
    echo -e "${CYAN}=================================================="
    echo "  Auto-Restart Monitor"
    echo -e "==================================================${NC}"
    echo ""
    echo -e "${YELLOW}[*] Auto-restart monitor running...${NC}"
    echo -e "${YELLOW}    Bot will auto-restart if it crashes.${NC}"
    echo -e "${YELLOW}    Press Ctrl+C to stop monitoring.${NC}"
    echo ""
    
    trap 'echo "Stopping monitor..."; exit 0' INT
    
    while true; do
        if ! is_running; then
            echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] Bot crashed, restarting...${NC}"
            cmd_start
            sleep 5
        else
            sleep 10
        fi
    done
}

# ============================================================================
# KILL-ALL (hard kill)
# ============================================================================

cmd_kill() {
    echo ""
    echo -e "${CYAN}=================================================="
    echo "  Hard Kill All Bot Processes"
    echo -e "==================================================${NC}"
    echo ""
    echo -e "${YELLOW}[!] Force-killing all Python bot processes...${NC}"
    
    # Kill all processes matching the script
    pkill -f "$BOT_SCRIPT" || true
    
    # Clean up PID file
    rm -f "$PID_FILE"
    
    sleep 1
    echo -e "${GREEN}✅ All bot processes killed.${NC}"
    echo ""
}

# ============================================================================
# MAIN
# ============================================================================

case "${1:-}" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs
        ;;
    auto-restart)
        cmd_auto_restart
        ;;
    kill)
        cmd_kill
        ;;
    *)
        # Default: run full setup
        cmd_setup
        ;;
esac
