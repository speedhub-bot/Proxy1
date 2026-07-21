"""Capture a cnfans account snapshot with pure `requests` (fast, no browser).

Pulls, for the logged-in account:
    * profile        (user/info)
    * VIP / membership benefits + current tier
    * wallet balance / top-up info
    * saved addresses
    * cart contents
    * previous-orders count (+ latest orders)
    * credits / points

Usage:
    python cnfans_capture.py                      # uses ./session.json
    python cnfans_capture.py --session s.json     # custom session file
    python cnfans_capture.py --proxy http://user:pass@host:port
    python cnfans_capture.py --out snapshot.json  # where to write the JSON

Create session.json first with cnfans_login.py (or by pasting a token, see README).
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from cnfans_api import CNFansClient, CNFansError


def _data(payload: dict[str, Any]) -> Any:
    """Return the `.data` field of a cnfans envelope, or the payload itself."""
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _ok(payload: dict[str, Any]) -> bool:
    return isinstance(payload, dict) and payload.get("code") in (200, 0)


def capture(client: CNFansClient) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    errors: dict[str, str] = {}

    def grab(key: str, path: str, params: dict[str, Any] | None = None):
        try:
            payload, resp = client.get_json(path, params=params)
            if _ok(payload):
                return _data(payload), resp
            errors[key] = payload.get("msg") or payload.get("message") or f"code={payload.get('code')}"
        except CNFansError as exc:
            errors[key] = str(exc)
        return None, None

    # --- profile -----------------------------------------------------------
    snapshot["profile"], _ = grab("profile", "user/info")

    # --- VIP / membership --------------------------------------------------
    membership, _ = grab("membership", "membership")
    current, _ = grab("membership_current", "membership/current")
    snapshot["vip"] = {"benefits": membership, "current": current}

    # --- wallet ------------------------------------------------------------
    snapshot["wallet"], _ = grab("wallet", "wallet")

    # --- addresses ---------------------------------------------------------
    snapshot["addresses"], _ = grab("addresses", "user/address/list")

    # --- cart --------------------------------------------------------------
    snapshot["cart"], _ = grab("cart", "cart")

    # --- credits / points --------------------------------------------------
    snapshot["credits"], _ = grab("credits", "credits", {"type": "details"})

    # --- orders (count comes from the X-WP-Total response header) ----------
    orders_data, orders_resp = grab("orders", "order/list", {"page": 1, "page_size": 10})
    order_count = None
    if orders_resp is not None:
        order_count = orders_resp.headers.get("X-WP-Total") or orders_resp.headers.get("x-wp-total")
        if order_count is not None:
            try:
                order_count = int(order_count)
            except ValueError:
                pass
    snapshot["orders"] = {"count": order_count, "recent": orders_data}

    if errors:
        snapshot["_errors"] = errors
    return snapshot


def _fmt_money(wallet: Any) -> str:
    if not isinstance(wallet, dict):
        return "n/a"
    for key in ("balance", "amount", "total", "wallet_balance"):
        if key in wallet:
            return str(wallet[key])
    return json.dumps(wallet)[:80]


def print_summary(snap: dict[str, Any]) -> None:
    print("\n================ CNFans account snapshot ================")
    prof = snap.get("profile") or {}
    if isinstance(prof, dict):
        print(f"  User   : {prof.get('nickname') or prof.get('username') or prof.get('email') or '?'}")
        print(f"  Email  : {prof.get('email', '?')}")
    vip = snap.get("vip") or {}
    cur = vip.get("current") if isinstance(vip, dict) else None
    if isinstance(cur, dict):
        print(f"  VIP    : level {cur.get('level', cur.get('current_level', '?'))} "
              f"({cur.get('name', '')})".rstrip())
    print(f"  Wallet : {_fmt_money(snap.get('wallet'))}")
    addrs = snap.get("addresses")
    if isinstance(addrs, list):
        print(f"  Address: {len(addrs)} saved")
    elif isinstance(addrs, dict) and isinstance(addrs.get("list"), list):
        print(f"  Address: {len(addrs['list'])} saved")
    cart = snap.get("cart") or {}
    if isinstance(cart, dict):
        totals = cart.get("totals") or {}
        print(f"  Cart   : {totals.get('cart_contents_count', len(cart.get('items', []) or []))} item(s)")
    orders = snap.get("orders") or {}
    print(f"  Orders : {orders.get('count', '?')} total")
    if snap.get("_errors"):
        print("  ! partial errors:")
        for k, v in snap["_errors"].items():
            print(f"      - {k}: {v}")
    print("========================================================\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Capture a cnfans account snapshot.")
    ap.add_argument("--session", default="session.json", help="path to session file")
    ap.add_argument("--proxy", default=None, help="optional proxy, e.g. http://user:pass@host:port")
    ap.add_argument("--out", default="cnfans_snapshot.json", help="output JSON path")
    args = ap.parse_args()

    try:
        client = CNFansClient.from_session_file(args.session, proxy=args.proxy)
    except CNFansError as exc:
        print(f"ERROR: {exc}")
        return 1

    snap = capture(client)
    with open(args.out, "w") as fh:
        json.dump(snap, fh, indent=2, ensure_ascii=False)
    print_summary(snap)
    print(f"Full snapshot written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
