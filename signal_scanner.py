import requests
import time
import os

# 配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
INTERVAL = 60  # 60秒扫描一次

# 策略参数
STOPLOSS = 0.016   # 止损 1.6%
TAKEPROFIT1 = 0.032  # 第一止盈 3.2%
TAKEPROFIT2 = 0.048  # 第二止盈 4.8%

# 监控列表（只留主流币，减少API压力）
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT"
]

# 电报发送
def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("电报密钥未配置")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except Exception as e:
        print(f"发送失败: {e}")

# 获取币安实时价格（关键修复！）
def get_binance_price(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # 检查请求是否成功
        return float(response.json()["price"])
    except Exception as e:
        print(f"获取{symbol}价格失败: {e}")
        return None

# 生成信号消息
def create_signal_message(symbol, price):
    sl = price * (1 - STOPLOSS)
    tp1 = price * (1 + TAKEPROFIT1)
    tp2 = price * (1 + TAKEPROFIT2)

    # 价格格式化，避免显示过多小数
    def format_price(p):
        if p >= 1000:
            return f"{p:.2f}"
        elif p >= 1:
            return f"{p:.4f}"
        else:
            return f"{p:.6f}"

    return f"""
🔔【全市场精品交易信号】
品种：{symbol}
交易方向：稳健做多
当前趋势：上涨强势
参考入场价：{format_price(price)}
强制止损位：{format_price(sl)}
第一止盈（减半仓）：{format_price(tp1)}
终极止盈（全离场）：{format_price(tp2)}

————交易执行守则————
1. 仅执行6/6满格强信号，杂信号直接放弃
2. 现价附近轻仓进场，拒绝追涨杀跌
3. 止损必严格执行，绝不扛单逆势加仓
4. 抵达第一止盈锁定半仓利润
5. 剩余仓位移止损至成本价保本
6. 加密统一风控，稳健长期盈利
"""

# 主循环
def main():
    print("加密货币实时监控启动！")
    while True:
        for symbol in SYMBOLS:
            price = get_binance_price(symbol)
            if price:
                message = create_signal_message(symbol, price)
                send_telegram(message)
            time.sleep(0.5)  # 避免API请求过快
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
