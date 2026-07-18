import datetime
import numpy as np
import pandas as pd
import yfinance as yf

# ─────────────────────────────────────────────────────────────────────────────
# 1. INPUTS & CONFIGURATIONS
# ─────────────────────────────────────────────────────────────────────────────
nav_label = "India Solar Basket"
start_date_str = "2024-01-01"  # "01 Jan 2024"
active_count = 9

# Tickers mapped to standard Yahoo Finance format (.NS for NSE, .BO for BSE)
all_tickers = [
    "WAAREEENER.NS",
    "PREMIERENE.NS",
    "INA.NS",
    "WEBELSOLAR.NS",
    "ALPEXSOLAR.NS",
    "SWELECTES.NS",
    "AWHCL.NS",  # Replaced placeholder with an actionable F&O/Equity example if needed
    "SOLEX.NS",
    "531260.BO",
] + ["^NSEI"] * 31  # Fill the rest up to 40 slots with Nifty Index placeholders

# Slice to only include the active tickers configured
tickers_to_fetch = all_tickers[:active_count]
print(f"Fetching data for {active_count} active tickers...")

# ─────────────────────────────────────────────────────────────────────────────
# 2. FETCH DATA & ALIGN TIMEFRAMES
# ─────────────────────────────────────────────────────────────────────────────
# Fetch extra historical overhead to allow smooth EMA warming
download_start = (
    pd.to_datetime(start_date_str) - pd.DateOffset(years=1)
).strftime("%Y-%m-%d")
end_date = datetime.date.today().strftime("%Y-%m-%d")

try:
    data = yf.download(
        tickers_to_fetch, start=download_start, end=end_date, group_by="ticker"
    )
except Exception as e:
    print(f"Error fetching data: {e}")
    exit()

# Extract 'Close' prices into a unified DataFrame
close_df = pd.DataFrame()
for ticker in tickers_to_fetch:
    if ticker in data.columns.levels[0] if isinstance(data.columns, pd.MultiIndex) else [ticker]:
        close_df[ticker] = data[ticker]["Close"] if isinstance(data.columns, pd.MultiIndex) else data["Close"]

# Drop rows where absolutely all assets are completely blank (e.g., weekends/holidays)
close_df = close_df.dropna(how="all").sort_index()

# ─────────────────────────────────────────────────────────────────────────────
# 3. DYNAMIC EQUAL-WEIGHTED NAV CALCULATION
# ─────────────────────────────────────────────────────────────────────────────
# Count valid prices bar-by-bar and calculate the average price
valid_stock_counts = close_df.notna().sum(axis=1)
avg_price = close_df.sum(axis=1) / valid_stock_counts

# Filter to your strict calculation Start Date boundary
target_start_dt = pd.to_datetime(start_date_str)
nav_df = pd.DataFrame(index=close_df.index)
nav_df["Avg_Price"] = avg_price
nav_df["Valid_Count"] = valid_stock_counts

# Locate the precise base price on or immediately after the start date
post_start_data = nav_df[nav_df.index >= target_start_dt]
if post_start_data.empty:
    print("Error: No market data found on or after the selected Start Date.")
    exit()

base_price = post_start_data["Avg_Price"].iloc[0]
print(f"Releasing Base Price established at: {base_price:.2f}")

# Calculate the rebased NAV series (Base 100)
nav_df["NAV"] = (nav_df["Avg_Price"] / base_price) * 100

# Calculate EMAs on the calculated NAV series
nav_df["EMA20"] = nav_df["NAV"].ewm(span=20, adjust=False).mean()
nav_df["EMA50"] = nav_df["NAV"].ewm(span=50, adjust=False).mean()
nav_df["EMA200"] = nav_df["NAV"].ewm(span=200, adjust=False).mean()

# Crop final dataframe to only display analysis results from the target start date forward
analysis_df = nav_df[nav_df.index >= target_start_dt]
latest_row = analysis_df.iloc[-1]
latest_nav = latest_row["NAV"]
latest_stocks = int(latest_row["Valid_Count"])

print("\n" + "=" * 50)
print(f"LATEST STATUS: {nav_label}")
print(f"Current NAV Value: {latest_nav:.2f} ({latest_stocks} Active Stocks)")
print("=" * 50)

# ─────────────────────────────────────────────────────────────────────────────
# 4. PERIODIC RETURNS TABLE
# ─────────────────────────────────────────────────────────────────────────────
print("\n[ PERIODIC RETURNS TABLE ]")
print(f"{'Period':<12} | {'Return (%)':<10}")
print("-" * 27)

periods = {
    "1 Day": 1,
    "1 Week": 7,
    "1 Month": 30,
    "3 Month": 91,
    "6 Month": 182,
    "1 Year": 365,
    "3 Year": 1095,
    "5 Year": 1825,
}

latest_date = analysis_df.index[-1]
for label, days in periods.items():
    target_date = latest_date - pd.Timedelta(days=days)
    # Find the closest matching historical data row at or prior to target window
    past_data = analysis_df[analysis_df.index <= target_date]

    if not past_data.empty:
        past_nav = past_data["NAV"].iloc[-1]
        chg = ((latest_nav - past_nav) / past_nav) * 100
        print(f"{label:<12} | {chg:>9.2f}%")
    else:
        print(f"{label:<12} | {'N/A':>10}")

# ─────────────────────────────────────────────────────────────────────────────
# 5. STOCK VS NAV PERFORMANCE TABLE
# ─────────────────────────────────────────────────────────────────────────────
print("\n[ STOCK VS NAV PERFORMANCE TABLE (Sorted Descending) ]")
print(f"{'Stock Ticker':<15} | {'Total Return':<12} | {'vs NAV Diff':<12}")
print("-" * 47)

nav_total_roc = latest_nav - 100
stock_perf_list = []

for ticker in tickers_to_fetch:
    ticker_series = close_df[ticker][close_df.index >= target_start_dt].dropna()
    if not ticker_series.empty:
        stock_base_px = ticker_series.iloc[0]
        stock_cur_px = ticker_series.iloc[-1]

        if stock_base_px > 0:
            stock_roc = ((stock_cur_px - stock_base_px) / stock_base_px) * 100
            vs_nav = stock_roc - nav_total_roc
            stock_perf_list.append(
                {"ticker": ticker, "roc": stock_roc, "vs_nav": vs_nav}
            )

# Sort performance arrays in descending order exactly like Pine Script's `array.sort_indices`
stock_perf_df = pd.DataFrame(stock_perf_list)
if not stock_perf_df.empty:
    stock_perf_df = stock_perf_df.sort_values(by="roc", ascending=False)

    # Print baseline tracking reference
    print(f"{'NAV (Baseline)':<15} | {nav_total_roc:>11.2f}% | {'—':^12}")

    for _, row in stock_perf_df.iterrows():
        clean_name = row["ticker"].split(".")[0]
        print(
            f"{clean_name:<15} | {row['roc']:>11.2f}% | {row['vs_nav']:>+11.2f}%"
        )