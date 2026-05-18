import requests
import time
import os

# 从环境变量读取配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MIN_SIGNALS = int(os.environ.get("MIN_SIGNALS", "6"))

def send_telegram_alert(message):
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
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ 电报信号推送成功！")
            return True
        else:
            print(f"❌ 推送失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 发送异常: {e}")
        return False

if __name__ == "__main__":
    # 这里是你的扫描逻辑，现在用测试数据代替
    print("正在运行加密信号扫描...")
    test_signals = 6  # 模拟信号数量，和MIN_SIGNALS对应
    if test_signals >= MIN_SIGNALS:
        alert_msg = f"🚨 信号触发！\n交易对: BTC-USDT\n方向: 上涨\n信号强度: {test_signals}/{MIN_SIGNALS}"
        send_telegram_alert(alert_msg)
    else:
        print(f"信号不足（当前{test_signals}，需≥{MIN_SIGNALS}），不推送")
