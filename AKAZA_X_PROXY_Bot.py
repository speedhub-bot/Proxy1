#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  AKAZA X PROXY  -  Telegram Proxy Extractor & Verifier
================================================================================
  Developer    : @akaza_isnt
  Brand        : AKAZA X PROXY
  Engine       : Pyrogram (Userbot / Bot hybrid — paste your API ID + API HASH)
  Features     :
      * Extracts proxies from .txt / .zip / .rar / .7z / .tar / .gz / .csv /
        .json / .log / .ini / .yaml / .xml and many more.
      * Detects every known proxy format:
            - http://   https://   socks4://   socks4a://
            - socks5://  socks5h://
            - ip:port
            - user:pass@ip:port
            - ip:port:user:pass
            - ip:port|user|pass
            - ip:port;user;pass
            - ip port (space separated)
      * Smart parallel verification (HTTP / HTTPS / SOCKS4 / SOCKS5)
      * Inline dashboard, Help menu, Stats panel, Custom buttons
      * All credits: @akaza_isnt
================================================================================

  INSTALL  :
      pip install pyrogram tgcrypto requests pysocks rarfile py7zr

  RUN      :
      EASIEST WAY (no code editing):
      1.  Create a file called `.env` in the same folder as this script.
      2.  Put two lines in it:
              BOT_TOKEN=123456789:ABCdef...   (from @BotFather)
              ADMIN_ID=123456789              (from @userinfobot)
      3.  Run:  python AKAZA_X_PROXY_Bot.py

      The bot auto-reads `.env` on startup.  No need to edit this file.

      ALTERNATIVE (edit code directly):
      Edit BOT_TOKEN and ADMIN_ID constants below, then run.

  ACCESS CONTROL :
      • Bot is OPEN to everyone by default.
      • Admin can ban users via /ban or the admin panel.
      • Admin can APPROVE users via /approve (whitelist).
      • Admin can LOCK the bot — when locked, only admin + approved
        users can use it.  Everyone else gets a polite denial.
================================================================================
"""

import os
import re
import io
import sys
import ipaddress
import time
import json
import zipfile
import tarfile
import gzip
import shutil
import asyncio
import logging
import tempfile
import datetime
import threading
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set, Any, Iterator, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED

# ---------------------------------------------------------------------------
#  CONFIG  —  Two ways to set your values:
#
#  METHOD A (RECOMMENDED — phone friendly):
#       Create a file called `.env` next to this script with:
#           BOT_TOKEN=123456789:ABCdef...
#           ADMIN_ID=123456789
#       The bot will read it automatically.  No code editing needed.
#
#  METHOD B (manual):
#       Edit the four constants below directly.
# ---------------------------------------------------------------------------
# PUBLIC Telegram API credentials (works for any bot — no my.telegram.org needed)
API_ID    = 611335                       # Public Telegram Desktop API ID
API_HASH  = "d524b414d21f4d37f08684c1df41ac9c"  # Public Telegram Desktop API HASH

BOT_TOKEN = "your_bot_token_here"        # <-- Replace with the token from @BotFather
ADMIN_ID  = 123456789                    # <-- Replace with your numeric Telegram user ID

# Default workspace — folder called `akaza_data` next to this script.
# Override with WORK_DIR=/some/path in .env if you want a different location.
WORK_DIR   = None   # set by _load_dotenv or fallback below


# ---------------------------------------------------------------------------
#  AUTO-LOAD `.env` FILE (if present)
#  Reads BOT_TOKEN / ADMIN_ID / API_ID / API_HASH / WORK_DIR from .env
#  without requiring you to edit this Python file.
# ---------------------------------------------------------------------------
def _load_dotenv():
    """Read .env file (if it exists) and override the constants above."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if not key or not value:
                    continue
                os.environ[key] = value
                if key == "API_ID":
                    try:
                        globals()["API_ID"] = int(value)
                    except ValueError:
                        pass
                elif key == "ADMIN_ID":
                    try:
                        globals()["ADMIN_ID"] = int(value)
                    except ValueError:
                        pass
                elif key in ("BOT_TOKEN", "API_HASH", "WORK_DIR"):
                    globals()[key] = value
        print(f"[AKAZA] Loaded configuration from {env_path.name}")
    except Exception as e:
        print(f"[AKAZA] WARNING: Failed to load .env file: {e}")

_load_dotenv()


# ---------------------------------------------------------------------------
#  BRAND CONSTANTS  —  DO NOT TOUCH
# ---------------------------------------------------------------------------
BRAND      = "AKAZA X PROXY"
DEV_HANDLE = "@akaza_isnt"
DEV_URL    = "https://t.me/akaza_isnt"
VERSION    = "v7.0 — Smart filter + button fix"
PROCESS_START_TIME = time.time()

# Resource limits — can be overridden through .env or the process environment.
EXTRACT_MAX_PROXIES = max(1000, int(os.getenv("EXTRACT_MAX_PROXIES", "1000000")))
VERIFY_MAX_PROXIES  = max(100, int(os.getenv("VERIFY_MAX_PROXIES", "50000")))
MAX_FILE_SIZE_MB    = max(1, int(os.getenv("MAX_FILE_SIZE_MB", "2048")))
# Workspace: a folder called `akaza_data` next to this script.
# Can be overridden via WORK_DIR=... in .env
if isinstance(WORK_DIR, str) and WORK_DIR:
    WORK_DIR = Path(WORK_DIR)
elif isinstance(WORK_DIR, Path):
    pass  # already a Path
else:
    # Fallback: data folder next to this script
    WORK_DIR = Path(__file__).resolve().parent / "akaza_data"
DOWNLOADS  = WORK_DIR / "downloads"
OUTPUTS    = WORK_DIR / "outputs"
LOG_FILE   = WORK_DIR / "akaza.log"
USERS_FILE = WORK_DIR / "users.json"

# Create workspace folders (idempotent)
for d in (WORK_DIR, DOWNLOADS, OUTPUTS):
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[AKAZA] WARNING: Could not create {d}: {e}")
        print(f"[AKAZA] Trying fallback to system temp dir...")
        import tempfile
        WORK_DIR = Path(tempfile.gettempdir()) / "akaza_data"
        DOWNLOADS = WORK_DIR / "downloads"
        OUTPUTS   = WORK_DIR / "outputs"
        LOG_FILE   = WORK_DIR / "akaza.log"
        USERS_FILE = WORK_DIR / "users.json"
        for d in (WORK_DIR, DOWNLOADS, OUTPUTS):
            d.mkdir(parents=True, exist_ok=True)
        break

# ---------------------------------------------------------------------------
#  LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [AKAZA] %(levelname)s :: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("AKAZA")


# ===========================================================================
#  1.  ARCHIVE & FILE HANDLING  —  supports everything
# ===========================================================================
SUPPORTED_EXTENSIONS = {
    # plain text-like
    ".txt", ".text", ".log", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml",
    ".ini", ".conf", ".cfg", ".lst", ".list", ".dat", ".srt", ".smi",
    # archives
    ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz",
}

TEXTUAL_EXTENSIONS = {
    ".txt", ".text", ".log", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml",
    ".ini", ".conf", ".cfg", ".lst", ".list", ".dat", ".srt", ".smi",
}


def _safe_read_bytes(data: bytes) -> str:
    """Decode bytes using multiple encodings, fallback to latin-1 ignore."""
    for enc in ("utf-8", "utf-16", "latin-1", "cp1252", "ascii"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore")


def _is_probably_text(data: bytes) -> bool:
    """Heuristic: reject if too many NUL bytes."""
    if not data:
        return False
    sample = data[:4096]
    nul = sample.count(b"\x00")
    return nul < 8


class _PrefixedBinaryReader:
    """Expose a consumed prefix before continuing with the original stream."""

    def __init__(self, prefix: bytes, stream):
        self._prefix = io.BytesIO(prefix)
        self._stream = stream

    def readable(self):
        return True

    def writable(self):
        return False

    def seekable(self):
        return False

    @property
    def closed(self):
        return bool(getattr(self._stream, "closed", False))

    def read(self, size: int = -1):
        if size is None or size < 0:
            return self._prefix.read() + self._stream.read()
        prefix = self._prefix.read(size)
        if len(prefix) < size:
            prefix += self._stream.read(size - len(prefix))
        return prefix


def _stream_binary_lines(binary_fileobj, source_name: str) -> Iterator[Tuple[str, str]]:
    """Yield decoded lines from a binary stream without loading it all."""
    try:
        peek = binary_fileobj.read(4096)
        if not _is_probably_text(peek):
            return
        stream = _PrefixedBinaryReader(peek, binary_fileobj)
        text_stream = io.TextIOWrapper(stream, encoding="utf-8", errors="ignore")
        for line in text_stream:
            yield source_name, line
    except Exception as e:
        log.warning(f"Failed streaming {source_name}: {e}")


def iter_text_lines_from_path(file_path: Path) -> Iterator[Tuple[str, str]]:
    """Stream (source filename, line) pairs from a file or supported archive."""
    ext = file_path.suffix.lower()

    if ext in TEXTUAL_EXTENSIONS or ext == "":
        try:
            with open(file_path, "rb") as f:
                yield from _stream_binary_lines(f, file_path.name)
        except Exception as e:
            log.warning(f"Failed reading {file_path.name}: {e}")
        return

    if ext == ".zip":
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    try:
                        with zf.open(member, "r") as fh:
                            yield from _stream_binary_lines(fh, member.filename)
                    except Exception as e:
                        log.warning(f"ZIP member read failed {member.filename}: {e}")
        except Exception as e:
            log.warning(f"ZIP read failed {file_path.name}: {e}")
        return

    if ext == ".rar":
        try:
            import rarfile  # type: ignore
            try:
                rarfile.UNRAR_TOOL = "unrar"
            except Exception:
                pass
            with rarfile.RarFile(file_path, "r") as rf:
                for member in rf.infolist():
                    if member.is_dir():
                        continue
                    try:
                        with rf.open(member, "r") as fh:
                            yield from _stream_binary_lines(fh, member.filename)
                    except Exception as e:
                        log.warning(f"RAR member read failed {member.filename}: {e}")
        except ImportError:
            log.warning("rarfile not installed — skipping .rar contents")
        except Exception as e:
            log.warning(f"RAR read failed {file_path.name}: {e}")
        return

    if ext == ".7z":
        try:
            import py7zr  # type: ignore
            with tempfile.TemporaryDirectory(prefix="akaza_7z_") as tmp_dir:
                tmp_path = Path(tmp_dir)
                with py7zr.SevenZipFile(file_path, mode="r") as sz:
                    sz.extractall(path=tmp_path)
                for extracted_file in tmp_path.rglob("*"):
                    if not extracted_file.is_file():
                        continue
                    try:
                        rel = str(extracted_file.relative_to(tmp_path))
                        with open(extracted_file, "rb") as fh:
                            yield from _stream_binary_lines(fh, rel)
                    except Exception as e:
                        log.warning(f"7z member read failed {extracted_file}: {e}")
        except ImportError:
            log.warning("py7zr not installed — skipping .7z contents")
        except Exception as e:
            log.warning(f"7z read failed {file_path.name}: {e}")
        return

    if ext in (".tar", ".tgz", ".gz"):
        try:
            with tarfile.open(file_path, "r:*") as tf:
                for member in tf:
                    if not member.isfile():
                        continue
                    try:
                        fobj = tf.extractfile(member)
                        if fobj is not None:
                            yield from _stream_binary_lines(fobj, member.name)
                    except Exception as e:
                        log.warning(f"TAR member read failed {member.name}: {e}")
            return
        except Exception as e:
            if ext != ".gz":
                log.warning(f"TAR read failed {file_path.name}: {e}")
                return
            try:
                with gzip.open(file_path, "rb") as fh:
                    yield from _stream_binary_lines(fh, file_path.stem)
            except Exception as e2:
                log.warning(f"GZ read failed {file_path.name}: {e2}")
            return

    if ext in (".bz2", ".xz"):
        try:
            import bz2
            import lzma
            opener = bz2.open if ext == ".bz2" else lzma.open
            with opener(file_path, "rb") as fh:
                yield from _stream_binary_lines(fh, file_path.stem)
        except Exception as e:
            log.warning(f"Compressed read failed {file_path.name}: {e}")
        return

    try:
        with open(file_path, "rb") as f:
            yield from _stream_binary_lines(f, file_path.name)
    except Exception as e:
        log.warning(f"Failed reading {file_path.name}: {e}")


def iter_text_files_from_path(file_path: Path) -> List[Tuple[str, str]]:
    """Compatibility wrapper that groups streamed lines into text content."""
    grouped: Dict[str, List[str]] = {}
    for source_name, line in iter_text_lines_from_path(file_path):
        grouped.setdefault(source_name, []).append(line)
    return [(source_name, "".join(lines)) for source_name, lines in grouped.items()]


# ===========================================================================
#  2.  PROXY EXTRACTION ENGINE  —  catches every known format
# ===========================================================================
# Strict IPv4: each octet is 0-255, and the whole address is bounded so it can
# never grab a shifted window out of a longer dotted sequence such as a version
# number ("1.2.3.4.5") or an id ("1234.5.6.7.8").  The leading (?<![\d.]) /
# trailing (?![\d.]) guards are what prevent that class of "trash" matches.
_OCTET_RE = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
IPV4_RE   = rf"(?<![\d.])(?:{_OCTET_RE}\.){{3}}{_OCTET_RE}(?![\d.])"
IPV6_RE   = r"(?:[A-Fa-f0-9:]+:+)+[A-Fa-f0-9]+"           # simplified IPv6
HOST_RE   = r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}"
# Port: 2-5 digits, not followed by another digit so ":123456" does not silently
# become port 12345 (which would then be reconstructed against the wrong number).
PORT_RE   = r"\d{2,5}(?!\d)"
USER_RE   = r"[A-Za-z0-9_\-\.]+"
PASS_RE   = r"[A-Za-z0-9_\-\.~!\$&\*\(\)\+\=;:%@\#\?\,\/]+"
# Expanded scheme list — covers HTTP/HTTPS/SOCKS4/SOCKS4a/SOCKS5/SOCKS5h +
# less common ones (quic, ssl, connect, ftp, ssh, proxy).  Unknown schemes
# fall back to "http" in the classifier.
SCHEME_RE = r"(?i:https?|socks[45]?[ha]?|quic|ssl|connect|ftp|ssh|proxy)"

# --- Master pattern collection (19 patterns, ordered by specificity) ---
PROXY_PATTERNS: List[str] = [

    # 1. Full URI: scheme://[user:pass@]host:port
    rf"(?P<scheme>{SCHEME_RE})://"
    rf"(?:(?P<u1>{USER_RE}):(?P<p1>{PASS_RE})@)?"
    rf"(?P<h1>{IPV4_RE}|{HOST_RE}):(?P<port1>{PORT_RE})",

    # 2. user:pass@host:port  (no scheme — inferred as http)
    rf"(?P<u2>{USER_RE}):(?P<p2>{PASS_RE})@"
    rf"(?P<h2>{IPV4_RE}|{HOST_RE}):(?P<port2>{PORT_RE})",

    # 3. host:port:user:pass
    rf"(?P<h3>{IPV4_RE}):(?P<port3>{PORT_RE}):"
    rf"(?P<u3>{USER_RE}):(?P<p3>{PASS_RE})\b",

    # 4. host:port|user|pass  (pipe separated)
    rf"(?P<h4>{IPV4_RE}):(?P<port4>{PORT_RE})\|"
    rf"(?P<u4>[^|\s]+)\|(?P<p4>[^|\s]+)",

    # 5. host:port;user;pass  (semicolon separated)
    rf"(?P<h5>{IPV4_RE}):(?P<port5>{PORT_RE});"
    rf"(?P<u5>[^;\s]+);(?P<p5>[^;\s]+)",

    # 6. host port user pass  (4 space-separated tokens)
    rf"(?P<h6>{IPV4_RE})\s+(?P<port6>{PORT_RE})\s+"
    rf"(?P<u6>\S+)\s+(?P<p6>\S+)",

    # 7. host port  (bare ip + space + port)
    rf"(?P<h7>{IPV4_RE})\s+(?P<port7>{PORT_RE})\b",

    # 8. CSV: host,port[,user,pass]
    rf"(?P<h9>{IPV4_RE}|{HOST_RE}),(?P<port9>{PORT_RE})"
    rf"(?:,(?P<u9>[^,\s]+),(?P<p9>[^,\s]+))?",

    # 9. Tab-separated: host\tport[\tuser\tpass]
    rf"(?P<h10>{IPV4_RE}|{HOST_RE})\t(?P<port10>{PORT_RE})"
    rf"(?:\t(?P<u10>[^\t\s]+)\t(?P<p10>[^\t\s]+))?",

    # 10. YAML / Markdown list:  - host:port   or   * host:port   or   + host:port
    rf"[\-\*\+]\s+(?P<h11>{IPV4_RE}|{HOST_RE}):(?P<port11>{PORT_RE})",

    # 11. Bracketed host:  [host]:port
    rf"\[(?P<h12>{IPV4_RE}|{HOST_RE})\]:(?P<port12>{PORT_RE})",

    # 12. Fully bracketed:  [host:port]
    rf"\[(?P<h13>{IPV4_RE}|{HOST_RE}):(?P<port13>{PORT_RE})\]",

    # 13. Quoted:  "host:port"  or  'host:port'
    rf"[\"'](?P<h14>{IPV4_RE}|{HOST_RE}):(?P<port14>{PORT_RE})[\"']",

    # 14. IPv6 bracketed:  [2001:db8::1]:8080
    rf"\[(?P<h15>{IPV6_RE})\]:(?P<port15>{PORT_RE})",

    # 15. env-var form:  http_proxy=host:port  /  https_proxy=...  /  all_proxy=...
    rf"(?i:(?:https?|all|socks[45]?)_proxy)=(?P<h16>{IPV4_RE}|{HOST_RE}):(?P<port16>{PORT_RE})",

    # 16. CLI flag:  --proxy host:port  or  --proxy=host:port
    rf"--proxy[=\s]+(?P<h17>{IPV4_RE}|{HOST_RE}):(?P<port17>{PORT_RE})",

    # 17. proxy=host:port[:user:pass]
    rf"(?i:proxy)=(?P<h18>{IPV4_RE}|{HOST_RE}):(?P<port18>{PORT_RE})"
    rf"(?::(?P<u18>{USER_RE}):(?P<p18>{PASS_RE}))?",

    # 18. PROTO host:port  (e.g. "HTTP 1.2.3.4:8080", "SOCKS5 1.2.3.4:1080")
    rf"(?i:(?P<scheme2>https?|socks[45][ha]?))\s+(?P<h19>{IPV4_RE}|{HOST_RE}):(?P<port19>{PORT_RE})",

    # 19. host:port (PROTO)  or  host:port [PROTO]
    rf"(?P<h20>{IPV4_RE}|{HOST_RE}):(?P<port20>{PORT_RE})\s*[\(\[]"
    rf"(?i:(?P<scheme3>https?|socks[45][ha]?))[\)\]]",

    # 20. host:port:PROTO  (e.g. "1.2.3.4:8080:http")
    rf"(?P<h21>{IPV4_RE}):(?P<port21>{PORT_RE}):(?i:(?P<scheme4>https?|socks[45][ha]?))\b",

    # 21. bare host:port (LAST RESORT — must stay last)
    rf"(?P<h8>{IPV4_RE}):(?P<port8>{PORT_RE})",
]

