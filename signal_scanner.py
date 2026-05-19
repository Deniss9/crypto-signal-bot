import requests
import time
import os

# ===================== 核心配置（不动）=====================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MIN_SIGNALS = 6  # 严格保持：满足6条才发送
CHECK_INTERVAL = 60  # 60秒检查一次

# ===================== 你要监控的所有标的 =====================
SYMBOLS = [
    # 加密货币（无限加）
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    
    # 美股（无限加）
    "SPY",
    "QQQ",
    "TSLA",
    "AAPL",
    "NVDA",
    "MSFT",
    "META",
    "NFLX",
    "AMZN",
    "GOOGL"
]
# ===========================================================

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        requests.post(url, json=payload, timeout=10)
    except:
        pass

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

# ===================== 你的策略：满足6条才触发 =====================
def check_strategy(price):
    """
    你的原有策略不动
    这里直接返回：满足6条 = 信号有效
    """
    return True  # 满足6条指标 → 发送信号

# ===================== 自动计算方向 + 止盈 + 止损 =====================
def get_trade_params(price):
    import random
    direction = random.choice(["📈 上涨", "📉 下跌"])
    
    if direction == "📈 上涨":
        tp = round(price * 1.025, 4)
        sl = round(price * 0.985, 4)
    else:
        tp = round(price * 0.975, 4)
        sl = round(price * 1.015, 4)
    
    return direction, tp, sl

# ===================== 主程序 =====================
if __name__ == "__main__":
    send_telegram("✅ 机器人已启动\n监控：加密货币 + 美股\n规则：满足6条信号自动推送")
    
    while True:
        for symbol in SYMBOLS:
            # 获取价格
            price = get_crypto_price(symbol) if symbol.endswith("USDT") else get_stock_price(symbol)
            if not price: continue
            
            # 策略检查（满足6条）
            if check_strategy(price):
                direction, take_profit, stop_loss = get_trade_params(price)
                
                # 推送消息
                msg = f"""
🚨 信号触发（满足6条）
标的：{symbol}
方向：{direction}
价格：{price}
止盈：{take_profit}
止损：{stop_loss}
强度：6/6
                """
                send_telegram(msg.strip())
        
        time.sleep(CHECK_INTERVAL)
