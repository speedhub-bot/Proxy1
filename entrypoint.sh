#!/bin/sh
# ============================================================================
#  AKAZA X PROXY — Docker entrypoint
#  Validates that BOT_TOKEN and ADMIN_ID are set, then starts the bot.
# ============================================================================
set -e

echo "=================================================="
echo "  AKAZA X PROXY  -  Telegram Proxy Bot"
echo "  v6.1 — Docker Edition"
echo "  Credit: @akaza_isnt"
echo "=================================================="

# --- Validate required env vars ---
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ ERROR: BOT_TOKEN environment variable is not set."
    echo "   Get it from @BotFather on Telegram."
    echo ""
    echo "   Docker run example:"
    echo "   docker run -e BOT_TOKEN=123:ABC -e ADMIN_ID=123456789 akaza-x-proxy"
    exit 1
fi

if [ -z "$ADMIN_ID" ]; then
    echo "❌ ERROR: ADMIN_ID environment variable is not set."
    echo "   Get your numeric Telegram user ID from @userinfobot."
    exit 1
fi

# --- Ensure data dir exists ---
mkdir -p "$WORK_DIR/downloads" "$WORK_DIR/outputs"
echo "✅ Workspace: $WORK_DIR"
echo "✅ Bot Token: ${BOT_TOKEN:0:10}..."
echo "✅ Admin ID:  $ADMIN_ID"
echo "=================================================="
echo ""

# --- Patch the script's constants from env vars at runtime ---
# (We use sed to replace the placeholder values so the .py file stays
#  editable for non-Docker users too.)
python - <<'PYEOF'
import os, re, pathlib

src = pathlib.Path("/app/AKAZA_X_PROXY_Bot.py")
text = src.read_text(encoding="utf-8")

api_id    = os.environ.get("API_ID", "611335")
api_hash  = os.environ.get("API_HASH", "d524b414d21f4d37f08684c1df41ac9c")
token     = os.environ["BOT_TOKEN"]
admin_id  = os.environ["ADMIN_ID"]
work_dir  = os.environ.get("WORK_DIR", "/app/data")

# Replace the four constants at the top of the file
text = re.sub(r"^API_ID\s+=\s+\d+", f"API_ID    = {int(api_id)}", text, count=1, flags=re.M)
text = re.sub(r'^API_HASH\s+=\s+"[^"]+"', f'API_HASH  = "{api_hash}"', text, count=1, flags=re.M)
text = re.sub(r'^BOT_TOKEN\s+=\s+"[^"]+"', f'BOT_TOKEN = "{token}"', text, count=1, flags=re.M)
text = re.sub(r"^ADMIN_ID\s+=\s+\d+", f"ADMIN_ID  = {int(admin_id)}", text, count=1, flags=re.M)
text = re.sub(r'^WORK_DIR\s+=\s+Path\("[^"]+"\)', f'WORK_DIR   = Path("{work_dir}")', text, count=1, flags=re.M)

src.write_text(text, encoding="utf-8")
print("✅ Config patched from environment variables.")
PYEOF

echo ""
echo "🚀 Starting AKAZA X PROXY..."
echo ""
exec python -u AKAZA_X_PROXY_Bot.py
