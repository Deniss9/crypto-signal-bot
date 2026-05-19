import requests
import time
import os
import yfinance as yf
from decimal import Decimal, ROUND_DOWN

# 基础配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MIN_SIGNAL = 6
SCAN_CYCLE = 60

# 稳健风控参数（全品种通用）
SL_RATE = 0.016    # 止损 1.6%
TP1_RATE = 0.032   # 第一止盈 3.2%
TP2_RATE = 0.048   # 第二止盈 4.8%

# 监控列表：加密+美股
WATCH_LIST = {
    "crypto": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","ADAUSDT",
               "DOGEUSDT","AVAXUSDT","DOTUSDT","MATICUSDT","LINKUSDT",
               "SHIBUSDT","UNIUSDT","ATOMUSDT","NEARUSDT","LTCUSDT"],
    "us": ["SPY","QQQ","TSLA","AAPL","AMZN","MSFT","GOOG",
           "META","NVDA","AMD","INTC","DIS","NFLX","COIN",
           "PLTR", "RIOT"]
}

# 电报推送
def send_tg_msg(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("电报密钥未配置")
        return
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(api, data={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        })
        print("✅ 信号已推送")
    except Exception as e:
        print(f"❌ 推送失败：{e}")

# --- 1. 获取加密货币实时价格（币安API）---
def get_crypto_price(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        price = Decimal(res.json()["price"])
        # 按币种精度四舍五入
        if symbol in ["BTCUSDT","ETHUSDT"]:
            return float(price.quantize(Decimal('0.01'), rounding=ROUND_DOWN))
        else:
            return float(price.quantize(Decimal('0.0001'), rounding=ROUND_DOWN))
    except Exception as e:
        print(f"获取{symbol}价格失败：{e}")
        return None

# --- 2. 获取美股实时价格（Yahoo Finance）---
def get_us_stock_price(symbol):
    try:
        ticker = yf.Ticker(symbol)
        price = ticker.history(period='1d')['Close'].iloc[-1]
        return round(price, 2)
    except Exception as e:
        print(f"获取{symbol}价格失败：{e}")
        return None

# --- 生成带实时价格的多空信号 ---
def get_trade_signal(symbol, direction, entry_price):
    if not entry_price:
        return
    if direction == "多头上涨":
        operate = "做多"
        stop_loss = entry_price * (1 - SL_RATE)
        take_profit1 = entry_price * (1 + TP1_RATE)
        take_profit2 = entry_price * (1 + TP2_RATE)
    else:
        operate = "做空"
        stop_loss = entry_price * (1 + SL_RATE)
        take_profit1 = entry_price * (1 - TP1_RATE)
        take_profit2 = entry_price * (1 - TP2_RATE)

    # 价格格式化，避免显示过多小数
    def fmt(p):
        if p >= 1000:
            return f"{p:.2f}"
        elif p >= 1:
            return f"{p:.4f}"
        else:
            return f"{p:.6f}"

    signal_text = f"""
🔔【全市场精品交易信号】
品种：{symbol}
操作方向：{operate}
当前趋势：{direction}
参考入场价：{fmt(entry_price)}
——————————————
🛑 硬性止损价：{fmt(stop_loss)}
✅ 第一止盈价（减半仓）：{fmt(take_profit1)}
🎯 终极止盈价（全离场）：{fmt(take_profit2)}
——————————————
交易执行守则
1. 仅执行6/6满格强信号，杂信号直接放弃
2. 现价附近轻仓进场，拒绝追涨杀跌
3. 止损必严格执行，绝不扛单逆势加仓
4. 抵达第一止盈锁定半仓利润
5. 剩余仓位移止损至成本价保本
6. 加密/美股统一风控，稳健长期盈利
"""
    send_tg_msg(signal_text)

# --- 全市场扫描 ---
def scan_all_market():
    # 扫描加密货币
    for symbol in WATCH_LIST["crypto"]:
        price = get_crypto_price(symbol)
        if price is None:
            continue
        # 这里用一个简单的示例：所有币种都视为多头上涨信号
        # 你可以在这里接入你原来的信号判定逻辑，替换下面两行
        signal_power = 6
        direction = "多头上涨"
        
        if signal_power >= MIN_SIGNAL:
            get_trade_signal(symbol, direction, price)
    
    # 扫描美股
    for symbol in WATCH_LIST["us"]:
        price = get_us_stock_price(symbol)
        if price is None:
            continue
        # 这里用一个简单的示例：所有股票都视为多头上涨信号
        # 你可以在这里接入你原来的信号判定逻辑，替换下面两行
        signal_power = 6
        direction = "多头上涨"
        
        if signal_power >= MIN_SIGNAL:
            get_trade_signal(symbol, direction, price)

if __name__ == "__main__":
    print("全市场实时监控启动成功！")
    while True:
        scan_all_market()
        time.sleep(SCAN_CYCLE)
