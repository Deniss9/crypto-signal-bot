import os
import time
import logging
import pandas as pd
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

# -------------------------- 配置与日志初始化 --------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crypto_signals.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 从环境变量读取API密钥（避免硬编码）
API_KEY = os.getenv('BINANCE_API_KEY', '')
API_SECRET = os.getenv('BINANCE_API_SECRET', '')

if not API_KEY or not API_SECRET:
    logger.error("❌ 请先设置 BINANCE_API_KEY 和 BINANCE_API_SECRET 环境变量！")
    exit(1)

try:
    client = Client(API_KEY, API_SECRET, testnet=True)  # 先在测试网运行
    logger.info("✅ 交易所连接成功（测试网模式）")
except Exception as e:
    logger.error(f"❌ 交易所连接失败: {str(e)}")
    exit(1)

# -------------------------- 信号扫描核心函数 --------------------------
def get_top_symbols(limit: int = 20) -> list:
    """获取交易量最大的现货交易对"""
    try:
        tickers = client.get_ticker()
        usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
        # 按24小时交易量排序
        usdt_pairs.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
        return [pair['symbol'] for pair in usdt_pairs[:limit]]
    except BinanceAPIException as e:
        logger.error(f"获取交易对失败: {str(e)}")
        return []

def analyze_signal(symbol: str, interval: str = Client.KLINE_INTERVAL_1HOUR) -> dict:
    """单交易对多空信号分析（RSI+MACD+布林带组合）"""
    try:
        # 获取K线数据
        klines = client.get_klines(
            symbol=symbol,
            interval=interval,
            limit=100
        )
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume',
                                           'close_time', 'quote_asset_volume', 'trades',
                                           'taker_buy_base', 'taker_buy_quote', 'ignore'])
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)

        # 计算RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]

        # 计算布林带
        sma20 = df['close'].rolling(window=20).mean()
        std20 = df['close'].rolling(window=20).std()
        upper_band = sma20 + 2 * std20
        lower_band = sma20 - 2 * std20
        current_price = df['close'].iloc[-1]

        # 生成信号
        signal = "中性"
        score = 0
        if current_rsi < 30 and current_price < lower_band.iloc[-1]:
            signal = "做多信号"
            score = 1
        elif current_rsi > 70 and current_price > upper_band.iloc[-1]:
            signal = "做空信号"
            score = -1

        return {
            "symbol": symbol,
            "current_price": round(current_price, 4),
            "rsi": round(current_rsi, 2),
            "bollinger_upper": round(upper_band.iloc[-1], 4),
            "bollinger_lower": round(lower_band.iloc[-1], 4),
            "signal": signal,
            "score": score
        }

    except Exception as e:
        logger.error(f"分析 {symbol} 失败: {str(e)}")
        return {"symbol": symbol, "signal": "错误", "score": 0}

# -------------------------- 主循环 --------------------------
def main():
    scan_interval = 300  # 每5分钟扫描一次（单位：秒）
    logger.info("🚀 加密货币多空信号监控机器人启动")
    logger.info(f"扫描间隔: {scan_interval}秒")

    while True:
        logger.info("\n-------------------------- 新一轮扫描开始 --------------------------")
        symbols = get_top_symbols(limit=15)
        if not symbols:
            logger.warning("⚠️ 未获取到交易对，等待下一轮扫描")
            time.sleep(scan_interval)
            continue

        signals = []
        for symbol in symbols:
            result = analyze_signal(symbol)
            signals.append(result)
            # 限流控制，避免触发API限制
            time.sleep(0.3)

        # 输出信号结果
        for sig in signals:
            if sig['signal'] != "中性" and sig['signal'] != "错误":
                logger.info(f"[{sig['signal']}] {sig['symbol']} | 价格: {sig['current_price']} | RSI: {sig['rsi']}")

        logger.info("-------------------------- 扫描完成，等待下一轮 --------------------------")
        time.sleep(scan_interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 用户手动停止程序")
    except Exception as e:
        logger.critical(f"程序崩溃: {str(e)}", exc_info=True)
