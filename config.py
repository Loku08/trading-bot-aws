# config.py

# Parametry strategii
SYMBOL = 'BTCUSDC'
INTERVAL = '1m'  # 1-minutowy interwał

# Wskaźniki
EMA_SHORT = 9
EMA_LONG = 21
RSI_PERIOD = 14
ATR_PERIOD = 14
VOLUME_PERIOD = 20
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65

# Zarządzanie ryzykiem
SL_ATR_MULTIPLIER = 1.5
TP_SL_RATIO = 1.5
RISK_PER_TRADE = 0.05  # 5% kapitału na transakcję
MAX_DAILY_RISK = 0.1   # 10% maksymalnego ryzyka dziennego 