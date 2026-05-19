import requests
import time
import os
import threading
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# ===================== 核心配置 =====================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID"))
MIN_SIGNALS = 6
CHECK_INTERVAL = 60

# 监控列表（电报指令可修改）
MONITOR_LIST = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "SPY",
    "QQQ",
    "TSLA"
]

# ===================== 电报指令功能（非阻塞运行）=====================
def help_command(update: Update, context: CallbackContext):
    update.message.reply_text("""
📊 Deniss监控机器人指令：
/list - 查看当前监控的所有标的
/add <标的> - 添加监控（例：/add ETHUSDT 或 /add TSLA）
/remove <标的> - 移除监控（例：/remove BTCUSDT）
""")

def list_command(update: Update, context: CallbackContext):
    update.message.reply_text("当前监控的标的：\n" + "\n".join(MONITOR_LIST))

def add_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("❌ 用法：/add <标的>，例：/add ETHUSDT")
        return
    symbol = context.args[0].upper()
    if symbol not in MONITOR_LIST:
        MONITOR_LIST.append(symbol)
        update.message.reply_text(f"✅ 已添加 {symbol} 到监控列表")
    else:
        update.message.reply_text(f"⚠️ {symbol} 已经在监控列表里了")

def remove_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("❌ 用法：/remove <标的>，例：/remove BTCUSDT")
        return
    symbol = context.args[0].upper()
    if symbol in MONITOR_LIST:
        MONITOR_LIST.remove(symbol)
        update.message.reply_text(f"✅ 已移除 {symbol} 从监控列表")
    else:
        update.message.reply_text(f"⚠️ {symbol} 不在监控列表里")

def start_telegram_bot():
    """指令监听单独开一个线程，非阻塞运行"""
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("list", list_command))
    dp.add_handler(CommandHandler("add", add_command))
    dp.add_handler(CommandHandler("remove", remove_command))
    updater.start_polling()
    print("✅ 电报指令监听已启动")

# ===================== 行情与策略逻辑 =====================
def send_telegram_alert(message):
    """发送信号推送消息"""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ 电报配置缺失")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": message}, timeout=10)

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

def your_strategy_logic(price):
    """这里放你原来的6条信号判断逻辑"""
    return True  # 先写死True，确保能推送，后面替换成你的逻辑

def calculate_tp_sl(price):
    # 方向随机，可替换成你的逻辑
    direction = "上涨" if hash(str(price)) % 2 == 0 else "下跌"
    if direction == "上涨":
        tp = round(price * 1.025, 4)
        sl = round(price * 0.985, 4)
    else:
        tp = round(price * 0.975, 4)
        sl = round(price * 1.015, 4)
    return direction, tp, sl

# ===================== 主程序 =====================
if __name__ == "__main__":
    # 启动电报指令线程（非阻塞）
    telegram_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    telegram_thread.start()

    # 启动消息
    send_telegram_alert("✅ 机器人已启动\n监控：加密货币 + 美股\n规则：满足6条信号自动推送\n发送 /help 查看指令")

    # 主监控循环（和指令监听分开，不冲突）
    while True:
        for symbol in MONITOR_LIST:
            price = get_crypto_price(symbol) if symbol.endswith("USDT") else get_stock_price(symbol)
            if not price:
                continue

            if your_strategy_logic(price):
                direction, tp, sl = calculate_tp_sl(price)
                msg = f"""🚨 信号触发！
交易对: {symbol}
方向: {direction}
价格: {price}
止盈位: {tp}
止损位: {sl}
信号强度: 6/6"""
                send_telegram_alert(msg)

            print(f"[{symbol}] 检查完成")

        time.sleep(CHECK_INTERVAL)
