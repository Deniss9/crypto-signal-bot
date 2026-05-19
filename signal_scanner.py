#!/usr/bin/env python3
"""
BTC / ETH / SOL 逢高做空信号扫描器 v3.0 (Python)
用法:
    python3 short_signal_scanner.py
    MIN_SIGNALS=6 ALERT_EMAIL=you@example.com python3 short_signal_scanner.py
依赖: 仅 Python 标准库（urllib, json, subprocess, os, math, datetime）
"""

import os
import json
import math
import subprocess
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

# ─── 配置 ────────────────────────────────────────────────
ALERT_EMAIL  = os.environ.get("ALERT_EMAIL", "fly15201344146@gmail.com")
MIN_SIGNALS  = int(os.environ.get("MIN_SIGNALS", "6"))
SQUARE_KEY   = os.environ.get("BINANCE_SQUARE_OPENAPI_KEY", "")
GMAIL_SERVER = "/home/user/servers/gmail/run.mjs"

OKX_CANDLE   = "https://www.okx.com/api/v5/market/candles"
OKX_FUNDING  = "https://www.okx.com/api/v5/public/funding-rate"
SQUARE_API   = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"

# ─── 工具函数 ─────────────────────────────────────────────

def fetch_json(url: str, headers: dict = None) -> dict:
    req = Request(url, headers={
        "User-Agent": "ShortScanner/3.0",
        **(headers or {})
    })
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_candles(inst_id: str, bar: str, limit: int = 60) -> list:
    url = f"{OKX_CANDLE}?instId={inst_id}&bar={bar}&limit={limit}"
    data = fetch_json(url).get("data", [])
    candles = [
        {"ts": int(r[0]), "o": float(r[1]), "h": float(r[2]),
         "l": float(r[3]), "c": float(r[4]), "v": float(r[5])}
        for r in data
    ]
    candles.reverse()
    return candles


def fetch_funding_rate(inst_id: str) -> float:
    url = f"{OKX_FUNDING}?instId={inst_id}"
    data = fetch_json(url).get("data", [{}])
    return float(data[0].get("fundingRate", 0)) * 100


def ema(values: list, period: int) -> list:
    k = 2 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def rsi_calc(closes: list, period: int = 14) -> list:
    if len(closes) < period + 1:
        return [None] * len(closes)
    result = [None] * period
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        if d > 0: gains += d
        else:     losses -= d
    ag, al = gains / period, losses / period
    result.append(100 if al == 0 else 100 - 100 / (1 + ag / al))
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + (d if d > 0 else 0)) / period
        al = (al * (period - 1) + (-d if d < 0 else 0)) / period
        result.append(100 if al == 0 else 100 - 100 / (1 + ag / al))
    return result


def macd_calc(closes: list, fast=12, slow=26, signal=9):
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(closes))]
    sig_input = macd_line[slow - 1:]
    sig_line  = ema(sig_input, signal)
    hist      = [sig_input[i] - sig_line[i] for i in range(len(sig_input))]
    return {"hist": hist, "macd": sig_input, "signal": sig_line}


def bollinger_bands(closes: list, period=20, mult=2):
    sl = closes[-period:]
    mid = sum(sl) / period
    std = math.sqrt(sum((x - mid) ** 2 for x in sl) / period)
    return {"upper": mid + mult * std, "mid": mid, "lower": mid - mult * std}


# ─── 核心分析 ─────────────────────────────────────────────