# Pre-compile for speed
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in PROXY_PATTERNS]

# Canonical full-line formats. The legacy patterns above remain for
# compatibility, but extraction uses this stricter ordered set.
_HOST_TOKEN = rf"(?:{IPV4_RE}|{HOST_RE})"
_AUTH_TOKEN = rf"(?:(?P<user>{USER_RE}):(?P<password>{PASS_RE})@)?"
PROXY_PATTERNS = [
    rf"^(?P<scheme>{SCHEME_RE})://{_AUTH_TOKEN}(?P<host>{_HOST_TOKEN}):(?P<port>{PORT_RE})$",
    rf"^(?P<user>{USER_RE}):(?P<password>{PASS_RE})@(?P<host>{_HOST_TOKEN}):(?P<port>{PORT_RE})$",
    rf"^(?P<host>{IPV4_RE}):(?P<port>{PORT_RE}):(?P<user>{USER_RE}):(?P<password>{PASS_RE})$",
    rf"^(?P<host>{IPV4_RE}):(?P<port>{PORT_RE})\|(?P<user>[^|\s]+)\|(?P<password>[^|\s]+)$",
    rf"^(?P<host>{IPV4_RE}):(?P<port>{PORT_RE});(?P<user>[^;\s]+);(?P<password>[^;\s]+)$",
    rf"^(?P<host>{_HOST_TOKEN})\|(?P<port>{PORT_RE})$",
    rf"^(?P<host>{_HOST_TOKEN}),(?P<port>{PORT_RE})(?:,(?P<user>[^,\s]+),(?P<password>[^,\s]+))?$",
    rf"^(?P<host>{_HOST_TOKEN})\t(?P<port>{PORT_RE})(?:\t(?P<user>[^\t\s]+)\t(?P<password>[^\t\s]+))?$",
    rf"^(?P<host>{_HOST_TOKEN})\s+(?P<port>{PORT_RE})(?:\s+(?P<user>\S+)\s+(?P<password>\S+))?$",
    rf"^\[(?P<host>{IPV6_RE})\]:(?P<port>{PORT_RE})$",
    rf"^\[(?P<host>{_HOST_TOKEN})\]:(?P<port>{PORT_RE})$",
    rf"^(?P<scheme>https?|socks[45][ha]?)\s+(?P<host>{_HOST_TOKEN}):(?P<port>{PORT_RE})$",
    rf"^(?P<host>{_HOST_TOKEN}):(?P<port>{PORT_RE}):(?P<scheme>https?|socks[45][ha]?)$",
    rf"^(?P<host>{_HOST_TOKEN}):(?P<port>{PORT_RE})$",
]
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in PROXY_PATTERNS]

# Global strict-mode flag — admin can toggle via /strict and /lenient commands.
# When True (default), the bot rejects trash like ULP URLs, log entries,
# database connection strings, private IPs, and non-proxy ports.
STRICT_MODE = True

# ============================================================================
#  SMART FILTERING — prevents "trash" false positives from ULP files
# ============================================================================

# Common proxy ports — used as a strong signal that an ip:port is really a proxy.
# (URIs like https://example.com:443/login.php should NOT be treated as proxies
#  unless they have a proxy scheme like socks5://)
COMMON_PROXY_PORTS = {
    # HTTP proxies
    80, 81, 3128, 8080, 8081, 8082, 8083, 8088, 8090, 8118, 8888, 9090, 9091,
    # HTTPS proxies
    443, 8443, 4443,
    # SOCKS proxies
    1080, 1081, 1082, 1083, 1084, 1085, 1086, 1087, 1088, 1089,
    4145, 4146,           # SOCKS4
    4153, 4154,           # SOCKS4a
    # SOCKS5 alt
    9050, 9051, 9150,
    # Misc proxy / tunnel
    3124, 3127, 3132, 53281, 65103, 65203, 65303,
    # Squid
    3128,
    # TinyProxy
    8888,
    # Charles Proxy / Fiddler
    8889, 8866, 7777,
    # Shadowsocks / V2Ray common
    8388, 8389, 10086,
    # Common alt ranges
    8000, 8001, 8008, 8089, 8181, 8223, 8444, 8445, 8530, 8889, 9000, 9001,
}
BARE_PROXY_PORTS = COMMON_PROXY_PORTS - {80, 443}

# Reserved / private IP ranges that are almost never public proxies
# (we still allow them, but flag as suspicious)
PRIVATE_IP_PREFIXES = ("10.", "127.", "169.254.", "192.168.", "172.16.",
                       "172.17.", "172.18.", "172.19.", "172.20.",
                       "172.21.", "172.22.", "172.23.", "172.24.",
                       "172.25.", "172.26.", "172.27.", "172.28.",
                       "172.29.", "172.30.", "172.31.", "0.")


def _valid_port(p) -> bool:
    try:
        n = int(p)
        return 1 <= n <= 65535
    except Exception:
        return False


def _valid_ipv4(ip: str) -> bool:
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        try:
            n = int(part)
            if n < 0 or n > 255:
                return False
        except Exception:
            return False
    return True


def _is_private_ip(ip: str) -> bool:
    """Returns True if IP is in a private/reserved range (not a public proxy)."""
    return ip.startswith(PRIVATE_IP_PREFIXES)


def _looks_like_proxy_line(line: str, scheme: str, host: str, port: int,
                           explicit_scheme: bool = False) -> bool:
    """
    Smart context filter — returns True if this line REALLY looks like a proxy.

    Rejects:
      • URLs with paths:  https://example.com/login.php  (not a proxy!)
      • URLs with query strings
      • Lines that look like log entries
      • Bare host:port from database connection strings
      • IP addresses from JSON / config files that aren't proxy lists
    """
    line_lower = line.lower()
    line_stripped = line.strip()

    # 1. SOCKS schemes — always accept (these are ALWAYS proxies, never websites)
    if explicit_scheme and scheme.startswith("socks"):
        return True

    # 2. http:// or https:// URLs — must NOT have a path/query to be a proxy
    if explicit_scheme and scheme in ("http", "https") and "://" in line_lower:
        # It's a URL — must NOT have a path/query to be a proxy
        after_scheme = line_lower.split("://", 1)[1] if "://" in line_lower else ""
        if "@" in after_scheme:
            after_scheme = after_scheme.rsplit("@", 1)[1]
        # Reject if there's a path / query / fragment after host:port
        for sep in ("/", "?", "#"):
            if sep in after_scheme:
                return False
        # Reject URLs that look like website resources
        website_indicators = (".php", ".html", ".aspx", ".jsp", ".gif", ".jpg",
                              ".png", ".css", ".js", ".xml", ".rss", ".woff",
                              ".ttf", ".svg", ".ico", ".pdf", ".zip", ".tar",
                              ".gz", ".rar", ".7z")
        if any(ind in line_lower for ind in website_indicators):
            return False
        # Reject if it contains common ULP / URL keywords
        ulp_keywords = ("login", "signin", "auth", "session", "cookie", "account",
                        "register", "signup", "dashboard", "admin", "wp-",
                        "checkout", "cart", "shop", "product", "category",
                        "search", "query", "api/", "v1/", "v2/", "user/",
                        "profile", "settings", "config", ".env", "uploads",
                        "download", "view", "edit", "delete", "create",
                        "logout", "reset", "verify", "confirm")
        if any(kw in line_lower for kw in ulp_keywords):
            return False
        return True

    # 3. Non-proxy schemes (ftp, ssh, quic, ssl, connect, proxy)
    if explicit_scheme and scheme not in ("http", "https", ""):
        # Accept only on common proxy ports
        return port in COMMON_PROXY_PORTS

    # 4. Bare ip:port (no scheme, or scheme defaulted to http by classifier)
    # Apply STRICT filtering — this is where most trash comes from
    # Reject if there are URL-like indicators
    if any(x in line_lower for x in ("http://", "https://", "ftp://",
                                      ".php", ".html", ".aspx", ".jsp",
                                      "login", "password=", "user=", "session",
                                      "cookie", "select ", "insert ",
                                      "update ", "create ", "drop ",
                                      "where ", "from ", "table ",
                                      "mailto:", "javascript:", "data:")):
        return False

    # Reject private IPs (they're not public proxies)
    if _is_private_ip(host):
        return False

    # Must be on a common proxy port
    if port not in BARE_PROXY_PORTS:
        return False

    # Reject if the line has too many words (looks like a log entry)
    # A proxy line should have at most: host port user pass  (4 tokens)
    # or host:port|user|pass etc.
    # If there are more than 6 whitespace-separated tokens, it's a log.
    if len(line_stripped.split()) > 6:
        return False

    # Reject if the line contains typical log markers
    log_markers = ("GET ", "POST ", "PUT ", "DELETE ", "HEAD ", "OPTIONS ",
                   "HTTP/", "[error]", "[notice]", "[warn]", "traceback",
                   "exception", "error:", "warning:", "fatal", "panic")
    if any(marker in line_lower for marker in log_markers):
        return False

    return True



