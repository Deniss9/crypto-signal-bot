import os
import time
import requests
from datetime import datetime

# 配置信息
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 币安备用API地址列表（自动轮询解决451限制）
BINANCE_API_HOSTS = [
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api.binance.us"
]

# 要监控的交易对
SYMBOLS = ["BTCUSDT", "ETHUSDT", "ATOMUSDT", "PLTRUSDT", "RIOTUSDT"]

def send_telegram_message(text):
    """发送Telegram通知"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram配置缺失，跳过通知")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Telegram通知失败: {e}")

def get_binance_price(symbol, retries=3):
    """从币安API获取价格，自动轮询备用地址+重试"""
    for attempt in range(retries):
        for host in BINANCE_API_HOSTS:
            try:
                url = f"{host}/api/v3/ticker/price"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                    "Accept": "application/json"
                }
                response = requests.get(url, params={"symbol": symbol}, headers=headers, timeout=10)
                response.raise_for_status()
                return response.json()["price"]
            except requests.exceptions.HTTPError as e:
                if response.status_code == 451:
                    print(f"[{symbol}] 地址 {host} 被451拦截，尝试下一个地址")
                    continue
                else:
                    print(f"[{symbol}] 请求失败: {e}")
                    continue
            except Exception as e:
                print(f"[{symbol}] 连接错误: {e}，尝试下一个地址")
                continue
        print(f"[{symbol}] 第{attempt+1}次重试失败，等待1秒后重试")
        time.sleep(1)
    print(f"[{symbol}] 所有地址重试失败，放弃获取")
    return None

def main():
    print(f"=== 扫描开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    results = []
    for symbol in SYMBOLS:
        price = get_binance_price(symbol)
        if price:
            print(f"✅ {symbol}: {price} USDT")
            results.append(f"{symbol}: {price} USDT")
        else:
            print(f"❌ {symbol}: 获取失败")
            results.append(f"{symbol}: 获取失败")
    
    # 发送Telegram汇总通知
    if results:
        message = f"📊 加密货币价格扫描结果\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" + "\n".join(results)
        send_telegram_message(message)

if __name__ == "__main__":
    main()