def analyze_symbol(sym: str, swap_sym: str) -> dict:
    c5m  = fetch_candles(sym, "5m",  30)
    c15m = fetch_candles(sym, "15m", 50)
    c1h  = fetch_candles(sym, "1H",  100)
    c4h  = fetch_candles(sym, "4H",  100)
    try:
        funding = fetch_funding_rate(swap_sym)
    except Exception:
        funding = 0.0

    price = c1h[-1]["c"]

    # 1H
    closes1h = [c["c"] for c in c1h]
    highs1h  = [c["h"] for c in c1h]
    vols1h   = [c["v"] for c in c1h]
    rsi1h    = rsi_calc(closes1h)
    macd1h   = macd_calc(closes1h)
    bb1h     = bollinger_bands(closes1h)
    cur_rsi1h = rsi1h[-1]
    avg_vol1h = sum(vols1h[-20:]) / 20
    last_vol1h = vols1h[-1]
    resistance1h = max(highs1h[-20:])
    hist1h = macd1h["hist"]
    cur_hist1h  = hist1h[-1]
    prev_hist1h = hist1h[-2]

    # 15m
    closes15m = [c["c"] for c in c15m]
    rsi15m = rsi_calc(closes15m)
    cur_rsi15m = rsi15m[-1]

    # 5m 形态
    l5 = c5m[-1]; p5 = c5m[-2]
    body5 = abs(l5["c"] - l5["o"])
    uw5   = l5["h"] - max(l5["c"], l5["o"])
    long_wick5   = uw5 > body5 * 1.5 and uw5 > price * 0.002
    engulf5 = l5["c"] < l5["o"] and l5["o"] > p5["c"] and l5["c"] < p5["o"]

    # 15m 形态
    l15 = c15m[-1]; p15 = c15m[-2]
    body15 = abs(l15["c"] - l15["o"])
    uw15   = l15["h"] - max(l15["c"], l15["o"])
    long_wick15   = uw15 > body15 * 1.5 and uw15 > price * 0.002
    engulf15 = l15["c"] < l15["o"] and l15["o"] > p15["c"] and l15["c"] < p15["o"]

    # 4H
    closes4h = [c["c"] for c in c4h]
    highs4h  = [c["h"] for c in c4h]
    e20_4h  = ema(closes4h, 20)
    e50_4h  = ema(closes4h, 50)
    e200_4h = ema(closes4h, 200)
    macd4h  = macd_calc(closes4h)
    bearish_ema4h = (closes4h[-1] < e20_4h[-1] < e50_4h[-1] < e200_4h[-1])
    macd_dead4h   = macd4h["macd"][-1] < macd4h["signal"][-1]
    peaks = [highs4h[i] for i in range(1, len(highs4h) - 1)
             if highs4h[i] > highs4h[i-1] and highs4h[i] > highs4h[i+1]]
    lower_highs4h = len(peaks) >= 2 and peaks[-1] < peaks[-2]

    # ── 信号条件检测 ──
    signals = []
    if price > resistance1h * 0.997 or price > bb1h["upper"] * 0.997:
        signals.append(f"价格触及压力区（近高 ${resistance1h:.0f} / 布林上轨 ${bb1h['upper']:.0f}）")
    if long_wick5:  signals.append("5m K线出现长上影线（假突破信号）")
    if engulf5:     signals.append("5m K线出现吞没阴线（反转信号）")
    if long_wick15: signals.append("15m K线出现长上影线（假突破信号）")
    if engulf15:    signals.append("15m K线出现吞没阴线（反转信号）")
    if cur_rsi1h  is not None and cur_rsi1h  > 65:
        signals.append(f"1H RSI 进入过热区（{cur_rsi1h:.1f}，>65）")
    if cur_rsi15m is not None and cur_rsi15m > 68:
        signals.append(f"15m RSI 接近过热（{cur_rsi15m:.1f}，>68）")
    if cur_hist1h is not None and prev_hist1h is not None:
        if cur_hist1h > 0 and cur_hist1h < prev_hist1h:
            signals.append("1H MACD 红柱缩短（上涨动能衰减）")
        if cur_hist1h < 0 and prev_hist1h > 0:
            signals.append("1H MACD 发生死叉")
    if last_vol1h < avg_vol1h * 0.5:
        signals.append(f"反弹缩量（当前成交量仅 {last_vol1h/avg_vol1h*100:.0f}% 均量）")
    if bearish_ema4h: signals.append("4H EMA 空头排列（价格在 EMA20/50/200 全线下方）")
    if macd_dead4h:   signals.append("4H MACD 死叉（中期趋势偏空）")
    if lower_highs4h: signals.append("4H 低高点结构确认（下降趋势形态）")
    if funding > 0.03:
        signals.append(f"资金费率偏高（{funding:.4f}%，多头持仓成本上升）")

    # ── 入场参数 ──
    stop_loss = resistance1h * 1.005
    risk_dist = stop_loss - price
    tp1 = price - risk_dist * 1.8
    tp2 = price - risk_dist * 3.0
    rr  = round((price - tp1) / risk_dist, 1) if risk_dist > 0 else 0

    n = len(signals)
    strength    = "无交易"
    should_alert = False
    if n >= MIN_SIGNALS:
        strength     = "强" if n >= 8 else "中"
        should_alert = True
    elif n >= 3:
        strength = "弱"

    if rr < 1.5:
        should_alert = False

    return {
        "sym": sym, "price": price, "signals": signals,
        "signal_count": n, "strength": strength, "should_alert": should_alert,
        "resistance": f"{resistance1h:.0f}", "bb_upper": f"{bb1h['upper']:.0f}",
        "rsi1h": f"{cur_rsi1h:.1f}" if cur_rsi1h else "N/A",
        "rsi15m": f"{cur_rsi15m:.1f}" if cur_rsi15m else "N/A",
        "funding": f"{funding:.4f}",
        "bearish_ema4h": bearish_ema4h,
        "stop_loss": f"{stop_loss:.2f}", "tp1": f"{tp1:.2f}",
        "tp2": f"{tp2:.2f}", "rr": str(rr),
    }


