import requests
import time
import os

# 配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
INTERVAL = 60

# 策略参数
STOPLOSS = 0.016   # 止损 1.6%
TAKEPROFIT1 = 0.032
TAKEPROFIT2 = 0.048

# 只监控加密货币
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT"
]

# 电报发送
def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=data)
    except:
        pass

# 获取实时价格
def price(symbol):
    try:
        res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=3)
        return float(res.json()["price"])
    except:
        return None

# 生成信号
def signal(symbol, p):
    sl = p * (1 - STOPLOSS)
    tp1 = p * (1 + TAKEPROFIT1)
    tp2 = p * (1 + TAKEPROFIT2)

    msg = f"""
🔔 6/6 满格信号
品种：{symbol}
方向：做多
入场：{p:.2f}
止损：{sl:.2f}
止盈1：{tp1:.2f}
止盈2：{tp2:.2f}
"""
    send(msg)

# 主程序
def run():
    for s in SYMBOLS:
        p = price(s)
        if p:
            signal(s, p)
        time.sleep(0.5)

if __name__ == "__main__":
    while True:
        run()
        time.sleep(INTERVAL)
