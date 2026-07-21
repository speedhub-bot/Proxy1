"""CNFans HTTP API client (pure `requests`, no browser).

Reverse-engineered from the cnfans.com single-page-app frontend bundle.

Key facts baked in here:
  * Base URL:        https://cnfans.com/wp-json/openapi/v1
  * Auth:            Authorization: Bearer <access token>   (localStorage["token"])
  * Required header: From-Source-Type: PC   -> without it the API returns 404
                     "rest_no_route" for most routes.
  * Fingerprint:     Fingerprint: <localStorage["fingerprint"]>  ("0" fallback ok)
  * Default params:  lang=en & wmc-currency=<currency>  on every request.
  * Response shape:  {"code": 200, "msg": null, "data": {...}}
  * Token refresh:   POST user/refresh_token {"refresh_token": ...}
                     -> data.access_token / data.refresh_token

Only the /user/login endpoint sits behind a Cloudflare "managed challenge";
every endpoint used here is reachable from any server IP once you hold a token.
Obtain the token once with cnfans_login.py (real browser, home/residential IP).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://cnfans.com/wp-json/openapi/v1"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SESSION_FILE = Path(os.environ.get("CNFANS_SESSION_FILE", "session.json"))


class CNFansError(RuntimeError):
    """Raised when the API returns a non-success payload we cannot recover from."""


class CNFansClient:
    """Thin authenticated client for the cnfans openapi endpoints."""

    def __init__(
        self,
        token: str,
        refresh_token: str = "",
        fingerprint: str = "0",
        currency: str = "USD",
        lang: str = "en",
        proxy: str | None = None,
        session_file: Path | None = None,
    ) -> None:
        self.token = token
        self.refresh_token = refresh_token
        self.fingerprint = fingerprint or "0"
        self.currency = currency or "USD"
        self.lang = lang or "en"
        self.session_file = session_file or SESSION_FILE

        self.http = requests.Session()
        if proxy:
            self.http.proxies.update({"http": proxy, "https": proxy})
        self.http.headers.update(
            {
                "User-Agent": DEFAULT_UA,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://cnfans.com",
                "Referer": "https://cnfans.com/",
                "From-Source-Type": "PC",
            }
        )

    # ------------------------------------------------------------------ helpers
    @classmethod
    def from_session_file(cls, path: str | Path = SESSION_FILE, proxy: str | None = None) -> "CNFansClient":
        path = Path(path)
        if not path.exists():
            raise CNFansError(
                f"Session file '{path}' not found. Run cnfans_login.py first to create it."
            )
        data = json.loads(path.read_text())
        token = data.get("token") or data.get("access_token")
        if not token:
            raise CNFansError(f"No 'token' found in {path}.")
        return cls(
            token=token,
            refresh_token=data.get("refresh_token", ""),
            fingerprint=data.get("fingerprint", "0"),
            currency=data.get("currency", "USD"),
            lang=data.get("lang", "en"),
            proxy=proxy,
            session_file=path,
        )

    def save_session(self) -> None:
        self.session_file.write_text(
            json.dumps(
                {
                    "token": self.token,
                    "refresh_token": self.refresh_token,
                    "fingerprint": self.fingerprint,
                    "currency": self.currency,
                    "lang": self.lang,
                },
                indent=2,
            )
        )

    def _base_params(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        params = {"lang": self.lang, "wmc-currency": self.currency}
        if extra:
            params.update(extra)
        return params

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Fingerprint": self.fingerprint,
        }

    # ------------------------------------------------------------------ core request
    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        _retry: bool = True,
    ) -> requests.Response:
        url = f"{BASE_URL}/{path.lstrip('/')}"
        resp = self.http.request(
            method.upper(),
            url,
            params=self._base_params(params),
            json=json_body,
            headers=self._headers(),
            timeout=30,
        )
        # Transparent one-shot token refresh on auth failure.
        if resp.status_code == 401 and _retry and self.refresh_token:
            if self._refresh():
                return self.request(
                    method, path, params=params, json_body=json_body, _retry=False
                )
        return resp

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> tuple[dict[str, Any], requests.Response]:
        resp = self.request("GET", path, params=params)
        return self._parse(resp), resp

    def _parse(self, resp: requests.Response) -> dict[str, Any]:
        try:
            payload = resp.json()
        except ValueError:
            if "just a moment" in resp.text.lower():
                raise CNFansError(
                    "Cloudflare challenge hit (403). This endpoint/IP is being "
                    "challenged; use a residential IP or refresh the token."
                )
            raise CNFansError(f"Non-JSON response ({resp.status_code}): {resp.text[:200]}")
        return payload

    # ------------------------------------------------------------------ auth refresh
    def _refresh(self) -> bool:
        url = f"{BASE_URL}/user/refresh_token"
        try:
            resp = self.http.post(
                url,
                params=self._base_params(),
                json={"refresh_token": self.refresh_token},
                headers={"Fingerprint": self.fingerprint},
                timeout=30,
            )
            data = resp.json()
        except (requests.RequestException, ValueError):
            return False
        if data.get("code") in (200, 0) and isinstance(data.get("data"), dict):
            new_access = data["data"].get("access_token")
            new_refresh = data["data"].get("refresh_token")
            if new_access:
                self.token = new_access
                if new_refresh:
                    self.refresh_token = new_refresh
                self.save_session()
                return True
        return False
