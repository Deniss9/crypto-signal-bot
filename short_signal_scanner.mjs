/**
 * BTC / ETH / SOL 逢高做空信号扫描器 v2.0
 * - 阈值：满足 6 个条件才触发预警
 * - 渠道：Gmail 邮件 + 币安广场同步发布
 * - 输出：纯文本，无表格
 */

import https from 'https';
import { execFileSync } from 'child_process';

const GMAIL_SERVER = '/home/user/servers/gmail/run.mjs';
const ALERT_EMAIL = process.env.ALERT_EMAIL || 'fly15201344146@gmail.com';
const MIN_SIGNALS = parseInt(process.env.MIN_SIGNALS || '6');
const SQUARE_API = 'https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add';
const SQUARE_KEY = process.env.BINANCE_SQUARE_OPENAPI_KEY || '';

// ─── 工具函数 ─────────────────────────────────────────────

function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { 'User-Agent': 'ShortScanner/2.0' } }, (res) => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } });
    }).on('error', reject);
  });
}

async function fetchCandles(instId, bar, limit = 60) {
  const url = `https://www.okx.com/api/v5/market/candles?instId=${instId}&bar=${bar}&limit=${limit}`;
  const res = await fetchJSON(url);
  return (res.data || []).map(r => ({
    ts: +r[0], o: +r[1], h: +r[2], l: +r[3], c: +r[4], v: +r[5]
  })).reverse();
}

async function fetchFundingRate(instId) {
  const url = `https://www.okx.com/api/v5/public/funding-rate?instId=${instId}`;
  const res = await fetchJSON(url);
  return parseFloat(res.data?.[0]?.fundingRate || 0) * 100;
}

function ema(data, period) {
  const k = 2 / (period + 1);
  let e = data[0];
  return data.map((v, i) => { if (i === 0) return e; e = v * k + e * (1 - k); return e; });
}

function rsi(closes, period = 14) {
  if (closes.length < period + 1) return closes.map(() => null);
  let ag = 0, al = 0;
  for (let i = 1; i <= period; i++) {
    const d = closes[i] - closes[i - 1];
    if (d > 0) ag += d; else al -= d;
  }
  ag /= period; al /= period;
  const result = new Array(period).fill(null);
  result.push(al === 0 ? 100 : 100 - 100 / (1 + ag / al));
  for (let i = period + 1; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    ag = (ag * (period - 1) + (d > 0 ? d : 0)) / period;
    al = (al * (period - 1) + (d < 0 ? -d : 0)) / period;
    result.push(al === 0 ? 100 : 100 - 100 / (1 + ag / al));
  }
  return result;
}

function macdCalc(closes, fast = 12, slow = 26, signal = 9) {
  const emaFast = ema(closes, fast);
  const emaSlow = ema(closes, slow);
  const macdLine = closes.map((_, i) => emaFast[i] - emaSlow[i]);
  const sigLine = ema(macdLine.slice(slow - 1), signal);
  const hist = macdLine.slice(slow - 1).map((v, i) => v - sigLine[i]);
  return { hist, macdLine: macdLine.slice(slow - 1), sigLine };
}

function bollingerBands(closes, period = 20, mult = 2) {
  const slice = closes.slice(-period);
  const mid = slice.reduce((a, b) => a + b) / period;
  const std = Math.sqrt(slice.reduce((a, b) => a + (b - mid) ** 2, 0) / period);
  return { upper: mid + mult * std, mid, lower: mid - mult * std };
}

// ─── 核心分析 ─────────────────────────────────────────────

