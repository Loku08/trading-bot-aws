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

# OPCJA 1: Obecna strategia (przecięcie konkretnych poziomów)
RSI_BUY_LEVEL = 50   # Poziom, którego przecięcie w górę przez RSI jest sygnałem kupna
RSI_SELL_LEVEL = 40  # Poziom, którego przecięcie w dół przez RSI jest sygnałem sprzedaży

# OPCJA 2: Alternatywna strategia (bardziej czuła na sygnały)
# Możesz przełączyć się na tę strategię jeśli obecna daje za mało sygnałów
USE_ALTERNATIVE_RSI = False  # Ustaw na True aby użyć alternatywnej strategii
RSI_BUY_LEVEL_ALT = 60      # Wyższy poziom dla częstszych sygnałów kupna
RSI_SELL_LEVEL_ALT = 30     # Niższy poziom dla częstszych sygnałów sprzedaży

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
# BACKTEST POKAZAŁ: +150.79% zysku z filtrem vs +89.77% bez filtru!
USE_MARKET_REGIME_FILTER = True  # Przywrócone na True - backtest potwierdził skuteczność
# Okres SMA na interwale dziennym. Optymalizacja na danych 3-letnich
# wykazała, że 50 dni daje najlepsze rezultaty.
REGIME_FILTER_PERIOD = 50

# ==============================================================================
# UWAGA: Poniższe filtry są zdefiniowane ale NIE SĄ OBECNIE IMPLEMENTOWANE w bot.py
# Zostały celowo wykomentowane aby uniknąć pomyłek
# ==============================================================================

# # Filtry Sygnałów - NIEIMPLEMENTOWANE
# USE_ADX_FILTER = True
# ADX_PERIOD = 14
# ADX_THRESHOLD = 25

# USE_VOLUME_FILTER = True
# VOLUME_PERIOD = 20 

# # Zarządzanie ryzykiem - NIEIMPLEMENTOWANE  
# SL_ATR_MULTIPLIER = 1.5  # Nie używany - używany jest TRAILING_SL_ATR_MULTIPLIER
# TP_SL_RATIO = 1.5        # Nie używany - brak implementacji take profit

# ==============================================================================
# 6. USTAWIENIA BACKTESTU
# ==============================================================================
INITIAL_CAPITAL = 1000  # Początkowy kapitał do backtestu w USDC

# Parametry do optymalizacji (używane tylko w trybie optimize)
OPTIMIZATION_PARAMS = {
    'EMA_SHORT': [20, 30, 40],
    'EMA_LONG': [50, 60, 70],
    'RSI_PERIOD': [14, 21, 28],
    'RSI_BUY_LEVEL': [45, 50, 55],
    'RSI_SELL_LEVEL': [35, 40, 45],
    'TRAILING_SL_ATR_MULTIPLIER': [1.5, 2.0, 2.5, 3.0],
    'REGIME_FILTER_PERIOD': [30, 50, 70]
}