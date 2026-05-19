import requests
import time
import os

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MIN_SIGNALS = 6
CHECK_INTERVAL = 60

WATCH_LIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "SPY", "QQQ", "TSLA", "AAPL"
]

def send_tg(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("未配置TG")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text},
            timeout=5
        )
    except:
        pass

def get_market_data(symbol):
    try:
        if symbol.endswith("USDT"):
            res = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=10)
            data = res.json()
            return float(data["lastPrice"]), float(data["priceChangePercent"]), float(data["quoteVolume"])
        else:
            res = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", timeout=10)
            meta = res.json()["chart"]["result"][0]["meta"]
            price = meta["regularMarketPrice"]
            prev = meta["previousClose"]
            change = (price - prev) / prev * 100
            return price, change, 1000000
    except:
        return None, None, None

def main():
    print("开始扫描")
    alerts = []
    for symbol in WATCH_LIST:
        p, c, v = get_market_data(symbol)
        if p is None:
            continue
        sig = abs(c)
        print(f"{symbol} 价格:{p:.2f} 变动:{c:.2f}% 信号:{sig:.1f}")
        if sig >= MIN_SIGNALS:
            alerts.append(f"⚠️ {symbol} 触发信号！变动{c:.2f}% 价格{p:.2f}")
        time.sleep(1)
    
    if alerts:
        send_tg("🔔 信号提醒：\n" + "\n".join(alerts))
    else:
        send_tg("✅ 本次扫描无信号")
    print("扫描完成")

if __name__ == "__main__":
    main()
