
import streamlit as st
import json
import os
import plotly.graph_objects as go
from dotenv import load_dotenv
from kiteconnect import KiteConnect, KiteTicker
import pandas as pd
import ta
from datetime import datetime, timedelta
import requests # For news API

# Load environment variables from .env file
load_dotenv()

# Functions to manage watchlist
def load_watchlist():
    try:
        with open("watchlist.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_watchlist(watchlist):
    with open("watchlist.json", "w") as f:
        json.dump(watchlist, f)

# Initialize session state
def init_session_state():
    if 'api_keys' not in st.session_state:
        st.session_state.api_keys = {
            "kite_api_key": os.getenv("KITE_API_KEY", ""),
            "kite_api_secret": os.getenv("KITE_API_SECRET", ""),
            "kite_access_token": os.getenv("KITE_ACCESS_TOKEN", ""),
            "fundamentals_api_key": os.getenv("FUNDAMENTALS_API_KEY", ""),
            "news_api_key": os.getenv("NEWS_API_KEY", ""),
            "shipping_api_key": os.getenv("SHIPPING_API_KEY", ""),
        }
    if 'ticker_running' not in st.session_state:
        st.session_state.ticker_running = False
    if 'ticks_data' not in st.session_state:
        st.session_state.ticks_data = pd.DataFrame(columns=['timestamp', 'last_price'])
    if 'kite' not in st.session_state:
        st.session_state.kite = KiteConnect(api_key=st.session_state.api_keys.get("kite_api_key"))
    if 'kws' not in st.session_state:
        st.session_state.kws = None

# Kite Ticker callbacks
def on_ticks(ws, ticks):
    for tick in ticks:
        new_row = pd.DataFrame([{'timestamp': tick['timestamp'], 'last_price': tick['last_price']}])
        st.session_state.ticks_data = pd.concat([st.session_state.ticks_data, new_row], ignore_index=True)
    st.rerun()

def on_connect(ws, response):
    st.session_state.ticker_running = True
    if watchlist:
        instruments = st.session_state.kite.instruments()
        instrument_tokens = [i['instrument_token'] for i in instruments if i['tradingsymbol'] in watchlist]
        ws.subscribe(instrument_tokens)
        ws.set_mode(ws.MODE_FULL, instrument_tokens)

def on_close(ws, code, reason):
    st.session_state.ticker_running = False

# Placeholder for sentiment analysis
def get_sentiment(text):
    # In a real application, you would use a sentiment analysis library like NLTK or TextBlob
    if "strong" in text or "high" in text or "new" in text:
        return "Positive"
    elif "weak" in text or "low" in text or "down" in text:
        return "Negative"
    else:
        return "Neutral"

# Main App
st.set_page_config(layout="wide")
st.title("Financial Dashboard")

init_session_state()
watchlist = load_watchlist()

# Sidebar
st.sidebar.header("Symbol Search")
new_symbol = st.sidebar.text_input("Add to watchlist:")
if st.sidebar.button("Add"):
    if new_symbol and new_symbol.upper() not in watchlist:
        watchlist.append(new_symbol.upper())
        save_watchlist(watchlist)
        st.sidebar.success(f"Added {new_symbol.upper()}")
        st.rerun()

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Market", "Technicals", "Fundamentals", "News", "Shipping", "Settings"])

with tab1:
    st.header("Market")
    selected_symbol = st.selectbox("Select Symbol", watchlist)

    if selected_symbol:
        chart_placeholder = st.empty()
        if not st.session_state.ticks_data.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=st.session_state.ticks_data['timestamp'], y=st.session_state.ticks_data['last_price'], mode='lines'))
            chart_placeholder.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Technicals")
    st.sidebar.header("Technical Indicators")
    selected_symbol_tech = st.selectbox("Select Symbol for Technicals", watchlist, key="tech_symbol")

    # Indicator Parameters
    st.sidebar.subheader("Indicator Settings")
    sma_window = st.sidebar.number_input("SMA Window", min_value=1, max_value=200, value=20)
    ema_window = st.sidebar.number_input("EMA Window", min_value=1, max_value=200, value=20)
    rsi_window = st.sidebar.number_input("RSI Window", min_value=1, max_value=200, value=14)
    bollinger_window = st.sidebar.number_input("Bollinger Bands Window", min_value=1, max_value=200, value=20)
    bollinger_std_dev = st.sidebar.number_input("Bollinger Bands Std Dev", min_value=1, max_value=10, value=2)
    stoch_window = st.sidebar.number_input("Stochastic Oscillator Window", min_value=1, max_value=200, value=14)
    stoch_smooth_k = st.sidebar.number_input("Stochastic Oscillator Smooth %K", min_value=1, max_value=50, value=3)
    atr_window = st.sidebar.number_input("ATR Window", min_value=1, max_value=200, value=14)

    if selected_symbol_tech:
        # Fetch historical data
        if st.session_state.kite and st.session_state.api_keys["kite_access_token"]:
            try:
                to_date = datetime.now().date()
                from_date = to_date - timedelta(days=365)
                instrument_token = [i['instrument_token'] for i in st.session_state.kite.instruments() if i['tradingsymbol'] == selected_symbol_tech][0]
                historical_data = st.session_state.kite.historical_data(instrument_token, from_date, to_date, "day")
                df = pd.DataFrame(historical_data)

                # Calculate technical indicators
                df['sma'] = ta.trend.sma_indicator(df['close'], window=sma_window)
                df['ema'] = ta.trend.ema_indicator(df['close'], window=ema_window)
                df['rsi'] = ta.momentum.rsi(df['close'], window=rsi_window)
                macd = ta.trend.MACD(df['close'])
                df['macd'] = macd.macd()
                df['macd_signal'] = macd.macd_signal()
                df['macd_diff'] = macd.macd_diff()
                bollinger = ta.volatility.BollingerBands(df['close'], window=bollinger_window, window_dev=bollinger_std_dev)
                df['bb_high'] = bollinger.bollinger_hband()
                df['bb_low'] = bollinger.bollinger_lband()
                stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'], window=stoch_window, smooth_window=stoch_smooth_k)
                df['stoch_k'] = stoch.stoch()
                df['stoch_d'] = stoch.stoch_signal()
                df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=atr_window)


                # Display charts
                st.subheader(f"Technical Analysis for {selected_symbol_tech}")

                # Price chart with moving averages and bollinger bands
                fig_price = go.Figure()
                fig_price.add_trace(go.Scatter(x=df['date'], y=df['close'], mode='lines', name='Close Price'))
                fig_price.add_trace(go.Scatter(x=df['date'], y=df['sma'], mode='lines', name=f'{sma_window}-Day SMA'))
                fig_price.add_trace(go.Scatter(x=df['date'], y=df['ema'], mode='lines', name=f'{ema_window}-Day EMA'))
                fig_price.add_trace(go.Scatter(x=df['date'], y=df['bb_high'], mode='lines', name='Bollinger High', line=dict(color='red', dash='dash')))
                fig_price.add_trace(go.Scatter(x=df['date'], y=df['bb_low'], mode='lines', name='Bollinger Low', line=dict(color='green', dash='dash')))
                fig_price.update_layout(title="Price, Moving Averages, and Bollinger Bands")
                st.plotly_chart(fig_price, use_container_width=True)

                # RSI chart
                fig_rsi = go.Figure()
                fig_rsi.add_trace(go.Scatter(x=df['date'], y=df['rsi'], mode='lines', name='RSI'))
                fig_rsi.update_layout(title="Relative Strength Index (RSI)")
                st.plotly_chart(fig_rsi, use_container_width=True)

                # MACD chart
                fig_macd = go.Figure()
                fig_macd.add_trace(go.Scatter(x=df['date'], y=df['macd'], mode='lines', name='MACD'))
                fig_macd.add_trace(go.Scatter(x=df['date'], y=df['macd_signal'], mode='lines', name='Signal Line'))
                fig_macd.add_trace(go.Bar(x=df['date'], y=df['macd_diff'], name='MACD Diff'))
                fig_macd.update_layout(title="MACD")
                st.plotly_chart(fig_macd, use_container_width=True)

                # Stochastic Oscillator chart
                fig_stoch = go.Figure()
                fig_stoch.add_trace(go.Scatter(x=df['date'], y=df['stoch_k'], mode='lines', name='%K'))
                fig_stoch.add_trace(go.Scatter(x=df['date'], y=df['stoch_d'], mode='lines', name='%D'))
                fig_stoch.update_layout(title="Stochastic Oscillator")
                st.plotly_chart(fig_stoch, use_container_width=True)
                
                # ATR chart
                fig_atr = go.Figure()
                fig_atr.add_trace(go.Scatter(x=df['date'], y=df['atr'], mode='lines', name='ATR'))
                fig_atr.update_layout(title="Average True Range (ATR)")
                st.plotly_chart(fig_atr, use_container_width=True)

            except Exception as e:
                st.error(f"Error fetching or processing data: {e}")

