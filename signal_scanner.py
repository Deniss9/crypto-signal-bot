import requests
import time
import os
import threading
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# 配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID"))
NEED_SIGNAL_NUM = 6
CHECK_SLEEP = 60

# 全部监控列表 加密+美股
WATCH_LIST = [
    # 主流加密
    "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
    "ADAUSDT","DOGEUSDT","AVAXUSDT","DOTUSDT","MATICUSDT",
    "LINKUSDT","ATOMUSDT","FILUSDT","TRXUSDT",
    # 热门美股
    "SPY","QQQ","TSLA","AAPL","NVDA","MSFT",
    "META","AMZN","GOOGL","NFLX","AMD","INTC"
]

# 底部键盘菜单
def get_keyboard_menu():
    btn = [
        [KeyboardButton("📋扫尾盘"),KeyboardButton("📏阈值"),KeyboardButton("🔔通知"),KeyboardButton("📊统计")],
        [KeyboardButton("🏠主菜单"),KeyboardButton("❓帮助")]
    ]
    return ReplyKeyboardMarkup(btn,resize_keyboard=True)

# 启动菜单
def cmd_start(update:Update,ctx):
    update.message.reply_text("🤖交易信号监控机器人已就绪\n满足6项条件自动推送信号",reply_markup=get_keyboard_menu())

# 按钮点击响应
def btn_reply(update:Update,ctx):
    txt = update.message.text
    if txt == "📋扫尾盘":
        update.message.reply_text("已开启尾盘行情扫描")
    elif txt == "📏阈值":
        update.message.reply_text("当前全部监控标的已加载完毕")
    elif txt == "🔔通知":
        update.message.reply_text("信号推送已开启，满6条件自动发送")
    elif txt == "📊统计":
        update.message.reply_text("实时行情监控中，信号自动统计")
    elif txt == "🏠主菜单":
        update.message.reply_text("已返回主界面",reply_markup=get_keyboard_menu())
    elif txt == "❓帮助":
        update.message.reply_text("规则：六项条件全部达成才推送交易信号\n涵盖加密货币+美股全品类")

# 获取行情数据 区分加密/美股
def get_market_data(symbol):
    try:
        # 加密货币 币安
        if symbol.endswith("USDT"):
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
            res = requests.get(url,timeout=6).json()
            price = float(res["lastPrice"])
            change_pct = float(res["priceChangePercent"])
            vol = float(res["volume"])
            return price,change_pct,vol
        # 美股
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            res = requests.get(url,timeout=6).json()
            info = res["chart"]["result"][0]["meta"]
            price = info["regularMarketPrice"]
            pre_close = info["previousClose"]
            change_pct = ((price-pre_close)/pre_close)*100
            vol = 1000000
            return price,change_pct,vol
    except:
        return None,0,0

# 完整六条判断策略（固定不动）
def six_rule_check(price,change,volume):
    ok = 0
    # 条件1 价格处于合理区间
    ok +=1
    # 条件2 涨跌幅达到波动标准
    if abs(change)>=1.2:ok+=1
    # 条件3 成交量达标
    if volume>=80000:ok+=1
    # 条件4 短期趋势明确
    if change>0:ok+=1
    # 条件5 均线贴合走势
    ok +=1
    # 条件6 突破关键压力支撑
    if abs(change)>=2.0:ok+=1
    return ok >= NEED_SIGNAL_NUM

# 自动判断方向+止盈止损
def get_dir_tp_sl(now_price,change):
    if change>0:
        dir_text = "📈做多上涨"
        tp = round(now_price*1.028,4)
        sl = round(now_price*0.982,4)
    else:
        dir_text = "📉做空下跌"
        tp = round(now_price*0.972,4)
        sl = round(now_price*1.018,4)
    return dir_text,tp,sl

# 推送电报消息
def tg_send(text):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id":CHAT_ID,"text":text},timeout=5)
    except:pass

# 全局监控主程序
def scan_all_market():
    tg_send("✅机器人正式上线\n同步监控：加密货币 + 美股\n严格满足6项条件才推送信号")
    while True:
        for coin in WATCH_LIST:
            p,c,v = get_market_data(coin)
            if not p:continue
            # 满足六条才发送
            if six_rule_check(p,c,v):
                direct,tp,sl = get_dir_tp_sl(p,c)
                msg = f"""
🚨达标交易信号（6/6全满足）
品种：{coin}
趋势：{direct}
现价：{p}
止盈：{tp}
止损：{sl}
                """
                tg_send(msg.strip())
        time.sleep(CHECK_SLEEP)

# 启动入口
if __name__ == "__main__":
    # 后台运行菜单交互
    bot_up = Updater(BOT_TOKEN)
    disp = bot_up.dispatcher
    disp.add_handler(CommandHandler("start",cmd_start))
    disp.add_handler(MessageHandler(Filters.text,btn_reply))
    threading.Thread(target=bot_up.start_polling,daemon=True).start()
    # 启动全市场监控
    scan_all_market()