def _classify_proxy(scheme: str, host: str, port: str,
                    username: Optional[str] = None,
                    password: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Build a normalized proxy dict or None if invalid."""
    if not _valid_port(port):
        return None
    if not (_valid_ipv4(host) or _valid_ipv6(host)
            or re.match(rf"^{HOST_RE}$", host)):
        return None

    scheme = (scheme or "").lower()
    if not scheme:
        scheme = "http"  # default assumption for bare ip:port
    if scheme in ("http", "https"):
        proxy_type = "http"
    elif scheme.startswith("socks4"):
        proxy_type = "socks4"
    elif scheme.startswith("socks5"):
        proxy_type = "socks5"
    else:
        proxy_type = "http"

    proxy = {
        "type":    proxy_type,
        "scheme":  scheme,
        "host":    host,
        "port":    int(port),
        "username": username or None,
        "password": password or None,
        "raw":     _reconstruct_proxy(scheme, host, port, username, password),
    }
    return proxy


def _valid_ipv6(host: str) -> bool:
    try:
        ipaddress.IPv6Address(host)
        return True
    except Exception:
        return False


def _reconstruct_proxy(scheme: str, host: str, port: str,
                       user: Optional[str], pwd: Optional[str]) -> str:
    auth = f"{user}:{pwd}@" if user and pwd else ""
    host_text = f"[{host}]" if _valid_ipv6(host) else host
    return f"{scheme}://{auth}{host_text}:{port}"


def extract_proxies_from_lines(lines_iterable: Iterable[str], strict: bool = True,
                               seen: Optional[Set[Tuple]] = None,
                               cap: Optional[int] = None,
                               log_rejections: bool = True) -> Iterator[Dict[str, Any]]:
    """Yield deduplicated proxies from an iterable of lines."""
    seen = seen if seen is not None else set()
    produced = 0
    rejected_trash = 0

    for line in lines_iterable:
        candidate = line.strip()
        if not candidate:
            continue
        candidate = re.sub(r"^(?:[-*+])\s+", "", candidate)
        candidate = re.sub(r"\s+#.*$", "", candidate).strip()
        if len(candidate) >= 2 and candidate[0] in "\"'" and candidate[-1] == candidate[0]:
            candidate = candidate[1:-1].strip()
        elif candidate.startswith("[") and candidate.endswith("]") and candidate.count(":") == 1:
            candidate = candidate[1:-1].strip()
        if not candidate:
            continue

        # Every accepted token must span the complete normalized line.
        for pat in _COMPILED_PATTERNS:
            m = pat.fullmatch(candidate)
            if not m:
                continue

            g = m.groupdict()
            scheme = (g.get("scheme") or "").lower()
            host = g.get("host") or ""
            port = g.get("port") or ""
            user = g.get("user") or ""
            pwd = g.get("password") or ""

            proxy = _classify_proxy(scheme, host, port, user, pwd)
            if not proxy:
                continue

            # === SMART FILTER — reject trash ===
            if strict:
                try:
                    port_int = int(proxy["port"])
                except Exception:
                    port_int = 0
                if not _looks_like_proxy_line(
                    candidate, proxy.get("scheme", ""), host, port_int,
                    explicit_scheme=bool(scheme),
                ):
                    rejected_trash += 1
                    continue  # try next pattern on this line

            key = (proxy["type"], proxy["host"], proxy["port"],
                   proxy["username"], proxy["password"])
            if key in seen:
                continue
            seen.add(key)
            yield proxy
            produced += 1
            if cap is not None and produced >= cap:
                return
            break  # one proxy per line is the common case

    if rejected_trash > 0 and strict and log_rejections:
        log.info(f"Smart filter rejected {rejected_trash} trash entries (URLs, log lines, non-proxy ports, etc.)")

def extract_proxies_from_text(text: str, strict: bool = True) -> List[Dict[str, Any]]:
    """
    Scan a blob of text and return every proxy we can identify.
    De-duplicates on (type, host, port, user, pass).

    Processes line-by-line so that patterns never accidentally merge two
    proxies that happen to sit on consecutive lines.

    If `strict=True` (default), applies smart filtering to reject trash
    like ULP URLs (https://example.com/login.php), database connection
    strings, log entries, private IPs, and non-proxy ports.
    """
    lines = re.split(r"\r\n|\r|\n", text)
    return list(extract_proxies_from_lines(lines, strict=strict))


def run_filter_selftest() -> bool:
    """Validate canonical positive formats and ULP rejection samples."""
    positive = [
        "1.2.3.4:8080",
        "socks5://1.2.3.4:1080",
        "user:pass@1.2.3.4:3128",
        "1.2.3.4:8080:user:pass",
        "1.2.3.4|8080",
        "1.2.3.4,8080,user,pass",
        "1.2.3.4\t8080\tuser\tpass",
        "HTTP 1.2.3.4:8080",
        "1.2.3.4:8080:socks5",
    ]
    negative = [
        "https://site.com/login.php:user:pass",
        "example.com:443",
        "1.2.3.4:443",
        "[error] GET /x 1.2.3.4:80",
        '{"proxy": "1.2.3.4:8080"}',
        "email@x.com:password",
    ]
    failures = []
    for sample in positive:
        if not extract_proxies_from_text(sample):
            failures.append(f"positive rejected: {sample}")
    for sample in negative:
        if extract_proxies_from_text(sample):
            failures.append(f"negative accepted: {sample}")
    if failures:
        print("FILTER SELFTEST: FAIL")
        for failure in failures:
            print(f"  - {failure}")
        return False
    print(
        f"FILTER SELFTEST: PASS ({len(positive)} positive, "
        f"{len(negative)} negative)"
    )
    return True


def extract_proxies_from_files(file_path: Path, strict: bool = True) -> Dict[str, List[Dict[str, Any]]]:
    """
    Returns a mapping:  { source_filename : [proxy_dict, ...] }
    Works for plain text files AND archives (.zip / .rar / .7z / .tar / .gz ...).

    If `strict=True` (default), applies smart filtering to reject trash.
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    seen: Set[Tuple] = set()
    total = 0

    for source_name, line in iter_text_lines_from_path(file_path):
        if total >= EXTRACT_MAX_PROXIES:
            break
        for proxy in extract_proxies_from_lines(
            (line,), strict=strict, seen=seen,
            cap=EXTRACT_MAX_PROXIES - total,
            log_rejections=False,
        ):
            out.setdefault(source_name, []).append(proxy)
            total += 1
            if total >= EXTRACT_MAX_PROXIES:
                break
    if total >= EXTRACT_MAX_PROXIES:
        log.warning(f"Extraction proxy cap reached ({EXTRACT_MAX_PROXIES}); remaining input skipped")
    return out


# ===========================================================================
#  3.  PROXY VERIFICATION ENGINE  —  parallel + smart
# ===========================================================================
VERIFY_TIMEOUT = 8          # seconds per proxy
VERIFY_URL     = "http://httpbin.org/ip"   # lightweight endpoint
VERIFY_URL_HTTPS = "https://httpbin.org/ip"
VERIFY_THREADS = 60          # parallel workers
MY_PUBLIC_IP: Optional[str] = None

try:
    import requests
    from requests.adapters import HTTPAdapter
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass
    REQUESTS_AVAILABLE = True
except Exception:
    REQUESTS_AVAILABLE = False


def _build_proxies_dict(proxy: Dict[str, Any]) -> Dict[str, str]:
    """Build the dict that `requests` expects."""
    auth = ""
    if proxy["username"] and proxy["password"]:
        auth = f"{proxy['username']}:{proxy['password']}@"
    scheme = proxy["scheme"].lower()
    if scheme.startswith("socks5"):
        scheme = "socks5h"
    elif scheme.startswith("socks4"):
        scheme = "socks4a"
    host = f"[{proxy['host']}]" if _valid_ipv6(proxy["host"]) else proxy["host"]
    url = f"{scheme}://{auth}{host}:{proxy['port']}"
    return {"http": url, "https": url}


def _parse_echo_ip(payload: Any, key: str) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    candidate = value.split(",", 1)[0].strip()
    return candidate if _valid_ipv4(candidate) else None


def detect_public_ip() -> Optional[str]:
    """Detect and cache this host's direct public IPv4 address."""
    global MY_PUBLIC_IP
    if MY_PUBLIC_IP is not None:
        return MY_PUBLIC_IP
    if not REQUESTS_AVAILABLE:
        return None
    try:
        response = requests.get(
            VERIFY_URL, timeout=min(VERIFY_TIMEOUT, 4),
            allow_redirects=False,
        )
        if response.status_code == 200:
            MY_PUBLIC_IP = _parse_echo_ip(response.json(), "origin")
    except Exception:
        pass
    if MY_PUBLIC_IP is None:
        try:
            response = requests.get(
                "https://api.ipify.org?format=json",
                timeout=min(VERIFY_TIMEOUT, 4),
                allow_redirects=False,
            )
            if response.status_code == 200:
                MY_PUBLIC_IP = _parse_echo_ip(response.json(), "ip")
        except Exception:
            pass
    return MY_PUBLIC_IP


def verify_one_proxy(proxy: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test a single proxy. Returns the proxy dict augmented with:
        working: bool
        latency_ms: int
        error: Optional[str]
    """
    result = dict(proxy)
    result["working"]    = False
    result["latency_ms"] = 0
    result["error"]      = None

    if not REQUESTS_AVAILABLE:
        result["error"] = "requests library missing"
        return result

    proxies = _build_proxies_dict(proxy)
    start = time.time()
    last_error = None
    for url, key in ((VERIFY_URL, "origin"),
                     ("https://api.ipify.org?format=json", "ip")):
        try:
            response = requests.get(
                url, proxies=proxies, timeout=VERIFY_TIMEOUT,
                verify=False, allow_redirects=False,
            )
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}"
                continue
            try:
                remote_ip = _parse_echo_ip(response.json(), key)
            except Exception:
                remote_ip = None
            if remote_ip is None:
                last_error = "bad-body"
                continue
            if MY_PUBLIC_IP and remote_ip == MY_PUBLIC_IP:
                result["error"] = "bypass/no-relay"
                return result
            result["working"] = True
            result["latency_ms"] = int((time.time() - start) * 1000)
            return result
        except requests.exceptions.ProxyError:
            last_error = "proxy error"
        except requests.exceptions.ConnectTimeout:
            last_error = "connect timeout"
        except requests.exceptions.ReadTimeout:
            last_error = "read timeout"
        except requests.exceptions.ConnectionError:
            last_error = "connection refused"
        except requests.exceptions.SSLError:
            last_error = "ssl error"
        except Exception as e:
            last_error = type(e).__name__
    result["error"] = last_error or "bypass/no-relay"
    return result


def verify_proxies_batch(proxies: List[Dict[str, Any]],
                         progress_cb=None) -> List[Dict[str, Any]]:
    """Verify a list of proxies in parallel. Returns augmented list."""
    if not proxies:
        return []
    detect_public_ip()
    results: List[Dict[str, Any]] = [None] * len(proxies)   # type: ignore

    with ThreadPoolExecutor(max_workers=VERIFY_THREADS) as ex:
        future_to_idx = {ex.submit(verify_one_proxy, p): i for i, p in enumerate(proxies)}
        done = 0
        total = len(proxies)
        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                results[idx] = fut.result()
            except Exception as e:
                results[idx] = dict(proxies[idx])
                results[idx]["working"]    = False
                results[idx]["latency_ms"] = 0
                results[idx]["error"]      = f"verify exception: {e}"
            done += 1
            if progress_cb and (done % 5 == 0 or done == total):
                try:
                    progress_cb(done, total)
                except Exception:
                    pass
    return results


def verify_proxies_streaming(proxies: List[Dict[str, Any]],
                              on_result=None,
                              on_progress=None):
    """
    Verify in parallel; call `on_result(result_dict)` for EACH finished proxy
    (so the caller can stream live notifications) and `on_progress(done, total)`
    for periodic status updates.

    Returns the full augmented list as results complete.
    """
    if not proxies:
        return []
    detect_public_ip()
    results: List[Dict[str, Any]] = []
    total = len(proxies)

    with ThreadPoolExecutor(max_workers=VERIFY_THREADS) as ex:
        proxy_iter = iter(proxies)
        future_to_proxy: Dict[Any, Dict[str, Any]] = {}
        window = max(VERIFY_THREADS, VERIFY_THREADS * 4)

        def submit_next():
            try:
                proxy = next(proxy_iter)
            except StopIteration:
                return False
            future_to_proxy[ex.submit(verify_one_proxy, proxy)] = proxy
            return True

        for _ in range(window):
            if not submit_next():
                break

        done = 0
        last_progress_tick = 0
        while future_to_proxy:
            completed, _ = wait(
                future_to_proxy, return_when=FIRST_COMPLETED
            )
            for fut in completed:
                proxy = future_to_proxy.pop(fut)
                try:
                    r = fut.result()
                except Exception as e:
                    r = dict(proxy)
                    r["working"]    = False
                    r["latency_ms"] = 0
                    r["error"]      = f"verify exception: {e}"
                results.append(r)
                done += 1
                submit_next()
                # Per-result callback (for live notifications)
                if on_result is not None:
                    try:
                        on_result(r)
                    except Exception:
                        pass
                # Progress callback (throttled to every 3 results or 1 second)
                now = time.time()
                if on_progress is not None and (done % 3 == 0 or done == total
                                                 or now - last_progress_tick > 1.0):
                    last_progress_tick = now
                    try:
                        on_progress(done, total)
                    except Exception:
                        pass
    return results


# ===========================================================================
#  4.  TELEGRAM BOT  —  Pyrogram-based with dashboard UI
# ===========================================================================
try:
    from pyrogram import Client, filters, raw
    from pyrogram.file_id import FileId, FileType
    from pyrogram.session import Auth, Session
    from pyrogram.errors import MessageNotModified
    from pyrogram.types import (
        Message, CallbackQuery, InlineKeyboardMarkup,
        InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton,
        ReplyKeyboardRemove, Document,
    )
    PYROGRAM_AVAILABLE = True
except Exception:
    PYROGRAM_AVAILABLE = False
    MessageNotModified = type("MessageNotModified", (Exception,), {})
    raw = FileId = FileType = Auth = Session = None

PYROGRAM_PARALLEL_SESSIONS = max(
    1, int(os.getenv("PYROGRAM_PARALLEL_SESSIONS", "4"))
)
PYROGRAM_PARALLEL_PER_SESSION = max(
    1, int(os.getenv("PYROGRAM_PARALLEL_PER_SESSION", "4"))
)
CHUNK_SIZE = 1024 * 1024
PYROGRAM_SLEEP_THRESHOLD = max(
    0, int(os.getenv("PYROGRAM_SLEEP_THRESHOLD", "60"))
)


async def _open_media_session(client: "Client", dc_id: int):
    """Open a media session for parallel upload.GetFile requests."""
    home_dc = await client.storage.dc_id()
    test_mode = await client.storage.test_mode()
    if dc_id == home_dc:
        auth_key = await client.storage.auth_key()
    else:
        auth_key = await Auth(client, dc_id, test_mode).create()
    session = Session(client, dc_id, auth_key, test_mode, is_media=True)
    await session.start()
    if dc_id != home_dc:
        exported = await client.invoke(
            raw.functions.auth.ExportAuthorization(dc_id=dc_id)
        )
        await session.invoke(
            raw.functions.auth.ImportAuthorization(
                id=exported.id, bytes=exported.bytes
            )
        )
    return session


async def _parallel_download(client, message, out_path: str, file_size: int,
                             progress_cb=None, cancel_cb=None) -> str:
    """Download document chunks concurrently across media sessions."""
    if raw is None or FileId is None:
        raise NotImplementedError("Pyrogram raw media API unavailable")
    media = message.document or getattr(message, "video", None)
    if media is None:
        raise NotImplementedError("message has no document media")
    file_id = FileId.decode(media.file_id)
    supported = (
        FileType.DOCUMENT, FileType.VIDEO, FileType.AUDIO,
        FileType.ANIMATION, FileType.VOICE, FileType.VIDEO_NOTE,
    )
    if file_id.file_type not in supported:
        raise NotImplementedError("unsupported media type")

    location = raw.types.InputDocumentFileLocation(
        id=file_id.media_id,
        access_hash=file_id.access_hash,
        file_reference=file_id.file_reference,
        thumb_size=file_id.thumbnail_size or "",
    )
    total_chunks = max(1, (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.truncate(file_size)
    fd = os.open(out_path, os.O_WRONLY)
    sessions = []
    next_idx = 0
    downloaded = 0
    last_progress = 0
    idx_lock = asyncio.Lock()
    write_lock = asyncio.Lock()

    async def next_chunk():
        nonlocal next_idx
        async with idx_lock:
            if next_idx >= total_chunks:
                return None
            idx = next_idx
            next_idx += 1
            return idx

    async def fetch(session, offset):
        try:
            from pyrogram.errors import FloodWait
        except Exception:
            FloodWait = ()  # type: ignore
        attempts = 0
        while True:
            attempts += 1
            try:
                response = await session.invoke(
                    raw.functions.upload.GetFile(
                        location=location, offset=offset, limit=CHUNK_SIZE
                    ),
                    sleep_threshold=PYROGRAM_SLEEP_THRESHOLD,
                )
            except Exception as exc:
                if FloodWait and isinstance(exc, FloodWait) and attempts < 5:
                    await asyncio.sleep(float(getattr(exc, "value", 5)))
                    continue
                raise
            if isinstance(response, raw.types.upload.FileCdnRedirect):
                raise NotImplementedError("CDN redirect")
            if not isinstance(response, raw.types.upload.File):
                raise RuntimeError(
                    f"unexpected GetFile response: {type(response).__name__}"
                )
            return response.bytes

    async def worker(session):
        nonlocal downloaded, last_progress
        while True:
            if cancel_cb is not None and cancel_cb():
                return
            idx = await next_chunk()
            if idx is None:
                return
            chunk = await fetch(session, idx * CHUNK_SIZE)
            async with write_lock:
                os.pwrite(fd, chunk, idx * CHUNK_SIZE)
                downloaded += len(chunk)
                if progress_cb is not None and (
                    downloaded - last_progress >= 2 * CHUNK_SIZE
                    or downloaded >= file_size
                ):
                    last_progress = downloaded
                    await progress_cb(downloaded, file_size)

    try:
        file_id_dc = file_id.dc_id
        for _ in range(PYROGRAM_PARALLEL_SESSIONS):
            sessions.append(await _open_media_session(client, file_id_dc))
        tasks = [
            asyncio.create_task(worker(session))
            for session in sessions
            for _ in range(PYROGRAM_PARALLEL_PER_SESSION)
        ]
        try:
            await asyncio.gather(*tasks)
        except Exception:
            for task in tasks:
                task.cancel()
            raise
    finally:
        os.close(fd)
        for session in sessions:
            try:
                await session.stop()
            except Exception:
                pass
    if file_size and os.path.getsize(out_path) != file_size:
        raise RuntimeError(
            f"Incomplete download: got {os.path.getsize(out_path):,} "
            f"of {file_size:,} bytes"
        )
    return out_path


# ---- Branding strings -----------------------------------------------------
BANNER = f"""
╔══════════════════════════════════════════╗
║   {BRAND:^36s}   ║
║   Telegram Proxy Extractor & Verifier    ║
╚══════════════════════════════════════════╝

 DEV  : {DEV_HANDLE}
 VER  : {VERSION}
"""

WELCOME_TEXT = f"""
**{BRAND}**
_Telegram Proxy Extractor & Verifier_

👋 Welcome!  Anyone can use this bot.

Send me any file containing proxies — I will:
  1.  Extract every proxy (HTTP / HTTPS / SOCKS4 / SOCKS5 + all variants)
  2.  Verify each one in parallel
  3.  Return a clean working-proxies file

**Supported file formats**
`.txt .log .csv .json .xml .yaml .ini .lst .dat`
`.zip .rar .7z .tar .gz .tgz .bz2 .xz`

**Supported proxy formats**
`http://ip:port`
`https://user:pass@ip:port`
`socks4://ip:port`
`socks5://user:pass@ip:port`
`ip:port:user:pass`
`ip:port|user|pass`
`ip:port;user;pass`
`user:pass@ip:port`
`ip:port`
`ip port`

**Commands**
`/start`        — Dashboard
`/help`         — Help menu
`/stats`        — Your stats
`/myinfo`       — Your account details
`/myproxies`    — View your working proxy history (with timestamps)
`/settings`     — Toggle live proxy notifications
`/about`        — About the bot

— All credits: **{DEV_HANDLE}**
"""

HELP_TEXT = f"""
**{BRAND} — Help Menu**

**User commands**
`/start`        — Show dashboard (new users get a welcome tutorial)
`/help`         — This help message
`/stats`        — Show your statistics
`/myinfo`       — Show your account details
`/myproxies`    — View your working proxy history
`/settings`     — Toggle live notif + filters + export format
`/leaderboard`  — Top 10 users by working proxies found 🏆
`/about`        — About the bot

**Admin commands** *(admin only)*
`/admin`          — Open admin panel
`/ban`            — Ban user (reply or `/ban <user_id>`)
`/unban <id>`     — Unban a user
`/approve`        — Approve user (reply or `/approve <user_id>`)
`/unapprove <id>` — Remove approval
`/lock`           — Lock bot (only admin + approved users can use)
`/unlock`         — Unlock bot (open to everyone)
`/users`          — List all users
`/userinfo <id>`  — Show details for a specific user
`/broadcast <msg>`   — Send a message to every user (with live progress)
`/backup`        — Download a backup of users.json
`/health`        — System health check (users, proxies, disk, engine)
`/auditlog`      — View last 15 admin actions
`/purgeaudit`    — Clear the audit log
`/strict`        — 🛡️ Enable smart filter (rejects ULP URLs, trash, non-proxy ports)
`/lenient`       — ⚠️ Disable smart filter (accept every ip:port found)
`/mode`          — Show current extraction mode
`/clear`         — Clear workspace cache

**Dashboard buttons**
🚀 Send File to Extract — upload a file to scan
📊 My Stats            — your lifetime statistics
📋 My Working Proxies  — every working proxy we've ever found for you,
                          with the timestamp of when each was verified
                          and its latency.  You can download all of them
                          as a .txt or clear the history.
❓ Help / 👤 About
ℹ️ My Info / ⚙️ Settings
🛡️ Admin Panel (admin only — cannot be forwarded)

**⚙️ Settings — Live Proxy Notifications**
• **ON** (default) — every working proxy is sent to your chat live as
  it is verified (batched every 3 seconds or 5 proxies to avoid spam),
  plus the final .txt summary at the end.
• **OFF** — you only receive the final .txt summary at the end.

**📥 MTProto Download**
Files are downloaded using Pyrogram's MTProto engine with the configured
worker and transmission limits.  Download progress is shown live
(MB downloaded / total MB / speed / ETA).

**📊 Live Dashboard**
While processing, you'll see real-time updates:
• Download: file size, % done, MB/s speed, ETA
• Extract: time spent, number of proxies found
• Verify: parallel workers, working/failed counters
• Final: complete timing summary (download + extract + verify)

**Supported file formats**
`.txt .log .csv .tsv .json .xml .yaml .ini .lst .dat .srt .smi`
`.zip .rar .7z .tar .gz .tgz .bz2 .xz`

**Supported proxy formats (20+ patterns)**
• Full URI: `http(s)://[user:pass@]host:port` (also socks4/4a/5/5h, quic, ssl)
• `user:pass@host:port`
• `host:port:user:pass`
• `host:port|user|pass` and `host:port;user;pass`
• `host port [user pass]` (space-separated)
• CSV: `host,port[,user,pass]`
• Tab-separated: `host\\tport[\\tuser\\tpass]`
• YAML/Markdown list: `- host:port` / `* host:port` / `+ host:port`
• Bracketed: `[host]:port` and `[host:port]`
• Quoted: `"host:port"` and `'host:port'`
• IPv6: `[2001:db8::1]:8080`
• Env-var: `http_proxy=host:port` / `https_proxy=...` / `all_proxy=...`
• CLI flag: `--proxy host:port` and `--proxy=host:port`
• `proxy=host:port[:user:pass]`
• `PROTO host:port` (e.g. `HTTP 1.2.3.4:8080`)
• `host:port (PROTO)` and `host:port [PROTO]`
• `host:port:PROTO` (e.g. `1.2.3.4:8080:socks5`)
• Bare `host:port` (last-resort)

**Smart verification** — {VERIFY_TIMEOUT}s timeout, parallel up to {VERIFY_THREADS}
workers, HTTPS retries over HTTP on SSL failure.  Working proxies are
recorded with timestamp + latency in your personal history.

**Access control**
• Bot is open to everyone by default.
• Banned users cannot use any feature.
• When locked, only admin + approved users can use the bot.
• Admin panel messages are sent with `protect_content=True` — they cannot
  be forwarded, saved, or screenshotted by Telegram Premium users.

**⚙️ Settings — full control panel** (tap ⚙️ Settings on dashboard)
• 🔔 Live Proxy Notifications: ON/OFF
• 🌐 Proxy Type Filter: All / HTTP / SOCKS4 / SOCKS5
• 📥 Export Format: TXT / CSV / JSON
• ⚡ Min Latency: Off / 100ms / 200ms / 500ms / 1s / 2s
• 🐢 Max Latency: Off / 500ms / 1s / 2s / 5s / 10s
• 📊 Sort By: Date / Latency / Type

All filters apply to both live notifications and the final results file.

**🛡️ Smart Filter (NEW in v7 — stops the trash!)**
By default, the bot rejects lines that don't really look like proxies:
• ULP URLs (`https://example.com/login.php`) — not proxies!
• Database URLs (`mysql://user:pass@host:3306`)
• Log entries (`192.168.1.1 - GET / HTTP/1.1`)
• Private IPs (`10.x`, `127.x`, `192.168.x`)
• Non-proxy ports (only `80, 443, 1080, 3128, 8080, 8888, ...` accepted)
• URLs with paths / queries (`https://site.com/path`)

Toggle:
• `/strict` → ON  (default — only real proxies accepted)
• `/lenient` → OFF (accept every ip:port, even trash)
• `/mode` → show current mode

**🛡️ Anti-abuse**
• Free users: **5 files/hour** (admin + approved users = unlimited)
• Admin can manually ban users who misuse the bot via `/ban`

**📜 Audit log**
Every admin action (ban, unban, approve, lock, broadcast, backup, ...)
is recorded with timestamp + actor + target.  View via `/auditlog`,
clear via `/purgeaudit`.

— Powered by **{BRAND}** · Credit: **{DEV_HANDLE}**
"""

ABOUT_TEXT = f"""
**{BRAND}**
`{VERSION}`

This bot extracts proxies from any plain-text or archive file you send
it, verifies them in parallel, and returns only the working ones.

**Tech stack**
• Pyrogram (MTProto)
• requests + PySocks (verification)
• rarfile / py7zr / tarfile / gzip (archives)

**Developer**: {DEV_HANDLE}
**Source**: {DEV_URL}

All credits reserved to **{DEV_HANDLE}**.
"""

# ===========================================================================
#  4b.  PERSISTENT USER STORE  —  JSON-backed
# ===========================================================================
class UserStore:
    """
    Stores per-user stats, ban/approval state, and bot-lock flag.
    Persists to USERS_FILE (JSON).
    """
    _data: Dict[str, Any] = {
        "bot_locked": False,
        "users": {},
    }

    # ---------- persistence ----------
    @classmethod
    def load(cls):
        if USERS_FILE.exists():
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    cls._data = json.load(f)
                cls._data.setdefault("users", {})
                cls._data.setdefault("bot_locked", False)
                log.info(f"Loaded {len(cls._data['users'])} users from {USERS_FILE.name}")
            except Exception as e:
                log.warning(f"Failed to load users.json: {e}")

    @classmethod
    def save(cls):
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning(f"Failed to save users.json: {e}")

    # ---------- bot lock ----------
    @classmethod
    def is_bot_locked(cls) -> bool:
        return bool(cls._data.get("bot_locked", False))

    @classmethod
    def set_bot_locked(cls, locked: bool):
        cls._data["bot_locked"] = bool(locked)
        cls.save()

    # ---------- user CRUD ----------
    @classmethod
    def get_user(cls, user_id: int) -> Dict[str, Any]:
        key = str(user_id)
        if key not in cls._data["users"]:
            cls._data["users"][key] = {
                "id": user_id,
                "username": "",
                "first_name": "",
                "banned": False,
                "approved": False,
                "live_notifications": True,   # send live working-proxy messages
                "files_processed": 0,
                "proxies_extracted": 0,
                "proxies_working": 0,
                "proxies_failed": 0,
                "first_seen": None,
                "last_seen": None,
                "last_file": None,
                # New in v6:
                "strikes": 0,                  # legacy field (auto-ban removed in v6.1)
                "min_latency_ms": 0,           # 0 = no filter
                "max_latency_ms": 0,           # 0 = no filter
                "proxy_type_filter": "all",    # all | http | socks4 | socks5
                "export_format": "txt",        # txt | csv | json
                "sort_by": "date",             # date | latency | type
                "is_new_user": True,           # set False after first /start reply
            }
        # Backfill missing keys for existing users loaded from old JSON
        u = cls._data["users"][key]
        u.setdefault("live_notifications", True)
        u.setdefault("strikes", 0)
        u.setdefault("min_latency_ms", 0)
        u.setdefault("max_latency_ms", 0)
        u.setdefault("proxy_type_filter", "all")
        u.setdefault("export_format", "txt")
        u.setdefault("sort_by", "date")
        u.setdefault("is_new_user", True)
        return u

    @classmethod
    def touch_user(cls, user) -> Dict[str, Any]:
        """Refresh user's identity + last-seen timestamp."""
        u = cls.get_user(user.id)
        u["username"]   = user.username or ""
        u["first_name"] = (user.first_name or "")[:64]
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not u["first_seen"]:
            u["first_seen"] = now
        u["last_seen"] = now
        cls.save()
        return u

    @classmethod
    def is_banned(cls, user_id: int) -> bool:
        return bool(cls.get_user(user_id).get("banned", False))

    @classmethod
    def is_approved(cls, user_id: int) -> bool:
        return bool(cls.get_user(user_id).get("approved", False))

    @classmethod
    def set_banned(cls, user_id: int, banned: bool):
        u = cls.get_user(user_id)
        u["banned"] = bool(banned)
        cls.save()

    @classmethod
    def set_approved(cls, user_id: int, approved: bool):
        u = cls.get_user(user_id)
        u["approved"] = bool(approved)
        cls.save()

    @classmethod
    def get_live_notifications(cls, user_id: int) -> bool:
        return bool(cls.get_user(user_id).get("live_notifications", True))

    @classmethod
    def set_live_notifications(cls, user_id: int, enabled: bool):
        u = cls.get_user(user_id)
        u["live_notifications"] = bool(enabled)
        cls.save()

    # ---------- New v6 settings ----------
    @classmethod
    def get_setting(cls, user_id: int, key: str, default=None):
        return cls.get_user(user_id).get(key, default)

    @classmethod
    def set_setting(cls, user_id: int, key: str, value):
        u = cls.get_user(user_id)
        u[key] = value
        cls.save()

    @classmethod
    def add_strike(cls, user_id: int) -> int:
        """Increment strike count; return new value."""
        u = cls.get_user(user_id)
        u["strikes"] = int(u.get("strikes", 0)) + 1
        cls.save()
        return u["strikes"]

    @classmethod
    def reset_strikes(cls, user_id: int):
        u = cls.get_user(user_id)
        u["strikes"] = 0
        cls.save()

    @classmethod
    def mark_seen(cls, user_id: int):
        """Mark user as no longer new (after first /start)."""
        u = cls.get_user(user_id)
        u["is_new_user"] = False
        cls.save()

    @classmethod
    def record_run(cls, user_id: int, file_name: str,
                   extracted: int, working: int, failed: int):
        u = cls.get_user(user_id)
        u["files_processed"]   += 1
        u["proxies_extracted"] += int(extracted)
        u["proxies_working"]   += int(working)
        u["proxies_failed"]    += int(failed)
        u["last_file"] = file_name
        cls.save()

    @classmethod
    def all_users(cls) -> List[Dict[str, Any]]:
        return list(cls._data["users"].values())

    @classmethod
    def all_users_sorted(cls, by: str = "last_seen") -> List[Dict[str, Any]]:
        return sorted(cls.all_users(),
                      key=lambda u: u.get(by) or "",
                      reverse=True)

    @classmethod
    def leaderboard(cls, limit: int = 10) -> List[Dict[str, Any]]:
        """Top users by working proxies found."""
        users = [u for u in cls.all_users() if not u.get("banned") and u["id"] != ADMIN_ID]
        users.sort(key=lambda u: u.get("proxies_working", 0), reverse=True)
        return users[:limit]

    @classmethod
    def reset_all_stats(cls):
        for u in cls._data["users"].values():
            u["files_processed"]   = 0
            u["proxies_extracted"] = 0
            u["proxies_working"]   = 0
            u["proxies_failed"]    = 0
            u["last_file"]         = None
            u["strikes"]           = 0
        cls.save()


# ===========================================================================
#  4b-ter.  AUDIT LOG  —  tracks every admin action
# ===========================================================================
AUDIT_FILE = WORK_DIR / "audit.log.jsonl"


class AuditLog:
    """Append-only JSON-lines log of admin actions."""

    @classmethod
    def log(cls, actor_id: int, action: str, target: Any = None,
            details: str = ""):
        entry = {
            "ts":        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "actor":     actor_id,
            "action":    action,
            "target":    target,
            "details":   details,
        }
        try:
            with open(AUDIT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            log.warning(f"Failed to write audit log: {e}")

    @classmethod
    def recent(cls, n: int = 20) -> List[Dict[str, Any]]:
        if not AUDIT_FILE.exists():
            return []
        out = []
        try:
            with open(AUDIT_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[-n:]:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
        except Exception:
            pass
        return out

    @classmethod
    def clear(cls):
        try:
            AUDIT_FILE.unlink(missing_ok=True)
        except Exception:
            pass


# ===========================================================================
#  4b-quat.  RATE LIMITER  —  in-memory, per-user, sliding window
# ===========================================================================
class RateLimiter:
    """
    Simple in-memory rate limiter.
    Limits normal users to N actions per window.  Admin + approved users
    are exempt.
    """
    _buckets: Dict[int, List[float]] = {}
    WINDOW_SECONDS = 3600      # 1 hour
    MAX_PER_WINDOW = 5         # 5 files per hour for normal users

    @classmethod
    def check(cls, user_id: int) -> Tuple[bool, str]:
        """Returns (allowed, reason_if_denied)."""
        if is_admin(user_id) or UserStore.is_approved(user_id):
            return True, ""
        now = time.time()
        bucket = cls._buckets.get(user_id, [])
        # Drop entries older than window
        bucket = [t for t in bucket if now - t < cls.WINDOW_SECONDS]
        if len(bucket) >= cls.MAX_PER_WINDOW:
            oldest = bucket[0]
            wait = int(cls.WINDOW_SECONDS - (now - oldest))
            return False, (
                f"⏳ Rate limit reached: `{cls.MAX_PER_WINDOW}` files/hour for free users.\n"
                f"Try again in `{wait//60}m {wait%60}s`, or ask the admin to approve you "
                f"(`/approve {user_id}`) for unlimited access."
            )
        bucket.append(now)
        cls._buckets[user_id] = bucket
        return True, ""


# Load the store at import time
UserStore.load()


# ===========================================================================
#  4b-bis.  WORKING PROXY HISTORY STORE  —  JSON-backed, per-user
# ===========================================================================
WORKING_PROXIES_FILE = WORK_DIR / "working_proxies.json"


class WorkingProxyStore:
    """
    Per-user history of working proxies with timestamps.
    Capped at MAX_PER_USER entries (most recent kept).
    """
    _data: Dict[str, List[Dict[str, Any]]] = {}
    MAX_PER_USER = 500

    # ---------- persistence ----------
    @classmethod
    def load(cls):
        if WORKING_PROXIES_FILE.exists():
            try:
                with open(WORKING_PROXIES_FILE, "r", encoding="utf-8") as f:
                    cls._data = json.load(f)
                log.info(f"Loaded working proxy history for {len(cls._data)} users")
            except Exception as e:
                log.warning(f"Failed to load working_proxies.json: {e}")

    @classmethod
    def save(cls):
        try:
            with open(WORKING_PROXIES_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning(f"Failed to save working_proxies.json: {e}")

    # ---------- API ----------
    @classmethod
    def record(cls, user_id: int, source: str, working_list: List[Dict[str, Any]]):
        key = str(user_id)
        if key not in cls._data:
            cls._data[key] = []
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for w in working_list:
            cls._data[key].append({
                "raw":        w.get("raw", ""),
                "type":       w.get("type", "http"),
                "latency_ms": int(w.get("latency_ms", 0) or 0),
                "source":     source,
                "checked_at": ts,
            })
        # Trim to most recent MAX_PER_USER
        if len(cls._data[key]) > cls.MAX_PER_USER:
            cls._data[key] = cls._data[key][-cls.MAX_PER_USER:]
        cls.save()

    @classmethod
    def get_user_proxies(cls, user_id: int) -> List[Dict[str, Any]]:
        return cls._data.get(str(user_id), [])

    @classmethod
    def clear_user(cls, user_id: int):
        cls._data[str(user_id)] = []
        cls.save()

    @classmethod
    def clear_all(cls):
        cls._data = {}
        cls.save()


WorkingProxyStore.load()


# ===========================================================================
#  4c.  GLOBAL STATS  —  aggregated from UserStore
# ===========================================================================
class Stats:
    @classmethod
    def snapshot(cls) -> str:
        users = UserStore.all_users()
        files     = sum(u.get("files_processed",   0) for u in users)
        extracted = sum(u.get("proxies_extracted", 0) for u in users)
        working   = sum(u.get("proxies_working",   0) for u in users)
        failed    = sum(u.get("proxies_failed",    0) for u in users)
        rate = (working / extracted * 100) if extracted else 0.0
        return (
            f"**{BRAND} — Global Statistics**\n\n"
            f"👥  Total users      : `{len(users)}`\n"
            f"📁  Files processed  : `{files}`\n"
            f"🔎  Proxies found    : `{extracted}`\n"
            f"✅  Working          : `{working}`\n"
            f"❌  Failed           : `{failed}`\n"
            f"📈  Success rate     : `{rate:.1f}%`\n"
            f"🔒  Bot locked       : `{UserStore.is_bot_locked()}`\n\n"
            f"— Credit: **{DEV_HANDLE}**"
        )

    @classmethod
    def snapshot_for_user(cls, user_id: int) -> str:
        u = UserStore.get_user(user_id)
        extracted = u.get("proxies_extracted", 0)
        working   = u.get("proxies_working",   0)
        failed    = u.get("proxies_failed",    0)
        rate = (working / extracted * 100) if extracted else 0.0
        flags = []
        if is_admin(user_id):
            flags.append("👑 Admin")
        if u.get("banned"):
            flags.append("⛔ Banned")
        if u.get("approved"):
            flags.append("✅ Approved")
        status = " | ".join(flags) if flags else "👤 Normal user"
        return (
            f"**{BRAND} — Your Statistics**\n\n"
            f"🆔  User ID         : `{u['id']}`\n"
            f"🏷  Status          : {status}\n\n"
            f"📁  Files processed : `{u.get('files_processed', 0)}`\n"
            f"🔎  Proxies tested  : `{extracted}`\n"
            f"✅  Working         : `{working}`\n"
            f"❌  Failed          : `{failed}`\n"
            f"📈  Success rate    : `{rate:.1f}%`\n"
            f"📄  Last file       : `{u.get('last_file') or 'none'}`\n"
            f"🕒  Last seen       : `{u.get('last_seen') or 'never'}`\n\n"
            f"— Credit: **{DEV_HANDLE}**"
        )

    @classmethod
    def reset(cls):
        UserStore.reset_all_stats()


# ===========================================================================
#  4d.  INLINE KEYBOARDS
# ===========================================================================
def build_dashboard_keyboard(is_admin_user: bool = False) -> "InlineKeyboardMarkup":
    rows = [
        [InlineKeyboardButton("🚀  Send File to Extract", callback_data="act_send")],
        [
            InlineKeyboardButton("📊  My Stats",          callback_data="act_stats"),
            InlineKeyboardButton("📋  My Working Proxies", callback_data="act_myproxies_p1"),
        ],
        [
            InlineKeyboardButton("❓  Help",     callback_data="act_help"),
            InlineKeyboardButton("👤  About",    callback_data="act_about"),
        ],
        [
            InlineKeyboardButton("ℹ️  My Info",   callback_data="act_myinfo"),
            InlineKeyboardButton("⚙️  Settings", callback_data="act_settings"),
        ],
    ]
    if is_admin_user:
        rows.append([InlineKeyboardButton("🛡️  Admin Panel", callback_data="adm_back")])
    rows.append([InlineKeyboardButton("👨‍💻  Developer", url=DEV_URL)])
    return InlineKeyboardMarkup(rows)


def build_cancel_keyboard(is_admin_user: bool = False) -> "InlineKeyboardMarkup":
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️  Back to Dashboard", callback_data="act_start")]
    ])


def build_settings_keyboard(user_id: int) -> "InlineKeyboardMarkup":
    u = UserStore.get_user(user_id)
    live_on = u.get("live_notifications", True)
    live_btn = InlineKeyboardButton(
        "🔔  Live Proxy Notifications: ON"  if live_on else
        "🔕  Live Proxy Notifications: OFF",
        callback_data="act_toggle_live"
    )
    ptype = u.get("proxy_type_filter", "all")
    ptype_label = {"all": "All", "http": "HTTP", "socks4": "SOCKS4",
                   "socks5": "SOCKS5"}.get(ptype, "All")
    min_lat = u.get("min_latency_ms", 0)
    max_lat = u.get("max_latency_ms", 0)
    fmt = u.get("export_format", "txt").upper()
    sort_by = u.get("sort_by", "date")
    sort_label = {"date": "Date", "latency": "Latency",
                  "type": "Type"}.get(sort_by, "Date")

    return InlineKeyboardMarkup([
        [live_btn],
        [
            InlineKeyboardButton(f"🌐  Type: {ptype_label}",  callback_data="act_cycle_ptype"),
            InlineKeyboardButton(f"📥  Format: {fmt}",         callback_data="act_cycle_format"),
        ],
        [
            InlineKeyboardButton(f"⚡  Min Lat: {min_lat}ms" if min_lat else "⚡  Min Lat: Off",
                                  callback_data="act_cycle_minlat"),
            InlineKeyboardButton(f"🐢  Max Lat: {max_lat}ms" if max_lat else "🐢  Max Lat: Off",
                                  callback_data="act_cycle_maxlat"),
        ],
        [InlineKeyboardButton(f"_SORT by: {sort_label}", callback_data="act_cycle_sort")],
        [InlineKeyboardButton("⬅️  Back to Dashboard", callback_data="act_start")],
    ])


def format_settings_text(user_id: int) -> str:
    u = UserStore.get_user(user_id)
    live_on = u.get("live_notifications", True)
    live_desc = (
        "**ON** — every working proxy is sent to you live as it is verified "
        "(plus the final summary file)."
        if live_on else
        "**OFF** — you only receive the final summary file at the end."
    )
    ptype = u.get("proxy_type_filter", "all")
    fmt = u.get("export_format", "txt").upper()
    min_lat = u.get("min_latency_ms", 0)
    max_lat = u.get("max_latency_ms", 0)
    sort_by = u.get("sort_by", "date")
    return (
        f"**{BRAND} — Settings**\n\n"
        f"🔔  **Live Notifications** : {live_desc}\n\n"
        f"🌐  **Proxy Type Filter** : `{ptype.upper()}`\n"
        f"_Only proxies matching this type will be reported as working._\n\n"
        f"📥  **Export Format** : `{fmt}`\n"
        f"_Format of the final results file (TXT / CSV / JSON)._\n\n"
        f"⚡  **Min Latency** : `{min_lat}ms`" + (" _(no filter)_" if not min_lat else "") + "\n"
        f"🐢  **Max Latency** : `{max_lat}ms`" + (" _(no filter)_" if not max_lat else "") + "\n"
        f"_Proxies outside this latency range are excluded._\n\n"
        f"📊  **Sort By** : `{sort_by}`\n"
        f"_How working proxies are sorted in your history view._\n\n"
        f"— Credit: **{DEV_HANDLE}**"
    )


# ---- Settings cycle values ----
PTYPE_CYCLE = ["all", "http", "socks4", "socks5"]
FORMAT_CYCLE = ["txt", "csv", "json"]
SORT_CYCLE = ["date", "latency", "type"]
MIN_LAT_CYCLE = [0, 100, 200, 500, 1000, 2000]
MAX_LAT_CYCLE = [0, 500, 1000, 2000, 5000, 10000]


def build_admin_keyboard() -> "InlineKeyboardMarkup":
    locked = UserStore.is_bot_locked()
    lock_btn = InlineKeyboardButton(
        "🔓  Unlock Bot (open to all)" if locked else "🔒  Lock Bot (approved only)",
        callback_data="adm_unlock" if locked else "adm_lock"
    )
    users = UserStore.all_users()
    banned   = sum(1 for u in users if u.get("banned"))
    approved = sum(1 for u in users if u.get("approved"))
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"👥  All Users ({len(users)})", callback_data="adm_users_p1")],
        [lock_btn],
        [
            InlineKeyboardButton("📊  Global Stats", callback_data="adm_stats"),
            InlineKeyboardButton("🧹  Reset Stats",  callback_data="adm_reset"),
        ],
        [
            InlineKeyboardButton(f"⛔  Banned ({banned})",   callback_data="adm_banned"),
            InlineKeyboardButton(f"✅  Approved ({approved})", callback_data="adm_approved"),
        ],
        [InlineKeyboardButton("🔄  Refresh", callback_data="adm_back")],
        [InlineKeyboardButton("⬅️  Back to Dashboard", callback_data="act_start")],
    ])


