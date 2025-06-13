import os
import time
import logging
import pandas as pd
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
logger = logging.getLogger("binance_scalping_bot")

# Załadowanie zmiennych środowiskowych
load_dotenv()

# Konfiguracja API
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

STATE_FILE = "state.json"

class BinanceScalpingBot:
    def __init__(self):
        self.client = Client(API_KEY, API_SECRET)
        self.telegram_bot = None
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            self.telegram_bot = telegram.Bot(token=TELEGRAM_TOKEN)
        
        # Domyślny stan bota
        self.active = True
        self.in_position = False
        self.position_side = None
        self.entry_price = 0
        self.position_size = 0
        self.stop_loss = 0
        self.take_profit = 0
        self.daily_pl = 0
        self.daily_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.last_day_reset = datetime.now().date().isoformat()
        
        self._load_state()
        
        logger.info(f"Bot zainicjalizowany dla {SYMBOL} na interwale {INTERVAL}")
        self._send_telegram_message("🤖 Bot został uruchomiony!")

    def _save_state(self):
        """Zapisuje stan bota do pliku JSON."""
        state = {
            "in_position": self.in_position,
            "position_side": self.position_side,
            "entry_price": self.entry_price,
            "position_size": self.position_size,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "daily_pl": self.daily_pl,
            "daily_trades": self.daily_trades,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "last_day_reset": self.last_day_reset,
        }
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f)
            logger.info("Stan bota został zapisany.")
        except IOError as e:
            logger.error(f"Błąd zapisu stanu: {e}")

    def _load_state(self):
        """Wczytuje stan bota z pliku JSON."""
        if not os.path.exists(STATE_FILE):
            logger.info("Plik stanu nie istnieje. Uruchamiam z domyślnym stanem.")
            return
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            self.in_position = state.get("in_position", False)
            self.position_side = state.get("position_side")
            self.entry_price = state.get("entry_price", 0)
            self.position_size = state.get("position_size", 0)
            self.stop_loss = state.get("stop_loss", 0)
            self.take_profit = state.get("take_profit", 0)
            self.daily_pl = state.get("daily_pl", 0)
            self.daily_trades = state.get("daily_trades", 0)
            self.successful_trades = state.get("successful_trades", 0)
            self.failed_trades = state.get("failed_trades", 0)
            self.last_day_reset = state.get("last_day_reset", datetime.now().date().isoformat())
            logger.info("Stan bota został wczytany.")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Błąd wczytywania stanu: {e}. Używam stanu domyślnego.")

    def _send_telegram_message(self, message):
        """Wysyła powiadomienie przez Telegram"""
        if self.telegram_bot and TELEGRAM_CHAT_ID:
            try:
                self.telegram_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            except Exception as e:
                logger.error(f"Błąd wysyłania wiadomości Telegram: {e}")
    
    def _get_account_balance(self):
        """Pobiera stan konta USDC"""
        try:
            account = self.client.get_account()
            for balance in account['balances']:
                if balance['asset'] == 'USDC':
                    return float(balance['free'])
            return 0
        except BinanceAPIException as e:
            logger.error(f"Błąd pobierania stanu konta: {e}")
            return 0
    
    def _fetch_data(self, limit=100):
        """Pobiera dane historyczne"""
        try:
            klines = self.client.get_klines(symbol=SYMBOL, interval=INTERVAL, limit=limit)
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except BinanceAPIException as e:
            logger.error(f"Błąd pobierania danych: {e}")
            return None
    
    def _calculate_indicators(self, df):
        """Oblicza wskaźniki techniczne"""
        try:
            df['ema_short'] = ta.ema(df['close'], length=EMA_SHORT)
            df['ema_long'] = ta.ema(df['close'], length=EMA_LONG)
            df['rsi'] = ta.rsi(df['close'], length=RSI_PERIOD)
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=ATR_PERIOD)
            df['vol_ma'] = df['volume'].rolling(window=VOLUME_PERIOD).mean()
            return df
        except Exception as e:
            logger.error(f"Błąd obliczania wskaźników: {e}")
            return df
    
    def _check_buy_signal(self, df):
        """Sprawdza sygnał kupna"""
        last = df.iloc[-1]
        return last['ema_short'] > last['ema_long'] and last['rsi'] < RSI_OVERSOLD and last['volume'] > last['vol_ma']

    def _check_sell_signal(self, df):
        """Sprawdza sygnał sprzedaży"""
        last = df.iloc[-1]
        previous = df.iloc[-2]
        return last['ema_short'] < last['ema_long'] and last['rsi'] > RSI_OVERBOUGHT and last['volume'] < previous['volume']

    def _calculate_position_size(self, entry_price, stop_loss_price):
        """Oblicza wielkość pozycji na podstawie ryzyka"""
        balance = self._get_account_balance()
        if balance == 0: return 0
        
        risk_amount = balance * RISK_PER_TRADE
        sl_distance_percent = abs(entry_price - stop_loss_price) / entry_price
        
        if sl_distance_percent == 0: return 0
        
        position_value = risk_amount / sl_distance_percent
        
        if self.daily_pl < -balance * MAX_DAILY_RISK:
            logger.warning("Osiągnięto dzienny limit strat. Handel wstrzymany na dziś.")
            return 0
        
        # Pobranie informacji o symbolu, aby uzyskać precyzję ilości
        info = self.client.get_symbol_info(SYMBOL)
        step_size = float([f['stepSize'] for f in info['filters'] if f['filterType'] == 'LOT_SIZE'][0])
        
        quantity = position_value / entry_price
        
        # Zaokrąglenie do właściwej precyzji
        precision = int(round(-np.log10(step_size)))
        return round(quantity, precision)

    def _calculate_stop_loss(self, side, entry_price, atr):
        if side == 'BUY':
            return entry_price - (SL_ATR_MULTIPLIER * atr)
        return entry_price + (SL_ATR_MULTIPLIER * atr)

    def _calculate_take_profit(self, side, entry_price, stop_loss):
        if side == 'BUY':
            return entry_price + (abs(entry_price - stop_loss) * TP_SL_RATIO)
        return entry_price - (abs(entry_price - stop_loss) * TP_SL_RATIO)

    def _execute_order(self, side, quantity):
        """Wykonuje zlecenie MARKET i zwraca cenę wykonania."""
        try:
            order = self.client.create_order(
                symbol=SYMBOL,
                side=side,
                type='MARKET',
                quantity=quantity
            )
            logger.info(f"Zlecenie wykonane: {order}")
            self._send_telegram_message(f"🔄 Zlecenie: {side} {quantity} {SYMBOL}")
            
            # Oblicz średnią cenę wykonania
            total_price = sum(float(f['price']) * float(f['qty']) for f in order['fills'])
            total_qty = sum(float(f['qty']) for f in order['fills'])
            avg_price = total_price / total_qty if total_qty > 0 else 0
            
            return avg_price
        except BinanceAPIException as e:
            logger.error(f"Błąd wykonania zlecenia: {e}")
            self._send_telegram_message(f"⚠️ Błąd zlecenia: {e}")
            return None

    def _check_exit_conditions(self, current_price):
        """Sprawdza warunki wyjścia z pozycji"""
        if not self.in_position: return False
        
        if self.position_side == 'BUY':
            if current_price <= self.stop_loss: return 'stop_loss'
            if current_price >= self.take_profit: return 'take_profit'
        elif self.position_side == 'SELL':
            if current_price >= self.stop_loss: return 'stop_loss'
            if current_price <= self.take_profit: return 'take_profit'
        return False

    def _process_exit(self, exit_price, exit_type):
        """Przetwarza wyjście z pozycji"""
        if self.position_side == 'BUY':
            pl_percent = (exit_price - self.entry_price) / self.entry_price
        else:
            pl_percent = (self.entry_price - exit_price) / self.entry_price
        
        pl_amount = self.position_size * self.entry_price * pl_percent
        self.daily_pl += pl_amount
        self.daily_trades += 1

        if pl_percent > 0:
            self.successful_trades += 1
            message = f"✅ Zamknięto pozycję ({exit_type}): {pl_percent:.2%} zysku ({pl_amount:.2f} USDC)"
        else:
            self.failed_trades += 1
            message = f"❌ Zamknięto pozycję ({exit_type}): {pl_percent:.2%} straty ({pl_amount:.2f} USDC)"
        
        logger.info(message)
        self._send_telegram_message(message)
        
        # Reset stanu pozycji
        self.in_position = False
        self.position_side = None
        self.entry_price = 0
        self.position_size = 0
        self.stop_loss = 0
        self.take_profit = 0
        self._save_state()

    def _open_position(self, side, current_price, atr):
        """Otwiera nową pozycję."""
        stop_loss_price = self._calculate_stop_loss(side, current_price, atr)
        position_size = self._calculate_position_size(current_price, stop_loss_price)

        if position_size <= 0:
            logger.info("Wielkość pozycji wynosi 0, zlecenie nie zostało złożone.")
            return

        # Wykonaj zlecenie
        executed_price = self._execute_order(side, position_size)
        if not executed_price:
            logger.error("Nie udało się otworzyć pozycji.")
            return

        # Aktualizuj SL i TP o rzeczywistą cenę wejścia
        self.entry_price = executed_price
        self.stop_loss = self._calculate_stop_loss(side, executed_price, atr)
        self.take_profit = self._calculate_take_profit(side, executed_price, self.stop_loss)
        self.position_side = side
        self.position_size = position_size
        self.in_position = True
        
        logger.info(f"Otwarto pozycję {side}: cena={self.entry_price:.2f}, SL={self.stop_loss:.2f}, TP={self.take_profit:.2f}")
        self._send_telegram_message(
            f"🟢 Pozycja {side}:\n"
            f"Wejście: {self.entry_price:.2f}\n"
            f"Stop Loss: {self.stop_loss:.2f}\n"
            f"Take Profit: {self.take_profit:.2f}"
        )
        self._save_state()

    def _reset_daily_stats(self):
        """Resetuje dzienne statystyki o północy."""
        current_date = datetime.now().date()
        last_reset_date = datetime.fromisoformat(self.last_day_reset).date()

        if current_date > last_reset_date:
            win_rate = (self.successful_trades / self.daily_trades * 100) if self.daily_trades > 0 else 0
            summary = (
                f"📊 Podsumowanie dnia {last_reset_date.isoformat()}:\n"
                f"Transakcje: {self.daily_trades}, Udane: {self.successful_trades} ({win_rate:.2f}%)\n"
                f"Zysk/strata: {self.daily_pl:.2f} USDC"
            )
            logger.info(summary)
            self._send_telegram_message(summary)
            
            self.daily_pl = 0
            self.daily_trades = 0
            self.successful_trades = 0
            self.failed_trades = 0
            self.last_day_reset = current_date.isoformat()
            self._save_state()

    def run(self):
        """Główna pętla bota."""
        logger.info("Bot rozpoczyna działanie...")
        
        while self.active:
            try:
                self._reset_daily_stats()
                
                # Czekaj na początek następnej minuty
                now = datetime.now()
                next_minute = (now + timedelta(minutes=1)).replace(second=5, microsecond=0)
                sleep_duration = (next_minute - now).total_seconds()
                
                if sleep_duration > 0:
                    logger.info(f"Czekam {sleep_duration:.2f}s do następnej świecy...")
                    time.sleep(sleep_duration)

                df = self._fetch_data(limit=100)
                if df is None or df.empty:
                    continue
                
                df = self._calculate_indicators(df)
                if df.empty or 'atr' not in df.columns:
                    logger.warning("Nie udało się obliczyć wskaźników.")
                    continue

                current_price = df['close'].iloc[-1]
                atr = df['atr'].iloc[-1]

                if self.in_position:
                    exit_type = self._check_exit_conditions(current_price)
                    if exit_type:
                        exit_side = 'SELL' if self.position_side == 'BUY' else 'BUY'
                        exit_price = self._execute_order(exit_side, self.position_size)
                        if exit_price:
                            self._process_exit(exit_price, exit_type)
                        else:
                            logger.error("Błąd zlecenia wyjścia, pozycja może być wciąż otwarta!")
                else: # Nie jesteśmy w pozycji
                    if self._check_buy_signal(df):
                        self._open_position('BUY', current_price, atr)
                    elif self._check_sell_signal(df):
                        self._open_position('SELL', current_price, atr)

            except Exception as e:
                logger.critical(f"Krytyczny błąd w pętli głównej: {e}", exc_info=True)
                self._send_telegram_message(f"🚨 Krytyczny błąd bota: {e}")
                time.sleep(60)

if __name__ == "__main__":
    bot = BinanceScalpingBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot zatrzymywany przez użytkownika...")
        bot.active = False
        bot._save_state()
        bot._send_telegram_message("🛑 Bot został zatrzymany.")
    except Exception as e:
        logger.critical(f"Krytyczny błąd poza pętlą główną: {e}", exc_info=True)
        bot._send_telegram_message(f"🚨 Krytyczny błąd bota: {e}")
        bot._save_state()
