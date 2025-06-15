# config.py

# ==============================================================================
# 1. USTAWIENIA OGÓLNE
# ==============================================================================
# Ustaw na True, aby połączyć się z Binance Spot Testnet (do testowania bez ryzyka)
# Ustaw na False, aby handlować na prawdziwym rynku
USE_TESTNET = False

SYMBOL = 'BTCUSDC'
INTERVAL = '15m'  # Interwał strategii

# ==============================================================================
# 2. STRATEGIA PRZECIĘCIA EMA (Exponential Moving Average)
# ==============================================================================
EMA_SHORT = 30
EMA_LONG = 60

# ==============================================================================
# 3. STRATEGIA RSI (Relative Strength Index)
# ==============================================================================
RSI_PERIOD = 21
RSI_BUY_LEVEL = 50   # Poziom, którego przecięcie w górę przez RSI jest sygnałem kupna
RSI_SELL_LEVEL = 40  # Poziom, którego przecięcie w dół przez RSI jest sygnałem sprzedaży

# ==============================================================================
# 4. ZARZĄDZANIE RYZYKIEM
# ==============================================================================

# 4.1 Trailing Stop Loss (oparty na ATR)
USE_TRAILING_STOP = True
ATR_PERIOD = 14  # Okres ATR dla obliczania zmienności
TRAILING_SL_ATR_MULTIPLIER = 2.25 # Mnożnik ATR dla Trailing Stop Lossa

# 4.2 Dynamiczna Wielkość Ryzyka (oparta na ADX)
USE_DYNAMIC_RISK = True
ADX_PERIOD_FOR_RISK = 14  # Okres ADX używany do oceny siły trendu
RISK_ADX_THRESHOLD = 25    # Próg ADX, powyżej którego trend uznajemy za silny
RISK_PER_TRADE_HIGH = 0.125 # 12.5% ryzyka kapitału na transakcję przy silnym trendzie
RISK_PER_TRADE_LOW = 0.03   # 3% ryzyka kapitału na transakcję przy słabym trendzie

# ==============================================================================
# 5. FILTR REŻIMU RYNKU (GLOBALNY TREND)
# ==============================================================================
# Używa nadrzędnego filtra opartego na długoterminowej średniej kroczącej (SMA)
# na interwale dziennym, aby unikać otwierania pozycji pod prąd głównego trendu.
USE_MARKET_REGIME_FILTER = True
# Okres SMA na interwale dziennym. Optymalizacja na danych 3-letnich
# wykazała, że 50 dni daje najlepsze rezultaty.
REGIME_FILTER_PERIOD = 50

# Filtry Sygnałów
USE_ADX_FILTER = True
ADX_PERIOD = 14
ADX_THRESHOLD = 25

USE_VOLUME_FILTER = True

# Zarządzanie ryzykiem
SL_ATR_MULTIPLIER = 1.5
TP_SL_RATIO = 1.5

# Zarządzanie ryzykiem
VOLUME_PERIOD = 20 