with tab3:
    st.header("Fundamentals")
    selected_symbol_fund = st.selectbox("Select Symbol for Fundamentals", watchlist, key="fund_symbol")

    if selected_symbol_fund:
        if st.session_state.kite and st.session_state.api_keys["kite_access_token"]:
            try:
                # Get instrument token and quote
                instrument_token = [i['instrument_token'] for i in st.session_state.kite.instruments() if i['tradingsymbol'] == selected_symbol_fund][0]
                quote = st.session_state.kite.quote(instrument_token)
                info = quote[f"NSE:{selected_symbol_fund}"]

                # Company Information
                st.subheader("Company Information")
                st.write(f"**Name:** {info['instrument_token']}") # Placeholder for name
                st.write(f"**Exchange:** {info['exchange']}")
                st.write(f"**Market Cap:** {info['market_cap']}")

                # Key Financial Ratios
                st.subheader("Key Financial Ratios")
                financial_ratios = {
                    "P/E Ratio": info.get('pe_ratio', 'N/A'),
                    "P/B Ratio": info.get('pb_ratio', 'N/A'),
                    "Dividend Yield": info.get('dividend_yield', 'N/A'),
                }
                # Bar chart for ratios
                fig_ratios = go.Figure(data=[go.Bar(x=list(financial_ratios.keys()), y=list(financial_ratios.values()))])
                fig_ratios.update_layout(title_text="Key Financial Ratios")
                st.plotly_chart(fig_ratios, use_container_width=True)


                # Financial Statements (Placeholder)
                st.subheader("Financial Statements")

                st.write("**Income Statement**")
                income_statement_df = pd.DataFrame({
                    'Metric': ['Revenue', 'Net Income', 'EPS'],
                    '2023': [1000, 100, 1.0],
                    '2022': [900, 90, 0.9],
                    '2021': [800, 80, 0.8]
                })
                st.table(income_statement_df)

                st.write("**Balance Sheet**")
                balance_sheet_df = pd.DataFrame({
                    'Metric': ['Total Assets', 'Total Liabilities', 'Total Equity'],
                    '2023': [2000, 1000, 1000],
                    '2022': [1800, 900, 900],
                    '2021': [1600, 800, 800]
                })
                st.table(balance_sheet_df)

                st.write("**Cash Flow Statement**")
                cash_flow_df = pd.DataFrame({
                    'Metric': ['Operating Cash Flow', 'Investing Cash Flow', 'Financing Cash Flow'],
                    '2023': [200, -100, -50],
                    '2022': [180, -90, -40],
                    '2021': [160, -80, -30]
                })
                st.table(cash_flow_df)
            except Exception as e:
                st.error(f"Error fetching fundamental data: {e}")