def build_user_list_keyboard(page: int = 1, per_page: int = 8,
                             filter_kind: str = "all") -> "InlineKeyboardMarkup":
    users = UserStore.all_users_sorted()
    if filter_kind == "banned":
        users = [u for u in users if u.get("banned")]
    elif filter_kind == "approved":
        users = [u for u in users if u.get("approved")]
    total_pages = max(1, (len(users) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    page_users = users[start:start + per_page]

    buttons = []
    for u in page_users:
        uid = u["id"]
        if u.get("username"):
            name = f"@{u['username']}"
        elif u.get("first_name"):
            name = u["first_name"]
        else:
            name = str(uid)
        flags = []
        if u.get("banned"):    flags.append("⛔")
        if u.get("approved"):  flags.append("✅")
        if is_admin(uid):      flags.append("👑")
        label = f"{name} {' '.join(flags)}".strip()
        # Truncate if too long for button label
        if len(label) > 40:
            label = label[:37] + "..."
        buttons.append([InlineKeyboardButton(label, callback_data=f"adm_user_{uid}")])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"adm_users_p{page-1}_{filter_kind}"))
    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="adm_noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"adm_users_p{page+1}_{filter_kind}"))
    if nav:
        buttons.append(nav)

    # Filter row
    buttons.append([
        InlineKeyboardButton("All",       callback_data="adm_users_p1_all"),
        InlineKeyboardButton("Banned",    callback_data="adm_users_p1_banned"),
        InlineKeyboardButton("Approved",  callback_data="adm_users_p1_approved"),
    ])
    buttons.append([InlineKeyboardButton("⬅️  Admin Menu", callback_data="adm_back")])
    return InlineKeyboardMarkup(buttons)


