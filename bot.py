import os
import time
import logging
import pandas as pd
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException
from datetime import datetime, timedelta
import pandas_ta as ta
import telegram
from dotenv import load_dotenv
import json

# Importuj konfigurację
from config import *

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_log.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("binance_bot")

# Załadowanie zmiennych środowiskowych
load_dotenv()

# Konfiguracja API
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

STATE_FILE = "state.json"

class BinanceTradingBot:
    def __init__(self):
        self.client = Client(API_KEY, API_SECRET)
        
        # Przełącz na Testnet, jeśli jest włączony w konfiguracji
        if USE_TESTNET:
            self.client.API_URL = 'https://testnet.binance.vision/api'
            logger.info("Łączenie z Binance Spot Testnet...")
        
        self.telegram_bot = None
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            self.telegram_bot = telegram.Bot(token=TELEGRAM_TOKEN)
        
        # Inicjalizacja stanu z wartościami domyślnymi
        self.in_position = False
        self.position_side = None
        self.entry_price = 0
        self.position_size_usdc = 0 # Przechowujemy wartość pozycji w USDC
        self.stop_loss = 0
        self.last_summary_date = datetime.now().date().isoformat()
        
        self._load_state()
        
        logger.info(f"Bot zainicjalizowany dla {SYMBOL} na interwale {INTERVAL}")
        if not self.in_position:
             self._send_telegram_message("🤖 Bot został uruchomiony i szuka okazji do wejścia.")
        else:
             self._send_telegram_message(f"🤖 Bot został zrestartowany i kontynuuje zarządzanie pozycją {self.position_side} otwartą po cenie {self.entry_price:.4f}.")

    def _save_state(self):
        state = {
            "in_position": self.in_position,
            "position_side": self.position_side,
            "entry_price": self.entry_price,
            "position_size_usdc": self.position_size_usdc,
            "stop_loss": self.stop_loss,
            "last_summary_date": self.last_summary_date
        }
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f)
            logger.info("Stan bota został zapisany.")
        except IOError as e:
            logger.error(f"Błąd zapisu stanu: {e}")

    def _load_state(self):
        if not os.path.exists(STATE_FILE):
            logger.info("Plik stanu nie istnieje. Uruchamiam z domyślnym stanem.")
            return
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            self.in_position = state.get("in_position", False)
            self.position_side = state.get("position_side")
            self.entry_price = state.get("entry_price", 0)
            self.position_size_usdc = state.get("position_size_usdc", 0)
            self.stop_loss = state.get("stop_loss", 0)
            self.last_summary_date = state.get("last_summary_date", datetime.now().date().isoformat())
            logger.info("Stan bota został wczytany.")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Błąd wczytywania stanu: {e}. Używam stanu domyślnego.")

    def _send_telegram_message(self, message):
        if self.telegram_bot and TELEGRAM_CHAT_ID:
            try:
                self.telegram_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            except Exception as e:
                logger.error(f"Błąd wysyłania wiadomości Telegram: {e}")

    def _get_account_balance(self, quote_asset='USDC'):
        try:
            account = self.client.get_account()
            for balance in account['balances']:
                if balance['asset'] == quote_asset:
                    return float(balance['free'])
            logger.warning(f"Nie znaleziono salda dla {quote_asset}. Zwracam 0.")
            return 0
        except BinanceAPIException as e:
            logger.error(f"Błąd pobierania stanu konta: {e}")
            return 0

    def _fetch_data(self, limit=200):
        try:
            klines = self.client.get_klines(symbol=SYMBOL, interval=INTERVAL, limit=limit)
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            df_daily = None
            if USE_MARKET_REGIME_FILTER:
                start_date_str = (datetime.utcnow() - timedelta(days=REGIME_FILTER_PERIOD * 2)).strftime("%d %b, %Y")
                daily_klines = self.client.get_historical_klines(SYMBOL, Client.KLINE_INTERVAL_1DAY, start_date_str)
                df_daily = pd.DataFrame(daily_klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df_daily[col] = pd.to_numeric(df_daily[col])
                df_daily['timestamp'] = pd.to_datetime(df_daily['timestamp'], unit='ms').dt.date
                df_daily.set_index('timestamp', inplace=True)
            
            return df, df_daily
        except BinanceAPIException as e:
            logger.error(f"Błąd pobierania danych z Binance: {e}")
            return None, None
            
    def _calculate_indicators(self, df, df_daily=None):
        try:
            df.set_index('timestamp', inplace=True)
            df['ema_short'] = ta.ema(df['close'], length=EMA_SHORT)
            df['ema_long'] = ta.ema(df['close'], length=EMA_LONG)
            df['rsi'] = ta.rsi(df['close'], length=RSI_PERIOD)
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=ATR_PERIOD)
            
            if USE_DYNAMIC_RISK:
                adx_df = ta.adx(df['high'], df['low'], df['close'], length=ADX_PERIOD_FOR_RISK)
                if adx_df is not None and not adx_df.empty:
                    df['adx'] = adx_df[f'ADX_{ADX_PERIOD_FOR_RISK}']

            if USE_MARKET_REGIME_FILTER and df_daily is not None and not df_daily.empty:
                df_daily['regime_sma'] = ta.sma(df_daily['close'], length=REGIME_FILTER_PERIOD)
                
                df['daily_close'] = df.index.to_series().dt.date.map(df_daily['close'])
                df['daily_regime_sma'] = df.index.to_series().dt.date.map(df_daily['regime_sma'])
            
            df.reset_index(inplace=True)
            df.dropna(inplace=True)
            return df
        except Exception as e:
            logger.error(f"Błąd obliczania wskaźników: {e}")
            return None

    def _check_buy_signal(self, df):
        if len(df) < 2: return False
        last = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Debug logging
        logger.info(f"Sprawdzanie sygnału BUY:")
        logger.info(f"  EMA30: {last['ema_short']:.4f}, EMA60: {last['ema_long']:.4f}")
        logger.info(f"  RSI poprzedni: {previous['rsi']:.2f}, RSI aktualny: {last['rsi']:.2f}")
        
        if USE_MARKET_REGIME_FILTER:
            if 'daily_regime_sma' not in last or pd.isna(last['daily_regime_sma']) or last['daily_close'] < last['daily_regime_sma']:
                logger.info(f"  Market regime filter: FAIL (daily_close: {last.get('daily_close', 'N/A'):.4f}, regime_sma: {last.get('daily_regime_sma', 'N/A'):.4f})")
                return False
            else:
                logger.info(f"  Market regime filter: PASS (daily_close: {last['daily_close']:.4f} >= regime_sma: {last['daily_regime_sma']:.4f})")

        trend_ok = last['ema_short'] > last['ema_long']
        rsi_level = RSI_BUY_LEVEL_ALT if USE_ALTERNATIVE_RSI else RSI_BUY_LEVEL
        rsi_signal = previous['rsi'] < rsi_level and last['rsi'] >= rsi_level
        
        logger.info(f"  Trend OK: {trend_ok}")
        logger.info(f"  RSI signal: {rsi_signal} (using level: {rsi_level})")
        logger.info(f"  Final BUY signal: {trend_ok and rsi_signal}")
        
        return trend_ok and rsi_signal

    def _check_sell_signal(self, df):
        if len(df) < 2: return False
        last = df.iloc[-1]
        previous = df.iloc[-2]

        # Debug logging
        logger.info(f"Sprawdzanie sygnału SELL:")
        logger.info(f"  EMA30: {last['ema_short']:.4f}, EMA60: {last['ema_long']:.4f}")
        logger.info(f"  RSI poprzedni: {previous['rsi']:.2f}, RSI aktualny: {last['rsi']:.2f}")

        if USE_MARKET_REGIME_FILTER:
            if 'daily_regime_sma' not in last or pd.isna(last['daily_regime_sma']) or last['daily_close'] > last['daily_regime_sma']:
                logger.info(f"  Market regime filter: FAIL (daily_close: {last.get('daily_close', 'N/A'):.4f}, regime_sma: {last.get('daily_regime_sma', 'N/A'):.4f})")
                return False
            else:
                logger.info(f"  Market regime filter: PASS (daily_close: {last['daily_close']:.4f} <= regime_sma: {last['daily_regime_sma']:.4f})")

        trend_ok = last['ema_short'] < last['ema_long']
        rsi_level = RSI_SELL_LEVEL_ALT if USE_ALTERNATIVE_RSI else RSI_SELL_LEVEL
        rsi_signal = previous['rsi'] > rsi_level and last['rsi'] <= rsi_level
        
        logger.info(f"  Trend OK: {trend_ok}")
        logger.info(f"  RSI signal: {rsi_signal} (using level: {rsi_level})")
        logger.info(f"  Final SELL signal: {trend_ok and rsi_signal}")
        
        return trend_ok and rsi_signal

    def _calculate_position_size_usdc(self, balance, entry_price, stop_loss_price, adx_value):
        if entry_price == stop_loss_price: return 0
        
        risk_per_trade = RISK_PER_TRADE_LOW
        if USE_DYNAMIC_RISK:
            risk_per_trade = RISK_PER_TRADE_HIGH if adx_value > RISK_ADX_THRESHOLD else RISK_PER_TRADE_LOW
            logger.info(f"Dynamiczne ryzyko aktywne. ADX={adx_value:.2f}, Ryzyko={risk_per_trade*100:.1f}%")

        risk_amount = balance * risk_per_trade
        sl_distance_percent = abs(entry_price - stop_loss_price) / entry_price
        
        position_size_usdc = risk_amount / sl_distance_percent
        return position_size_usdc

    def _execute_market_order(self, side, quantity_usdc):
        try:
            # Binance API dla zleceń MARKET wymaga `quoteOrderQty` dla ilości w USDC
            order = self.client.create_order(
                symbol=SYMBOL,
                side=side,
                type='MARKET',
                quoteOrderQty=round(quantity_usdc, 2) # Zaokrąglij do 2 miejsc po przecinku dla USDC
            )
            logger.info(f"Zlecenie wykonane: {order}")
            
            # Pobierz rzeczywistą cenę wejścia i ilość z odpowiedzi
            entry_price = float(order['fills'][0]['price']) if order['fills'] else float(order['price'])
            executed_qty = float(order['executedQty'])
            
            return entry_price, executed_qty

        except BinanceAPIException as e:
            logger.error(f"Błąd wykonania zlecenia na Binance: {e}")
            self._send_telegram_message(f"⚠️ KRYTYCZNY BŁĄD ZLECENIA: {e}")
            return None, None
            
    def _open_position(self, side, df):
        last_row = df.iloc[-1]
        current_price = last_row['close']
        atr = last_row['atr']
        adx = last_row.get('adx', 0)

        balance = self._get_account_balance()
        if balance <= 10: # Minimalna kwota do handlu
            logger.warning(f"Niewystarczające środki na koncie ({balance:.2f} USDC). Handel wstrzymany.")
            return

        # Ustaw SL na podstawie ATR
        sl_price = current_price - atr * TRAILING_SL_ATR_MULTIPLIER if side == 'BUY' else current_price + atr * TRAILING_SL_ATR_MULTIPLIER
        
        # Oblicz wielkość pozycji
        position_size_usdc = self._calculate_position_size_usdc(balance, current_price, sl_price, adx)
        if position_size_usdc < 10: # Minimalna wartość zlecenia na Binance
            logger.warning(f"Obliczona wielkość pozycji ({position_size_usdc:.2f} USDC) jest poniżej minimum. Nie otwieram pozycji.")
            return
        
        # Wykonaj zlecenie
        entry_price, executed_qty = self._execute_market_order(side, position_size_usdc)
        
        if entry_price is not None and executed_qty > 0:
            self.in_position = True
            self.position_side = side
            self.entry_price = entry_price
            self.position_size_usdc = executed_qty * entry_price
            self.stop_loss = sl_price

            self._save_state()
            msg = f"✅ OTWARTA POZYCJA {side} | Cena: {self.entry_price:.4f} | Wielkość: {self.position_size_usdc:.2f} USDC | Stop Loss: {self.stop_loss:.4f}"
            logger.info(msg)
            self._send_telegram_message(msg)

    def _close_position(self, exit_price):
        side = 'SELL' if self.position_side == 'BUY' else 'BUY'
        
        # Pobierz aktualną ilość BASE asset (np. BTC) do zamknięcia
        base_asset = SYMBOL.replace('USDC', '')
        try:
            qty_to_close = float(self.client.get_asset_balance(asset=base_asset)['free'])
        except BinanceAPIException as e:
            logger.error(f"Nie udało się pobrać salda {base_asset} do zamknięcia pozycji: {e}")
            self._send_telegram_message(f"⚠️ BŁĄD KRYTYCZNY: Nie mogę pobrać salda {base_asset} do zamknięcia pozycji!")
            return # Nie resetuj stanu, jeśli nie wiemy, czy pozycja jest zamknięta

        # Wykonaj zlecenie zamknięcia
        self.client.create_order(symbol=SYMBOL, side=side, type='MARKET', quantity=qty_to_close)

        pnl = (exit_price - self.entry_price) if self.position_side == 'BUY' else (self.entry_price - exit_price)
        pnl_percent = (pnl / self.entry_price) * 100
        pnl_usdc = self.position_size_usdc * (pnl_percent / 100)
        
        msg = f"❌ ZAMKNIĘTA POZYCJA {self.position_side} | Cena wyjścia: {exit_price:.4f} | Zysk/Strata: {pnl_usdc:.2f} USDC ({pnl_percent:.2f}%)"
        logger.info(msg)
        self._send_telegram_message(msg)
        
        # Resetuj stan
        self.in_position = False
        self.position_side = None
        self.entry_price = 0
        self.position_size_usdc = 0
        self.stop_loss = 0
        self._save_state()

    def _monitor_and_manage_position(self):
        logger.info(f"Rozpoczynam monitorowanie otwartej pozycji {self.position_side}...")
        
        while self.in_position:
            try:
                # Pobierz najnowszą cenę i wskaźniki
                df, _ = self._fetch_data(limit=100) # Pobierz mniej danych, tylko do TSL
                if df is None or df.empty:
                    time.sleep(60)
                    continue

                df_with_indicators = self._calculate_indicators(df)
                if df_with_indicators is None or df_with_indicators.empty:
                    time.sleep(60)
                    continue
                    
                last_row = df_with_indicators.iloc[-1]
                current_price = last_row['close']
                current_atr = last_row['atr']
                
                # Sprawdź warunek Stop Loss
                if (self.position_side == 'BUY' and current_price <= self.stop_loss) or \
                   (self.position_side == 'SELL' and current_price >= self.stop_loss):
                    logger.info(f"Warunek Stop Loss ({self.stop_loss:.4f}) został spełniony przy cenie {current_price:.4f}.")
                    self._close_position(self.stop_loss)
                    break # Wyjdź z pętli monitorowania

                # Zaktualizuj Trailing Stop Loss
                if USE_TRAILING_STOP:
                    new_sl = 0
                    if self.position_side == 'BUY':
                        new_sl = max(self.stop_loss, current_price - current_atr * TRAILING_SL_ATR_MULTIPLIER)
                    else: # SELL
                        new_sl = min(self.stop_loss, current_price + current_atr * TRAILING_SL_ATR_MULTIPLIER)
                    
                    if new_sl != self.stop_loss:
                        self.stop_loss = new_sl
                        self._save_state()
                        logger.info(f"Trailing Stop Loss zaktualizowany do: {self.stop_loss:.4f}")

                time.sleep(60) # Sprawdzaj co 60 sekund

            except Exception as e:
                logger.error(f"Wystąpił błąd w pętli monitorującej: {e}")
                self._send_telegram_message(f"⚠️ Błąd w pętli monitorującej: {e}")
                time.sleep(60)

    def _send_daily_summary(self):
        today_str = datetime.now().date().isoformat()
        if today_str > self.last_summary_date:
            logger.info("Nowy dzień, wysyłanie podsumowania...")
            try:
                balance = self._get_account_balance()
                msg = f"☀️ Podsumowanie dzienne: Aktualne saldo konta USDC wynosi: {balance:.2f} USDC."
                self._send_telegram_message(msg)
                
                self.last_summary_date = today_str
                self._save_state()
            except Exception as e:
                logger.error(f"Nie udało się wysłać dziennego podsumowania: {e}")

    def run(self):
        while True:
            try:
                self._send_daily_summary() # Sprawdź, czy wysłać podsumowanie

                if self.in_position:
                    self._monitor_and_manage_position()
                else:
                    # Logika szukania wejścia
                    now = datetime.utcnow()
                    minutes = now.minute
                    seconds = now.second
                    
                    # Sprawdzaj sygnały w pierwszych 2 minutach po zamknięciu świecy 15-minutowej
                    # To daje większe okno na sprawdzenie sygnałów w przypadku problemów z API
                    if minutes % 15 <= 1:  # 0 lub 1 minuta po zamknięciu świecy
                        logger.info(f"Sprawdzanie sygnałów na nowej świecy (minuta {minutes})...")
                        df, df_daily = self._fetch_data()
                        if df is not None:
                            df_with_indicators = self._calculate_indicators(df, df_daily)
                            if df_with_indicators is not None and not df_with_indicators.empty:
                                if self._check_buy_signal(df_with_indicators):
                                    logger.info("Wykryto sygnał KUPNA.")
                                    self._open_position('BUY', df_with_indicators)
                                elif self._check_sell_signal(df_with_indicators):
                                    logger.info("Wykryto sygnał SPRZEDAŻY.")
                                    self._open_position('SELL', df_with_indicators)
                        
                        # Po sprawdzeniu sygnałów, czekaj do następnego okna
                        time.sleep(60)  # Czekaj minutę przed następnym sprawdzeniem
                    else:
                        # Uśpij bota do następnej świecy
                        time_to_sleep = (15 - (minutes % 15)) * 60 - seconds
                        logger.info(f"Brak pozycji. Czekam {time_to_sleep:.0f} sekund do następnej świecy.")
                        time.sleep(max(60, time_to_sleep))  # Minimum 60 sekund
            
            except KeyboardInterrupt:
                logger.info("Zatrzymywanie bota...")
                self._save_state()
                break
            except Exception as e:
                logger.critical(f"KRYTYCZNY BŁĄD w głównej pętli: {e}", exc_info=True)
                self._send_telegram_message(f"🚨 KRYTYCZNY BŁĄD BOTA: {e}")
                time.sleep(60)

if __name__ == "__main__":
    bot = BinanceTradingBot()
    bot.run()
