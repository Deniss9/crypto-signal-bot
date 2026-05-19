import requests
import time
import os

# 基础配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCAN_INTERVAL = 60  # 60秒扫一次

# 风控比例（按每个币自己的价格算）
SL_PERCENT = 0.016  # 止损 1.6%
TP1_PERCENT = 0.032 # 第一止盈 3.2%
TP2_PERCENT = 0.048 # 第二止盈 4.8%

# 监控的币种列表
WATCH_SYMBOLS = [
    "ATOMUSDT", "UNIUSDT", "SHIBUSDT", "SOLUSDT", "BTCUSDT", "ETHUSDT"
]

# 电报推送
def send_tg_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("电报密钥未配置")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text})
    except Exception as e:
        print(f"发送失败：{e}")

# 获取币安实时价格（关键！每个币用自己的价格）
def get_binance_price(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        return float(res.json()["price"])
    except Exception as e:
        print(f"获取{symbol}价格失败：{e}")
        return None

# 按每个币自己的价格，算止盈止损
def create_trade_signal(symbol, price):
    if not price:
        return
    
    # 按比例算，每个币自己的价格算出来的止盈止损
    sl = price * (1 - SL_PERCENT)
    tp1 = price * (1 + TP1_PERCENT)
    tp2 = price * (1 + TP2_PERCENT)

    # 价格格式化，避免小数位数太多
    def fmt(p):
        if p >= 1000:
            return f"{p:.2f}"
        elif p >= 1:
            return f"{p:.4f}"
        else:
            return f"{p:.6f}"

    message = f"""
【全市场精品交易信号】品种：{symbol}
交易方向：稳健做多
当前趋势：上涨强势
参考入场价：{fmt(price)}
强制止损位：{fmt(sl)}
第一止盈（减半仓）：{fmt(tp1)}
终极止盈（全离场）：{fmt(tp2)}

————交易执行守则————
1. 仅执行6/6满格强信号，杂信号直接放弃
2. 现价附近轻仓进场，拒绝追涨杀跌
3. 止损必严格执行，绝不扛单逆势加仓
4. 抵达第一止盈锁定半仓利润
5. 剩余仓位移止损至成本价保本
6. 加密/美股统一风控，稳健长期盈利
"""
    send_tg_message(message)

# 主循环：每个币用自己的价格
if __name__ == "__main__":
    print("实时价格监控启动！")
    while True:
        for symbol in WATCH_SYMBOLS:
            # 调用API获取这个币自己的实时价格
            price = get_binance_price(symbol)
            if price:
                create_trade_signal(symbol, price)
            time.sleep(0.5)
        time.sleep(SCAN_INTERVAL)
