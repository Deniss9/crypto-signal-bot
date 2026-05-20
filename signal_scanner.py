
#!/usr/bin/env python3
"""
BTC / ETH / SOL 做空信号扫描器 v4.4 (Python)
用法:
    python3 short_signal_scanner.py
    MIN_SIGNALS=6 ALERT_EMAIL=you@example.com python3 short_signal_scanner.py
依赖: 仅 Python 标准库（urllib, json, subprocess, os, math, datetime）
缓存策略: 记录最近 1 次触发预警的 (币种+方向+价格+时间)，若下次触发方向一致、价格波动
         在 1% 以内、且缓存未过期（8 小时内）则跳过邮件发送，避免重复通知。
         超过 8 小时的缓存自动视为过期，下次触发将重新发送。
"""

import os
import json
import math
import subprocess
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request

ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "fly15201344146@gmail.com")
ALERT_EMAILS = [x.strip() for x in ALERT_EMAIL.split(";") if x.strip()]
MIN_SIGNALS = int(os.environ.get("MIN_SIGNALS", "6"))
GMAIL_SERVER = "/home/user/servers/gmail/run.mjs"

# 缓存文件存放在与脚本同目录下，持久化跨运行
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(_SCRIPT_DIR, "signal_cache.json")
CACHE_PRICE_TOLERANCE = 0.01   # 1% 价格波动阈值
CACHE_TTL_HOURS = 8             # 缓存过期时长（小时）

OKX_CANDLE = "https://www.okx.com/api/v5/market/candles"
OKX_FUNDING = "https://www.okx.com/api/v5/public/funding-rate"

# ─── 缓存工具 ───────────────────────────────────────────────────────────────

def load_cache() -> dict:
    """读取上一次的预警缓存，格式: {cache_key: {price: float, sent_at: str, expires_at: str}}"""
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache: dict):
    """将最新缓存写入文件（只保留每个 key 的最新一条）"""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  [WARN] 缓存写入失败: {e}")


def is_cache_expired(entry: dict) -> bool:
    """判断缓存条目是否已过期（超过 CACHE_TTL_HOURS 小时）"""
    expires_at_str = entry.get("expires_at")
    if not expires_at_str:
        # 旧格式缓存：用 sent_at 推算过期时间
        sent_at_str = entry.get("sent_at")
        if not sent_at_str:
            return True  # 无时间信息，视为过期
        try:
            sent_at = datetime.strptime(sent_at_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) - sent_at > timedelta(hours=CACHE_TTL_HOURS)
        except Exception:
            return True
    try:
        expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires_at
    except Exception:
        return True


def is_duplicate(cache: dict, sym: str, direction: str, price: float) -> bool:
    """
    判断是否为重复预警（三个条件同时满足才视为重复）：
    1. 相同 sym + direction
    2. 当前价格与缓存价格偏差 <= 1%
    3. 缓存未过期（8 小时内）
    """
    key = f"{sym}:{direction}"
    entry = cache.get(key)
    if not entry:
        return False
    # 条件 3：缓存已过期 → 视为全新信号
    if is_cache_expired(entry):
        return False
    cached_price = entry.get("price", 0)
    if cached_price <= 0:
        return False
    deviation = abs(price - cached_price) / cached_price
    return deviation <= CACHE_PRICE_TOLERANCE


def update_cache(cache: dict, sym: str, direction: str, price: float, sent_at: str):
    """更新缓存：记录刚刚发送成功的预警信息（含过期时间）"""
    key = f"{sym}:{direction}"
    sent_dt = datetime.strptime(sent_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    expires_dt = sent_dt + timedelta(hours=CACHE_TTL_HOURS)
    cache[key] = {
        "price": price,
        "sent_at": sent_at,
        "expires_at": expires_dt.strftime("%Y-%m-%d %H:%M:%S"),
    }

# ─── 行情工具 ────────────────────────────────────────────────────────────────

def fetch_json(url: str, headers: dict = None) -> dict:
    req = Request(url, headers={"User-Agent": "ShortSignalScanner/4.4", **(headers or {})})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_candles(inst_id: str, bar: str, limit: int = 100) -> list:
    url = f"{OKX_CANDLE}?instId={inst_id}&bar={bar}&limit={limit}"
    rows = fetch_json(url).get("data", [])
    candles = [
        {"ts": int(r[0]), "o": float(r[1]), "h": float(r[2]), "l": float(r[3]),
         "c": float(r[4]), "v": float(r[5])}
        for r in rows
    ]
    candles.reverse()
    return candles


def fetch_funding_rate(inst_id: str) -> float:
    data = fetch_json(f"{OKX_FUNDING}?instId={inst_id}").get("data", [{}])
    return float(data[0].get("fundingRate", 0)) * 100

# ─── 技术指标 ────────────────────────────────────────────────────────────────

def ema(values: list, period: int) -> list:
    if not values:
        return []
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi_calc(closes: list, period: int = 14) -> list:
    if len(closes) < period + 1:
        return [None] * len(closes)
    result = [None] * period
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    ag, al = gains / period, losses / period
    result.append(100 if al == 0 else 100 - 100 / (1 + ag / al))
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + max(d, 0)) / period
        al = (al * (period - 1) + max(-d, 0)) / period
        result.append(100 if al == 0 else 100 - 100 / (1 + ag / al))
    return result


def macd_calc(closes: list, fast=12, slow=26, signal=9):
    ef = ema(closes, fast)
    es = ema(closes, slow)
    macd_line = [ef[i] - es[i] for i in range(len(closes))]
    sig_input = macd_line[slow - 1:]
    sig_line = ema(sig_input, signal)
    hist = [sig_input[i] - sig_line[i] for i in range(len(sig_input))]
    return {"hist": hist, "macd": sig_input, "signal": sig_line}


def bollinger_bands(closes: list, period=20, mult=2):
    sl = closes[-period:]
    mid = sum(sl) / period
    std = math.sqrt(sum((x - mid) ** 2 for x in sl) / period)
    return {"upper": mid + mult * std, "mid": mid, "lower": mid - mult * std}


def candle_patterns(c5m, c15m, price):
    l5, p5 = c5m[-1], c5m[-2]
    body5 = abs(l5["c"] - l5["o"])
    upper5 = l5["h"] - max(l5["c"], l5["o"])
    long_upper5 = upper5 > body5 * 1.5 and upper5 > price * 0.002
    bearish_engulf5 = l5["c"] < l5["o"] and l5["o"] >