async function analyzeSymbol(sym, swapSym) {
  const [c5m, c15m, c1h, c4h, funding] = await Promise.all([
    fetchCandles(sym, '5m', 30),
    fetchCandles(sym, '15m', 50),
    fetchCandles(sym, '1H', 100),
    fetchCandles(sym, '4H', 100),
    fetchFundingRate(swapSym)
  ]);

  const price = c1h[c1h.length - 1].c;

  // 1H
  const closes1h = c1h.map(c => c.c);
  const highs1h = c1h.map(c => c.h);
  const vols1h = c1h.map(c => c.v);
  const e20_1h = ema(closes1h, 20);
  const e50_1h = ema(closes1h, 50);
  const e200_1h = ema(closes1h, 200);
  const rsi1h = rsi(closes1h);
  const macd1h = macdCalc(closes1h);
  const bb1h = bollingerBands(closes1h);
  const n1h = closes1h.length - 1;
  const curRsi1h = rsi1h[n1h];
  const curMacdHist1h = macd1h.hist[macd1h.hist.length - 1];
  const prevMacdHist1h = macd1h.hist[macd1h.hist.length - 2];
  const avgVol1h = vols1h.slice(-20).reduce((a, b) => a + b) / 20;
  const lastVol1h = vols1h[n1h];
  const resistance1h = Math.max(...highs1h.slice(-20));

  // 15m
  const closes15m = c15m.map(c => c.c);
  const rsi15m = rsi(closes15m);
  const curRsi15m = rsi15m[closes15m.length - 1];

  // 5m 形态
  const last5m = c5m[c5m.length - 1];
  const prev5m = c5m[c5m.length - 2];
  const body5m = Math.abs(last5m.c - last5m.o);
  const upperWick5m = last5m.h - Math.max(last5m.c, last5m.o);
  const hasLongUpperWick5m = upperWick5m > body5m * 1.5 && upperWick5m > price * 0.002;
  const bearishEngulf5m = last5m.c < last5m.o && last5m.o > prev5m.c && last5m.c < prev5m.o;

  // 15m 形态
  const last15m = c15m[c15m.length - 1];
  const prev15m = c15m[c15m.length - 2];
  const body15m = Math.abs(last15m.c - last15m.o);
  const upperWick15m = last15m.h - Math.max(last15m.c, last15m.o);
  const hasLongUpperWick15m = upperWick15m > body15m * 1.5 && upperWick15m > price * 0.002;
  const bearishEngulf15m = last15m.c < last15m.o && last15m.o > prev15m.c && last15m.c < prev15m.o;

  // 4H
  const closes4h = c4h.map(c => c.c);
  const highs4h = c4h.map(c => c.h);
  const e20_4h = ema(closes4h, 20);
  const e50_4h = ema(closes4h, 50);
  const e200_4h = ema(closes4h, 200);
  const macd4h = macdCalc(closes4h);
  const n4h = closes4h.length - 1;
  const bearishEma4h = closes4h[n4h] < e20_4h[n4h] && e20_4h[n4h] < e50_4h[n4h] && e50_4h[n4h] < e200_4h[n4h];
  const macdDead4h = macd4h.macdLine[macd4h.macdLine.length - 1] < macd4h.sigLine[macd4h.sigLine.length - 1];
  const peaksH4 = [];
  for (let i = 1; i < highs4h.length - 1; i++) {
    if (highs4h[i] > highs4h[i - 1] && highs4h[i] > highs4h[i + 1]) peaksH4.push(highs4h[i]);
  }
  const lowerHighs4h = peaksH4.length >= 2 && peaksH4[peaksH4.length - 1] < peaksH4[peaksH4.length - 2];

  // ── 信号条件检测 ──
  const signals = [];

  if (price > resistance1h * 0.997 || price > bb1h.upper * 0.997)
    signals.push(`价格触及压力区（近高 $${resistance1h.toFixed(0)} / 布林上轨 $${bb1h.upper.toFixed(0)}）`);

  if (hasLongUpperWick5m) signals.push('5m K线出现长上影线（假突破信号）');
  if (bearishEngulf5m)    signals.push('5m K线出现吞没阴线（反转信号）');
  if (hasLongUpperWick15m) signals.push('15m K线出现长上影线（假突破信号）');
  if (bearishEngulf15m)   signals.push('15m K线出现吞没阴线（反转信号）');

  if (curRsi1h !== null && curRsi1h > 65)
    signals.push(`1H RSI 进入过热区（${curRsi1h.toFixed(1)}，>65）`);
  if (curRsi15m !== null && curRsi15m > 68)
    signals.push(`15m RSI 接近过热（${curRsi15m.toFixed(1)}，>68）`);

  if (curMacdHist1h !== null && prevMacdHist1h !== null) {
    if (curMacdHist1h > 0 && curMacdHist1h < prevMacdHist1h)
      signals.push('1H MACD 红柱缩短（上涨动能衰减）');
    if (curMacdHist1h < 0 && prevMacdHist1h > 0)
      signals.push('1H MACD 发生死叉');
  }

  if (lastVol1h < avgVol1h * 0.5)
    signals.push(`反弹缩量（当前成交量仅 ${(lastVol1h / avgVol1h * 100).toFixed(0)}% 均量）`);

  if (bearishEma4h) signals.push('4H EMA 空头排列（价格在 EMA20/50/200 全线下方）');
  if (macdDead4h)   signals.push('4H MACD 死叉（中期趋势偏空）');
  if (lowerHighs4h) signals.push('4H 低高点结构确认（下降趋势形态）');
  if (funding > 0.03) signals.push(`资金费率偏高（${funding.toFixed(4)}%，多头持仓成本上升）`);

  // ── 入场参数 ──
  const stopLoss = resistance1h * 1.005;
  const riskDist = stopLoss - price;
  const tp1 = price - riskDist * 1.8;
  const tp2 = price - riskDist * 3.0;
  const rr = (riskDist > 0) ? ((price - tp1) / riskDist).toFixed(1) : '0';

  const signalCount = signals.length;
  let strength = '无交易';
  let shouldAlert = false;
  if (signalCount >= MIN_SIGNALS) {
    if (signalCount >= 8)      { strength = '强'; shouldAlert = true; }
    else if (signalCount >= 6) { strength = '中'; shouldAlert = true; }
  } else if (signalCount >= 3) {
    strength = '弱';
  }

  if (parseFloat(rr) < 1.5) shouldAlert = false;

  return {
    sym,
    price,
    signals,
    signalCount,
    strength,
    shouldAlert,
    resistance: resistance1h.toFixed(0),
    bbUpper: bb1h.upper.toFixed(0),
    rsi1h: curRsi1h?.toFixed(1),
    rsi15m: curRsi15m?.toFixed(1),
    funding: funding.toFixed(4),
    bearishEma4h,
    stopLoss: stopLoss.toFixed(2),
    tp1: tp1.toFixed(2),
    tp2: tp2.toFixed(2),
    rr
  };
}

