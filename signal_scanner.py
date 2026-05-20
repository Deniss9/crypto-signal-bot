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

# ====================== 电报配置（你必须填）======================
TELEGRAM_BOT_TOKEN = "这里填你的机器人TOKEN"
TELEGRAM_CHAT_ID = "这里填你的CHAT_ID"
# ================================================================

ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "fly15201344146@gmail.com")
ALERT_EMAILS = [x.strip() for x in ALERT_EMAIL.split(";") if x.strip()]
MIN_SIGNALS = int(os.environ.get("MIN_SIGNALS", "6"))
GMAIL_SERVER = "/home/user/servers/gmail/run.mjs"

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(_SCRIPT_DIR, "signal_cache.json")
CACHE_PRICE_TOLERANCE = 0.01
CACHE_TTL_HOURS = 8

OKX_CANDLE = "https://www.okx.com/api/v5/market/candles"
OKX_FUNDING = "https://www.okx.com/api/v5/public/funding-rate"

# ─── 缓存工具 ───────────────────────────────────────────────────────────────
def load_cache() -> dict:
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_cache(cache: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  [WARN] 缓存写入失败: {e}")

def is_cache_expired(entry: dict) -> bool:
    expires_at_str = entry.get("expires_at")
    if not expires_at_str:
        sent_at_str = entry.get("sent_at")
        if not sent_at_str:
            return True
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
    key = f"{sym}:{direction}"
    entry = cache.get(key)
    if not entry:
        return False
    if is_cache_expired(entry):
        return False
    cached_price = entry.get("price", 0)
    if cached_price <= 0:
        return False
    deviation = abs(price - cached_price) / cached_price
    return deviation <= CACHE_PRICE_TOLERANCE

def update_cache(cache: dict, sym: str, direction: str, price: float, sent_at: str):
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
    bearish_engulf5 = l5["c"] < l5["o"] and l5["o"] > p5["c"] and l5["c"] < p5["o"]
    return long_upper5, bearish_engulf5

# ─── 电报推送（我加的） ───────────────────────────────────────────────────────
def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = f"chat_id={TELEGRAM_CHAT_ID}&text={text}&parse_mode=Markdown"
        req = Request(url, data=data.encode("utf-8"))
        urlopen(req, timeout=5)
    except:
        pass

# ─── 信号扫描主逻辑 ───────────────────────────────────────────────────────────
def scan_one(sym: str, inst_id: str):
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_utc}] Scan {sym} {inst_id}")

    try:
        c5m = fetch_candles(inst_id, "5m", 50)
        c15m = fetch_candles(inst_id, "15m", 30)
        price = c5m[-1]["c"]
        closes5 = [x["c"] for x in c5m]
        rsi = rsi_calc(closes5, 14)[-1] if len(closes5) >= 15 else None
        macd = macd_calc(closes5)
        bb = bollinger_bands(closes5, 20, 2)
        funding = fetch_funding_rate(inst_id)
        long_upper5, bearish_engulf5 = candle_patterns(c5m, c15m, price)

        score = 0
        if rsi and rsi > 75: score += 2
        if macd["hist"] and macd["hist"][-1] < -0.0001: score += 2
        if price > bb["upper"] * 1.005: score += 2
        if bearish_engulf5: score += 2
        if long_upper5: score += 1
        if funding > 0.15: score += 1

        print(f"  {sym} price={price:.2f} rsi={rsi:.1f} score={score}")

        if score >= MIN_SIGNALS:
            msg = f"""
🔔 【强力做空信号】
币种：{sym}
价格：{price:.2f}
得分：{score}/6
RSI：{rsi:.1f}
资金费率：{funding:.2f}%
"""
            send_telegram(msg)
            print("✅ 信号已发送到电报！")
    except Exception as e:
        print(f"❌ 扫描失败: {e}")

# ─── 主入口 ──────────────────────────────────────────────────────────────────
def main():
    symbols = [
        ("BTC", "BTC-USDT-SWAP"),
        ("ETH", "ETH-USDT-SWAP"),
        ("SOL", "SOL-USDT-SWAP"),
    ]
    for s, i in symbols:
        scan_one(s, i)

if __name__ == "__main__":
    main()  
# 在主循环里，只调用 auto_reply()，不发其他自动消息
while True:
    auto_reply()  # 只处理你发的指令
    # 你的原策略代码...
    time.sleep(10)  # 10秒循环一次，避免请求太频繁
