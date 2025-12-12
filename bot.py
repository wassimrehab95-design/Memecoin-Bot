import os
import time
import sqlite3
import requests
from datetime import datetime, timezone

# =============== CONFIG ===============
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# DexScreener endpoints (documented)
TOKEN_PROFILES_LATEST = "https://api.dexscreener.com/token-profiles/latest/v1"
TOKEN_BOOSTS_LATEST = "https://api.dexscreener.com/token-boosts/latest/v1"
TOKEN_PAIRS = "https://api.dexscreener.com/token-pairs/v1/solana/{}"

SCAN_EVERY_SECONDS = 10

# Your filters
MIN_CAP = 20_000
MAX_CAP = 40_000
MIN_VOL_24H = 20_000
MAX_AGE_MINUTES = 20
MIN_LIQUIDITY_USD = 2_000  # helps avoid total junk pools

# Spam control
MAX_POSTS_PER_SCAN = 3
TELEGRAM_COOLDOWN_SECONDS = 4

# Source restriction
ALLOW_PUMPFUN = True
ALLOW_BONK_LAUNCHLAB = False  # set True if you *also* want LaunchLab BONK stuff

# Dex IDs on DexScreener UI you may see include "pumpswap", "pumpfun", "launchlab", "raydium", etc.
ALLOWED_DEX_IDS = set()
if ALLOW_PUMPFUN:
    ALLOWED_DEX_IDS.update({"pumpswap", "pumpfun"})
if ALLOW_BONK_LAUNCHLAB:
    ALLOWED_DEX_IDS.add("launchlab")

DB_PATH = "sent_tokens.sqlite3"

# =============== HTTP SESSION ===============
session = requests.Session()
session.headers.update({"User-Agent": "QuantBotV2/1.0"})

def must_env(name: str, value: str):
    if not value:
        raise SystemExit(f"Missing required env var: {name}")

def db_init():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sent (
            token_address TEXT PRIMARY KEY,
            sent_at_utc TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn

def already_sent(conn, token_address: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sent WHERE token_address = ? LIMIT 1", (token_address,))
    return cur.fetchone() is not None

def mark_sent(conn, token_address: str):
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO sent(token_address, sent_at_utc) VALUES(?, ?)",
        (token_address, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()

def send_telegram_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    r = session.post(url, data=payload, timeout=15)
    data = r.json()
    return bool(data.get("ok"))

def safe_get_json(url: str, timeout=15):
    r = session.get(url, timeout=timeout)
    if r.status_code != 200:
        return None
    return r.json()

def now_ts_ms() -> int:
    return int(time.time() * 1000)

def minutes_old_from_pair(pair: dict):
    ts = pair.get("pairCreatedAt")
    if not ts:
        return None
    # pairCreatedAt is ms since epoch
    age_ms = now_ts_ms() - int(ts)
    return int(age_ms / 60000)

def pick_best_allowed_pair(pairs: list[dict]) -> dict | None:
    """Pick the most useful pool among allowed DEX ids (prefer highest liquidity)."""
    allowed = []
    for p in pairs:
        if p.get("chainId") != "solana":
            continue
        dex_id = (p.get("dexId") or "").lower()
        if dex_id in ALLOWED_DEX_IDS:
            allowed.append(p)

    if not allowed:
        return None

    def liq(p):
        return float((p.get("liquidity") or {}).get("usd") or 0.0)

    allowed.sort(key=liq, reverse=True)
    return allowed[0]

def format_usd(x):
    try:
        x = float(x)
    except Exception:
        return "N/A"
    if x >= 1_000_000_000:
        return f"${x/1_000_000_000:.2f}B"
    if x >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"${x/1_000:.2f}K"
    return f"${x:.2f}"

def candidate_token_addresses() -> set[str]:
    addrs = set()

    # Latest token profiles
    profiles = safe_get_json(TOKEN_PROFILES_LATEST, timeout=15)
    if isinstance(profiles, list):
        for item in profiles:
            if (item.get("chainId") == "solana") and item.get("tokenAddress"):
                addrs.add(item["tokenAddress"])

    # Latest boosted tokens
    boosts = safe_get_json(TOKEN_BOOSTS_LATEST, timeout=15)
    if isinstance(boosts, list):
        for item in boosts:
            if item.get("tokenAddress"):
                addrs.add(item["tokenAddress"])

    return addrs

def passes_filters(pair: dict) -> tuple[bool, str]:
    # cap: prefer marketCap, fallback to fdv
    mcap = pair.get("marketCap")
    fdv = pair.get("fdv")
    cap_value = mcap if mcap is not None else fdv
    cap_label = "Mkt Cap" if mcap is not None else "FDV"
    if cap_value is None:
        return False, "no cap"

    cap_value = float(cap_value)
    if cap_value < MIN_CAP or cap_value > MAX_CAP:
        return False, f"cap out of range ({cap_label}={cap_value})"

    vol24 = (pair.get("volume") or {}).get("h24")
    if vol24 is None:
        return False, "no volume"
    vol24 = float(vol24)
    if vol24 < MIN_VOL_24H:
        return False, "volume too low"

    liq = float((pair.get("liquidity") or {}).get("usd") or 0.0)
    if liq < MIN_LIQUIDITY_USD:
        return False, "liquidity too low"

    age_min = minutes_old_from_pair(pair)
    if age_min is None:
        return False, "no pairCreatedAt"
    if age_min > MAX_AGE_MINUTES:
        return False, "too old"

    return True, ""

def build_message(pair: dict) -> str:
    base = pa

