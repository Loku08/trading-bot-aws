# Użyj oficjalnego obrazu Python
FROM python:3.9-slim

# Ustaw katalog roboczy w kontenerze
WORKDIR /app

# Skopiuj plik z zależnościami i zainstaluj je
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Skopiuj resztę kodu aplikacji do katalogu roboczego
COPY . .

# Ustaw zmienne środowiskowe (opcjonalnie, można je przekazać przy uruchamianiu kontenera)
# ENV BINANCE_API_KEY="your_api_key"
# ENV BINANCE_API_SECRET="your_api_secret"
# ENV TELEGRAM_TOKEN="your_telegram_token"
# ENV TELEGRAM_CHAT_ID="your_telegram_chat_id"

# Uruchom bota
CMD ["python", "bot.py"] 