def build_user_detail_keyboard(user_id: int) -> "InlineKeyboardMarkup":
    u = UserStore.get_user(user_id)
    is_self_admin = is_admin(user_id)
    buttons = []

    # Always allow admin to view / download this user's working proxies
    buttons.append([InlineKeyboardButton(
        "📥  View / Download Working Proxies",
        callback_data=f"adm_user_proxies_{user_id}_p1"
    )])

    if not is_self_admin:
        if u.get("banned"):
            buttons.append([InlineKeyboardButton("♻️  Unban User", callback_data=f"adm_unban_{user_id}")])
        else:
            buttons.append([InlineKeyboardButton("⛔  Ban User", callback_data=f"adm_ban_{user_id}")])

        if u.get("approved"):
            buttons.append([InlineKeyboardButton("❌  Remove Approval", callback_data=f"adm_unappr_{user_id}")])
        else:
            buttons.append([InlineKeyboardButton("✅  Approve User", callback_data=f"adm_appr_{user_id}")])
    else:
        buttons.append([InlineKeyboardButton("👑  Admin account (cannot be modified)", callback_data="adm_noop")])

    buttons.append([InlineKeyboardButton("⬅️  Back to Users", callback_data="adm_users_p1_all")])
    buttons.append([InlineKeyboardButton("⬅️  Admin Menu", callback_data="adm_back")])
    return InlineKeyboardMarkup(buttons)


def format_user_info(u: Dict[str, Any]) -> str:
    extracted = u.get("proxies_extracted", 0)
    working   = u.get("proxies_working",   0)
    failed    = u.get("proxies_failed",    0)
    rate = (working / extracted * 100) if extracted else 0.0

    flags = []
    if is_admin(u["id"]):  flags.append("👑 Admin")
    if u.get("banned"):    flags.append("⛔ Banned")
    if u.get("approved"):  flags.append("✅ Approved")
    status = " | ".join(flags) if flags else "👤 Normal user"

    name_parts = []
    if u.get("first_name"): name_parts.append(u["first_name"])
    if u.get("username"):   name_parts.append(f"@{u['username']}")
    display = " ".join(name_parts) or "Unknown"

    return (
        f"**{BRAND} — User Detail**\n\n"
        f"👤  Name        : {display}\n"
        f"🆔  User ID     : `{u['id']}`\n"
        f"🏷  Status      : {status}\n\n"
        f"**Activity**\n"
        f"📁  Files processed : `{u.get('files_processed', 0)}`\n"
        f"🔎  Proxies tested  : `{extracted}`\n"
        f"✅  Working         : `{working}`\n"
        f"❌  Failed          : `{failed}`\n"
        f"📈  Success rate    : `{rate:.1f}%`\n\n"
        f"**Timeline**\n"
        f"🆕  First seen : `{u.get('first_seen') or 'unknown'}`\n"
        f"🕒  Last seen  : `{u.get('last_seen') or 'unknown'}`\n"
        f"📄  Last file  : `{u.get('last_file') or 'none'}`\n\n"
        f"— Credit: **{DEV_HANDLE}**"
    )


# ---- Working proxy view helpers ------------------------------------------
WORKING_PROXIES_PER_PAGE = 8


def format_working_proxies_page(user_id: int, page: int = 1,
                                viewer_is_admin: bool = False) -> str:
    """
    Build the text for one page of a user's working proxy history.
    Shows the most recent entries first; each entry shows proxy + latency + checked_at.
    """
    all_w = WorkingProxyStore.get_user_proxies(user_id)
    # Newest first
    all_w = list(reversed(all_w))
    total = len(all_w)
    per_page = WORKING_PROXIES_PER_PAGE
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    page_items = all_w[start:start + per_page]

    u = UserStore.get_user(user_id)
    name_parts = []
    if u.get("first_name"): name_parts.append(u["first_name"])
    if u.get("username"):   name_parts.append(f"@{u['username']}")
    display = " ".join(name_parts) or str(user_id)

    header = (
        f"**{BRAND} — Working Proxies**\n\n"
        f"👤  User    : {display}\n"
        f"🆔  User ID : `{user_id}`\n"
        f"📋  Total   : `{total}` working proxies on record\n"
        f"📄  Page    : `{page}/{total_pages}`\n\n"
    )
    if not page_items:
        header += "_No working proxies found yet._\n\n"
    else:
        header += "**Most recent:**\n"
        for i, w in enumerate(page_items, start=start + 1):
            header += (
                f"\n`{i}.` `{w.get('raw','')}`\n"
                f"   ⏱  `{w.get('checked_at','?')}` · "
                f"⚡ `{w.get('latency_ms',0)}ms` · "
                f"📦 `{w.get('source','?')}`"
            )
        header += "\n\n"
    header += f"— Credit: **{DEV_HANDLE}**"
    return header


def build_working_proxies_keyboard(user_id: int, page: int = 1,
                                   viewer_is_admin: bool = False,
                                   back_to_admin: bool = False) -> "InlineKeyboardMarkup":
    all_w = WorkingProxyStore.get_user_proxies(user_id)
    total = len(all_w)
    per_page = WORKING_PROXIES_PER_PAGE
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    prefix = "adm" if viewer_is_admin else "act"
    buttons = []

    # Download all button
    if total > 0:
        dl_cb = f"adm_dlproxies_{user_id}" if viewer_is_admin else "act_dlproxies"
        buttons.append([InlineKeyboardButton(f"📥  Download All ({total})", callback_data=dl_cb)])

    # Clear button (only for self, or admin viewing another user)
    if total > 0:
        clr_cb = f"adm_clrproxies_{user_id}" if viewer_is_admin else "act_clrproxies"
        buttons.append([InlineKeyboardButton("🧹  Clear History", callback_data=clr_cb)])

    # Pagination
    nav = []
    if page > 1:
        if viewer_is_admin:
            cb_prev = f"adm_user_proxies_{user_id}_p{page-1}"
        else:
            cb_prev = f"act_myproxies_p{page-1}"
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=cb_prev))
    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data=f"{prefix}_noop"))
    if page < total_pages:
        if viewer_is_admin:
            cb_next = f"adm_user_proxies_{user_id}_p{page+1}"
        else:
            cb_next = f"act_myproxies_p{page+1}"
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=cb_next))
    if nav:
        buttons.append(nav)

    # Back button
    if viewer_is_admin:
        buttons.append([InlineKeyboardButton("⬅️  Back to User Detail",
                       callback_data=f"adm_user_{user_id}")])
        buttons.append([InlineKeyboardButton("⬅️  Admin Menu", callback_data="adm_back")])
    else:
        buttons.append([InlineKeyboardButton("⬅️  Back to Dashboard", callback_data="act_start")])
    return InlineKeyboardMarkup(buttons)


def _filter_and_sort_proxies(items: List[Dict[str, Any]],
                              ptype: str = "all",
                              min_lat: int = 0,
                              max_lat: int = 0,
                              sort_by: str = "date") -> List[Dict[str, Any]]:
    """Apply the user's filters + sort to a list of working-proxy entries."""
    out = []
    for w in items:
        if ptype != "all" and w.get("type", "http") != ptype:
            continue
        lat = int(w.get("latency_ms", 0) or 0)
        if min_lat and lat < min_lat:
            continue
        if max_lat and lat > max_lat:
            continue
        out.append(w)
    if sort_by == "latency":
        out.sort(key=lambda x: int(x.get("latency_ms", 0)))
    elif sort_by == "type":
        out.sort(key=lambda x: (x.get("type", ""), x.get("raw", "")))
    else:  # date (newest first)
        out = list(reversed(out))
    return out


def build_working_proxies_file(user_id: int) -> Path:
    """
    Build a results file with all of a user's working proxies.
    Respects the user's format (txt/csv/json), type filter, latency
    filters, and sort order.
    """
    u = UserStore.get_user(user_id)
    all_w = WorkingProxyStore.get_user_proxies(user_id)
    ptype = u.get("proxy_type_filter", "all")
    min_lat = int(u.get("min_latency_ms", 0) or 0)
    max_lat = int(u.get("max_latency_ms", 0) or 0)
    sort_by = u.get("sort_by", "date")
    fmt = u.get("export_format", "txt").lower()
    items = _filter_and_sort_proxies(all_w, ptype, min_lat, max_lat, sort_by)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name_parts = []
    if u.get("first_name"): name_parts.append(u["first_name"])
    if u.get("username"):   name_parts.append(f"@{u['username']}")
    display = "_".join(name_parts) or str(user_id)
    display = re.sub(r"[^\w\-.]", "_", display)[:40]
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if fmt == "json":
        out_path = OUTPUTS / f"AKAZA_history_{display}_{user_id}_{ts}.json"
        payload = {
            "brand":     BRAND,
            "credit":    DEV_HANDLE,
            "user_id":   user_id,
            "name":      display,
            "generated": now_str,
            "total":     len(items),
            "filters": {
                "type": ptype, "min_latency_ms": min_lat,
                "max_latency_ms": max_lat, "sort_by": sort_by,
            },
            "proxies": items,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    elif fmt == "csv":
        out_path = OUTPUTS / f"AKAZA_history_{display}_{user_id}_{ts}.csv"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("proxy,type,latency_ms,source,checked_at\n")
            for w in items:
                f.write(f"\"{w.get('raw','')}\",{w.get('type','http')},"
                        f"{w.get('latency_ms',0)},\"{w.get('source','')}\","
                        f"\"{w.get('checked_at','')}\"\n")
    else:  # txt
        out_path = OUTPUTS / f"AKAZA_history_{display}_{user_id}_{ts}.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# {BRAND} — Working Proxy History\n")
            f.write(f"# User ID  : {user_id}\n")
            f.write(f"# Name     : {display}\n")
            f.write(f"# Total    : {len(items)} working proxies\n")
            f.write(f"# Filters  : type={ptype} min_lat={min_lat} max_lat={max_lat} sort={sort_by}\n")
            f.write(f"# Generated: {now_str}\n")
            f.write(f"# Credit   : {DEV_HANDLE}\n")
            f.write("=" * 60 + "\n")
            for w in items:
                f.write(f"{w.get('raw',''):50s}  # {w.get('checked_at','?')}  "
                        f"{w.get('latency_ms',0)}ms  src={w.get('source','?')}\n")
    return out_path


# ===========================================================================
#  5.  BOT HANDLERS  +  ACCESS CONTROL
# ===========================================================================
app: Optional["Client"] = None
DOWNLOAD_WORKERS = max(8, int(os.getenv("DOWNLOAD_WORKERS", "16")))
EXTRACT_QUEUE_WORKERS = max(1, int(os.getenv("EXTRACT_QUEUE_WORKERS", "2")))
_EXTRACT_JOB_QUEUE: Optional[asyncio.Queue] = None
_EXTRACT_WORKER_TASKS: List[asyncio.Task] = []
_ADM_USERS_CB_RE = re.compile(r"^adm_users_p(?P<page>\d+)(?:_(?P<kind>all|banned|approved))?$")


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def can_use_bot(user_id: int) -> Tuple[bool, str]:
    """
    Returns (allowed, reason_if_denied).
    Rules:
      • Admin always allowed.
      • Banned users always denied.
      • If bot is locked, only admin + approved users are allowed.
      • Otherwise everyone is allowed.
    """
    if is_admin(user_id):
        return True, ""
    if UserStore.is_banned(user_id):
        return False, "⛔ You are banned by the admin."
    if UserStore.is_bot_locked() and not UserStore.is_approved(user_id):
        return False, ("🔒 Bot is currently **locked**.\n"
                       "Only admin-approved users can use it right now.\n"
                       "Please contact the admin to request access.")
    return True, ""


async def _deny(client, message, reason: str):
    """Send a denial reply."""
    await message.reply(
        f"**{BRAND}**\n\n{reason}\n\n— Credit: **{DEV_HANDLE}**"
    )


def _parse_user_id_from_command(message) -> Optional[int]:
    """
    Parse target user ID from a command:
      • /cmd 123456789
      • /cmd (as reply to a message from the target user)
    """
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) >= 2:
        try:
            return int(parts[1].strip())
        except Exception:
            return None
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    return None


async def _extract_worker_loop():
    """Background worker that executes blocking extraction jobs from a queue."""
    global _EXTRACT_JOB_QUEUE
    while True:
        if _EXTRACT_JOB_QUEUE is None:
            await asyncio.sleep(0.1)
            continue
        file_path, strict, fut = await _EXTRACT_JOB_QUEUE.get()
        try:
            result = await asyncio.to_thread(extract_proxies_from_files, file_path, strict)
            if not fut.done():
                fut.set_result(result)
        except Exception as e:
            if not fut.done():
                fut.set_exception(e)
        finally:
            _EXTRACT_JOB_QUEUE.task_done()


def _ensure_extract_workers():
    """Ensure queue + worker tasks are running for extraction jobs."""
    global _EXTRACT_JOB_QUEUE, _EXTRACT_WORKER_TASKS
    if _EXTRACT_JOB_QUEUE is None:
        _EXTRACT_JOB_QUEUE = asyncio.Queue()
    _EXTRACT_WORKER_TASKS = [t for t in _EXTRACT_WORKER_TASKS if not t.done()]
    missing = EXTRACT_QUEUE_WORKERS - len(_EXTRACT_WORKER_TASKS)
    for _ in range(max(0, missing)):
        _EXTRACT_WORKER_TASKS.append(asyncio.create_task(_extract_worker_loop()))


async def submit_extract_job(file_path: Path, strict: bool = True) -> Tuple[asyncio.Future, int]:
    """
    Queue an extraction job and return (future, jobs_ahead).
    `jobs_ahead` excludes currently running workers and counts waiting jobs only.
    """
    _ensure_extract_workers()
    assert _EXTRACT_JOB_QUEUE is not None
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    jobs_ahead = _EXTRACT_JOB_QUEUE.qsize()
    await _EXTRACT_JOB_QUEUE.put((file_path, strict, fut))
    return fut, jobs_ahead


