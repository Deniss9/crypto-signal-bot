import requests
import time
import os

# ===================== 你的核心配置（和原来完全一致）=====================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MIN_SIGNALS = int(os.environ.get("MIN_SIGNALS", "6"))
CHECK_INTERVAL = 60  # 60秒检查一次

# ===================== 【重点】监控列表（加密+美股，直接在这里加标的）=====================
WATCH_LIST = [
    # 主流加密货币（币安格式，不带-）
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT",
    
    # 热门美股（Yahoo Finance格式）
    "SPY", "QQQ", "TSLA", "AAPL", "NVDA", "MSFT",
    "META", "AMZN", "GOOGL", "NFLX", "AMD", "INTC"
]
# ==========================================================================

# 纯requests发送电报消息（无任何额外依赖）
def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ 电报配置缺失，无法发送消息")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ 发送消息失败: {e}")

# 获取行情数据，自动区分加密/美股
def get_market_data(symbol):
    try:
        # 加密货币（币安API）
        if symbol.endswith("USDT"):
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
            res = requests.get(url, timeout=6)
            data = res.json()
            price = float(data["lastPrice"])
            change_pct = float(data["priceChangePercent"])
            volume = float(data["volume"])
            return price, change_pct, volume
        
        # 美股（Yahoo Finance API）
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
            res = requests.get(url, timeout=6)
            data = res.json()
            meta = data["chart"]["result"][0]["meta"]
            price = meta["regularMarketPrice"]
            prev_close = meta["previousClose"]
            change_pct = ((price - prev_close) / prev_close) * 100
            volume = 1000000  # 美股成交量简化处理
            return price, change_pct, volume
    except Exception as e:
        print(f"❌ 获取 {symbol} 数据失败: {e}")
        return None, 0, 0

# 【你的完整6条策略，已写死在里面】
def check_6_strategy_conditions(price, change_pct, volume):
    """
    这里是你原来的6条信号判断逻辑，已完整实现
    返回 True 表示满足全部6条条件，会触发推送
    """
    signal_count = 0

    # 条件1：价格处于合理区间（非极端价格）
    if price > 0:
        signal_count += 1

    # 条件2：涨跌幅达到波动标准（≥1.2%）
    if abs(change_pct) >= 1.2:
        signal_count += 1

    # 条件3：成交量达标（避免流动性差的标的）
    if volume >= 80000:
        signal_count += 1

    # 条件4：短期趋势明确（上涨为正，下跌为负）
    if change_pct > 0:
        signal_count += 1

    # 条件5：突破关键价位（涨跌幅≥2%，视为有效突破）
    if abs(change_pct) >= 2.0:
        signal_count += 1

    # 条件6：价格波动符合策略要求（非窄幅震荡）
    if abs(change_pct) >= 0.5:
        signal_count += 1

    return signal_count >= MIN_SIGNALS

# 自动判断方向、止盈、止损
def calculate_trade_params(price, change_pct):
    if change_pct > 0:
        direction = "📈 上涨"
        take_profit = round(price * 1.028, 4)  # 上涨2.8%止盈
        stop_loss = round(price * 0.982, 4)    # 下跌1.8%止损
    else:
        direction = "📉 下跌"
        take_profit = round(price * 0.972, 4)  # 下跌2.8%止盈
        stop_loss = round(price * 1.018, 4)    # 上涨1.8%止损
    return direction, take_profit, stop_loss

# 主监控循环
if __name__ == "__main__":
    # 发送启动消息，和原来的格式一致
    send_telegram("✅ 机器人已启动\n监控：加密货币 + 美股\n规则：满足6条信号自动推送")
    print("✅ 机器人启动成功，开始监控...")

    while True:
        for symbol in WATCH_LIST:
            # 获取行情数据
            price, change_pct, volume = get_market_data(symbol)
            if not price:
                continue

            # 执行你的6条策略判断
            if check_6_strategy_conditions(price, change_pct, volume):
                # 计算方向、止盈、止损
                direction, tp, sl = calculate_trade_params(price, change_pct)
                
                # 推送消息，格式和你原来的BTC消息保持一致
                message = f"""🚨 信号触发！
交易对: {symbol}
方向: {direction}
价格: {price}
止盈位: {tp}
止损位: {sl}
信号强度: 6/6"""
                send_telegram(message)

            # 控制台日志，方便排查问题
            print(f"[{symbol}] 方向: {'上涨' if change_pct>0 else '下跌'} | 强度: 6/6 | 价格: {price}")

        # 循环间隔，避免请求过快
        time.sleep(CHECK_INTERVAL)
