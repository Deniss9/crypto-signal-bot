#!/usr/bin/env python3
"""
BTC/ETH/SOL 多空信号自动扫描器 GitHub免费挂机版
"""

import os
import json
import math
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request

ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "")
ALERT_EMAILS = [x.strip() for x in ALERT_EMAIL.split(";") if x.strip()]
MIN_SIGNALS = int(os.environ.get("MIN_SIGNALS", "6"))

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(_SCRIPT_DIR, "signal_cache.json")
CACHE_PRICE_TOLERANCE = 0.01
CACHE_TTL_HOURS = 8

OKX_CANDLE = "https://www.okx.com/api/v5/market/candles"
OKX_FUNDING = "https://www.okx.com/api/v5/public/funding-rate"

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
        print(f"缓存写入失败: {e}")

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
    return abs(price - cached_price) / cached_price <= CACHE_PRICE_TOLERANCE

def update_cache(cache: dict, sym: str, direction: str, price: float, sent_at: str):
    key = f"{sym}:{direction}"
    sent_dt = datetime.strptime(sent_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    expires_dt = sent_dt + timedelta(hours=CACHE_TTL_HOURS)
    cache[key] = {
        "price": price,
        "sent_at": sent_at,
        "expires_at": expires_dt.strftime("%Y-%m-%d %H:%M:%S"),
    }

def fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "SignalScanner/5.0"})
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
    result.append(100 if al == 0 else 100 - 100 / (1 + ag / (al + 1e-10)))
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + max(d, 0)) / period
        al = (al * (period - 1) + max(-d, 0)) / period
        result.append(100 if al == 0 else 100 - 100 / (1 + ag / (al + 1e-10)))
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

