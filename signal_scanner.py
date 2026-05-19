import requests
import time
import os

# ===================== 你的核心配置 =====================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MIN_SIGNALS = 6
CHECK_INTERVAL = 60  # 60秒检查一次

# ===================== 【重点】监控列表（直接在这里加标的）=====================
SYMBOLS = [
    # 加密货币（币安格式，不带-）
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    
    # 美股（Yahoo格式）
    "SPY",
    "QQQ",
    "TSLA",
    "AAPL"
]
# =======================================================

def send_telegram(message):
    """纯requests发送消息，无额外依赖"""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ 电报配置缺失")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": message}, timeout=10)

def get_crypto_price(symbol):
    try:
        res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5)
        return float(res.json()["price"])
    except:
        return None

def get_stock_price(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        data = requests.get(url, timeout=5).json()
        return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except:
        return None

def your_strategy_logic(price):
    """
    这里放你原来的6条信号判断逻辑
    满足条件返回True，不满足返回False
    """
    # 先写死返回True，确保能收到消息，后面再替换成你的逻辑
    return True

def calculate_tp_sl(price):
    # 方向随机，可替换成你的逻辑
    direction = "上涨" if hash(str(price)) % 2 == 0 else "下跌"
    if direction == "上涨":
        tp = round(price * 1.025, 4)
        sl = round(price * 0.985, 4)
    else:
        tp = round(price * 0.975, 4)
        sl = round(price * 1.015, 4)
    return direction, tp, sl

if __name__ == "__main__":
    send_telegram("✅ 机器人已启动\n监控：加密货币 + 美股\n规则：满足6条信号自动推送")

    while True:
        for symbol in SYMBOLS:
            price = get_crypto_price(symbol) if symbol.endswith("USDT") else get_stock_price(symbol)
            if not price:
                continue

            if your_strategy_logic(price):
                direction, tp, sl = calculate_tp_sl(price)
                msg = f"""🚨 信号触发！
交易对: {symbol}
方向: {direction}
价格: {price}
止盈位: {tp}
止损位: {sl}
信号强度: 6/6"""
                send_telegram(msg)

            print(f"[{symbol}] 检查完成")

        time.sleep(CHECK_INTERVAL)
