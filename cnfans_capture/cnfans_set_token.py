"""Create session.json from a token you copied out of a logged-in browser.

Use this if you don't want to run the Playwright login (e.g. you're already
logged into cnfans in your normal browser). In that browser:

    F12 -> Console, then run:
        localStorage.getItem("token")
        localStorage.getItem("refreshToken")
        localStorage.getItem("fingerprint")

Then:
    python cnfans_set_token.py --token "<token>" --refresh "<refreshToken>" \
        --fingerprint "<fingerprint>"

Only --token is strictly required; --refresh enables auto-renew.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Write session.json from a copied token.")
    ap.add_argument("--token", required=True)
    ap.add_argument("--refresh", default="")
    ap.add_argument("--fingerprint", default="0")
    ap.add_argument("--currency", default="USD")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--out", default="session.json")
    args = ap.parse_args()

    Path(args.out).write_text(
        json.dumps(
            {
                "token": args.token,
                "refresh_token": args.refresh,
                "fingerprint": args.fingerprint,
                "currency": args.currency,
                "lang": args.lang,
            },
            indent=2,
        )
    )
    print(f"[+] Wrote {args.out}. Now run: python cnfans_capture.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
