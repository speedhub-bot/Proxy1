"""Log into cnfans.com with a real browser and save the session token.

Why a browser: the /user/login endpoint is behind a Cloudflare "managed
challenge" (Turnstile). It CANNOT be solved with plain HTTP from a datacenter
IP. A real browser on a normal/home (residential) IP passes it. This script
drives Chromium, lets the Cloudflare Turnstile resolve (auto or manual), reads
the auth token out of localStorage, and writes session.json — which the fast
`cnfans_capture.py` scraper then reuses with no browser at all.

Run this on your own machine / a residential IP. Datacenter IPs (most VPS,
CI runners) get stuck in an endless Cloudflare loop and will NOT work.

Setup:
    pip install playwright
    playwright install chromium

Usage:
    python cnfans_login.py                      # prompts / uses env creds, headful
    python cnfans_login.py -u EMAIL -p PASS
    python cnfans_login.py --proxy http://user:pass@host:port
    python cnfans_login.py --headless           # only works on a trusted IP
    CNFANS_USERNAME=.. CNFANS_PASSWORD=.. python cnfans_login.py

Credentials are read from --user/--pass, then env CNFANS_USERNAME/CNFANS_PASSWORD,
then an interactive prompt.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    print("Playwright is required: pip install playwright && playwright install chromium")
    raise

LOGIN_URL = "https://cnfans.com/login"
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = window.chrome || {runtime: {}};
"""


def _read_session(page) -> dict[str, str]:
    return page.evaluate(
        """() => ({
            token: localStorage.getItem('token') || '',
            refresh_token: localStorage.getItem('refreshToken') || '',
            fingerprint: localStorage.getItem('fingerprint') || '0',
            userInfo: localStorage.getItem('userInfo') || '',
        })"""
    )


def login(
    username: str,
    password: str,
    out: Path,
    proxy: str | None = None,
    headless: bool = False,
    wait_seconds: int = 180,
) -> dict[str, str]:
    with sync_playwright() as pw:
        launch_kwargs: dict = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }
        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}
        browser = pw.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 800},
        )
        context.add_init_script(STEALTH_JS)
        page = context.new_page()

        print(f"[*] Opening {LOGIN_URL} ...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        # Fill credentials (selectors match the placeholders in the SPA form).
        try:
            page.fill("input[placeholder*='Username'], input[placeholder*='email']", username, timeout=20000)
            page.fill("input[type='password']", password, timeout=20000)
        except Exception:
            print("[!] Could not auto-fill the form; fill it manually in the window.")

        # Click login (button text is 'login').
        try:
            page.click("button:has-text('login')", timeout=10000)
        except Exception:
            pass

        print("[*] Waiting for Cloudflare Turnstile + login to complete ...")
        print("    If a 'Verify you are human' box shows, it should auto-solve;")
        print("    otherwise click it in the browser window. Waiting up to "
              f"{wait_seconds}s.")

        session: dict[str, str] = {}
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            # Re-click login if the button re-enabled after a Turnstile solve.
            try:
                if page.locator("button:has-text('login')").is_enabled(timeout=500):
                    page.click("button:has-text('login')", timeout=1000)
            except Exception:
                pass
            try:
                session = _read_session(page)
            except Exception:
                session = {}
            if session.get("token"):
                break
            time.sleep(2)

        browser_currency = "USD"
        if session.get("userInfo"):
            try:
                browser_currency = json.loads(session["userInfo"]).get("currency", "USD")
            except (ValueError, AttributeError):
                pass

        context.close()
        browser.close()

        if not session.get("token"):
            raise SystemExit(
                "Login did not complete (no token in localStorage). "
                "On a datacenter IP the Cloudflare challenge loops forever — "
                "run this on a residential IP or via a residential --proxy."
            )

        out_data = {
            "token": session["token"],
            "refresh_token": session.get("refresh_token", ""),
            "fingerprint": session.get("fingerprint", "0"),
            "currency": browser_currency,
            "lang": "en",
        }
        out.write_text(json.dumps(out_data, indent=2))
        print(f"[+] Login OK. Session saved to {out}")
        return out_data


def main() -> int:
    ap = argparse.ArgumentParser(description="Log into cnfans and save session.json")
    ap.add_argument("-u", "--user", default=os.environ.get("CNFANS_USERNAME"))
    ap.add_argument("-p", "--pass", dest="password", default=os.environ.get("CNFANS_PASSWORD"))
    ap.add_argument("--proxy", default=None, help="residential proxy http://user:pass@host:port")
    ap.add_argument("--headless", action="store_true", help="headless (trusted IPs only)")
    ap.add_argument("--out", default="session.json")
    ap.add_argument("--wait", type=int, default=180, help="seconds to wait for challenge+login")
    args = ap.parse_args()

    username = args.user or input("cnfans username/email: ").strip()
    password = args.password or getpass.getpass("cnfans password: ")

    login(
        username=username,
        password=password,
        out=Path(args.out),
        proxy=args.proxy,
        headless=args.headless,
        wait_seconds=args.wait,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
