import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

LOG_FILE = "signals_log.csv"

def load_signal_log():
    if os.path.exists(LOG_FILE):
        return pd.read_csv(LOG_FILE)
    else:
        return pd.DataFrame(columns=["symbol", "date", "signal", "price"])

def save_signal_log(df):
    df.to_csv(LOG_FILE, index=False)

def last_signal(df, symbol):
    filtered = df[df["symbol"] == symbol]
    if filtered.empty:
        return None
    return filtered.iloc[-1]["signal"]

def log_signal(df, symbol, signal_type, date, price):
    new_row = {"symbol": symbol, "date": date, "signal": signal_type, "price": price}
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_ID").split(',')

def get_nifty_100_symbols():
    try:
        df = pd.read_csv("ind_nifty100list.csv")
        return df["Symbol"].tolist()
    except Exception as e:
        print(f"⚠️ Error reading Nifty 100 CSV: {e}")
        return []

NIFTY_100 = get_nifty_100_symbols()

def fetch_data(symbol, end_date, lookback_days=300):
    start_date = (end_date - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    end_date_str = (end_date + timedelta(days=1)).strftime('%Y-%m-%d')
    try:
        df = yf.download(symbol + ".NS", start=start_date, end=end_date_str)
        return df[['Close']]
    except:
        return None
def analyze(df, check_date, symbol):
    df = df.copy()
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()

    if check_date not in df.index:
        return "Something is Wrong", None
        return None

    row = df.loc[check_date]
    row = df.loc[date_to_check]
    sma20 = row[('SMA20', '')]
    sma50 = row[('SMA50', '')]
    sma200 = row[('SMA200', '')]
    close = row[('Close', symbol+'.NS')]

    if pd.isna(sma20) or pd.isna(sma50) or pd.isna(sma200) or pd.isna(close):
        return None, None

    buy = (sma50 < sma200) and (sma20 < sma50) and (close < 0.95 * sma20)
    sell = (sma50 > sma200) and (sma20 > sma50) and (close > sma20)

    if buy:
        return "BUY", close
    elif sell:
        return "SELL", close
    else:
        return None, None


def send_telegram_message(message):
    for TELEGRAM_CHAT_ID in TELEGRAM_CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
        r = requests.post(url, data=payload)
    return r.status_code == 200

def run_strategy(check_date):
    results = []
    signal_log = load_signal_log()

    for symbol in NIFTY_100:
        df = fetch_data(symbol, check_date)
        if df is None or df.empty:
            continue
        df.index = pd.to_datetime(df.index).map(lambda x: x.date())
        if check_date not in df.index:
            continue

        signal, close_price = analyze(df, check_date, symbol)

        if not signal:
            continue

        last = last_signal(signal_log, symbol)

        # Avoid repeating the same signal again
        if signal == last:
            continue

        # BUY: Always allowed unless it's a repeat
        if signal == "BUY":
            signal_log = log_signal(signal_log, symbol, "BUY", check_date, close_price)
            results.append(f"{symbol}: 📉BUY at {round(close_price, 2)}")

        # SELL: Only if last was BUY (and not repeating SELL)
        elif signal == "SELL" and last == "BUY":
            signal_log = log_signal(signal_log, symbol, "SELL", check_date, close_price)
            results.append(f"{symbol}: 📈SELL at {round(close_price, 2)}")

    save_signal_log(signal_log)

    if results:
        text = f"📊 SMA Signals for {check_date}:\n\n" + "\n".join(results)
        send_telegram_message(text)
        print(f"✅ Sent {len(results)} signals.")
    else:
        text = f"📭 No SMA signals generated for {check_date}."
        send_telegram_message(text)
        print(f"❌ No new signals on {check_date}")

    print(f"✔️ Checked date: {check_date}")


# Change mode for testing
MODE = "LIVE"  # Change to "LIVE" to auto-check today
TEST_DATE_STR = "2025-05-23"

if MODE == "LIVE":
    date_to_check = datetime.now().date()
else:
    date_to_check = datetime.strptime(TEST_DATE_STR, "%Y-%m-%d").date()

print(date_to_check)
run_strategy(date_to_check)