# ─── 格式化文本报告 ────────────────────────────────────────

def format_text_report(alerts: list, now: str) -> str:
    lines = [
        "🚨 做空信号预警",
        f"时间：{now} UTC",
        f"触发标的：{'、'.join(a['sym'].replace('-USDT','') for a in alerts)}",
        "",
    ]
    for a in alerts:
        name = a["sym"].replace("-USDT", "")
        lines += [
            "━━━━━━━━━━━━━━━━━━━━",
            f"【{name}】信号强度：{a['strength']}（{a['signal_count']} 个条件触发）",
            f"当前价格：${a['price']:.2f}",
            "",
            "触发条件：",
        ]
        for i, s in enumerate(a["signals"], 1):
            lines.append(f"  {i}. {s}")
        lines += [
            "",
            f"建议入场：${a['price']*0.999:.2f} – ${a['price']*1.001:.2f}",
            f"止损位置：${a['stop_loss']}（压力位上方 0.5%）",
            f"第一止盈：${a['tp1']}",
            f"第二止盈：${a['tp2']}",
            f"盈亏比：{a['rr']}:1",
            "",
        ]
    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        "⚠️ 风控提醒：",
        "  · 必须等 5m 或 15m 收线确认后再入场",
        "  · 禁止第一次触碰压力位时直接追空",
        "  · 单笔风险控制在账户权益 0.3%–1%",
        "  · 本预警由 CREAO 自动扫描，仅供参考，不构成投资建议",
    ]
    return "\n".join(lines)


def format_square_post(alerts: list, now: str) -> str:
    lines = [
        f"【做空信号播报 {now[:10]}】",
        "",
        "多周期技术扫描发现以下标的出现做空信号，供参考：",
        "",
    ]
    for a in alerts:
        name = a["sym"].replace("-USDT", "")
        lines.append(f"▌ {name}  当前价 ${a['price']:.2f}  信号强度：{a['strength']}")
        lines.append(f"  已触发 {a['signal_count']} 个做空条件：")
        for s in a["signals"][:4]:
            lines.append(f"  · {s}")
        lines.append(f"  建议止损 ${a['stop_loss']}，目标 ${a['tp1']}，盈亏比 {a['rr']}:1")
        lines.append("")
    lines += [
        "策略说明：",
        "本信号基于 5m / 15m / 1H / 4H 四周期联合扫描，",
        "需满足 6 个以上技术条件（EMA排列、RSI过热、MACD死叉、K线反转形态、成交量、资金费率）才触发。",
        "",
        "入场原则：等待 5m 或 15m 收线确认，禁止在压力位第一次触碰时直接追空。",
        "",
        "以上内容仅为技术分析，不构成投资建议，请结合自身风险偏好操作。",
        "",
        "#加密货币 #BTC #ETH #SOL #合约交易 #技术分析",
    ]
    return "\n".join(lines)


