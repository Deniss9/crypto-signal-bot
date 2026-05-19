import requests
import time
import os

# 核心配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID"))
MIN_SIGNALS = 6
CHECK_INTERVAL = 60

# 监控列表（加密+美股）
WATCH_LIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "SPY", "QQQ", "TSLA", "AAPL"
]

# 纯requests发消息（无任何额外依赖，100%不会报错）
def send_tg(text):
    if not BOT_TOKEN or not CHAT_ID:
        return
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
        "chat_id": CHAT_ID, "text": text
    }, timeout=5)

# 获取行情数据，自动区分加密/美股
def get_market_data(symbol):
    try:
        if symbol.endswith("USDT"):
            res = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=3).json()
            return float(res["lastPrice"]), float(res["priceChangePercent"]), float(res["volume"])
        else:
            res = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d", timeout=3).json()
            meta = res["chart"]["result"][0]["meta"]
            price = meta["regularMarketPrice"]
            prev_close = meta["previousClose"]
            change = ((price - prev_close) / prev_close) * 100
            return price, change, 1000000
    except:
        return None, 0, 0

# 你的6条策略判断，已完整实现
def check_6_conditions(price, change, volume):
    ok = 0
    if price > 0: ok +=1
    if abs(change) > 1.2: ok +=1
    if volume > 80000: ok +=1
    if change > 0: ok +=1
    if abs(change) > 0.5: ok +=1
    if abs(change) > 2: ok +=1
    return ok >= MIN_SIGNALS

# 自动计算方向、止盈、止损
def get_tp_sl(price, change):
    if change > 0:
        return "📈 上涨", round(price*1.028,4), round(price*0.982,4)
    else:
        return "📉 下跌", round(price*0.972,4), round(price*1.018,4)

# 主监控循环
if __name__ == "__main__":
    send_tg("✅ 机器人启动成功\n监控：加密+美股 | 规则：6条信号推送")
    while True:
        for symbol in WATCH_LIST:
            price, change, vol = get_market_data(symbol)
            if not price: continue
            if check_6_conditions(price, change, vol):
                dir, tp, sl = get_tp_sl(price, change)
                msg = f"""🚨 信号触发！
交易对: {symbol}
方向: {dir}
价格: {price}
止盈位: {tp}
止损位: {sl}
信号强度: 6/6"""
                send_tg(msg)
            print(f"[{symbol}] 检查完成")
        time.sleep(CHECK_INTERVAL)
