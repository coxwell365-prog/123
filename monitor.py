import ccxt
import pandas as pd
import requests
import os

# 配置
FEISHU_KEY = os.environ.get('WECHAT_KEY') 
FEISHU_URL = f"https://open.feishu.cn/open-apis/bot/v2/hook/{FEISHU_KEY}"
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT']
exchange = ccxt.binance()

def send_feishu_msg(text):
    payload = {"msg_type": "text", "content": {"text": text}}
    try:
        res = requests.post(FEISHU_URL, json=payload)
        print(f"飞书推送状态: {res.json()}")
    except Exception as e:
        print(f"推送失败: {e}")

def get_signals(symbol):
    # 获取K线数据
    ohlcv_4h = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=100)
    df_4h = pd.DataFrame(ohlcv_4h, columns=['t', 'o', 'h', 'l', 'c', 'v'])
    
    # 手动计算 EMA20
    ema_20_4h = df_4h['c'].ewm(span=20, adjust=False).mean().iloc[-1]
    last_price = df_4h['c'].iloc[-1]
    trend = "看涨 📈" if last_price > ema_20_4h else "看跌 📉"

    ohlcv_15m = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=100)
    df_15m = pd.DataFrame(ohlcv_15m, columns=['t', 'o', 'h', 'l', 'c', 'v'])
    
    # 手动计算 RSI
    delta = df_15m['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_15m = 100 - (100 / (1 + rs)).iloc[-1]

    signal = "观望"
    if trend == "看涨 📈" and rsi_15m < 35:
        signal = "🚀 多头入场机会 (趋势支撑+低位回踩)"
    elif trend == "看跌 📉" and rsi_15m > 65:
        signal = "⚠️ 空头入场机会 (趋势压制+反弹受阻)"
    return trend, signal, last_price, rsi_15m

def detect_walls(symbol):
    ob = exchange.fetch_order_book(symbol, limit=20)
    avg_vol = sum([b[1] for b in ob['bids']]) / 20
    walls = []
    for price, vol in ob['bids'][:10]:
        if vol > avg_vol * 8: walls.append(f"🟢 支撑: {price}")
    for price, vol in ob['asks'][:10]:
        if vol > avg_vol * 8: walls.append(f"🔴 压力: {price}")
    return walls

def run():
    report = "📊 【币圈行情异动预警】\n"
    has_action = False
    for symbol in SYMBOLS:
        try:
            trend, signal, price, rsi = get_signals(symbol)
            walls = detect_walls(symbol)
            if "机会" in signal or walls:
                has_action = True
                wall_info = ", ".join(walls) if walls else "无显著大单"
                report += f"\n🔥 {symbol}\n价格: {price}\n趋势: {trend}\n信号: {signal}\nRSI: {rsi:.2f}\n大单流: {wall_info}\n"
        except Exception as e:
            print(f"分析 {symbol} 出错: {e}")
    if has_action:
        send_feishu_msg(report)
    else:
        print("当前无显著信号。")

if __name__ == "__main__":
    run()
