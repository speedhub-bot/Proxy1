# CNFans account capture

Fast, pure-`requests` scraper for a cnfans.com account. After a one-time login
it captures, for the logged-in account:

- **VIP / membership** benefits + current tier
- **Wallet** balance / top-up info
- **Addresses** (saved shipping addresses)
- **Cart** contents
- **Orders** — total count (+ recent orders)
- Profile + credits/points

## How the auth works (important)

The site is a WordPress + REST (`/wp-json/openapi/v1/...`) SPA. Requests need:

- `Authorization: Bearer <token>` — the token from `localStorage["token"]`
- `From-Source-Type: PC` — **without this header the API returns 404**
- `Fingerprint: <localStorage["fingerprint"]>` (`"0"` works)
- `lang` + `wmc-currency` query params on every call

### The one catch: Cloudflare on `/user/login`

Only the **login** endpoint is behind a Cloudflare *managed challenge*
(Turnstile). It cannot be solved with plain HTTP, and from a **datacenter IP**
(most VPS / CI / cloud) even a real browser gets stuck in an endless Cloudflare
loop. Everything else (wallet, VIP, address, cart, orders) is **not** challenged
and works from any IP once you hold a token.

So the design is: **log in once in a real browser on a normal/home IP to get a
token, then scrape with pure requests anywhere.**

## Install

```bash
pip install -r requirements.txt
# for cnfans_login.py only:
playwright install chromium
```

## Usage

### 1. Get a session token (pick ONE)

**A. Automated browser login** (run on your own machine / residential IP):

```bash
python cnfans_login.py -u you@email.com -p 'yourpassword'
# writes session.json
```

**B. Paste a token from a browser you're already logged into:**

Open cnfans.com (logged in) → `F12` → Console:

```js
localStorage.getItem("token"); localStorage.getItem("refreshToken"); localStorage.getItem("fingerprint");
```

```bash
python cnfans_set_token.py --token "<token>" --refresh "<refreshToken>" --fingerprint "<fingerprint>"
```

### 2. Capture (fast, no browser — runs anywhere)

```bash
python cnfans_capture.py
# -> prints a summary and writes cnfans_snapshot.json
```

Options: `--session PATH`, `--out PATH`, `--proxy http://user:pass@host:port`.

The scraper auto-refreshes the access token via `user/refresh_token` when it
expires (needs the refresh token in `session.json`).

## Files

| file | purpose |
|------|---------|
| `cnfans_api.py` | authenticated HTTP client (headers, params, token refresh) |
| `cnfans_login.py` | Playwright browser login → `session.json` |
| `cnfans_set_token.py` | build `session.json` from a copied token |
| `cnfans_capture.py` | capture VIP/wallet/address/cart/orders → JSON |

## Notes on "bypassing" Cloudflare from a server

Tested from a datacenter IP and confirmed these do **not** get past the login
challenge (it's IP-reputation + a managed Turnstile, not a TLS-fingerprint gate):
`curl_cffi` (chrome impersonation), `cloudscraper`. Real Chrome loops forever.

Options that *do* work for automated login:
- run on a **residential/mobile IP**, or route the browser through a
  **residential proxy** (`--proxy`),
- or a paid captcha/turnstile solver that also returns a `cf_clearance` cookie
  (e.g. CapSolver) combined with a matching proxy.

For a set-and-forget scraper the simplest reliable path is: refresh the token in
a browser occasionally; the scraper keeps working from any IP in between.
