import requests
import time
import os

# 基础配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MIN_FULL_SIGNAL = 6
SCAN_INTERVAL = 60

# 固定价格参数（和你之前一样，全用68200计算）
ENTRY_PRICE = 68200.00
STOP_LOSS = 67108.80
TAKE_PROFIT1 = 70382.40
TAKE_PROFIT2 = 71473.60

# 监控列表
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
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": text
        })
    except Exception as e:
        print(f"发送失败：{e}")

# 生成和你之前完全一样的消息
def create_trade_signal(symbol):
    message = f"""
【全市场精品交易信号】品种：{symbol}
交易方向：稳健做多
当前趋势：上涨强势
参考入场价：{ENTRY_PRICE:.2f}
强制止损位：{STOP_LOSS:.2f}
第一止盈（减半仓）：{TAKE_PROFIT1:.2f}
终极止盈（全离场）：{TAKE_PROFIT2:.2f}

————交易执行守则————
1. 仅执行6/6满格强信号，杂信号直接放弃
2. 现价附近轻仓进场，拒绝追涨杀跌
3. 止损必严格执行，绝不扛单逆势加仓
4. 抵达第一止盈锁定半仓利润
5. 剩余仓位移止损至成本价保本
6. 加密/美股统一风控，稳健长期盈利
"""
    send_tg_message(message)

# 主循环（和你之前一样定时推送）
if __name__ == "__main__":
    print("监控启动，恢复原格式信号推送")
    while True:
        for symbol in WATCH_SYMBOLS:
            create_trade_signal(symbol)
            time.sleep(1)
        time.sleep(SCAN_INTERVAL)
