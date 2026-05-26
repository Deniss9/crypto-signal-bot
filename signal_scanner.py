import os
import time
import requests
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException

# ===================== 从 GitHub Secrets 读取配置（关键！） =====================
# 这些变量必须在仓库的 Settings → Secrets and variables → Actions 里添加
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ===================== Telegram 推送函数 =====================
def send_telegram_message(text):
    """发送消息到 Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ 缺少 Telegram 配置，无法推送消息")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✅ 消息已推送到 Telegram")
            return True
        else:
            print(f"❌ Telegram 推送失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Telegram 推送出错: {str(e)}")
        return False

# ===================== 币安连接 =====================
try:
    client = Client(API_KEY, API_SECRET, testnet=False)  # 主网读取权限即可
    print("✅ 币安 API 连接成功")
except Exception as e:
    error_msg = f"❌ 币安 API 连接失败: {str(e)}"
    print(error_msg)
    send_telegram_message(f"⚠️ 加密信号机器人出错：\n{error_msg}")
    exit(1)

# ===================== 信号扫描逻辑（可自定义） =====================
def scan_signals():
    """扫描多空信号，返回结果列表"""
    signals = []
    try:
        # 获取交易量前15的USDT交易对
        tickers = client.get_ticker()
        usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
        usdt_pairs.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
        top_symbols = [pair['symbol'] for pair in usdt_pairs[:15]]

        for symbol in top_symbols:
            # 获取1小时K线数据
            klines = client.get_klines(
                symbol=symbol,
                interval=Client.KLINE_INTERVAL_1HOUR,
                limit=50
            )
            close_prices = [float(k[4]) for k in klines]
            current_price = close_prices[-1]
            
            # 简单信号逻辑：价格突破20周期均线
            ma20 = sum(close_prices[-20:]) / 20
            if current_price > ma20 * 1.02:
                signals.append(f"📈 做多信号: {symbol} | 当前价: {current_price:.4f} | 20均线: {ma20:.4f}")
            elif current_price < ma20 * 0.98:
                signals.append(f"📉 做空信号: {symbol} | 当前价: {current_price:.4f} | 20均线: {ma20:.4f}")
            
            # 限流，避免触发API限制
            time.sleep(0.3)

        return signals

    except BinanceAPIException as e:
        print(f"❌ 扫描出错: {str(e)}")
        return []

# ===================== 主函数 =====================
def main():
    print(f"🚀 开始扫描，时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    signals = scan_signals()

    if signals:
        message = "🔔 加密货币信号扫描结果：\n" + "\n".join(signals)
    else:
        message = "🔔 加密货币信号扫描完成，未发现有效信号"
    
    print(message)
    send_telegram_message(message)
    print("✅ 本次扫描任务完成")

if __name__ == "__main__":
    main()
