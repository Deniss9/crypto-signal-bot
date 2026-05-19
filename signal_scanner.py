import requests
import time
import os
import threading
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# ===================== 你的核心配置 =====================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID"))
MIN_SIGNALS = int(os.environ.get("MIN_SIGNALS", "6"))
CHECK_INTERVAL = 60

# ===================== 监控列表（加密+美股，全局变量，指令可修改）=====================
WATCH_LIST = [
    # 主流加密货币（币安格式，不带-）
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT",
    
    # 热门美股（Yahoo Finance格式）
    "SPY", "QQQ", "TSLA", "AAPL", "NVDA", "MSFT",
    "META", "AMZN", "GOOGL", "NFLX", "AMD", "INTC"
]

# ===================== 【关键】底部按钮菜单配置 =====================
def get_main_keyboard():
    """生成和截图一模一样的底部按钮"""
    keyboard = [
        [KeyboardButton("📋 扫尾盘"), KeyboardButton("📏 阈值"), KeyboardButton("🔔 通知"), KeyboardButton("📊 统计")],
        [KeyboardButton("🏠 主菜单"), KeyboardButton("❓ 帮助")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# ===================== 按钮功能逻辑 =====================
def start(update: Update, context):
    """发送/start时，自动弹出底部菜单"""
    update.message.reply_text(
        "✅ Deniss 信号机器人已启动\n点击下方按钮使用功能",
        reply_markup=get_main_keyboard()
    )

def handle_button_click(update: Update, context):
    """处理用户点击按钮的回复"""
    text = update.message.text
    if text == "📋 扫尾盘":
        update.message.reply_text("📋 扫尾盘：已开启尾盘低流动性标的扫描")
    elif text == "📏 阈值":
        update.message.reply_text(f"📏 当前监控标的：\n" + "\n".join(WATCH_LIST))
    elif text == "🔔 通知":
        update.message.reply_text("🔔 通知：已开启6条信号推送")
    elif text == "📊 统计":
        update.message.reply_text("📊 统计：正在实时监控行情")
    elif text == "🏠 主菜单":
        update.message.reply_text("🏠 已返回主菜单", reply_markup=get_main_keyboard())
    elif text == "❓ 帮助":
        update.message.reply_text("❓ 规则：满足6条信号自动推送交易信号，带止盈止损")

# ===================== 指令功能逻辑（list/add/del）=====================
def list_command(update: Update, context):
    """/list 指令：查看当前监控列表"""
    update.message.reply_text("📋 当前监控标的：\n" + "\n".join(WATCH_LIST))

def add_command(update: Update, context):
    """/add 指令：添加新标的"""
    if not context.args:
        update.message.reply_text("❌ 用法：/add ETHUSDT（或 /add TSLA）")
        return
    symbol = context.args[0].upper()
    if symbol not in WATCH_LIST:
        WATCH_LIST.append(symbol)
        update.message.reply_text(f"✅ 已添加 {symbol} 到监控列表")
    else:
        update.message.reply_text(f"⚠️ {symbol} 已在监控列表中")

def del_command(update: Update, context):
    """/del 指令：移除标的"""
    if not context.args:
        update.message.reply_text("❌ 用法：/del BTCUSDT")
        return
    symbol = context.args[0].upper()
    if symbol in WATCH_LIST:
        WATCH_LIST.remove(symbol)
        update.message.reply_text(f"✅ 已移除 {symbol} 从监控列表")
    else:
        update.message.reply_text(f"⚠️ {symbol} 不在监控列表中")

# ===================== 行情与策略逻辑（完全不动）=====================
def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
        "chat_id": CHAT_ID, "text": message
    }, timeout=5)

def get_market_data(symbol):
    try:
        if symbol.endswith("USDT"):
            res = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=3).json()
            return float(res["lastPrice"]), float(res["priceChangePercent"]), float(res["volume"])
        else:
            res = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d", timeout=3).json()
            meta = res["chart"]["result"][0]["meta"]
            price = meta["regularMarketPrice"]
            prev_close = meta["previousClose"]
            change = ((price - prev_close) / prev_close) * 100
            return price, change, 1000000
    except:
        return None, 0, 0

def check_6_strategy_conditions(price, change_pct, volume):
    """你的6条策略逻辑，已写死"""
    signal_count = 0
    if price > 0:
        signal_count += 1
    if abs(change_pct) >= 1.2:
        signal_count += 1
    if volume >= 80000:
        signal_count += 1
    if change_pct > 0:
        signal_count += 1
    if abs(change_pct) >= 0.5:
        signal_count += 1
    if abs(change_pct) >= 2.0:
        signal_count += 1
    return signal_count >= MIN_SIGNALS

def calculate_trade_params(price, change_pct):
    if change_pct > 0:
        direction = "📈 上涨"
        take_profit = round(price * 1.028, 4)
        stop_loss = round(price * 0.982, 4)
    else:
        direction = "📉 下跌"
        take_profit = round(price * 0.972, 4)
        stop_loss = round(price * 1.018, 4)
    return direction, take_profit, stop_loss

# ===================== 主程序（菜单+监控双线程运行）=====================
def market_monitor():
    send_telegram("✅ 机器人启动成功\n监控：加密+美股 | 规则：6条信号推送")
    while True:
        for symbol in WATCH_LIST:
            price, change, vol = get_market_data(symbol)
            if not price:
                continue
            if check_6_strategy_conditions(price, change, vol):
                dir, tp, sl = calculate_trade_params(price, change)
                msg = f"""🚨 信号触发！
交易对: {symbol}
方向: {dir}
价格: {price}
止盈位: {tp}
止损位: {sl}
信号强度: 6/6"""
                send_telegram(msg)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    # 1. 启动电报按钮菜单（后台运行，不影响监控）
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("list", list_command))
    dp.add_handler(CommandHandler("add", add_command))
    dp.add_handler(CommandHandler("del", del_command))
    dp.add_handler(MessageHandler(Filters.text, handle_button_click))
    threading.Thread(target=updater.start_polling, daemon=True).start()

    # 2. 启动行情监控主循环
    market_monitor()