// ─── 格式化纯文本报告 ────────────────────────────────────

function formatTextReport(alerts, allResults, now) {
  const lines = [];
  lines.push(`🚨 做空信号预警`);
  lines.push(`时间：${now} UTC`);
  lines.push(`触发标的：${alerts.map(a => a.sym.replace('-USDT', '')).join('、')}`);
  lines.push('');

  for (const a of alerts) {
    const name = a.sym.replace('-USDT', '');
    lines.push(`━━━━━━━━━━━━━━━━━━━━`);
    lines.push(`【${name}】信号强度：${a.strength}（${a.signalCount} 个条件触发）`);
    lines.push(`当前价格：$${a.price.toFixed(2)}`);
    lines.push('');
    lines.push('触发条件：');
    a.signals.forEach((s, i) => lines.push(`  ${i + 1}. ${s}`));
    lines.push('');
    lines.push(`建议入场：$${(a.price * 0.999).toFixed(2)} – $${(a.price * 1.001).toFixed(2)}`);
    lines.push(`止损位置：$${a.stopLoss}（压力位上方 0.5%）`);
    lines.push(`第一止盈：$${a.tp1}`);
    lines.push(`第二止盈：$${a.tp2}`);
    lines.push(`盈亏比：${a.rr}:1`);
    lines.push('');
  }

  lines.push(`━━━━━━━━━━━━━━━━━━━━`);
  lines.push('⚠️ 风控提醒：');
  lines.push('  · 必须等 5m 或 15m 收线确认后再入场');
  lines.push('  · 禁止第一次触碰压力位时直接追空');
  lines.push('  · 单笔风险控制在账户权益 0.3%–1%');
  lines.push('  · 本预警由 CREAO 自动扫描，仅供参考，不构成投资建议');

  return lines.join('\n');
}

// ─── 币安广场文本（精简版，无表格）────────────────────────

function formatSquarePost(alerts, now) {
  const lines = [];
  lines.push(`【做空信号播报 ${now.slice(0, 10)}】`);
  lines.push('');
  lines.push('多周期技术扫描发现以下标的出现做空信号，供参考：');
  lines.push('');

  for (const a of alerts) {
    const name = a.sym.replace('-USDT', '');
    lines.push(`▌ ${name}  当前价 $${a.price.toFixed(2)}  信号强度：${a.strength}`);
    lines.push(`  已触发 ${a.signalCount} 个做空条件：`);
    // 只取前4条最关键的
    a.signals.slice(0, 4).forEach(s => lines.push(`  · ${s}`));
    lines.push(`  建议止损 $${a.stopLoss}，目标 $${a.tp1}，盈亏比 ${a.rr}:1`);
    lines.push('');
  }

  lines.push('策略说明：');
  lines.push('本信号基于 5m / 15m / 1H / 4H 四周期联合扫描，');
  lines.push('需满足 6 个以上技术条件（EMA排列、RSI过热、MACD死叉、K线反转形态、成交量、资金费率）才触发。');
  lines.push('');
  lines.push('入场原则：等待 5m 或 15m 收线确认，禁止在压力位第一次触碰时直接追空。');
  lines.push('');
  lines.push('以上内容仅为技术分析，不构成投资建议，请结合自身风险偏好操作。');
  lines.push('');
  lines.push('#加密货币 #BTC #ETH #SOL #合约交易 #技术分析');

  return lines.join('\n');
}

// ─── 发送邮件 ─────────────────────────────────────────────

