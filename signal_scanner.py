#!/usr/bin/env python3
"""
BTC / ETH / SOL 做空信号扫描器 v4.4 (Python)
用法：
    python3 short_signal_scanner.py
    MIN_SIGNALS=6 ALERT_EMAIL=you@example.com python3 short_signal_scanner.py
依赖: 仅 Python 标准库 (urllib, json, subprocess, os, math, datetime)
缓存策略: 记录最近 1 次触发预警的 (币种+方向+价格+时间)，若下次触发方向一致、价格波动在 1% 以内、且缓存未过期（8 小时内）则跳过邮件发送，避免重复通知。
超过 8 小时的缓存自动视为过期，下次触发将重新发送。
"""

import os
import json
import math
import subprocess
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request

# ====================== 电报配置（你必须填）========================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
# ====================================================================

ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "fly15201344146@gmail.com")
GMAIL_SERVER = "/home/user/servers/gmail/run.mjs"

# 缓存配置（防重复推送）
CACHE_FILE = "signal_cache.json"
CACHE_PRICE_TOLERANCE = 0.01  # 价格波动1%以内视为重复信号
CACHE_TTL_HOURS = 8            # 缓存8小时过期

def send_telegram_message(text):
    """只在信号触发时发送电报消息"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text})
        req = Request(url, data=data.encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urlopen(req) as response:
            return response.read()
    except Exception as e:
        print(f"电报发送失败: {e}")

def send_email(subject, body):
    """邮件告警（原功能保留）"""
    try:
        cmd = [
            "node", GMAIL_SERVER,
            "--to", ALERT_EMAIL,
            "--subject", subject,
            "--body", body
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    except Exception as e:
        print(f"邮件发送失败: {e}")

def load_cache():
    """加载信号缓存"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache):
    """保存信号缓存"""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def is_duplicate_signal(cache, symbol, direction, price):
    """判断是否为重复信号"""
    key = f"{symbol}_{direction}"
    if key not in cache:
        return False
    
    cached = cache[key]
    # 价格波动在1%以内，且未过期（8小时内）
    if abs(price - cached["price"]) / cached["price"] <= CACHE_PRICE_TOLERANCE:
        cached_time = datetime.fromisoformat(cached["time"])
        if datetime.now(timezone.utc) - cached_time <= timedelta(hours=CACHE_TTL_HOURS):
            return True
    return False

def update_cache(cache, symbol, direction, price):
    """更新信号缓存"""
    cache[f"{symbol}_{direction}"] = {
        "price": price,
        "time": datetime.now(timezone.utc).isoformat()
    }
    save_cache(cache)

def fetch_okx_candles(symbol, bar="5m", limit=50):
    """从OKX获取K线数据"""
    url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}&bar={bar}&limit={limit}"
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(req) as response:
        data = json.loads(response.read())
        if data["code"] != "0":
            return []
        # 数据格式：[时间, 开, 高, 低, 收, 成交量]
        candles = []
        for item in data["data"]:
            candles.append({
                "time": int(item[0]),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5])
            })
        # 按时间升序排列
        candles.reverse()
        return candles

def calculate_rsi(closes, period=14):
    """计算RSI指标"""
    if len(closes) < period + 1:
        return 0
    
    gains = []
    losses = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(-change)
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    if avg_gain == 0:
        return 0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def scan_short_signal(symbol, okx_symbol):
    """扫描做空信号"""
    candles = fetch_okx_candles(okx_symbol)
    if not candles:
        return False, 0
    
    closes = [c["close"] for c in candles]
    current_price = closes[-1]
    rsi = calculate_rsi(closes)
    
    # 做空信号条件：RSI > 70（超买）
    signal_strength = 0
    if rsi > 70:
        signal_strength += 2
    if current_price > sum(closes[-20:])/20 * 1.02:
        signal_strength += 2
    
    return signal_strength >= 4, current_price

def main():
    print("=== BTC/ETH/SOL 做空信号扫描器 v4.4 ===")
    print("开始扫描...")
    
    cache = load_cache()
    # 币种配置：(显示名称, OKX交易对)
    symbols = [
        ("BTC", "BTC-USDT-SWAP"),
        ("ETH", "ETH-USDT-SWAP"),
        ("SOL", "SOL-USDT-SWAP")
    ]
    
    while True:
        for symbol, okx_symbol in symbols:
            try:
                hit, price = scan_short_signal(symbol, okx_symbol)
                if hit:
                    if not is_duplicate_signal(cache, symbol, "SHORT", price):

                        # ========== 自动计算 止盈 止损 ==========
                        take_profit = price * 0.98   # 止盈 2%
                        stop_loss = price * 1.01    # 止损 1%
                        # ===================================

                        message = f"""🔔 做空信号触发 {symbol}
📌 入场价格：{price:.2f}
🎯 止盈：{take_profit:.2f}
🚨 止损：{stop_loss:.2f}
✅ 策略：RSI超买回调"""

                        send_telegram_message(message)
                        send_email(f"做空信号：{symbol}", message)
                        update_cache(cache, symbol, "SHORT", price)
                        print(f"[{datetime.now()}] 触发做空信号：{symbol}，价格：{price:.2f}")
            except Exception as e:
                print(f"扫描 {symbol} 失败: {e}")
        
        # 每60秒扫描一次，避免请求过于频繁
        from time import sleep
        sleep(60)

if __name__ == "__main__":
    main()
