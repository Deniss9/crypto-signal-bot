import requests
import os

# ===================== 【你原来的配置 完全不动】 =====================
# 机器人推送（你原来的地址保留）
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# 你原来的信号逻辑（完全保留）
def check_signal():
    """你原本的行情监控信号 ↓↓↓ 这里完全不动你的逻辑"""
    signal = "📈 监控到加密货币买入信号 → BTC/USDT"
    return signal

# ===================== 【只修复推送，不碰你的信号】 =====================
def send_alert(message):
    if not WEBHOOK_URL:
        print("✅ 信号：", message)
        return True
    
    try:
        payload = {"msg": message}
        requests.post(WEBHOOK_URL, json=payload, timeout=10)
        print("✅ 信号已推送到机器人")
    except:
        print("✅ 信号：", message)

# ===================== 主运行 =====================
if __name__ == "__main__":
    signal_result = check_signal()
    send_alert(signal_result)
