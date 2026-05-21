
import ccxt
import json
import numpy as np
from datetime import datetime, timezone

exchange = ccxt.okx({'enableRateLimit': True})

symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']
timeframes = ['1d', '4h', '1h']

def ema(closes, period):
    k = 2 / (period + 1)
    ema_val = closes[0]
    for c in closes[1:]:
        ema_val = c * k + ema_val * (1 - k)
    return ema_val

def rsi(closes, period=14):
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)

def atr(highs, lows, closes, period=14):
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    return np.mean(trs[-period:])

results = {}

for sym in symbols:
    results[sym] = {}
    for tf in timeframes:
        try:
            ohlcv = exchange.fetch_ohlcv(sym, tf, limit=100)
            if not ohlcv or len(ohlcv) < 30:
                continue
            ts = [x[0] for x in ohlcv]
            opens = [x[1] for x in ohlcv]
            highs = [x[2] for x in ohlcv]
            lows = [x[3] for x in ohlcv]
            closes = [x[4] for x in ohlcv]
            vols = [x[5] for x in ohlcv]

            e20 = ema(closes[-30:], 20)
            e60 = ema(closes[-70:], 60)
            r = rsi(closes[-20:])
            at = atr(highs[-20:], lows[-20:], closes[-20:])
            current = closes[-1]
            trend = 'BULLISH' if e20 > e60 else 'BEARISH'
            results[sym][tf] = {
                'close': round(current, 2),
                'ema20': round(e20, 2),
                'ema60': round(e60, 2),
                'rsi': round(r, 2),
                'atr': round(at, 2),
                'trend': trend,
                'vol': round(vols[-1], 2)
            }
        except Exception as e:
            results[sym][tf] = {'error': str(e)}

# Funding rates
funding = {}
for sym in symbols:
    try:
        fr = exchange.fetch_funding_rate(sym)
        funding[sym] = round(float(fr.get('fundingRate', 0)) * 100, 4)
    except Exception as e:
        funding[sym] = None

# Open Interest
oi = {}
for sym in symbols:
    try:
        inst_id = sym.replace('/USDT:USDT', '-USDT-SWAP')
        resp = exchange.publicGetPublicOpenInterest({'instId': inst_id})
        oi_val = float(resp['data'][0]['oi']) if resp.get('data') else None
        oi[sym] = round(oi_val, 0) if oi_val else None
    except Exception as e:
        oi[sym] = None

print(json.dumps({
    'market': results,
    'funding': funding,
    'oi': oi,
    'timestamp': datetime.now(timezone.utc).isoformat()
}))
