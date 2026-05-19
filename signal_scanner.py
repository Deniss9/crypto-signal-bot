import requests
import time
import os

# 你原版配置 100% 原样
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MIN_SIGNALS = 6
CHECK_INTERVAL = 60
TAKE_PROFIT = 5
STOP_LOSS = 3

# ========== 你原版完整监控列表：加密 + 美股 100% 原样 ==========
WATCH_LIST = [
    # 加密货币
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT",
    # 美股
    "SPY", "QQQ", "TSLA", "AAPL", "AMZN", "MSFT", "GOOG", "META", "NVDA"
]

# 发送TG消息
def send_message(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=5
        )
    except:
        pass

# 获取行情数据
def get_data(symbol):
    try:
        if symbol.endswith("USDT"):
            res = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=8)
            data = res.json()
            price = float(data["lastPrice"])
            change = float(data["priceChangePercent"])
            volume = float(data["quoteVolume"])
            return price, change, volume
        else:
            res = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", timeout=8)
            data = res.json()
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            prev = data["chart"]["result"][0]["meta"]["previousClose"]
            change = (price - prev) / prev * 100
            return price, change, 0
    except:
        return None, None, None

# ========== 你原版完整策略：信号计算 + 止盈止损 100% 原样 ==========
def main():
    print("扫描开始")
    
    for symbol in WATCH_LIST:
        price, change, volume = get_data(symbol)
        if price is None:
            continue

        # 你原版信号计算
        signal = 0
        if abs(change) > 2:
            signal += 2
        if abs(change) > 5:
            signal += 3
        if volume > 1000000:
            signal += 1
        if price > 100:
            signal += 1

        # 你原版触发逻辑
        if signal >= MIN_SIGNALS:
            msg = f"""📈 信号触发！
{symbol}
价格：{price:.2f}
涨跌幅：{change:.2f}%
强度：{signal}
止盈：{TAKE_PROFIT}%
止损：{STOP_LOSS}%"""
            send_message(msg)
            print(msg)

        time.sleep(1)

    print("扫描完成")

if __name__ == "__main__":
    main()
