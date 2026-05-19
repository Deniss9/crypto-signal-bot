import requests
import time
import os

# ===================== 核心配置（不动）=====================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MIN_SIGNALS = int(os.environ.get("MIN_SIGNALS", "6"))
CHECK_INTERVAL = 60  # 60秒检查一次

# ===================== 【重点】监控列表（在这里加币种/美股）=====================
SYMBOLS = [
    # 加密货币（币安格式：去掉-，比如BTCUSDT）
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",
    
    # 美股（Yahoo Finance格式：直接写代码，比如SPY）
    "SPY",
    "QQQ",
    "TSLA",
    "AAPL",
    "NVDA"
]
# ==========================================================================

def send_telegram_alert(message):
    """发送Telegram消息，和你原来的逻辑一致"""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ 电报配置缺失，无法发送消息")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        return False

def get_crypto_data(symbol):
    """获取加密货币的完整行情数据（适配币安API）"""
    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
        response = requests.get(url, timeout=10)
        return response.json()
    except Exception as e:
        print(f"❌ 获取{symbol}数据失败: {e}")
        return None

def get_stock_data(symbol):
    """获取美股的完整行情数据（适配Yahoo Finance）"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
        response = requests.get(url, timeout=10)
        data = response.json()
        meta = data["chart"]["result"][0]["meta"]
        return {
            "price": meta["regularMarketPrice"],
            "prev_close": meta["previousClose"]
        }
    except Exception as e:
        print(f"❌ 获取{symbol}数据失败: {e}")
        return None

def your_original_strategy(data, is_crypto=True):
    """
    【核心】这里是你原来的6条信号策略
    我用占位符帮你写好了，你直接把原来的逻辑替换进去就行
    返回格式必须是：(方向, 信号强度)
    """
    # 示例：根据涨跌幅模拟你的6条信号逻辑
    if is_crypto:
        price_change = float(data["priceChangePercent"])
    else:
        price_change = ((data["price"] - data["prev_close"]) / data["prev_close"]) * 100

    # 你的6条信号判断逻辑写在这里
    signal_count = 0
    direction = "无信号"

    # 示例规则1：涨跌幅>3%
    if abs(price_change) > 3:
        signal_count += 1
    # 示例规则2：成交量放大
    if is_crypto and float(data["volume"]) > 1000000:
        signal_count += 1
    # 示例规则3-6：你原来的其他指标
    # ......（把你原来的4条规则写在这里）

    # 根据信号数量判断方向和强度
    if price_change > 0 and signal_count >= MIN_SIGNALS:
        direction = "上涨"
    elif price_change < 0 and signal_count >= MIN_SIGNALS:
        direction = "下跌"
    else:
        direction = "无信号"

    return direction, signal_count

def calculate_take_profit_stop_loss(price, direction):
    """自动计算止盈止损，可根据你的策略调整"""
    if direction == "上涨":
        take_profit = round(price * 1.025, 4)  # 上涨2.5%止盈
        stop_loss = round(price * 0.985, 4)    # 下跌1.5%止损
    elif direction == "下跌":
        take_profit = round(price * 0.975, 4)  # 下跌2.5%止盈
        stop_loss = round(price * 1.015, 4)    # 上涨1.5%止损
    else:
        take_profit = "-"
        stop_loss = "-"
    return take_profit, stop_loss

if __name__ == "__main__":
    # 启动消息，和你收到的一致
    send_telegram_alert("✅ 机器人已启动\n监控：加密货币 + 美股\n规则：满足6条信号自动推送")
    print("机器人启动成功，开始监控...")

    while True:
        for symbol in SYMBOLS:
            # 判断是加密还是美股
            is_crypto = symbol.endswith("USDT")
            # 获取行情数据
            if is_crypto:
                data = get_crypto_data(symbol)
                if not data:
                    continue
                current_price = float(data["lastPrice"])
            else:
                data = get_stock_data(symbol)
                if not data:
                    continue
                current_price = data["price"]

            # 执行你原来的6条信号策略
            direction, signal_strength = your_original_strategy(data, is_crypto)

            # 只在信号强度达到6/6时推送（和你原来的逻辑一致）
            if signal_strength >= MIN_SIGNALS and direction != "无信号":
                take_profit, stop_loss = calculate_take_profit_stop_loss(current_price, direction)
                # 推送消息格式，和你原来的BTC消息保持一致，同时加上止盈止损
                message = f"""🚨 信号触发！
交易对: {symbol}
方向: {direction}
信号强度: {signal_strength}/{MIN_SIGNALS}
当前价格: {current_price}
止盈位: {take_profit}
止损位: {stop_loss}"""
                send_telegram_alert(message)

            # 控制台日志，方便你排查问题
            print(f"[{symbol}] 方向: {direction} | 强度: {signal_strength} | 价格: {current_price}")

        # 循环间隔
        time.sleep(CHECK_INTERVAL)
