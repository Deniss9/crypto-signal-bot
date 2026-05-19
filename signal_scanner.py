import requests
import time
import os

# 基础环境配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MIN_FULL_SIGNAL = 6
SCAN_INTERVAL = 60

# 顶级稳健交易参数（全品种通用）
FIX_SL_PERCENT = 0.016    # 统一止损 1.6%
FIX_TP1_PERCENT = 0.032   # 第一止盈 3.2%
FIX_TP2_PERCENT = 0.048   # 第二止盈 4.8%

# ========== 全网最全监控池 加密+美股全部纳入 ==========
WATCH_ALL_SYMBOLS = [
    # 主流加密货币
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "LINKUSDT",
    "SHIBUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT", "FTMUSDT",
    "TRXUSDT", "LTCUSDT", "BCHUSDT", "ETCUSDT", "FILUSDT",
    
    # 美股大盘指数 + 核心热门个股
    "SPY", "QQQ", "DIA", "IWM", "VIX",
    "TSLA", "AAPL", "AMZN", "MSFT", "GOOG", "META",
    "NVDA", "AMD", "INTC", "ORCL", "CRM", "DIS",
    "NFLX", "UBER", "COIN", "PLTR", "RIOT"
]

# 电报推送消息
def tg_send(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("电报密钥缺失")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        })
        print("✅ 信号推送成功")
    except Exception as e:
        print(f"推送失败：{str(e)}")

# 自动计算多空点位 + 生成完整交易策略
def create_order_info(symbol, trend, now_price):
    if trend == "上涨强势":
        mode = "稳健做多"
        stop_loss = now_price * (1 - FIX_SL_PERCENT)
        take1 = now_price * (1 + FIX_TP1_PERCENT)
        take2 = now_price * (1 + FIX_TP2_PERCENT)
    else:
        mode = "稳健做空"
        stop_loss = now_price * (1 + FIX_SL_PERCENT)
        take1 = now_price * (1 - FIX_TP1_PERCENT)
        take2 = now_price * (1 - FIX_TP2_PERCENT)

    content = f"""
📊【全市场精品交易信号】
品种：{symbol}
交易方向：{mode}
当前趋势：{trend}
参考入场价：{now_price:.2f}
强制止损位：{stop_loss:.2f}
第一止盈(减半仓)：{take1:.2f}
终极止盈(全离场)：{take2:.2f}

————交易执行守则————
1. 仅执行6/6满格强信号，杂信号直接放弃
2. 现价附近轻仓进场，拒绝追涨杀跌
3. 止损必严格执行，绝不扛单逆势加仓
4. 抵达第一止盈锁定半仓利润
5. 剩余仓位移动止损至成本价保本
6. 加密/美股统一风控，稳健长期盈利
"""
    tg_send(content)

# 全市场自动轮询扫描
def market_all_scan():
    for target in WATCH_ALL_SYMBOLS:
        # 对接你原有行情逻辑 识别趋势+信号强度
        signal_score = 6
        if signal_score >= MIN_FULL_SIGNAL:
            # 识别上涨/下跌趋势
            trend_direct = "上涨强势"
            # 填入实时价格即可自动计算全部点位
            create_order_info(target, trend_direct, 68200)

if __name__ == "__main__":
    print("全市场加密+美股监控系统启动成功")
    while True:
        market_all_scan()
        time.sleep(SCAN_INTERVAL)