with tab4:
    st.header("News")
    selected_symbol_news = st.selectbox("Select Symbol for News", watchlist, key="news_symbol")

    if selected_symbol_news:
        st.subheader(f"Latest News for {selected_symbol_news}")
        if st.session_state.api_keys["news_api_key"]:
            try:
                url = f"https://newsapi.org/v2/everything?q={selected_symbol_news}&apiKey={st.session_state.api_keys['news_api_key']}"
                response = requests.get(url)
                news_data = response.json()
                if news_data['status'] == 'ok':
                    for article in news_data['articles']:
                        sentiment = get_sentiment(article['title'])
                        st.write(f"**[{article['title']}]({article['url']})** - *{sentiment}*")
                        st.write(f"Source: {article['source']['name']} | Published at: {article['publishedAt']}")
                        st.write("---")
                else:
                    st.error("Could not fetch news.")
            except Exception as e:
                st.error(f"Error fetching news: {e}")
        else:
            st.warning("Please enter your News API key in the settings tab to fetch news.")

with tab5:
    st.header("Shipping")
    st.subheader("Key Shipping Indices")

    if st.session_state.api_keys["shipping_api_key"]:
        # Example of how you might fetch and display shipping data
        # This is a placeholder and will not work without a valid API key and endpoint
        try:
            # Baltic Dry Index
            bdi_url = f"https://api.shipping-data.com/bdi?apiKey={st.session_state.api_keys['shipping_api_key']}"
            bdi_response = requests.get(bdi_url)
            bdi_data = bdi_response.json()
            bdi_df = pd.DataFrame(bdi_data['data'])
            bdi_df['Date'] = pd.to_datetime(bdi_df['Date'])
            fig_bdi = go.Figure(data=[go.Scatter(x=bdi_df['Date'], y=bdi_df['Value'], mode='lines')])
            fig_bdi.update_layout(title_text="Baltic Dry Index (BDI)")
            st.plotly_chart(fig_bdi, use_container_width=True)

            # Container Shipping Rates (SCFI)
            scfi_url = f"https://api.shipping-data.com/scfi?apiKey={st.session_state.api_keys['shipping_api_key']}"
            scfi_response = requests.get(scfi_url)
            scfi_data = scfi_response.json()
            scfi_df = pd.DataFrame(scfi_data['data'])
            scfi_df['Date'] = pd.to_datetime(scfi_df['Date'])
            fig_scfi = go.Figure(data=[go.Scatter(x=scfi_df['Date'], y=scfi_df['Value'], mode='lines')])
            fig_scfi.update_layout(title_text="Container Shipping Rates (SCFI)")
            st.plotly_chart(fig_scfi, use_container_width=True)

        except Exception as e:
            st.error("Error fetching shipping data. Please check your API key and endpoint.")

    else:
        st.warning("Please enter your Shipping API key in the settings tab to fetch shipping data.")