def atr_calc(candles: list, period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        prev_c = candles[i-1]["c"]
        h = candles[i]["h"]
        l = candles[i]["l"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    return sum(trs[-period:]) / period

def candle_patterns(c5m, c15m, price):
    l5, p5 = c5m[-1], c5m[-2]
    body5 = abs(l5["c"] - l5["o"])
    upper5 = l5["h"] - max(l5["c"], l5["o"])
    lower5 = min(l5["c"], l5["o"]) - l5["l"]
    long_upper5 = upper5 > body5 * 1.5 and upper5 > price * 0.002
    bearish_engulf5 = l5["c"] < l5["o"] and l5["o"] > p5["c"] and l5["c"] < p5["o"]
    long_lower5 = lower5 > body5 * 1.5 and lower5 > price * 0.002
    bullish_engulf5 = l5["c"] > l5["o"] and l5["o"] < p5["c"] and l5["c"] > p5["o"]

    l15, p15 = c15m[-1], c15m[-2]
    body15 = abs(l15["c"] - l15["o"])
    upper15 = l15["h"] - max(l15["c"], l15["o"])
    lower15 = min(l15["c"], l15["o"]) - l15["l"]
    long_upper15 = upper15 > body15 * 1.5 and upper15 > price * 0.002
    bearish_engulf15 = l15["c"] < l15["o"] and l15["o"] > p15["c"] and l15["c"] < p15["o"]
    long_lower15 = lower15 > body15 * 1.5 and lower15 > price * 0.002
    bullish_engulf15 = l15["c"] > l15["o"] and l15["o"] < p15["c"] and l15["c"] > p15["o"]
    return locals()

def strength_of(n: int) -> str:
    if n >= 8:
        return "强"
    if n >= MIN_SIGNALS:
        return "中"
    if n >= 3:
        return "弱"
    return "无交易"

def analyze_symbol(sym: str, swap_sym: str) -> dict:
    c5m  = fetch_candles(sym, "5m",  30)
    c15m = fetch_candles(sym, "15m", 50)
    c1h  = fetch_candles(sym, "1H",  100)
    c4h  = fetch_candles(sym, "4H",  120)
    try:
        funding = fetch_funding_rate(swap_sym)
    except Exception:
        funding = 0.0

    price    = c1h[-1]["c"]
    closes1h = [c["c"] for c in c1h]
    highs1h  = [c["h"] for c in c1h]
    lows1h   = [c["l"] for c in c1h]
    vols1h   = [c["v"] for c in c1h]
    rsi1h    = rsi_calc(closes1h)[-1]
    rsi15m   = rsi_calc([c["c"] for c in c15m])[-1]
    macd1h   = macd_calc(closes1h)
    cur_hist1h, prev_hist1h = macd1h["hist"][-1], macd1h["hist"][-2]
    bb1h     = bollinger_bands(closes1h)
    avg_vol  = sum(vols1h[-20:]) / 20
    last_vol = vols1h[-1]
    resistance = max(highs1h[-20:])
    support    = min(lows1h[-20:])

    closes4h = [c["c"] for c in c4h]
    highs4h  = [c["h"] for c in c4h]
    lows4h   = [c["l"] for c in c4h]
    e20_4h   = ema(closes4h, 20)
    e50_4h   = ema(closes4h, 50)
    e200_4h  = ema(closes4h, 200)
    macd4h   = macd_calc(closes4h)
    atr4h    = atr_calc(c4h, 14)

    bearish_ema4h  = closes4h[-1] < e20_4h[-1] < e50_4h[-1] < e200_4h[-1]
    bullish_ema4h  = closes4h[-1] > e20_4h[-1] > e50_4h[-1] > e200_4h[-1]
    macd_dead4h    = macd4h["macd"][-1] < macd4h["signal"][-1]
    macd_golden4h  = macd4h["macd"][-1] > macd4h["signal"][-1]
    macd_hist_up   = macd4h["hist"][-1] > macd4h["hist"][-2]
    macd_hist_down = macd4h["hist"][-1] < macd4h["hist"][-2]

    peaks  = [highs4h[i] for i in range(1, len(highs4h)-1) if highs4h[i] > highs4h[i-1] and highs4h[i] > highs4h[i+1]]
    troughs = [lows4h[i] for i in range(1, len(lows4h)-1) if lows4h[i] < lows4h[i-1] and lows4h[i] < lows4h[i+1]]
    lower_highs4h  = len(peaks)  >= 2 and peaks[-1]  < peaks[-2]
    higher_lows4h  = len(troughs) >= 2 and troughs[-1] > troughs[-2]

    pat = candle_patterns(c5m, c15m, price)

    short_signals = []
    if price > resistance * 0.997 or price > bb1h["upper"] * 0.997:
        short_signals.append(f"价格触及压力区（近高 ${resistance:.0f} / 布林上轨 ${bb1h['upper']:.0f}）")
    if pat["long_upper5"]:      short_signals.append("5m K线出现长上影线（假突破信号）")
    if pat["bearish_engulf5"]:  short_signals.append("5m K线出现吞没阴线（反转信号）")
    if pat["long_upper15"]:     short_signals.append("15m K线出现长上影线（假突破信号）")
    if pat["bearish_engulf15"]: short_signals.append("15m K线出现吞没阴线（反转信号）")
    if rsi1h  is not None and rsi1h  > 65: short_signals.append(f"1H RSI 进入过热区（{rsi1h:.1f} >65）")
    if rsi15m is not None and rsi15m > 68: short_signals.append(f"15m RSI 接近过热（{rsi15m:.1f} >68）")
    if cur_hist1h > 0 and cur_hist1h < prev_hist1h: short_signals.append("1H MACD 红柱缩短（动能衰减）")
    if cur_hist1h < 0 and prev_hist1h > 0:           short_signals.append("1H MACD 发生死叉")
    if last_vol < avg_vol * 0.5: short_signals.append(f"反弹缩量（当前成交量仅 {last_vol/avg_vol*100:.0f}% 均量）")
    if bearish_ema4h:    short_signals.append("4H EMA 空头排列（价格在 EMA20/50/200 全线下方）")
    if macd_dead4h:      short_signals.append("4H MACD 死叉（中期趋势偏空）")
    if lower_highs4h:    short_signals.append("4H 低高点结构确认（下降趋势形态）")
    if funding > 0.03:   short_signals.append(f"资金费率偏高（{funding:.4f}%，多头拥挤）")

    short_sl_atr = price + max(atr4h * 1.5, price * 0.008)
    short_sl     = min(short_sl_atr, resistance * 1.005)
    short_risk   = short_sl - price
    short_tp1    = price - short_risk * 1.5
    short_tp2    = price - short_risk * 2.5
    short_tp3    = price - short_risk * 4.0
    short_rr     = round((price - short_tp1) / short_risk, 1) if short_risk > 0 else 0

    short = {
        "direction": "SHORT", "label": "做空",
        "signals": short_signals, "signal_count": len(short_signals),
        "strength": strength_of(len(short_signals)),
        "should_alert": len(short_signals) >= MIN_SIGNALS and short_rr >= 1.5,
        "entry_low":  f"{price * 0.999:.2f}",
        "entry_high": f"{price * 1.001:.2f}",
        "stop_loss":  f"{short_sl:.2f}",
        "tp1": f"{short_tp1:.2f}", "tp2": f"{short_tp2:.2f}", "tp3": f"{short_tp3:.2f}",
        "rr":  str(short_rr),
    }

    long_signals = []
    if price < support * 1.003 or price < bb1h["lower"] * 1.003:
        long_signals.append(f"价格触及支撑区（近低 ${support:.0f} / 布林下轨 ${bb1h['lower']:.0f}）")
    if pat["long_lower5"]:      long_signals.append("5m K线出现长下影线（支撑吸筹信号）")
    if pat["bullish_engulf5"]:  long_signals.append("5m K线出现吞没阳线（反转信号）")
    if pat["long_lower15"]:     long_signals.append("15m K线出现长下影线（支撑吸筹信号）")
    if pat["bullish_engulf15"]: long_signals.append("15m K线出现吞没阳线（反转信号）")
    if rsi1h  is not None and rsi1h  < 35: long_signals.append(f"1H RSI 进入超卖区（{rsi1h:.1f} <35）")
    if rsi15m is not None and rsi15m < 32: long_signals.append(f"15m RSI 深度超卖（{rsi15m:.1f} <32）")
    if cur_hist1h < 0 and cur_hist1h > prev_hist1h: long_signals.append("1H MACD 绿柱缩短（下跌动能衰减）")
    if cur_hist1h > 0 and prev_hist1h < 0:           long_signals.append("1H MACD 发生金叉")
    if last_vol > avg_vol * 1.5: long_signals.append(f"放量回调（成交量 {last_vol/avg_vol*100:.0f}% 均量，资金介入）")
    if bullish_ema4h:    long_signals.append("4H EMA 多头排列（价格在 EMA20/50/200 全线上方）")
    if macd_golden4h:    long_signals.append("4H MACD 金叉（中期趋势偏多）")
    if macd_hist_up and macd4h["hist"][-1] < 0: long_signals.append("4H MACD 绿柱收窄（空头动能衰减）")
    if higher_lows4h:    long_signals.append("4H 高低点结构确认（上升趋势形态）")
    if funding < -0.02:  long_signals.append(f"资金费率为负（{funding:.4f}%，空头拥挤、多头反弹机会）")

    long_sl_atr = price - max(atr4h * 1.5, price * 0.008)
    long_sl     = max(long_sl_atr, support * 0.995)
    long_risk   = price - long_sl
    long_tp1    = price + long_risk * 1.5
    long_tp2    = price + long_risk * 2.5
    long_tp3    = price + long_risk * 4.0
    long_rr     = round((long_tp1 - price) / long_risk, 1) if long_risk > 0 else 0

    longg = {
        "direction": "LONG", "label": "做多",
        "signals": long_signals, "signal_count": len(long_signals),
        "strength": strength_of(len(long_signals)),
        "should_alert": len(long_signals) >= MIN_SIGNALS and long_rr >= 1.5,
        "entry_low":  f"{price * 0.999:.2f}",
        "entry_high": f"{price * 1.001:.2f}",
        "stop_loss":  f"{long_sl:.2f}",
        "tp1": f"{long_tp1:.2f}", "tp2": f"{long_tp2:.2f}", "tp3": f"{long_tp3:.2f}",
        "rr":  str(long_rr),
    }

    return {
        "sym": sym, "price": price, "funding": f"{funding:.4f}",
        "rsi1h":  f"{rsi1h:.1f}"  if rsi1h  else "N/A",
        "rsi15m": f"{rsi15m:.1f}" if rsi15m else "N/A",
        "short": short, "long": longg,
        "directions": [longg, short],
    }

def format_text_report(alerts: list, now: str) -> str:
    lines = ["🚨 BTC/ETH/SOL 交易信号预警", f"时间：{now} UTC",
             f"触发标的：{len(alerts)} 个", ""]
    for item in alerts:
        r, a = item["result"], item["side"]
        name = r["sym"].replace("-USDT", "")
        icon = "📈" if a["direction"] == "LONG" else "📉"
        lines += [
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            f"{icon} 【{name} {a['label']}】信号强度：{a['strength']}（{a['signal_count']} 个条件触发）",
            f"当前价格：${r['price']:.2f}", "",
            "触发条件："
        ]
        for i, s in enumerate(a["signals"], 1):
            lines.append(f"  {i}. {s}")
        lines += [
            "",
            f"建议入场区间：${a['entry_low']} – ${a['entry_high']}",
            f"止  损  位：${a['stop_loss']}",
            f"第一止盈：${a['tp1']}（盈亏比 {a['rr']}:1）",
            f"第二止盈：${a['tp2']}",
            f"第三止盈：${a['tp3']}",
            ""
        ]
    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "⚠️ 风控提醒：",
        "  · 等待 5m/15m K线收线确认后入场",
        "  · 触及止损线务必执行，不可移动",
        "  · 到达第一止盈可移动止损至成本价",
        "  · 单笔风险控制在账户权益 0.3%–1%",
        "  · 本预警由自动化脚本扫描，仅供参考，不构成投资建议"
    ]
    return "\n".join(lines)

def send_email(subject: str, body_text: str):
    if not SMTP_USER or not SMTP_PASSWORD:
        print("📧 邮件未配置，跳过发送")
        return
    
    msg = MIMEText(body_text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_EMAIL

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, ALERT_EMAILS, msg.as_string())
        print(f"📧 邮件发送成功：{ALERT_EMAIL}")
    except Exception as e:
        print(f"📧 邮件发送失败：{e}")

def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now}] 🔍 扫描中（信号阈值：{MIN_SIGNALS}）...")

    cache = load_cache()
    targets = [("BTC-USDT", "BTC-USDT-SWAP"), ("ETH-USDT", "ETH-USDT-SWAP"), ("SOL-USDT", "SOL-USDT-SWAP")]
    results = []
    
    for sym, swap in targets:
        try:
            results.append(analyze_symbol(sym, swap))
        except Exception as e:
            print(f"[ERROR] {sym}: {e}")

    for r in results:
        for side in r["directions"]:
            icon = "🔴" if side["should_alert"] else ("🟡" if side["signal_count"] >= 3 else "🟢")
            print(f"  {icon} {r['sym']:<12} {side['direction']:<5} ${r['price']:>10.2f}  {side['strength']}（{side['signal_count']}/{MIN_SIGNALS}）")

    raw_alerts = [{"result": r, "side": s} for r in results for s in r["directions"] if s["should_alert"]]
    dedup_alerts = [item for item in raw_alerts if not is_duplicate(cache, item["result"]["sym"], item["side"]["direction"], item["result"]["price"])]

    if not dedup_alerts:
        print("\n✅ 暂无新信号\n")
        return

    print(f"\n⚡ 触发 {len(dedup_alerts)} 个新信号")
    report = format_text_report(dedup_alerts, now)
    send_email(f"🚨 交易信号预警", report)

    for item in dedup_alerts:
        update_cache(cache, item["result"]["sym"], item["side"]["direction"], item["result"]["price"], now)
    save_cache(cache)
    print("\n✅ 扫描完成\n")

if __name__ == "__main__":
    main()
