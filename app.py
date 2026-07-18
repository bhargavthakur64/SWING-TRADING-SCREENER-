import datetime
import json
import os
import urllib.parse
from io import StringIO

import numpy as np
import pandas as pd
import requests
import uvicorn
import yfinance as yf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Swing Trading Sector Screener API")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Enable CORS for local development and testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SPREADSHEET_ID = "1G_lZbCc74MsJAHUsbTNx6v1KGlCZAiBwxTUU792BAzc"
CACHE_FILE = "isin_cache.json"

# Helper to load/save ISIN to Symbol cache
def load_isin_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_isin_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=4)
    except Exception as e:
        print(f"Error saving ISIN cache: {e}")

# Yahoo Finance Search API to map ISIN to Yahoo Ticker (ends in .NS or .BO)
def resolve_isin_to_ticker(isin):
    if not isin or not isinstance(isin, str) or len(isin.strip()) < 5:
        return None
    
    isin = isin.strip().upper()
    cache = load_isin_cache()
    if isin in cache:
        return cache[isin]
    
    # Query Yahoo Finance Search API
    url = f"https://query1.finance.yahoo.com/v1/finance/search?q={isin}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            quotes = data.get("quotes", [])
            
            # 1. Prefer NSE symbol
            for q in quotes:
                symbol = q.get("symbol", "")
                if symbol.endswith(".NS"):
                    cache[isin] = symbol
                    save_isin_cache(cache)
                    return symbol
                    
            # 2. Prefer BSE symbol
            for q in quotes:
                symbol = q.get("symbol", "")
                if symbol.endswith(".BO"):
                    cache[isin] = symbol
                    save_isin_cache(cache)
                    return symbol
                    
            # 3. Fallback to first available symbol
            if quotes:
                symbol = quotes[0].get("symbol")
                if symbol:
                    cache[isin] = symbol
                    save_isin_cache(cache)
                    return symbol
    except Exception as e:
        print(f"Error resolving ISIN {isin} using Yahoo: {e}")
        
    return None

# Helper to find column by common aliases
def find_column(df, aliases):
    for alias in aliases:
        for col in df.columns:
            if col.strip().lower() == alias.lower():
                return col
    return None

# Normalize DataFrame structure for processing
def normalize_dataframe(df):
    cols = df.columns.tolist()
    
    industry_col = find_column(df, ["Industry", "Sector", "Sectors", "Industries", "Group", "Segment"])
    isin_col = find_column(df, ["ISIN", "isin", "ISIN Number", "ISIN Code", "Isin Number"])
    ticker_col = find_column(df, ["Yahoo Ticker", "yahoo Symbol", "Yahoo Symbol", "Ticker", "Symbol", "NSE Symbol"])
    name_col = find_column(df, ["Stock Name", "Name", "Company Name", "Company", "Stock"])
    
    normalized_df = pd.DataFrame()
    
    # 1. Sector / Industry
    if industry_col:
        normalized_df["industry"] = df[industry_col].fillna("General").astype(str).str.strip()
    else:
        normalized_df["industry"] = "General"
        
    # 2. ISIN
    if isin_col:
        normalized_df["isin"] = df[isin_col].fillna("").astype(str).str.strip()
    else:
        normalized_df["isin"] = ""
        
    # 3. Ticker
    if ticker_col:
        normalized_df["ticker"] = df[ticker_col].fillna("").astype(str).str.strip()
    else:
        normalized_df["ticker"] = ""
        
    # 4. Stock Name
    if name_col:
        normalized_df["name"] = df[name_col].fillna("").astype(str).str.strip()
    else:
        normalized_df["name"] = ""
        
    return normalized_df

