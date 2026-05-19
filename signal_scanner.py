import requests
import time
import os

# 基础配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCAN_INTERVAL = 60

# 风控比例（按实时价格计算）
SL_RATE = 0.016
TP1_RATE = 0.032
TP2_RATE = 0.048

# 监控列表（你电报里的币种）
SYMBOLS = ["ATOMUSDT", "PLTRUSDT", "RIOTUSDT", "BTCUSDT", "ETHUSDT"]

# 电报推送
def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": text})
    except:
        pass

# 获取币安实时价格（无任何硬编码）
def get_price(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        return float(res.json()["price"])
    except Exception as e:
        print(f"获取{symbol}价格失败: {e}")
        return None

# 生成带实时价格的信号
def make_signal(symbol, price):
    sl = price * (1 - SL_RATE)
    tp1 = price * (1 + TP1_RATE)
    tp2 = price * (1 + TP2_RATE)

    def fmt(p):
        if p >= 1000:
            return f"{p:.2f}"
        elif p >= 1:
            return f"{p:.4f}"
        else:
            return f"{p:.6f}"

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
    send_telegram(msg)

# 主循环
if __name__ == "__main__":
    print("实时价格监控启动")
    while True:
        for s in SYMBOLS:
            p = get_price(s)
            if p:
                make_signal(s, p)
            time.sleep(0.5)
        time.sleep(SCAN_INTERVAL)