with tab6:
    st.header("Settings")
    st.subheader("API Keys")
    st.session_state.api_keys["kite_api_key"] = st.text_input("Kite API Key", value=st.session_state.api_keys["kite_api_key"], type="password")
    st.session_state.api_keys["kite_api_secret"] = st.text_input("Kite API Secret", value=st.session_state.api_keys["kite_api_secret"], type="password")
    st.session_state.api_keys["fundamentals_api_key"] = st.text_input("Fundamentals API Key", value=st.session_state.api_keys["fundamentals_api_key"], type="password")
    st.session_state.api_keys["news_api_key"] = st.text_input("News API Key", value=st.session_state.api_keys["news_api_key"], type="password")
    st.session_state.api_keys["shipping_api_key"] = st.text_input("Shipping API Key", value=st.session_state.api_keys["shipping_api_key"], type="password")

    st.subheader("Kite Connection")
    if st.session_state.ticker_running:
        if st.button("Disconnect"):
            if st.session_state.kws:
                st.session_state.kws.stop()
            st.session_state.ticker_running = False
            st.session_state.ticks_data = pd.DataFrame(columns=['timestamp', 'last_price'])
            st.rerun()
    else:
        if st.button("Connect"):
            if st.session_state.api_keys["kite_access_token"]:
                st.session_state.kws = KiteTicker(st.session_state.api_keys["kite_api_key"], st.session_state.api_keys["kite_access_token"])
                st.session_state.kws.on_ticks = on_ticks
                st.session_state.kws.on_connect = on_connect
                st.session_state.kws.on_close = on_close
                st.session_state.kws.connect(threaded=True)
            else:
                st.warning("Please generate an access token first.")

    if not st.session_state.api_keys.get("kite_access_token"):
        st.write("Login to Kite to get an access token.")
        if st.button("Login with Kite"):
             st.write("Please login using this URL and paste the request token below:")
             st.write(st.session_state.kite.login_url())
        request_token = st.text_input("Request Token")
        if st.button("Generate Access Token"):
            try:
                data = st.session_state.kite.generate_session(request_token, api_secret=st.session_state.api_keys["kite_api_secret"])
                st.session_state.api_keys["kite_access_token"] = data["access_token"]
                with open(".env", "a") as f:
                    f.write(f'KITE_ACCESS_TOKEN="{st.session_state.api_keys["kite_access_token"]}"\n')
                st.rerun()
            except Exception as e:
                st.error(e)