async def _safe_edit(msg, text, reply_markup=None):
    """Edit a Telegram message while tolerating duplicate updates."""
    try:
        await msg.edit_text(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
    except MessageNotModified:
        pass
    except Exception as e:
        log.warning(f"Failed editing Telegram message: {e}")


def admin_panel_text() -> str:
    """Build the live admin dashboard status text."""
    users = UserStore.all_users()
    banned = sum(1 for u in users if u.get("banned"))
    approved = sum(1 for u in users if u.get("approved"))
    locked = UserStore.is_bot_locked()
    queue_depth = _EXTRACT_JOB_QUEUE.qsize() if _EXTRACT_JOB_QUEUE is not None else 0
    disk_text = "unknown"
    try:
        disk = shutil.disk_usage(DOWNLOADS)
        disk_text = f"{disk.free / 1024 / 1024:.1f} MB free"
    except Exception:
        pass
    memory_text = ""
    try:
        import psutil  # type: ignore
        memory_text = f"\n💾  Memory       : `{psutil.Process().memory_info().rss / 1024 / 1024:.1f} MB`"
    except Exception:
        pass
    uptime = int(max(0, time.time() - PROCESS_START_TIME))
    uptime_text = f"{uptime // 3600}h {(uptime % 3600) // 60}m {uptime % 60}s"
    return (
        f"**{BRAND} — Admin Panel**\n\n"
        f"**Users**\n"
        f"👥  Total        : `{len(users)}`\n"
        f"✅  Approved     : `{approved}`\n"
        f"⛔  Banned       : `{banned}`\n"
        f"🔒  Bot status   : `{'LOCKED' if locked else 'OPEN'}`\n\n"
        f"**Runtime**\n"
        f"🧵  Extract queue: `{queue_depth}` waiting\n"
        f"💿  Disk         : `{disk_text}`"
        f"{memory_text}\n"
        f"⏱  Uptime       : `{uptime_text}`\n\n"
        f"**Configuration**\n"
        f"📥  Download workers : `{DOWNLOAD_WORKERS}`\n"
        f"🔎  Verify threads   : `{VERIFY_THREADS}`\n"
        f"📦  Extract cap      : `{EXTRACT_MAX_PROXIES}`\n"
        f"✅  Verify cap       : `{VERIFY_MAX_PROXIES}`\n"
        f"📏  File size limit  : `{MAX_FILE_SIZE_MB} MB`\n\n"
        f"— Credit: **{DEV_HANDLE}**"
    )


def register_handlers(application: "Client"):
    global app
    app = application

    # ---------------------- /start ----------------------
    @application.on_message(filters.command("start") & filters.private)
    async def _start(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        allowed, reason = can_use_bot(user.id)
        if not allowed:
            await _deny(client, message, reason)
            return
        print(BANNER)
        # Detect brand-new user → send a special welcome
        is_new = UserStore.get_user(user.id).get("is_new_user", True)
        if is_new:
            name = user.first_name or user.username or "there"
            welcome = (
                f"**🎉 Welcome to {BRAND}, {name}!**\n\n"
                f"You're new here — here's the quick start:\n\n"
                f"1️⃣  Tap **🚀 Send File to Extract** below and upload a `.txt` / "
                f"`.zip` / `.rar` / `.7z` file containing proxies.\n"
                f"2️⃣  Bot downloads it via MTProto ({DOWNLOAD_WORKERS} workers), "
                f"extracts every proxy, and verifies each one.\n"
                f"3️⃣  You'll see live download / extract / verify progress with timing.\n"
                f"4️⃣  Working proxies are sent as a `.txt` (or `.csv` / `.json` — "
                f"see ⚙️ Settings).\n\n"
                f"📊  Use **📋 My Working Proxies** to view your full history "
                f"with timestamps and latencies.\n"
                f"🏆  Type `/leaderboard` to see top users.\n"
                f"⚙️  Tap **Settings** to toggle live notifications, filter by "
                f"proxy type, set latency limits, and change export format.\n\n"
                f"💡  _Free users: 5 files/hour. Ask admin for unlimited access._\n\n"
                f"— Credit: **{DEV_HANDLE}**"
            )
            await message.reply(welcome, disable_web_page_preview=True)
            UserStore.mark_seen(user.id)
            AuditLog.log(ADMIN_ID, "new_user", target=user.id,
                         details=f"Name: {name}")
        await message.reply(
            WELCOME_TEXT,
            reply_markup=build_dashboard_keyboard(is_admin(user.id)),
            disable_web_page_preview=True,
        )

    # ---------------------- /help ----------------------
    @application.on_message(filters.command("help") & filters.private)
    async def _help(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        allowed, reason = can_use_bot(user.id)
        if not allowed:
            await _deny(client, message, reason)
            return
        await message.reply(HELP_TEXT, disable_web_page_preview=True)

    # ---------------------- /stats ----------------------
    @application.on_message(filters.command("stats") & filters.private)
    async def _stats(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        allowed, reason = can_use_bot(user.id)
        if not allowed:
            await _deny(client, message, reason)
            return
        await message.reply(Stats.snapshot_for_user(user.id))

    # ---------------------- /myinfo ----------------------
    @application.on_message(filters.command("myinfo") & filters.private)
    async def _myinfo(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        allowed, reason = can_use_bot(user.id)
        if not allowed:
            await _deny(client, message, reason)
            return
        await message.reply(format_user_info(UserStore.get_user(user.id)))

    # ---------------------- /myproxies ----------------------
    @application.on_message(filters.command("myproxies") & filters.private)
    async def _myproxies(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        allowed, reason = can_use_bot(user.id)
        if not allowed:
            await _deny(client, message, reason)
            return
        await message.reply(
            format_working_proxies_page(user.id, 1, viewer_is_admin=False),
            reply_markup=build_working_proxies_keyboard(
                user.id, 1, viewer_is_admin=False),
        )

    # ---------------------- /settings ----------------------
    @application.on_message(filters.command("settings") & filters.private)
    async def _settings_cmd(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        allowed, reason = can_use_bot(user.id)
        if not allowed:
            await _deny(client, message, reason)
            return
        await message.reply(
            format_settings_text(user.id),
            reply_markup=build_settings_keyboard(user.id),
        )

    # ---------------------- /about ----------------------
    @application.on_message(filters.command("about") & filters.private)
    async def _about(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        allowed, reason = can_use_bot(user.id)
        if not allowed:
            await _deny(client, message, reason)
            return
        await message.reply(ABOUT_TEXT, disable_web_page_preview=True)

    # ---------------------- /clear ----------------------
    @application.on_message(filters.command("clear") & filters.private)
    async def _clear(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        try:
            for d in (DOWNLOADS, OUTPUTS):
                for child in d.iterdir():
                    try:
                        if child.is_file():
                            child.unlink()
                        elif child.is_dir():
                            shutil.rmtree(child, ignore_errors=True)
                    except Exception:
                        pass
            await message.reply(
                f"**{BRAND}**\n\n✅ Workspace cleared.\n\n— Credit: **{DEV_HANDLE}**"
            )
        except Exception as e:
            await message.reply(f"❌ Clear failed: `{e}`")

    # ===================================================================
    #  ADMIN COMMANDS
    # ===================================================================

    # ---------------------- /admin ----------------------
    @application.on_message(filters.command("admin") & filters.private)
    async def _admin(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        await message.reply(
            admin_panel_text(),
            reply_markup=build_admin_keyboard(),
            protect_content=True,
        )

    # ---------------------- /ban ----------------------
    @application.on_message(filters.command("ban") & filters.private)
    async def _ban(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        target = _parse_user_id_from_command(message)
        if target is None:
            await message.reply(
                f"**{BRAND}**\n\nUsage: `/ban <user_id>`  or  reply to a user's message with `/ban`."
            )
            return
        if is_admin(target):
            await message.reply("⚠️ Cannot ban an admin.")
            return
        UserStore.set_banned(target, True)
        AuditLog.log(user.id, "ban", target=target)
        tu = UserStore.get_user(target)
        name = tu.get("first_name") or tu.get("username") or target
        await message.reply(
            f"**{BRAND}**\n\n⛔ Banned: `{name}` (`{target}`)"
        )

    # ---------------------- /unban ----------------------
    @application.on_message(filters.command("unban") & filters.private)
    async def _unban(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        target = _parse_user_id_from_command(message)
        if target is None:
            await message.reply(
                f"**{BRAND}**\n\nUsage: `/unban <user_id>`"
            )
            return
        UserStore.set_banned(target, False)
        AuditLog.log(user.id, "unban", target=target)
        await message.reply(
            f"**{BRAND}**\n\n♻️ Unbanned: `{target}`"
        )

    # ---------------------- /approve ----------------------
    @application.on_message(filters.command("approve") & filters.private)
    async def _approve(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        target = _parse_user_id_from_command(message)
        if target is None:
            await message.reply(
                f"**{BRAND}**\n\nUsage: `/approve <user_id>`  or  reply to a user's message with `/approve`."
            )
            return
        UserStore.set_approved(target, True)
        # Auto-unban if banned
        if UserStore.is_banned(target):
            UserStore.set_banned(target, False)
        AuditLog.log(user.id, "approve", target=target)
        tu = UserStore.get_user(target)
        name = tu.get("first_name") or tu.get("username") or target
        await message.reply(
            f"**{BRAND}**\n\n✅ Approved: `{name}` (`{target}`)\n"
            f"They can now use the bot even when it is locked."
        )

    # ---------------------- /unapprove ----------------------
    @application.on_message(filters.command("unapprove") & filters.private)
    async def _unapprove(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        target = _parse_user_id_from_command(message)
        if target is None:
            await message.reply(
                f"**{BRAND}**\n\nUsage: `/unapprove <user_id>`"
            )
            return
        UserStore.set_approved(target, False)
        AuditLog.log(user.id, "unapprove", target=target)
        await message.reply(
            f"**{BRAND}**\n\n❌ Approval removed: `{target}`"
        )

    # ---------------------- /lock ----------------------
    @application.on_message(filters.command("lock") & filters.private)
    async def _lock(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        UserStore.set_bot_locked(True)
        AuditLog.log(user.id, "lock")
        await message.reply(
            f"**{BRAND}**\n\n🔒 Bot is now **LOCKED**.\n"
            f"Only admin + approved users can use it."
        )

    # ---------------------- /unlock ----------------------
    @application.on_message(filters.command("unlock") & filters.private)
    async def _unlock(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        UserStore.set_bot_locked(False)
        AuditLog.log(user.id, "unlock")
        await message.reply(
            f"**{BRAND}**\n\n🔓 Bot is now **OPEN** to everyone (except banned users)."
        )

    # ---------------------- /users ----------------------
    @application.on_message(filters.command("users") & filters.private)
    async def _users(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        users = UserStore.all_users_sorted()
        if not users:
            await message.reply("**{BRAND}**\n\nNo users registered yet.")
            return
        await message.reply(
            f"**{BRAND} — All Users ({len(users)})**\n\nTap a user to view details:",
            reply_markup=build_user_list_keyboard(1, 8, "all"),
        )

    # ---------------------- /userinfo ----------------------
    @application.on_message(filters.command("userinfo") & filters.private)
    async def _userinfo(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        target = _parse_user_id_from_command(message)
        if target is None:
            await message.reply(
                f"**{BRAND}**\n\nUsage: `/userinfo <user_id>`"
            )
            return
        tu = UserStore.get_user(target)
        await message.reply(
            format_user_info(tu),
            reply_markup=build_user_detail_keyboard(target),
            protect_content=True,
        )

    # ---------------------- /broadcast ----------------------
    @application.on_message(filters.command("broadcast") & filters.private)
    async def _broadcast(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        # Get message text after /broadcast
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await message.reply(
                f"**{BRAND}**\n\nUsage: `/broadcast <message>`\n\n"
                f"The message will be sent to every registered user."
            )
            return
        text = parts[1].strip()
        users = UserStore.all_users()
        total = len(users)
        await message.reply(
            f"**{BRAND} — Broadcast**\n\n"
            f"📢 Sending to `{total}` users...\n\n"
            f"Message preview:\n\n{text}\n\n"
            f"— Credit: **{DEV_HANDLE}**"
        )
        AuditLog.log(user.id, "broadcast", target=None, details=f"to {total} users")
        sent = 0
        failed = 0
        status = await message.reply(f"📤 Progress: `0/{total}`")
        last_edit = 0.0
        full_text = f"**{BRAND} — Announcement**\n\n{text}\n\n— Credit: **{DEV_HANDLE}**"
        for i, u in enumerate(users, 1):
            try:
                await client.send_message(u["id"], full_text)
                sent += 1
            except Exception:
                failed += 1
            now = time.time()
            if now - last_edit > 2.0 or i == total:
                last_edit = now
                try:
                    await status.edit_text(
                        f"**{BRAND} — Broadcast**\n\n"
                        f"📤 Progress: `{i}/{total}`\n"
                        f"✅ Sent: `{sent}`\n"
                        f"❌ Failed: `{failed}`"
                    )
                except Exception:
                    pass
            await asyncio.sleep(0.05)  # avoid flood
        await status.edit_text(
            f"**{BRAND} — Broadcast Complete**\n\n"
            f"📤 Total : `{total}`\n"
            f"✅ Sent  : `{sent}`\n"
            f"❌ Failed: `{failed}`\n\n"
            f"— Credit: **{DEV_HANDLE}**"
        )

    # ---------------------- /leaderboard ----------------------
    @application.on_message(filters.command("leaderboard") & filters.private)
    async def _leaderboard(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        allowed, reason = can_use_bot(user.id)
        if not allowed:
            await _deny(client, message, reason)
            return
        top = UserStore.leaderboard(10)
        if not top:
            await message.reply(
                f"**{BRAND} — Leaderboard**\n\nNo data yet. Be the first! 🏆"
            )
            return
        lines = [f"**{BRAND} — Leaderboard 🏆**\n"]
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        for i, u in enumerate(top):
            name = u.get("first_name") or u.get("username") or u["id"]
            working = u.get("proxies_working", 0)
            extracted = u.get("proxies_extracted", 0)
            files = u.get("files_processed", 0)
            lines.append(
                f"{medals[i]}  `{name}`\n"
                f"     ✅ `{working}` working · 🔎 `{extracted}` tested · 📁 `{files}` files"
            )
        lines.append(f"\n— Credit: **{DEV_HANDLE}**")
        await message.reply("\n".join(lines))

    # ---------------------- /backup ----------------------
    @application.on_message(filters.command("backup") & filters.private)
    async def _backup(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        # Save current state
        UserStore.save()
        if not USERS_FILE.exists():
            await message.reply("❌ users.json not found.")
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = OUTPUTS / f"users_backup_{ts}.json"
        shutil.copy2(USERS_FILE, backup_path)
        AuditLog.log(user.id, "backup", target=str(backup_path))
        await client.send_document(
            chat_id=message.chat.id,
            document=str(backup_path),
            caption=f"**{BRAND}** — User database backup\n"
                    f"`{len(UserStore.all_users())}` users · Credit: {DEV_HANDLE}",
            protect_content=True,
        )

    # ---------------------- /health ----------------------
    @application.on_message(filters.command("health") & filters.private)
    async def _health(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        users = UserStore.all_users()
        banned   = sum(1 for u in users if u.get("banned"))
        approved = sum(1 for u in users if u.get("approved"))
        all_w = WorkingProxyStore._data
        total_proxies = sum(len(v) for v in all_w.values())
        # Workspace size
        ws_size = 0
        for d in (DOWNLOADS, OUTPUTS, WORK_DIR):
            try:
                for root, _, files in os.walk(d):
                    for f in files:
                        try:
                            fp = os.path.join(root, f)
                            ws_size += os.path.getsize(fp)
                        except Exception:
                            pass
            except Exception:
                pass
        ws_mb = ws_size / 1024 / 1024
        audit_entries = len(AuditLog.recent(99999))
        text = (
            f"**{BRAND} — System Health**\n\n"
            f"**📊 Users**\n"
            f"👥  Total        : `{len(users)}`\n"
            f"✅  Approved     : `{approved}`\n"
            f"⛔  Banned       : `{banned}`\n"
            f"🔒  Bot locked   : `{UserStore.is_bot_locked()}`\n\n"
            f"**📋 Data**\n"
            f"🌐  Working proxies stored : `{total_proxies}`\n"
            f"📜  Audit log entries      : `{audit_entries}`\n"
            f"💾  Workspace size         : `{ws_mb:.2f} MB`\n\n"
            f"**⚙️  Engine**\n"
            f"🔧  Verify threads  : `{VERIFY_THREADS}`\n"
            f"⏱   Verify timeout  : `{VERIFY_TIMEOUT}s`\n"
            f"📥  MTProto workers : `{DOWNLOAD_WORKERS}`\n\n"
            f"— Credit: **{DEV_HANDLE}**"
        )
        await message.reply(text, protect_content=True)

    # ---------------------- /auditlog ----------------------
    @application.on_message(filters.command("auditlog") & filters.private)
    async def _auditlog(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        entries = AuditLog.recent(15)
        if not entries:
            await message.reply(
                f"**{BRAND} — Audit Log**\n\nNo admin actions logged yet.",
                protect_content=True,
            )
            return
        lines = [f"**{BRAND} — Audit Log (last 15)**\n"]
        for e in entries:
            lines.append(
                f"🕐 `{e['ts']}`\n"
                f"   👤 `{e['actor']}` · 🎯 `{e['action']}`"
                + (f" · → `{e['target']}`" if e.get("target") else "")
                + (f" · `{e['details']}`" if e.get("details") else "")
            )
        lines.append(f"\n— Credit: **{DEV_HANDLE}**")
        await message.reply("\n".join(lines), protect_content=True)

    # ---------------------- /purgeaudit ----------------------
    @application.on_message(filters.command("purgeaudit") & filters.private)
    async def _purgeaudit(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        AuditLog.clear()
        AuditLog.log(user.id, "purge_audit")
        await message.reply(
            f"**{BRAND}**\n\n🧹 Audit log cleared."
        )

    # ---------------------- /strict ----------------------
    @application.on_message(filters.command("strict") & filters.private)
    async def _strict(client: Client, message: Message):
        global STRICT_MODE
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        STRICT_MODE = True
        AuditLog.log(user.id, "set_strict", details="ON")
        await message.reply(
            f"**{BRAND}**\n\n🛡️ **Strict mode ON**\n\n"
            f"The bot now rejects trash like:\n"
            f"• ULP URLs (`https://example.com/login.php`)\n"
            f"• Database connection strings\n"
            f"• Log entries (GET / POST / HTTP/...)\n"
            f"• Private IPs (10.x / 192.168.x / 127.x)\n"
            f"• Non-proxy ports (only 80/443/1080/3128/8080/8888/... accepted)\n\n"
            f"This catches real proxies and skips garbage."
        )

    # ---------------------- /lenient ----------------------
    @application.on_message(filters.command("lenient") & filters.private)
    async def _lenient(client: Client, message: Message):
        global STRICT_MODE
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        STRICT_MODE = False
        AuditLog.log(user.id, "set_strict", details="OFF")
        await message.reply(
            f"**{BRAND}**\n\n⚠️ **Lenient mode ON**\n\n"
            f"Smart filtering is DISABLED.  The bot will accept every ip:port it finds,\n"
            f"including ULP URLs and trash.  Use `/strict` to re-enable filtering."
        )

    # ---------------------- /mode ----------------------
    @application.on_message(filters.command("mode") & filters.private)
    async def _mode(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        if not is_admin(user.id):
            await _deny(client, message, "⛔ Admin only.")
            return
        mode = "🛡️ STRICT (smart filtering ON)" if STRICT_MODE else "⚠️ LENIENT (no filtering)"
        await message.reply(
            f"**{BRAND}**\n\nCurrent extraction mode: `{mode}`\n\n"
            f"Toggle with `/strict` or `/lenient`."
        )

    # ---------------------- Callback queries ----------------------
    @application.on_callback_query()
    async def _callback(client: Client, cb: CallbackQuery):
        user = cb.from_user
        UserStore.touch_user(user)
        data = cb.data or ""

        # ----- Public actions (require access) -----
        if data.startswith("act_"):
            allowed, reason = can_use_bot(user.id)
            if not allowed:
                await cb.answer(reason, show_alert=True)
                return

            if data == "act_start":
                await _safe_edit(
                    cb.message,
                    WELCOME_TEXT,
                    reply_markup=build_dashboard_keyboard(is_admin(user.id)),
                )
            elif data == "act_send":
                await cb.answer("📤 Send any file now", show_alert=False)
                await cb.message.reply(
                    f"**{BRAND}**\n\n📤 Send me a file (`.txt / .zip / .rar / .7z / .csv ...`).\n"
                    f"I will extract & verify all proxies inside.\n\n"
                    f"— Credit: **{DEV_HANDLE}**",
                    reply_markup=build_cancel_keyboard(),
                )
            elif data == "act_help":
                await _safe_edit(
                    cb.message,
                    HELP_TEXT,
                    reply_markup=build_cancel_keyboard(),
                )
            elif data == "act_stats":
                await _safe_edit(
                    cb.message,
                    Stats.snapshot_for_user(user.id),
                    reply_markup=build_cancel_keyboard(),
                )
            elif data == "act_myinfo":
                await _safe_edit(
                    cb.message,
                    format_user_info(UserStore.get_user(user.id)),
                    reply_markup=build_cancel_keyboard(),
                )
            elif data == "act_about":
                await _safe_edit(
                    cb.message,
                    ABOUT_TEXT,
                    reply_markup=build_cancel_keyboard(),
                )

            elif data == "act_settings":
                await _safe_edit(
                    cb.message,
                    format_settings_text(user.id),
                    reply_markup=build_settings_keyboard(user.id),
                )

            elif data == "act_toggle_live":
                current = UserStore.get_live_notifications(user.id)
                UserStore.set_live_notifications(user.id, not current)
                new_state = not current
                await cb.answer(
                    f"🔔 Live notifications {'ENABLED' if new_state else 'DISABLED'}"
                )
                await _safe_edit(
                    cb.message,
                    format_settings_text(user.id),
                    reply_markup=build_settings_keyboard(user.id),
                )

            elif data == "act_cycle_ptype":
                cur = UserStore.get_setting(user.id, "proxy_type_filter", "all")
                try:
                    nxt = PTYPE_CYCLE[(PTYPE_CYCLE.index(cur) + 1) % len(PTYPE_CYCLE)]
                except Exception:
                    nxt = "all"
                UserStore.set_setting(user.id, "proxy_type_filter", nxt)
                await cb.answer(f"🌐 Proxy type: {nxt.upper()}")
                await _safe_edit(
                    cb.message,
                    format_settings_text(user.id),
                    reply_markup=build_settings_keyboard(user.id),
                )

            elif data == "act_cycle_format":
                cur = UserStore.get_setting(user.id, "export_format", "txt")
                try:
                    nxt = FORMAT_CYCLE[(FORMAT_CYCLE.index(cur) + 1) % len(FORMAT_CYCLE)]
                except Exception:
                    nxt = "txt"
                UserStore.set_setting(user.id, "export_format", nxt)
                await cb.answer(f"📥 Export format: {nxt.upper()}")
                await _safe_edit(
                    cb.message,
                    format_settings_text(user.id),
                    reply_markup=build_settings_keyboard(user.id),
                )

            elif data == "act_cycle_minlat":
                cur = int(UserStore.get_setting(user.id, "min_latency_ms", 0) or 0)
                try:
                    nxt = MIN_LAT_CYCLE[(MIN_LAT_CYCLE.index(cur) + 1) % len(MIN_LAT_CYCLE)]
                except Exception:
                    nxt = 0
                UserStore.set_setting(user.id, "min_latency_ms", nxt)
                await cb.answer(f"⚡ Min latency: {nxt}ms" if nxt else "⚡ Min latency: Off")
                await _safe_edit(
                    cb.message,
                    format_settings_text(user.id),
                    reply_markup=build_settings_keyboard(user.id),
                )

            elif data == "act_cycle_maxlat":
                cur = int(UserStore.get_setting(user.id, "max_latency_ms", 0) or 0)
                try:
                    nxt = MAX_LAT_CYCLE[(MAX_LAT_CYCLE.index(cur) + 1) % len(MAX_LAT_CYCLE)]
                except Exception:
                    nxt = 0
                UserStore.set_setting(user.id, "max_latency_ms", nxt)
                await cb.answer(f"🐢 Max latency: {nxt}ms" if nxt else "🐢 Max latency: Off")
                await _safe_edit(
                    cb.message,
                    format_settings_text(user.id),
                    reply_markup=build_settings_keyboard(user.id),
                )

            elif data == "act_cycle_sort":
                cur = UserStore.get_setting(user.id, "sort_by", "date")
                try:
                    nxt = SORT_CYCLE[(SORT_CYCLE.index(cur) + 1) % len(SORT_CYCLE)]
                except Exception:
                    nxt = "date"
                UserStore.set_setting(user.id, "sort_by", nxt)
                await cb.answer(f"📊 Sort by: {nxt}")
                await _safe_edit(
                    cb.message,
                    format_settings_text(user.id),
                    reply_markup=build_settings_keyboard(user.id),
                )

            elif data == "act_clear":
                if not is_admin(user.id):
                    await cb.answer("⛔ Admin only", show_alert=True)
                    return
                try:
                    for d in (DOWNLOADS, OUTPUTS):
                        for child in d.iterdir():
                            try:
                                if child.is_file():
                                    child.unlink()
                                elif child.is_dir():
                                    shutil.rmtree(child, ignore_errors=True)
                            except Exception:
                                pass
                    await cb.answer("✅ Workspace cleared")
                except Exception as e:
                    await cb.answer(f"❌ {e}", show_alert=True)
                await _safe_edit(
                    cb.message,
                    f"**{BRAND}**\n\n✅ Workspace cleared.\n\n— Credit: **{DEV_HANDLE}**",
                    reply_markup=build_cancel_keyboard(),
                )

            elif data == "act_noop":
                await cb.answer()

            elif data.startswith("act_myproxies_p"):
                # User views their own working proxy history (paginated)
                try:
                    page = int(data.rsplit("_p", 1)[-1])
                except Exception:
                    page = 1
                await _safe_edit(
                    cb.message,
                    format_working_proxies_page(user.id, page, viewer_is_admin=False),
                    reply_markup=build_working_proxies_keyboard(
                        user.id, page, viewer_is_admin=False),
                )

            elif data == "act_dlproxies":
                # User downloads all their own working proxies
                all_w = WorkingProxyStore.get_user_proxies(user.id)
                if not all_w:
                    await cb.answer("❌ No working proxies on record", show_alert=True)
                    return
                await cb.answer("📥 Building file...")
                out_path = build_working_proxies_file(user.id)
                try:
                    await client.send_document(
                        chat_id=cb.message.chat.id,
                        document=str(out_path),
                        caption=(
                            f"**{BRAND}** — Your working proxy history\n"
                            f"`{len(all_w)}` proxies · Credit: {DEV_HANDLE}"
                        ),
                    )
                finally:
                    try:
                        out_path.unlink(missing_ok=True)
                    except Exception:
                        pass

            elif data == "act_clrproxies":
                WorkingProxyStore.clear_user(user.id)
                await cb.answer("🧹 History cleared")
                await _safe_edit(
                    cb.message,
                    f"**{BRAND}**\n\n🧹 Your working proxy history has been cleared.\n\n"
                    f"— Credit: **{DEV_HANDLE}**",
                    reply_markup=build_cancel_keyboard(),
                )
            else:
                await cb.answer("⚠️ Unknown action button", show_alert=True)
            return

        # ----- Admin actions -----
        if data.startswith("adm_"):
            if not is_admin(user.id):
                await cb.answer("⛔ Admin only", show_alert=True)
                return

            if data == "adm_back":
                await _safe_edit(
                    cb.message,
                    admin_panel_text(),
                    reply_markup=build_admin_keyboard(),
                )
                await cb.answer()

            elif data == "adm_noop":
                await cb.answer()

            elif data == "adm_lock":
                UserStore.set_bot_locked(True)
                AuditLog.log(user.id, "lock")
                await cb.answer("🔒 Bot locked")
                await _safe_edit(
                    cb.message,
                    f"**{BRAND} — Admin Panel**\n\n🔒 Bot is now **LOCKED**.\n\n— Credit: **{DEV_HANDLE}**",
                    reply_markup=build_admin_keyboard(),
                )

            elif data == "adm_unlock":
                UserStore.set_bot_locked(False)
                AuditLog.log(user.id, "unlock")
                await cb.answer("🔓 Bot unlocked")
                await _safe_edit(
                    cb.message,
                    f"**{BRAND} — Admin Panel**\n\n🔓 Bot is now **OPEN** to everyone.\n\n— Credit: **{DEV_HANDLE}**",
                    reply_markup=build_admin_keyboard(),
                )

            elif data == "adm_stats":
                await _safe_edit(
                    cb.message,
                    Stats.snapshot(),
                    reply_markup=build_admin_keyboard(),
                )
                await cb.answer()

            elif data == "adm_reset":
                UserStore.reset_all_stats()
                AuditLog.log(user.id, "reset_stats")
                await cb.answer("🧹 All user stats reset")
                await _safe_edit(
                    cb.message,
                    f"**{BRAND}**\n\n🧹 All user stats reset.\n\n— Credit: **{DEV_HANDLE}**",
                    reply_markup=build_admin_keyboard(),
                )

            elif data.startswith("adm_users_p"):
                m = _ADM_USERS_CB_RE.match(data)
                if not m:
                    await cb.answer("Invalid user list callback", show_alert=True)
                    return
                page = int(m.group("page"))
                filter_kind = m.group("kind") or "all"
                await _safe_edit(
                    cb.message,
                    f"**{BRAND} — User List**\n\nTap a user to view details & actions:",
                    reply_markup=build_user_list_keyboard(page, 8, filter_kind),
                )
                await cb.answer()

            elif data == "adm_banned":
                await _safe_edit(
                    cb.message,
                    f"**{BRAND} — Banned Users**",
                    reply_markup=build_user_list_keyboard(1, 8, "banned"),
                )
                await cb.answer()

            elif data == "adm_approved":
                await _safe_edit(
                    cb.message,
                    f"**{BRAND} — Approved Users**",
                    reply_markup=build_user_list_keyboard(1, 8, "approved"),
                )
                await cb.answer()

            # IMPORTANT: check 'adm_user_proxies_' BEFORE 'adm_user_' because
            # 'adm_user_proxies_123_p1' would otherwise match the 'adm_user_'
            # branch and try to int('proxies_123_p1') → fail.
            elif data.startswith("adm_user_proxies_"):
                # Admin views a user's working proxy history (paginated)
                # Format: adm_user_proxies_<uid>_p<page>
                rest = data[len("adm_user_proxies_"):]
                parts = rest.split("_p")
                try:
                    target = int(parts[0])
                except Exception:
                    await cb.answer("Invalid user", show_alert=True)
                    return
                try:
                    page = int(parts[1]) if len(parts) > 1 else 1
                except Exception:
                    page = 1
                await _safe_edit(
                    cb.message,
                    format_working_proxies_page(target, page, viewer_is_admin=True),
                    reply_markup=build_working_proxies_keyboard(
                        target, page, viewer_is_admin=True),
                )
                await cb.answer()

            elif data.startswith("adm_user_"):
                try:
                    target = int(data[len("adm_user_"):])
                except Exception:
                    await cb.answer("Invalid user", show_alert=True)
                    return
                tu = UserStore.get_user(target)
                await _safe_edit(
                    cb.message,
                    format_user_info(tu),
                    reply_markup=build_user_detail_keyboard(target),
                )
                await cb.answer()

            elif data.startswith("adm_ban_"):
                try:
                    target = int(data[len("adm_ban_"):])
                except Exception:
                    await cb.answer("Invalid user", show_alert=True)
                    return
                if is_admin(target):
                    await cb.answer("Cannot ban admin", show_alert=True)
                    return
                UserStore.set_banned(target, True)
                AuditLog.log(user.id, "ban", target=target)
                tu = UserStore.get_user(target)
                name = tu.get("first_name") or tu.get("username") or target
                await cb.answer(f"⛔ Banned {name}")
                await _safe_edit(
                    cb.message,
                    format_user_info(tu),
                    reply_markup=build_user_detail_keyboard(target),
                )

            elif data.startswith("adm_unban_"):
                try:
                    target = int(data[len("adm_unban_"):])
                except Exception:
                    await cb.answer("Invalid user", show_alert=True)
                    return
                UserStore.set_banned(target, False)
                AuditLog.log(user.id, "unban", target=target)
                tu = UserStore.get_user(target)
                name = tu.get("first_name") or tu.get("username") or target
                await cb.answer(f"♻️ Unbanned {name}")
                await _safe_edit(
                    cb.message,
                    format_user_info(tu),
                    reply_markup=build_user_detail_keyboard(target),
                )

            elif data.startswith("adm_appr_"):
                try:
                    target = int(data[len("adm_appr_"):])
                except Exception:
                    await cb.answer("Invalid user", show_alert=True)
                    return
                UserStore.set_approved(target, True)
                if UserStore.is_banned(target):
                    UserStore.set_banned(target, False)
                AuditLog.log(user.id, "approve", target=target)
                tu = UserStore.get_user(target)
                name = tu.get("first_name") or tu.get("username") or target
                await cb.answer(f"✅ Approved {name}")
                await _safe_edit(
                    cb.message,
                    format_user_info(tu),
                    reply_markup=build_user_detail_keyboard(target),
                )

            elif data.startswith("adm_unappr_"):
                try:
                    target = int(data[len("adm_unappr_"):])
                except Exception:
                    await cb.answer("Invalid user", show_alert=True)
                    return
                UserStore.set_approved(target, False)
                AuditLog.log(user.id, "unapprove", target=target)
                tu = UserStore.get_user(target)
                name = tu.get("first_name") or tu.get("username") or target
                await cb.answer(f"❌ Removed approval for {name}")
                await _safe_edit(
                    cb.message,
                    format_user_info(tu),
                    reply_markup=build_user_detail_keyboard(target),
                )

            elif data.startswith("adm_dlproxies_"):
                # Admin downloads a user's working proxy history
                try:
                    target = int(data[len("adm_dlproxies_"):])
                except Exception:
                    await cb.answer("Invalid user", show_alert=True)
                    return
                all_w = WorkingProxyStore.get_user_proxies(target)
                if not all_w:
                    await cb.answer("❌ No working proxies on record", show_alert=True)
                    return
                await cb.answer("📥 Building file...")
                out_path = build_working_proxies_file(target)
                # protect_content=True so the file cannot be forwarded
                try:
                    await client.send_document(
                        chat_id=cb.message.chat.id,
                        document=str(out_path),
                        caption=(
                            f"**{BRAND}** — Working proxies for user `{target}`\n"
                            f"`{len(all_w)}` proxies · Credit: {DEV_HANDLE}"
                        ),
                        protect_content=True,
                    )
                finally:
                    try:
                        out_path.unlink(missing_ok=True)
                    except Exception:
                        pass

            elif data.startswith("adm_clrproxies_"):
                # Admin clears a user's working proxy history
                try:
                    target = int(data[len("adm_clrproxies_"):])
                except Exception:
                    await cb.answer("Invalid user", show_alert=True)
                    return
                WorkingProxyStore.clear_user(target)
                AuditLog.log(user.id, "clear_proxies", target=target)
                await cb.answer("🧹 History cleared")
                await _safe_edit(
                    cb.message,
                    f"**{BRAND}**\n\n🧹 Working proxy history cleared for `{target}`.\n\n"
                    f"— Credit: **{DEV_HANDLE}**",
                    reply_markup=build_user_detail_keyboard(target),
                )
            else:
                await cb.answer("⚠️ Unknown admin button", show_alert=True)
            return

    # ---------------------- Document handler ----------------------
    @application.on_message(filters.document & filters.private)
    async def _document(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        allowed, reason = can_use_bot(user.id)
        if not allowed:
            await _deny(client, message, reason)
            return

        # Rate limit check
        ok, reason = RateLimiter.check(user.id)
        if not ok:
            await _deny(client, message, reason)
            return

        doc = message.document
        if not doc:
            return
        fname = doc.file_name or "uploaded_file"
        ext = Path(fname).suffix.lower()
        file_size = doc.file_size or 0
        size_mb = file_size / (1024 * 1024) if file_size else 0

        live_notif = UserStore.get_live_notifications(user.id)

        log.info(f"Received file: {fname} ({ext}, {size_mb:.1f} MB) from user {user.id}")

        if file_size and size_mb > MAX_FILE_SIZE_MB:
            await message.reply(
                f"**{BRAND}**\n\n"
                f"❌ This file is `{size_mb:.2f} MB`, above the "
                f"`{MAX_FILE_SIZE_MB} MB` limit.\n\n"
                f"Please split the file into smaller parts and try again."
            )
            return

        try:
            if file_size:
                disk = shutil.disk_usage(DOWNLOADS)
                required = file_size * 3
                if disk.free < required:
                    await message.reply(
                        f"**{BRAND}**\n\n"
                        f"❌ Not enough free disk space to process this file.\n"
                        f"Available: `{disk.free / 1024 / 1024:.1f} MB`\n"
                        f"Required: approximately `{required / 1024 / 1024:.1f} MB`."
                    )
                    return
        except Exception as e:
            log.warning(f"Disk-space check failed: {e}")

        # Initial status
        size_str = f"📦 Size: `{size_mb:.2f} MB`" if file_size else "📦 Size: unknown"
        status_msg = await message.reply(
            f"**{BRAND}**\n\n"
            f"📥 File: `{fname}`\n"
            f"{size_str}\n"
            f"⏳ Downloading via parallel chunked MTProto "
            f"({PYROGRAM_PARALLEL_SESSIONS}×{PYROGRAM_PARALLEL_PER_SESSION})...\n\n"
            f"— Credit: **{DEV_HANDLE}**"
        )

        # ---- Download with progress callback ----
        local_path = DOWNLOADS / f"{user.id}_{Path(fname).name}"
        dl_state = {"last_tick": 0.0, "start": time.time(),
                    "last_bytes": 0, "last_edit": 0.0}

        async def _dl_progress(current, total):
            now = time.time()
            # Throttle Telegram edits to every 1.5s
            if now - dl_state["last_edit"] < 1.5 and current < total:
                return
            dl_state["last_edit"] = now
            elapsed = now - dl_state["start"]
            speed = (current / 1024 / 1024) / elapsed if elapsed > 0 else 0
            pct = (current / total * 100) if total else 0
            eta = ((total - current) / (current / elapsed)) if current > 0 and elapsed > 0 else 0
            done_mb = current / 1024 / 1024
            total_mb = total / 1024 / 1024
            try:
                await status_msg.edit_text(
                    f"**{BRAND} — Downloading**\n\n"
                    f"📥 File: `{fname}`\n"
                    f"📦 Size: `{total_mb:.2f} MB`\n"
                    f"⬇️  Downloaded: `{done_mb:.2f} MB / {total_mb:.2f} MB` ({pct:.0f}%)\n"
                    f"⚡ Speed: `{speed:.2f} MB/s`\n"
                    f"⏱  ETA: `{eta:.0f}s`\n\n"
                    f"— Credit: **{DEV_HANDLE}**"
                )
            except Exception:
                pass  # Telegram rate-limit — ignore

        try:
            # The parallel chunk downloader needs a known file size to
            # partition the file; without it we cannot detect a short
            # read, so fall back to the sequential downloader.
            used_parallel = False
            if file_size and file_size > 0:
                try:
                    await _parallel_download(
                        client, message, str(local_path), file_size,
                        progress_cb=_dl_progress,
                        cancel_cb=lambda: False,
                    )
                    used_parallel = True
                except Exception as parallel_error:
                    log.warning(
                        f"Parallel download unavailable/failed; falling back: "
                        f"{parallel_error}"
                    )
            if not used_parallel:
                await client.download_media(
                    message=message,
                    file_name=str(local_path),
                    progress=_dl_progress,
                )
            if file_size and local_path.stat().st_size != file_size:
                raise RuntimeError(
                    f"Downloaded file size mismatch: "
                    f"{local_path.stat().st_size} != {file_size}"
                )
        except Exception as e:
            try:
                local_path.unlink(missing_ok=True)
            except Exception:
                pass
            await status_msg.edit_text(f"❌ Download failed: `{e}`")
            return

        dl_elapsed = time.time() - dl_state["start"]
        dl_speed = (file_size / 1024 / 1024 / dl_elapsed) if dl_elapsed > 0 and file_size else 0

        # ---- Extraction ----
        await status_msg.edit_text(
            f"**{BRAND} — Extracting**\n\n"
            f"📥 File: `{fname}`\n"
            f"✅ Download: `{dl_elapsed:.1f}s` (`{dl_speed:.2f} MB/s`)\n"
            f"🔎 Extracting proxies...\n\n"
            f"— Credit: **{DEV_HANDLE}**"
        )

        extract_start = time.time()
        try:
            extract_future, jobs_ahead = await submit_extract_job(local_path, strict=STRICT_MODE)
            spinner = ("⏳", "⌛", "🔄")
            spin_idx = 0
            while not extract_future.done():
                queue_hint = (
                    f"🧵 Queue: `{jobs_ahead}` ahead\n"
                    if jobs_ahead > 0 else
                    "🧵 Queue: processing now\n"
                )
                try:
                    await status_msg.edit_text(
                        f"**{BRAND} — Extracting**\n\n"
                        f"📥 File: `{fname}`\n"
                        f"✅ Download: `{dl_elapsed:.1f}s` (`{dl_speed:.2f} MB/s`)\n"
                        f"{queue_hint}"
                        f"🔎 Extracting proxies... {spinner[spin_idx % len(spinner)]}\n\n"
                        f"— Credit: **{DEV_HANDLE}**"
                    )
                except Exception:
                    pass
                spin_idx += 1
                await asyncio.sleep(1.25)
            per_file = await extract_future
        except Exception as e:
            try:
                local_path.unlink(missing_ok=True)
            except Exception:
                pass
            await status_msg.edit_text(f"❌ Extract failed: `{e}`")
            return
        extract_elapsed = time.time() - extract_start

        all_proxies: List[Dict[str, Any]] = []
        per_file_summary: List[str] = []
        for source_name, plist in per_file.items():
            all_proxies.extend(plist)
            per_file_summary.append(f"  • `{source_name}` — {len(plist)} proxies")
            log.info(f"  [{fname}] {source_name}: {len(plist)} proxies")

        print(f"[AKAZA] User {user.id} ({user.first_name or '?'}) — extracted from: {fname}")

        if not all_proxies:
            await status_msg.edit_text(
                f"**{BRAND}**\n\n"
                f"📥 File: `{fname}`\n"
                f"✅ Download: `{dl_elapsed:.1f}s` · 🔎 Extract: `{extract_elapsed:.2f}s`\n"
                f"❌ No proxies found in this file.\n\n"
                f"_Tip: make sure your file actually contains proxy lines "
                f"(http://ip:port, socks5://..., ip:port, etc.)._\n\n"
                f"— Credit: **{DEV_HANDLE}**"
            )
            try: local_path.unlink(missing_ok=True)
            except Exception: pass
            return

        # ---- Verification ----
        verify_proxies = all_proxies[:VERIFY_MAX_PROXIES]
        verify_note = ""
        if len(all_proxies) > VERIFY_MAX_PROXIES:
            verify_note = (
                f"⚠️ Verifying first `{VERIFY_MAX_PROXIES}` of "
                f"`{len(all_proxies)}` extracted (cap)\n"
            )
        notif_state = {
            "working": 0, "failed": 0, "done": 0,
            "total": len(verify_proxies),
            "last_edit": 0.0,
            "live_batch": [],  # batch live notifications to reduce spam
            "last_live_send": 0.0,
        }

        async def _send_live_batch():
            """Flush the live batch buffer to chat."""
            if not notif_state["live_batch"]:
                return
            batch = notif_state["live_batch"][:]
            notif_state["live_batch"].clear()
            notif_state["last_live_send"] = time.time()
            lines = [f"✅ `{r['raw']}` · ⚡ `{r['latency_ms']}ms`" for r in batch]
            text = (
                f"**{BRAND} — Live Working Proxy**\n\n"
                + "\n".join(lines)
                + f"\n\n📊 Working so far: `{notif_state['working']}` / "
                  f"`{notif_state['total']}`\n"
                f"— Credit: **{DEV_HANDLE}**"
            )
            try:
                await client.send_message(message.chat.id, text)
            except Exception:
                pass

        def _on_result(r):
            notif_state["done"] += 1
            if r.get("working"):
                notif_state["working"] += 1
                if live_notif:
                    notif_state["live_batch"].append(r)
            else:
                notif_state["failed"] += 1

        def _on_progress(done, total):
            now = time.time()
            if now - notif_state["last_edit"] < 1.5 and done < total:
                return
            notif_state["last_edit"] = now
            pct = done * 100 / max(total, 1)
            # Build the progress text in a way we can edit_text later.
            notif_state["_last_text"] = (
                f"**{BRAND} — Verifying**\n\n"
                f"📥 File: `{fname}`\n"
                f"✅ Download: `{dl_elapsed:.1f}s` · 🔎 Extract: `{extract_elapsed:.2f}s`\n"
                f"🔎 Proxies found: `{total}`\n\n"
                f"⏳ Verifying... `{done}/{total}` ({pct:.0f}%)\n"
                f"✅ Working: `{notif_state['working']}`\n"
                f"❌ Failed: `{notif_state['failed']}`\n\n"
                f"— Credit: **{DEV_HANDLE}**"
            )

        # Initial verify status
        await status_msg.edit_text(
            f"**{BRAND} — Verifying**\n\n"
            f"📥 File: `{fname}`\n"
            f"✅ Download: `{dl_elapsed:.1f}s` · 🔎 Extract: `{extract_elapsed:.2f}s`\n"
            f"🔎 Proxies found: `{len(all_proxies)}`\n"
            f"{verify_note}"
            f"⏳ Verifying in parallel (max {VERIFY_THREADS} workers)...\n\n"
            f"**Sources:**\n" + "\n".join(per_file_summary[:8]) +
            (f"\n  ...and {len(per_file_summary)-8} more" if len(per_file_summary) > 8 else "") +
            f"\n\n— Credit: **{DEV_HANDLE}**"
        )

        verify_start = time.time()

        # Run streaming verification in a thread (so we can await periodically)
        # (threading already imported at top)
        result_box = {"results": None}

        def _run_verify():
            result_box["results"] = verify_proxies_streaming(
                verify_proxies,
                on_result=_on_result,
                on_progress=_on_progress,
            )

        verify_thread = threading.Thread(target=_run_verify, daemon=True)
        verify_thread.start()

        # While the verify thread runs, periodically:
        #   - update the status message
        #   - flush live notifications (if enabled)
        while verify_thread.is_alive():
            await asyncio.sleep(1.5)
            # Edit status with latest progress text
            last_text = notif_state.get("_last_text")
            if last_text:
                try:
                    await status_msg.edit_text(last_text)
                except Exception:
                    pass
            # Flush live notifications (batch every 3s or 5 proxies)
            if live_notif and notif_state["live_batch"] and (
                len(notif_state["live_batch"]) >= 5
                or (time.time() - notif_state["last_live_send"]) > 3.0
            ):
                await _send_live_batch()

        verify_thread.join()
        results = result_box["results"]

        # Flush any remaining live notifications
        if live_notif and notif_state["live_batch"]:
            await _send_live_batch()

        verify_elapsed = time.time() - verify_start

        if results is None:
            try:
                local_path.unlink(missing_ok=True)
            except Exception:
                pass
            await status_msg.edit_text("❌ Verify failed unexpectedly.")
            return

        working_all = [r for r in results if r and r.get("working")]
        failed  = [r for r in results if r and not r.get("working")]

        # Apply user's proxy-type + latency filters to the "working" list
        u_filters = UserStore.get_user(user.id)
        u_ptype = u_filters.get("proxy_type_filter", "all")
        u_minlat = int(u_filters.get("min_latency_ms", 0) or 0)
        u_maxlat = int(u_filters.get("max_latency_ms", 0) or 0)
        working = []
        for r in working_all:
            if u_ptype != "all" and r.get("type", "http") != u_ptype:
                continue
            lat = int(r.get("latency_ms", 0) or 0)
            if u_minlat and lat < u_minlat:
                continue
            if u_maxlat and lat > u_maxlat:
                continue
            working.append(r)
        filtered_out = len(working_all) - len(working)

        # Record per-user stats
        UserStore.record_run(
            user_id=user.id,
            file_name=fname,
            extracted=len(all_proxies),
            working=len(working),
            failed=len(failed),
        )
        # Persist working proxies with timestamps
        if working:
            WorkingProxyStore.record(user.id, fname, working)

        # Console announce
        print(f"[AKAZA] User {user.id} ({user.first_name or '?'}) — proxy source: {fname}")
        print(f"[AKAZA] Total extracted: {len(all_proxies)}")
        print(f"[AKAZA] Working: {len(working)}  |  Failed: {len(failed)}")
        for w in working:
            print(f"[AKAZA] {DEV_HANDLE} working proxy: {w['raw']}  ({w['latency_ms']}ms)")

        # Build the failed-proxies file (for debugging)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_stem = Path(fname).stem or "akaza"
        fail_path = OUTPUTS / f"AKAZA_failed_{safe_stem}_{ts}.txt"
        with open(fail_path, "w", encoding="utf-8") as f:
            f.write(f"# {BRAND} — Failed Proxies\n# Credit: {DEV_HANDLE}\n")
            for r in failed:
                f.write(f"{r['raw']}    # {r.get('error','unknown')}\n")
        try:
            fail_path.unlink(missing_ok=True)
        except Exception:
            pass

        # Send the final summary
        rate = (len(working) / len(all_proxies) * 100) if all_proxies else 0
        filter_line = ""
        if filtered_out > 0:
            filter_line = (
                f"🗑  Filtered : `{filtered_out}` (excluded by your filters: "
                f"type=`{u_ptype}` min=`{u_minlat}ms` max=`{u_maxlat}ms`)\n"
            )
        fmt = u_filters.get("export_format", "txt").upper()
        summary = (
            f"**{BRAND} — Done!**\n\n"
            f"📥 Source file : `{fname}`\n"
            f"📦 Size        : `{size_mb:.2f} MB`\n\n"
            f"{verify_note}\n"
            f"**⏱  Timing**\n"
            f"⬇️  Download : `{dl_elapsed:.1f}s` (`{dl_speed:.2f} MB/s`)\n"
            f"🔎  Extract  : `{extract_elapsed:.2f}s`\n"
            f"✅  Verify   : `{verify_elapsed:.1f}s`\n\n"
            f"**📊 Results**\n"
            f"🔎  Extracted : `{len(all_proxies)}`\n"
            f"✅  Working   : `{len(working)}`\n"
            + filter_line +
            f"❌  Failed    : `{len(failed)}`\n"
            f"📈  Success   : `{rate:.1f}%`\n\n"
            f"📎 Working proxies attached below (`{fmt}`).\n\n"
            f"— Credit: **{DEV_HANDLE}**"
        )
        await status_msg.edit_text(summary)

        # Always send the final results file (format respects user setting)
        if working:
            # Build the file using the user's format + filters
            # (working list is already filtered; but build_working_proxies_file
            # rebuilds from WorkingProxyStore history.  To honor this run's
            # exact working list, we build a one-off file here.)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_stem = Path(fname).stem or "akaza"
            ext = u_filters.get("export_format", "txt").lower()
            out_name = f"AKAZA_working_{safe_stem}_{ts}.{ext}"
            out_path = OUTPUTS / out_name
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if ext == "json":
                payload = {
                    "brand": BRAND, "credit": DEV_HANDLE,
                    "user_id": user.id, "source": fname,
                    "generated": now_str,
                    "total": len(working),
                    "filters": {"type": u_ptype, "min_latency_ms": u_minlat,
                                "max_latency_ms": u_maxlat},
                    "timing": {"download_s": round(dl_elapsed, 1),
                               "extract_s": round(extract_elapsed, 2),
                               "verify_s": round(verify_elapsed, 1)},
                    "proxies": [{"raw": r["raw"], "type": r["type"],
                                 "latency_ms": r["latency_ms"]} for r in working],
                }
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
            elif ext == "csv":
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write("proxy,type,latency_ms\n")
                    for r in sorted(working, key=lambda x: x.get("latency_ms", 9999)):
                        f.write(f"\"{r['raw']}\",{r['type']},{r['latency_ms']}\n")
            else:  # txt
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(f"# {BRAND} — Working Proxies\n")
                    f.write(f"# Source : {fname}\n")
                    f.write(f"# User   : {user.id} ({user.first_name or user.username or 'unknown'})\n")
                    f.write(f"# Generated: {now_str}\n")
                    f.write(f"# Credit : {DEV_HANDLE}\n")
                    f.write(f"# Total  : {len(working)} working / {len(all_proxies)} extracted\n")
                    f.write(f"# Timing : download {dl_elapsed:.1f}s · "
                            f"extract {extract_elapsed:.2f}s · verify {verify_elapsed:.1f}s\n")
                    if filtered_out:
                        f.write(f"# Filtered: {filtered_out} (type={u_ptype} "
                                f"min={u_minlat}ms max={u_maxlat}ms)\n")
                    f.write("=" * 60 + "\n")
                    for r in sorted(working, key=lambda x: x.get("latency_ms", 9999)):
                        f.write(f"{r['raw']}    # {r['latency_ms']}ms\n")

            try:
                await client.send_document(
                    chat_id=message.chat.id,
                    document=str(out_path),
                    caption=f"**{BRAND}** — {len(working)} working proxies ({fmt})\n"
                            f"Credit: {DEV_HANDLE}",
                )
            finally:
                try:
                    out_path.unlink(missing_ok=True)
                except Exception:
                    pass

        # Clean up the uploaded file
        try: local_path.unlink(missing_ok=True)
        except Exception: pass

    # ---------------------- Plain text handler ----------------------
    @application.on_message(filters.text & ~filters.command(
        ["start", "help", "stats", "about", "clear", "myinfo", "myproxies",
         "settings", "admin", "ban", "unban", "approve", "unapprove",
         "lock", "unlock", "users", "userinfo", "broadcast", "leaderboard",
         "backup", "health", "auditlog", "purgeaudit",
         "strict", "lenient", "mode"]) & filters.private)
    async def _text(client: Client, message: Message):
        user = message.from_user
        UserStore.touch_user(user)
        allowed, reason = can_use_bot(user.id)
        if not allowed:
            await _deny(client, message, reason)
            return

        text = message.text or ""
        extract_start = time.time()
        proxies = await asyncio.to_thread(extract_proxies_from_text, text, STRICT_MODE)
        extract_elapsed = time.time() - extract_start

        if not proxies:
            await message.reply(
                f"**{BRAND}**\n\n❌ No proxies found in your message.\n"
                f"Send a file or paste proxy lines directly "
                f"(e.g. `http://1.2.3.4:8080`, `socks5://5.6.7.8:1080`).\n\n"
                f"— Credit: **{DEV_HANDLE}**"
            )
            return

        live_notif = UserStore.get_live_notifications(user.id)
        status = await message.reply(
            f"**{BRAND} — Verifying**\n\n"
            f"🔎 Proxies found: `{len(proxies)}` (extract: `{extract_elapsed:.2f}s`)\n"
            f"⏳ Verifying in parallel...\n\n"
            f"— Credit: **{DEV_HANDLE}**"
        )

        # Streaming verify with live notifications
        notif_state = {
            "working": 0, "failed": 0, "done": 0, "total": len(proxies),
            "live_batch": [], "last_live_send": 0.0, "last_edit": 0.0,
            "_last_text": None,
        }

        async def _send_live_batch():
            if not notif_state["live_batch"]:
                return
            batch = notif_state["live_batch"][:]
            notif_state["live_batch"].clear()
            notif_state["last_live_send"] = time.time()
            lines = [f"✅ `{r['raw']}` · ⚡ `{r['latency_ms']}ms`" for r in batch]
            text = (
                f"**{BRAND} — Live Working Proxy**\n\n"
                + "\n".join(lines)
                + f"\n\n📊 Working so far: `{notif_state['working']}` / "
                  f"`{notif_state['total']}`\n"
                f"— Credit: **{DEV_HANDLE}**"
            )
            try:
                await client.send_message(message.chat.id, text)
            except Exception:
                pass

        def _on_result(r):
            notif_state["done"] += 1
            if r.get("working"):
                notif_state["working"] += 1
                if live_notif:
                    notif_state["live_batch"].append(r)
            else:
                notif_state["failed"] += 1

        def _on_progress(done, total):
            now = time.time()
            if now - notif_state["last_edit"] < 1.5 and done < total:
                return
            notif_state["last_edit"] = now
            pct = done * 100 / max(total, 1)
            notif_state["_last_text"] = (
                f"**{BRAND} — Verifying**\n\n"
                f"🔎 Proxies found: `{total}` (extract: `{extract_elapsed:.2f}s`)\n"
                f"⏳ Verifying... `{done}/{total}` ({pct:.0f}%)\n"
                f"✅ Working: `{notif_state['working']}`\n"
                f"❌ Failed: `{notif_state['failed']}`\n\n"
                f"— Credit: **{DEV_HANDLE}**"
            )

        # (threading already imported at top)
        verify_start = time.time()
        result_box = {"results": None}

        def _run_verify():
            result_box["results"] = verify_proxies_streaming(
                proxies, on_result=_on_result, on_progress=_on_progress,
            )

        verify_thread = threading.Thread(target=_run_verify, daemon=True)
        verify_thread.start()

        while verify_thread.is_alive():
            await asyncio.sleep(1.5)
            last_text = notif_state.get("_last_text")
            if last_text:
                try:
                    await status.edit_text(last_text)
                except Exception:
                    pass
            if live_notif and notif_state["live_batch"] and (
                len(notif_state["live_batch"]) >= 5
                or (time.time() - notif_state["last_live_send"]) > 3.0
            ):
                await _send_live_batch()

        verify_thread.join()
        results = result_box["results"]
        if live_notif and notif_state["live_batch"]:
            await _send_live_batch()

        verify_elapsed = time.time() - verify_start
        working = [r for r in results if r and r.get("working")]
        failed_count = len(proxies) - len(working)

        # Record per-user stats
        UserStore.record_run(
            user_id=user.id,
            file_name="<inline message>",
            extracted=len(proxies),
            working=len(working),
            failed=failed_count,
        )
        # Persist working proxies with timestamps
        if working:
            WorkingProxyStore.record(user.id, "<inline message>", working)

        # Console announce
        print(f"[AKAZA] User {user.id} ({user.first_name or '?'}) — inline message")
        print(f"[AKAZA] Extracted: {len(proxies)}  Working: {len(working)}")
        for w in working:
            print(f"[AKAZA] {DEV_HANDLE} working proxy: {w['raw']}  ({w['latency_ms']}ms)")

        if working:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = OUTPUTS / f"AKAZA_working_inline_{ts}.txt"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"# {BRAND} — Working Proxies (inline)\n# Credit: {DEV_HANDLE}\n")
                f.write(f"# Timing: extract {extract_elapsed:.2f}s · verify {verify_elapsed:.1f}s\n")
                for r in sorted(working, key=lambda x: x.get("latency_ms", 9999)):
                    f.write(f"{r['raw']}    # {r['latency_ms']}ms\n")
            rate = (len(working) / len(proxies) * 100) if proxies else 0
            await status.edit_text(
                f"**{BRAND} — Done!**\n\n"
                f"🔎 Extracted: `{len(proxies)}` · ✅ Working: `{len(working)}` "
                f"· ❌ Failed: `{failed_count}`\n"
                f"📈 Success: `{rate:.1f}%`\n"
                f"⏱ Extract: `{extract_elapsed:.2f}s` · Verify: `{verify_elapsed:.1f}s`\n\n"
                f"— Credit: **{DEV_HANDLE}**"
            )
            await client.send_document(
                chat_id=message.chat.id,
                document=str(out_path),
                caption=f"**{BRAND}** — {len(working)} working proxies\nCredit: {DEV_HANDLE}",
            )
        else:
            await status.edit_text(
                f"**{BRAND}**\n\n❌ None of the `{len(proxies)}` proxies worked.\n"
                f"⏱ Verify: `{verify_elapsed:.1f}s`\n\n— Credit: **{DEV_HANDLE}**"
            )


# ===========================================================================
#  6.  ENTRY POINT
# ===========================================================================
def _validate_config():
    problems = []
    if not isinstance(API_ID, int) or API_ID <= 0:
        problems.append("API_ID must be a positive integer")
    if not API_HASH:
        problems.append("API_HASH is missing")
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        problems.append("BOT_TOKEN is missing (get it from @BotFather)")
    if not isinstance(ADMIN_ID, int) or ADMIN_ID <= 0:
        problems.append("ADMIN_ID must be your numeric Telegram user ID")
    return problems


def main():
    if "--selftest" in sys.argv:
        sys.exit(0 if run_filter_selftest() else 1)
    print(BANNER)
    problems = _validate_config()
    if problems:
        print("❌  CONFIGURATION INCOMPLETE  ❌")
        print("=" * 50)
        for p in problems:
            print(f"  • {p}")
        print("=" * 50)
        print("Edit BOT_TOKEN and ADMIN_ID at the top of this file and re-run.")
        print(f"\n— {BRAND} · Credit: {DEV_HANDLE}\n")
        sys.exit(1)

    if not PYROGRAM_AVAILABLE:
        print("❌ Pyrogram not installed.  Run:  pip install pyrogram tgcrypto")
        sys.exit(1)

    if not REQUESTS_AVAILABLE:
        print("❌ requests not installed.  Run:  pip install requests pysocks")
        sys.exit(1)

    log.info(f"Starting {BRAND} {VERSION}")
    log.info(f"Admin ID: {ADMIN_ID}")
    log.info(f"Workspace: {WORK_DIR}")

    client = Client(
        name="akaza_x_proxy",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        workdir=str(WORK_DIR),
        workers=DOWNLOAD_WORKERS,
        max_concurrent_transmissions=max(
            1, int(os.getenv("MAX_CONCURRENT_TRANSMISSIONS", "4"))
        ),
    )
    register_handlers(client)

    print(f"\n✅  {BRAND} is running.  Open Telegram and send /start\n")
    try:
        client.run()
    except KeyboardInterrupt:
        print("\n👋  Shutting down.  Bye!")


if __name__ == "__main__":
    main()
