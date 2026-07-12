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
    echo "  v6.2 — Phone-friendly"
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
# SETUP Command (Full Setup - Original Setup Steps)
# ============================================================================

cmd_setup() {
    print_header
    
    # --- Check Python ---
    echo -e "${YELLOW}[1/6] Checking Python...${NC}"
    if command -v python3 >/dev/null 2>&1; then
        PY=python3
    elif command -v python >/dev/null 2>&1; then
        PY=python
    else
        echo -e "${RED}❌ Python 3 is not installed.${NC}"
        echo ""
        echo "Install it first:"
        echo "  Ubuntu/Debian:  sudo apt install python3 python3-pip python3-venv"
        echo "  Termux:         pkg install python"
        echo "  Alpine:         apk add python3 py3-pip"
        exit 1
    fi
    echo -e "${GREEN}✅ Found: $($PY --version)${NC}"
    echo ""
    
    # --- Create virtual environment ---
    echo -e "${YELLOW}[2/6] Creating virtual environment (.venv)...${NC}"
    if [ -d ".venv" ]; then
        echo -e "${GREEN}✅ .venv already exists — skipping${NC}"
    else
        $PY -m venv .venv
        echo -e "${GREEN}✅ Created .venv${NC}"
    fi
    echo ""
    
    # --- Install dependencies ---
    echo -e "${YELLOW}[3/6] Installing Python dependencies...${NC}"
    .venv/bin/pip install --upgrade pip --quiet
    .venv/bin/pip install -r requirements.txt --quiet
    echo -e "${GREEN}✅ Dependencies installed${NC}"
    echo ""
    
    # --- Ask for credentials ---
    echo -e "${YELLOW}[4/6] Configure your bot${NC}"
    echo ""
    echo "You need two things:"
    echo "  • BOT_TOKEN  → from @BotFather on Telegram (looks like 123456:ABC-DEF...)"
    echo "  • ADMIN_ID   → your numeric Telegram user ID (from @userinfobot)"
    echo ""
    
    # If .env already exists, show current values
    if [ -f ".env" ]; then
        echo -e "${YELLOW}Existing .env found. Press Enter to keep current value.${NC}"
        CURRENT_TOKEN=$(grep "^BOT_TOKEN=" .env | cut -d= -f2- || echo "")
        CURRENT_ADMIN=$(grep "^ADMIN_ID=" .env | cut -d= -f2- || echo "")
    fi
    
    # Ask for BOT_TOKEN
    if [ -n "$CURRENT_TOKEN" ] && [ "$CURRENT_TOKEN" != "BOT_TOKEN=" ]; then
        read -p "BOT_TOKEN [current: ${CURRENT_TOKEN:0:15}...]: " NEW_TOKEN
        TOKEN="${NEW_TOKEN:-$CURRENT_TOKEN}"
    else
        read -p "BOT_TOKEN: " TOKEN
    fi
    
    if [ -z "$TOKEN" ]; then
        echo -e "${RED}❌ BOT_TOKEN is required.${NC}"
        exit 1
    fi
    
    # Ask for ADMIN_ID
    if [ -n "$CURRENT_ADMIN" ]; then
        read -p "ADMIN_ID [current: $CURRENT_ADMIN]: " NEW_ADMIN
        ADMIN="${NEW_ADMIN:-$CURRENT_ADMIN}"
    else
        read -p "ADMIN_ID: " ADMIN
    fi
    
    if [ -z "$ADMIN" ]; then
        echo -e "${RED}❌ ADMIN_ID is required.${NC}"
        exit 1
    fi
    
    # Write .env
    cat > .env <<EOF
# AKAZA X PROXY — auto-generated by setup.sh
BOT_TOKEN=$TOKEN
ADMIN_ID=$ADMIN
EOF
    
    echo -e "${GREEN}✅ Saved to .env${NC}"
    echo ""
    
    # --- Start the bot in nohup mode ---
    echo -e "${YELLOW}[5/6] Starting bot in background (nohup mode)...${NC}"
    echo ""
    
    nohup $VENV_PYTHON "$BOT_SCRIPT" > "$NOHUP_LOG" 2>&1 &
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