async function sendEmail(subject, bodyText) {
  // 转为 HTML 但保留文本排版
  const html = '<pre style="font-family:monospace;font-size:14px;line-height:1.6;">'
    + bodyText.replace(/</g, '&lt;').replace(/>/g, '&gt;')
    + '</pre>';

  const args = JSON.stringify({
    to: [ALERT_EMAIL],
    subject,
    body: html,
    bodyType: 'html'
  });

  execFileSync('node', [GMAIL_SERVER, 'sendEmail', args], {
    stdio: ['ignore', 'pipe', 'pipe'],
    timeout: 30000
  });
}

// ─── 发布币安广场 ─────────────────────────────────────────

async function postToSquare(content) {
  if (!SQUARE_KEY) {
    console.log('  ⚠️  BINANCE_SQUARE_OPENAPI_KEY 未配置，跳过币安广场发布');
    return null;
  }

  return new Promise((resolve) => {
    const body = JSON.stringify({ bodyTextOnly: content });
    const options = {
      hostname: 'www.binance.com',
      path: '/bapi/composite/v1/public/pgc/openApi/content/add',
      method: 'POST',
      headers: {
        'X-Square-OpenAPI-Key': SQUARE_KEY,
        'Content-Type': 'application/json',
        'clienttype': 'binanceSkill',
        'Content-Length': Buffer.byteLength(body)
      }
    };

    const req = https.request(options, (res) => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => {
        try {
          const json = JSON.parse(d);
          if (json.code === '000000' && json.data?.id) {
            const url = `https://www.binance.com/square/post/${json.data.id}`;
            resolve({ success: true, url, id: json.data.id });
          } else {
            resolve({ success: false, code: json.code, message: json.message });
          }
        } catch (e) {
          resolve({ success: false, error: e.message });
        }
      });
    });
    req.on('error', e => resolve({ success: false, error: e.message }));
    req.write(body);
    req.end();
  });
}

// ─── 主流程 ───────────────────────────────────────────────

async function main() {
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  console.log(`\n[${now}] 🔍 扫描中（阈值：${MIN_SIGNALS} 个条件）...`);

  const targets = [
    { spot: 'BTC-USDT', swap: 'BTC-USDT-SWAP' },
    { spot: 'ETH-USDT', swap: 'ETH-USDT-SWAP' },
    { spot: 'SOL-USDT', swap: 'SOL-USDT-SWAP' }
  ];

  const results = await Promise.all(
    targets.map(t => analyzeSymbol(t.spot, t.swap).catch(e => {
      console.error(`[ERROR] ${t.spot}:`, e.message);
      return null;
    }))
  );

  const valid = results.filter(Boolean);

  // 打印扫描摘要
  for (const r of valid) {
    const icon = r.shouldAlert ? '🔴' : r.signalCount >= 3 ? '🟡' : '🟢';
    console.log(`  ${icon} ${r.sym.padEnd(12)} $${r.price.toFixed(2).padStart(10)}  ${r.strength}（${r.signalCount}/${MIN_SIGNALS}）`);
    if (r.signalCount > 0) console.log(`     └─ ${r.signals.slice(0, 3).join(' | ')}`);
  }

  const alertTargets = valid.filter(r => r.shouldAlert);

  if (alertTargets.length === 0) {
    console.log(`\n✅ 暂无有效做空信号（需满足 ${MIN_SIGNALS} 个条件）。\n`);
    return { alertCount: 0, results: valid };
  }

  console.log(`\n⚡ ${alertTargets.length} 个标的触发做空信号，发送预警...`);
  const subject = `🚨 做空信号预警 [${alertTargets.map(a => a.sym.replace('-USDT', '')).join('/')}] ${now}`;
  const report = formatTextReport(alertTargets, valid, now);
  const squarePost = formatSquarePost(alertTargets, now);

  // 并行发送邮件 + 广场
  const [emailResult, squareResult] = await Promise.allSettled([
    sendEmail(subject, report).then(() => ({ success: true })).catch(e => ({ success: false, error: e.message })),
    postToSquare(squarePost)
  ]);

  // 打印结果
  const emailOk = emailResult.status === 'fulfilled' && emailResult.value?.success;
  const squareOk = squareResult.status === 'fulfilled' && squareResult.value?.success;

  console.log(`  📧 邮件：${emailOk ? `✅ 已发送至 ${ALERT_EMAIL}` : `❌ 失败 ${emailResult.value?.error || ''}`}`);
  if (squareResult.value?.success) {
    console.log(`  🟡 币安广场：✅ 已发布 → ${squareResult.value.url}`);
  } else if (squareResult.value) {
    console.log(`  🟡 币安广场：❌ 失败 code=${squareResult.value?.code} ${squareResult.value?.message || squareResult.value?.error || ''}`);
  }

  console.log(`\n[${new Date().toISOString().replace('T', ' ').slice(0, 19)}] 扫描完成。\n`);
  return {
    alertCount: alertTargets.length,
    results: valid,
    squareUrl: squareResult.value?.url || null
  };
}

main().catch(console.error);
