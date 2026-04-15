import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import os

# 从 GitHub Secrets 获取飞书 Token (Name 设为 WECHAT_KEY 即可)
FEISHU_KEY = os.environ.get('WECHAT_KEY') 
FEISHU_URL = f"https://open.feishu.cn/open-apis/bot/v2/hook/{FEISHU_KEY}"

# 监控配置
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT']
exchange = ccxt.binance()

def send_feishu_msg(text):
    """发送飞书文本消息"""
    payload = {"msg_type": "text", "content": {"text": text}}
    try:
        res = requests.post(FEISHU_URL, json=payload)
        print(f"飞书推送状态: {res.json()}")
    except Exception as e:
        print(f"推送失败: {e}")

def get_signals(symbol):
    """多周期验证：4H 均线趋势 + 15M RSI 找买卖点"""
    # 1. 4H 趋势判断
    ohlcv_4h = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=50)
    df_4h = pd.DataFrame(ohlcv_4h, columns=['t', 'o', 'h', 'l', 'c', 'v'])
    ema_20_4h = ta.ema(df_4h['c'], length=20).iloc[-1]
    last_price = df_4h['c'].iloc[-1]
    trend = "看涨 📈" if last_price > ema_20_4h else "看跌 📉"

    # 2. 15M RSI 信号
    ohlcv_15m = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
    df_15m = pd.DataFrame(ohlcv_15m, columns=['t', 'o', 'h', 'l', 'c', 'v'])
    rsi_15m = ta.rsi(df_15m['c'], length=14).iloc[-1]

    signal = "观望"
    # 策略：顺大势，逆小势（4H看涨时，15M超卖买入）
    if trend == "看涨 📈" and rsi_15m < 35:
        signal = "🚀 多头入场机会 (趋势支撑+低位回踩)"
    elif trend == "看跌 📉" and rsi_15m > 65:
        signal = "⚠️ 空头入场机会 (趋势压制+反弹受阻)"
    return trend, signal, last_price, rsi_15m

def detect_walls(symbol):
    """订单流监控：识别大于平均值 8 倍的大单墙"""
    ob = exchange.fetch_order_book(symbol, limit=20)
    avg_vol = sum([b[1] for b in ob['bids']]) / 20
    walls = []
    # 检查买盘(支撑)和卖盘(压力)
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
            
            # 只有出现交易信号或大单墙时才汇总报告
            if "机会" in signal or walls:
                has_action = True
                wall_info = ", ".join(walls) if walls else "无显著大单"
                report += f"\n🔥 {symbol}\n价格: {price}\n趋势: {trend}\n信号: {signal}\nRSI: {rsi:.2f}\n大单流: {wall_info}\n"
        except Exception as e:
            print(f"分析 {symbol} 出错: {e}")

    if has_action:
        send_feishu_msg(report)
    else:
        print("当前无显著信号，跳过推送。")

if __name__ == "__main__":
    run()