# Fetch sheet data (with local file fallback)
def load_data():
    # 1. Try local watchlist.csv (highly recommended for offline/instant speed)
    if os.path.exists("watchlist.csv"):
        try:
            df = pd.read_csv("watchlist.csv")
            return normalize_dataframe(df), "Local CSV (watchlist.csv)"
        except Exception as e:
            print(f"Failed to read local watchlist.csv: {e}")
            
    # 2. Try local watchlist.xlsx
    if os.path.exists("watchlist.xlsx"):
        try:
            df = pd.read_excel("watchlist.xlsx")
            return normalize_dataframe(df), "Local Excel (watchlist.xlsx)"
        except Exception as e:
            print(f"Failed to read local watchlist.xlsx: {e}")

    # 3. Try fetching from Google Sheet
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    sheet_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv"
    try:
        resp = requests.get(sheet_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            df = pd.read_csv(StringIO(resp.text))
            return normalize_dataframe(df), "Google Sheet (Live)"
        elif resp.status_code == 401:
            print("Google Sheet access unauthorized. Trying local file...")
        else:
            print(f"Google Sheet returned status code {resp.status_code}. Trying local file...")
    except Exception as e:
        print(f"Error fetching Google Sheet: {e}. Trying local file...")

    # 4. Local Swing Trading Excel file
    local_excel = "swing trade stock/Multi Checks 13072026.xlsx"
    if os.path.exists(local_excel):
        try:
            df = pd.read_excel(local_excel, sheet_name="Watchlist")
            normalized = normalize_dataframe(df)
            normalized["industry"] = "Watchlist Excel"
            return normalized, f"Local Excel ({os.path.basename(local_excel)})"
        except Exception as e:
            print(f"Failed to read Excel {local_excel}: {e}")
            
    raise HTTPException(
        status_code=401,
        detail="Could not access Google Sheet (401 Unauthorized) and no local fallback (watchlist.csv/watchlist.xlsx) was found. Please share the sheet as 'Anyone with the link can view' or save it locally as 'watchlist.csv'."
    )

# API: Get list of sectors / industries
@app.get("/api/industries")
def get_industries():
    try:
        df, source = load_data()
        industries = sorted(list(df["industry"].unique()))
        return {
            "success": True,
            "source": source,
            "industries": industries,
            "total_stocks": len(df)
        }
    except HTTPException as he:
        # Re-raise HTTPExceptions
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API: Fetch screener data for selected industry
@app.get("/api/screener")
def get_screener(industry: str, start_date: str = "2024-01-01"):
    try:
        df, source = load_data()
        
        # Filter for the selected industry
        industry_df = df[df["industry"] == industry]
        if industry_df.empty:
            raise HTTPException(status_code=404, detail=f"Industry '{industry}' not found.")
            
        tickers_to_fetch = []
        ticker_to_info = {}
        
        # Resolve tickers/ISINs
        for _, row in industry_df.iterrows():
            ticker = row["ticker"]
            isin = row["isin"]
            name = row["name"]
            
            # Map ISIN to ticker if ticker is missing
            if (not ticker or pd.isna(ticker) or str(ticker).strip() == "") and isin:
                resolved = resolve_isin_to_ticker(isin)
                if resolved:
                    ticker = resolved
            
            if ticker and isinstance(ticker, str) and ticker.strip() != "":
                ticker = ticker.strip()
                tickers_to_fetch.append(ticker)
                ticker_to_info[ticker] = {
                    "isin": isin,
                    "name": name if name else ticker.split(".")[0],
                }
                
        # Filter duplicates while preserving order
        tickers_to_fetch = list(dict.fromkeys(tickers_to_fetch))
        
        if not tickers_to_fetch:
            raise HTTPException(
                status_code=400,
                detail=f"No valid tickers or ISINs could be resolved for the industry '{industry}'."
            )
            
        # Fetch historical data
        download_start = (pd.to_datetime(start_date) - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
        end_date = datetime.date.today().strftime("%Y-%m-%d")
        
        data = yf.download(tickers_to_fetch, start=download_start, end=end_date, group_by="ticker", progress=False)
        
        if data.empty:
            raise HTTPException(status_code=500, detail="Failed to fetch any market data from Yahoo Finance.")
            
        # Extract close prices
        close_df = pd.DataFrame()
        if len(tickers_to_fetch) == 1:
            ticker = tickers_to_fetch[0]
            if "Close" in data.columns:
                close_df[ticker] = data["Close"]
        else:
            for ticker in tickers_to_fetch:
                if isinstance(data.columns, pd.MultiIndex):
                    if ticker in data.columns.levels[0]:
                        close_df[ticker] = data[ticker]["Close"]
                else:
                    if ticker in data.columns:
                        close_df[ticker] = data[ticker]
                        
        close_df = close_df.dropna(how="all").sort_index()
        if close_df.empty:
            raise HTTPException(status_code=500, detail="No historical price data found after aligning columns.")
            
        # Calculate dynamic EQUAL-WEIGHTED NAV
        target_start_dt = pd.to_datetime(start_date)
        rebased_df = pd.DataFrame(index=close_df.index)
        
        for ticker in close_df.columns:
            ticker_series = close_df[ticker]
            # Find base price: first valid price on or after the target start date
            post_start_series = ticker_series[ticker_series.index >= target_start_dt].dropna()
            if not post_start_series.empty:
                base_price_i = post_start_series.iloc[0]
                if base_price_i > 0:
                    rebased_df[ticker] = (ticker_series / base_price_i) * 100
                    
        if rebased_df.empty:
            raise HTTPException(status_code=400, detail=f"No market data found on or after the selected Start Date: {start_date}")
            
        # Portfolio NAV is the mean of the rebased prices of all active stocks on each day
        nav_series = rebased_df.mean(axis=1, skipna=True)
        valid_stock_counts = rebased_df.notna().sum(axis=1)
        
        nav_df = pd.DataFrame(index=close_df.index)
        nav_df["NAV"] = nav_series
        nav_df["Valid_Count"] = valid_stock_counts
        nav_df["EMA20"] = nav_df["NAV"].ewm(span=20, adjust=False).mean()
        nav_df["EMA50"] = nav_df["NAV"].ewm(span=50, adjust=False).mean()
        nav_df["EMA200"] = nav_df["NAV"].ewm(span=200, adjust=False).mean()
        
        analysis_df = nav_df[nav_df.index >= target_start_dt]
        latest_row = analysis_df.iloc[-1]
        latest_nav = latest_row["NAV"]
        
        # Formulate chart series
        chart_series = []
        for idx, row in analysis_df.iterrows():
            chart_series.append({
                "date": idx.strftime("%Y-%m-%d"),
                "nav": round(float(row["NAV"]), 2),
                "ema20": round(float(row["EMA20"]), 2) if not pd.isna(row["EMA20"]) else None,
                "ema50": round(float(row["EMA50"]), 2) if not pd.isna(row["EMA50"]) else None,
                "ema200": round(float(row["EMA200"]), 2) if not pd.isna(row["EMA200"]) else None,
                "stocks_count": int(row["Valid_Count"])
            })
            
        # Calculate Periodic Returns
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
        periodic_returns = []
        for label, days in periods.items():
            target_date = latest_date - pd.Timedelta(days=days)
            past_data = analysis_df[analysis_df.index <= target_date]
            if not past_data.empty:
                past_nav = past_data["NAV"].iloc[-1]
                chg = ((latest_nav - past_nav) / past_nav) * 100
                periodic_returns.append({
                    "period": label,
                    "return_pct": round(float(chg), 2)
                })
            else:
                periodic_returns.append({
                    "period": label,
                    "return_pct": None
                })
                
        # Calculate Stock vs NAV Performance
        nav_total_roc = latest_nav - 100
        stock_performances = []
        for ticker in tickers_to_fetch:
            if ticker in close_df.columns:
                ticker_series = close_df[ticker][close_df.index >= target_start_dt].dropna()
                if not ticker_series.empty:
                    stock_base_px = ticker_series.iloc[0]
                    stock_cur_px = ticker_series.iloc[-1]
                    if stock_base_px > 0:
                        stock_roc = ((stock_cur_px - stock_base_px) / stock_base_px) * 100
                        vs_nav = stock_roc - nav_total_roc
                        
                        info = ticker_to_info.get(ticker, {"isin": "", "name": ticker})
                        stock_performances.append({
                            "ticker": ticker,
                            "name": info["name"],
                            "isin": info["isin"],
                            "start_price": round(float(stock_base_px), 2),
                            "current_price": round(float(stock_cur_px), 2),
                            "return_pct": round(float(stock_roc), 2),
                            "vs_nav_pct": round(float(vs_nav), 2)
                        })
                        
        stock_performances.sort(key=lambda x: x["return_pct"], reverse=True)
        
        return {
            "success": True,
            "source": source,
            "industry": industry,
            "start_date": start_date,
            "latest_nav": round(float(latest_nav), 2),
            "nav_return_pct": round(float(nav_total_roc), 2),
            "active_stocks": len(tickers_to_fetch),
            "chart_data": chart_series,
            "periodic_returns": periodic_returns,
            "stocks_performance": stock_performances
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Route to serve the main HTML file
@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join("templates", "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Frontend templates/index.html not found.")
    
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
