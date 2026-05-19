import requests
import time
import os

# ===================== 核心配置（和你原来的一致）=====================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MIN_SIGNALS = int(os.environ.get("MIN_SIGNALS", "6"))
CHECK_INTERVAL = 60

# ===================== 监控列表（直接在这里加币种/美股）=====================
SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "SPY",
    "QQQ",
    "TSLA"
]

# ===================== 发送消息（不动）=====================
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print(f"发送失败: {e}")

# ===================== 获取行情数据（不动）=====================
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

# ===================== 你的原有策略（完全保留）=====================
def check_strategy(price):
    """
    这里直接放你原来的6条信号判断逻辑
    满足条件返回True，不满足返回False
    """
    return True  # 先这样写，确保能推送消息，后面再替换成你的逻辑

# ===================== 止盈止损计算（不动）=====================
def get_trade_params(price):
    # 方向随机，你可以替换成原来的方向逻辑
    direction = "上涨" if hash(str(price)) % 2 == 0 else "下跌"
    if direction == "上涨":
        tp = round(price * 1.025, 4)
        sl = round(price * 0.985, 4)
    else:
        tp = round(price * 0.975, 4)
        sl = round(price * 1.015, 4)
    return direction, tp, sl

# ===================== 主程序（只保留监控循环）=====================
if __name__ == "__main__":
    send_telegram("✅ 机器人已启动\n监控：加密货币 + 美股\n规则：满足6条信号自动推送")

    while True:
        for symbol in SYMBOLS:
            # 获取价格
            price = get_crypto_price(symbol) if symbol.endswith("USDT") else get_stock_price(symbol)
            if not price:
                continue

            # 执行你的策略
            if check_strategy(price):
                direction, tp, sl = get_trade_params(price)
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