# ─── 发送邮件 ─────────────────────────────────────────────

def send_email(subject: str, body_text: str):
    html = (
        '<pre style="font-family:monospace;font-size:14px;line-height:1.6;">'
        + body_text.replace("<", "&lt;").replace(">", "&gt;")
        + "</pre>"
    )
    args = json.dumps({
        "to": [ALERT_EMAIL],
        "subject": subject,
        "body": html,
        "bodyType": "html",
    })
    subprocess.run(
        ["node", GMAIL_SERVER, "sendEmail", args],
        check=True, capture_output=True, timeout=30
    )


# ─── 发布币安广场 ─────────────────────────────────────────

def post_to_square(content: str) -> dict:
    if not SQUARE_KEY:
        print("  ⚠️  BINANCE_SQUARE_OPENAPI_KEY 未配置，跳过币安广场发布")
        return {"success": False, "error": "no key"}

    import http.client, urllib.parse
    body = json.dumps({"bodyTextOnly": content}).encode()
    conn = http.client.HTTPSConnection("www.binance.com", timeout=15)
    conn.request("POST",
        "/bapi/composite/v1/public/pgc/openApi/content/add",
        body=body,
        headers={
            "X-Square-OpenAPI-Key": SQUARE_KEY,
            "Content-Type": "application/json",
            "clienttype": "binanceSkill",
            "Content-Length": str(len(body)),
        }
    )
    resp = conn.getresponse()
    data = json.loads(resp.read())
    if data.get("code") == "000000" and data.get("data", {}).get("id"):
        post_id = data["data"]["id"]
        return {"success": True, "url": f"https://www.binance.com/square/post/{post_id}", "id": post_id}
    return {"success": False, "code": data.get("code"), "message": data.get("message")}


# ─── 主流程 ───────────────────────────────────────────────

def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now}] 🔍 扫描中（阈值：{MIN_SIGNALS} 个条件）...")

    targets = [
        ("BTC-USDT", "BTC-USDT-SWAP"),
        ("ETH-USDT", "ETH-USDT-SWAP"),
        ("SOL-USDT", "SOL-USDT-SWAP"),
    ]

    results = []
    for sym, swap in targets:
        try:
            r = analyze_symbol(sym, swap)
            results.append(r)
        except Exception as e:
            print(f"  [ERROR] {sym}: {e}")

    # 打印扫描摘要
    for r in results:
        icon = "🔴" if r["should_alert"] else ("🟡" if r["signal_count"] >= 3 else "🟢")
        print(f"  {icon} {r['sym']:<12} ${r['price']:>10.2f}  {r['strength']}（{r['signal_count']}/{MIN_SIGNALS}）")
        if r["signal_count"] > 0:
            preview = " | ".join(r["signals"][:3])
            print(f"     └─ {preview}")

    alert_targets = [r for r in results if r["should_alert"]]

    if not alert_targets:
        print(f"\n✅ 暂无有效做空信号（需满足 {MIN_SIGNALS} 个条件）。\n")
        return

    print(f"\n⚡ {len(alert_targets)} 个标的触发做空信号，发送预警...")
    syms  = "/".join(a["sym"].replace("-USDT", "") for a in alert_targets)
    subject = f"🚨 做空信号预警 [{syms}] {now}"
    report  = format_text_report(alert_targets, now)
    post    = format_square_post(alert_targets, now)

    # 发送邮件
    try:
        send_email(subject, report)
        print(f"  📧 邮件：✅ 已发送至 {ALERT_EMAIL}")
    except Exception as e:
        print(f"  📧 邮件：❌ 失败 {e}")

    # 发布广场
    try:
        sq = post_to_square(post)
        if sq.get("success"):
            print(f"  🟡 币安广场：✅ 已发布 → {sq['url']}")
        else:
            print(f"  🟡 币安广场：❌ 失败 code={sq.get('code')} {sq.get('message','')}")
    except Exception as e:
        print(f"  🟡 币安广场：❌ 异常 {e}")

    print(f"\n[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] 扫描完成。\n")


if __name__ == "__main__":
    main()
