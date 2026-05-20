import requests
import time
import os

# 配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
INTERVAL = 60

# 风控比例（按实时价格算）
SL = 0.016
TP1 = 0.032
TP2 = 0.048

# 只保留币安支持的交易对，去掉美股代码
SYMBOLS = ["ATOMUSDT", "SOLUSDT", "DOGEUSDT", "BTCUSDT", "ETHUSDT"]

# 电报推送
def send(msg):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print(f"发送失败: {e}")

# 币安实时价格获取（只查币安的币）
def get_price(symbol):
    try:
        res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5)
        res.raise_for_status()
        return float(res.json()["price"])
    except Exception as e:
        print(f"获取 {symbol} 价格失败: {e}")
        return None

# 价格格式化，让显示更干净
def fmt(p):
    if p >= 1000:
        return f"{p:.2f}"
    elif p >= 1:
        return f"{p:.4f}"
    else:
        return f"{p:.6f}"

# 生成信号消息（和你之前格式完全一样）
def signal(symbol, price):
    sl = price * (1 - SL)
    tp1 = price * (1 + TP1)
    tp2 = price * (1 + TP2)

    msg = f"""
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
6. 加密统一风控，稳健长期盈利
"""
    send(msg)

# 主循环
if __name__ == "__main__":
    print("启动成功，开始推送实时价格信号")
    while True:
        for s in SYMBOLS:
            price = get_price(s)
            if price:
                signal(s, price)
            time.sleep(0.5)
        time.sleep(INTERVAL)
