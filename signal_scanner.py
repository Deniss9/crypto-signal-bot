#!/usr/bin/env python3
"""
BTC/ETH/SOL 多空信号自动扫描器 电报推送版
"""
import os
import requests
import json
import math
from datetime import datetime, timezone, timedelta

# 读取配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MIN_SIGNALS = int(os.environ.get("MIN_SIGNALS", "6"))

def send_telegram_alert(message):
    """把信号推送到你的电报机器人"""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ 电报配置缺失，请检查TELEGRAM_BOT_TOKEN和TELEGRAM_CHAT_ID")
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

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 扫描中 (信号阈值: {MIN_SIGNALS}) ...")
    
    # 这里保留你原来的扫描逻辑（如果有），下面是示例模拟数据
    signals = [
        {"pair": "BTC-USDT", "side": "LONG", "price": 77288.20, "count": 2},
        {"pair": "BTC-USDT", "side": "SHORT", "price": 77288.20, "count": 3},
        {"pair": "ETH-USDT", "side": "LONG", "price": 2134.29, "count": 2},
        {"pair": "ETH-USDT", "side": "SHORT", "price": 2134.29, "count": 4},
        {"pair": "SOL-USDT", "side": "LONG", "price": 84.99, "count": 2},
        {"pair": "SOL-USDT", "side": "SHORT", "price": 84.99, "count": 2}
    ]
    
    alerts = []
    for sig in signals:
        if sig["count"] >= MIN_SIGNALS:
            alerts.append(
                f"🚨 信号触发！\n"
                f"交易对: {sig['pair']}\n"
                f"方向: {sig['side']}\n"
                f"价格: ${sig['price']:.2f}\n"
                f"信号数: {sig['count']}/{MIN_SIGNALS}"
            )
    
    if alerts:
        print(f"📢 发现{len(alerts)}个满足条件的信号，正在推送...")
        for alert in alerts:
            send_telegram_alert(alert)
    else:
        print("✅ 暂无新信号")

if __name__ == "__main__":
    main()
