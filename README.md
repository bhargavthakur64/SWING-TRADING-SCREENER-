# Equal-Weighted Sector Watchlist Screener & TradingView Dashboard

A high-performance financial analytics web application designed for active swing traders. It loads sector watchlists containing **288 stocks** across **11 sectors**, pulls historical price data, computes a **true equal-weighted portfolio NAV**, calculates key exponential moving averages (20, 50, 200 EMA) for trend identification, and displays the result on a dark-themed responsive dashboard powered by the official **TradingView Lightweight Charts** engine.

---

## 🚀 Key Features

1. **True Equal-Weighted NAV Calculation**:
   - Eliminates price-weighted biases. Each stock's price is normalized to a base value of 100 on your selected start date:
     $$P_{i, t}^{norm} = \frac{P_{i, t}}{P_{i, t_{0}}} \times 100$$
   - The overall portfolio NAV is calculated daily as the mathematical average of these normalized stock prices:
     $$\text{NAV}_{t} = \frac{1}{N_{t}} \sum_{i=1}^{N_{t}} P_{i, t}^{norm}$$
   - This ensures a 10% move in a ₹100 stock carries the exact same weight as a 10% move in a ₹2,000 stock.

2. **Official TradingView Charts (v5.2.0)**:
   - Integrates the high-performance canvas-rendered **TradingView Lightweight Charts** library.
   - Supports intuitive browser controls:
     - **Mouse Drag-Pan**: Hold and drag left/right to scroll the timeline, or drag up/down to scroll the canvas.
     - **Mouse Wheel / Trackpad Zoom**: Scroll to zoom in/out of the dates timeline.
     - **Y-Axis Scale Dragging**: Click and drag the right-side price axis scale up/down to compress or stretch the price y-axis manually.
     - **Reset View**: Click the **Reset Zoom** button in the header toolbar to fit all data back to the default viewport immediately.

3. **Multi-Sector Watchlist Dropdown**:
   - Toggle instantly between 11 sectors parsed from your watchlist database.
   - Quick filtering of watchlist stocks using the sidebar search box.

4. **Floating Analytics Cards**:
   - **Periodic Returns Table**: Calculates real-time portfolio performance across standard periods (1 Day, 1 Week, 1 Month, 3 Month, 6 Month, 1 Year, etc.).
   - **Holdings Table**: Displays current stock prices, period rate of change (ROC%), and relative outperformance/underperformance vs. the basket NAV (vs. NAV%).

5. **Local Offline-First Support**:
   - Built-in static copies of React, ReactDOM, Babel, and Lightweight Charts are served directly from the `/static` folder. No reliance on external CDNs ensures ultra-fast offline page load speeds.

---

## 📊 Data Sources & Libraries Used

### 1. Watchlist Database
*   **Local File (`watchlist.csv`)**: Contains 288 National Stock Exchange of India (NSE) symbols mapped directly to company names, sectors, Yahoo symbols (using the `.NS` suffix), and ISIN codes.
*   **Google Sheets (Live Sync Fallback)**: Configured to pull live updates from Google Sheets if configured as public.

### 2. Historical Price Data
*   **Yahoo Finance API (`yfinance`)**: Downloads daily adjusted close prices for all active stocks in the selected sector starting from the warming period (200 trading days prior to the base date) to calculate accurate EMAs.

### 3. Frontend Dependencies
*   **React 18 & Babel**: For component rendering and browser JSX compilation.
*   **TradingView Lightweight Charts v5.2.0**: The official financial charting engine.

---

## 🛠️ Installation & Setup

To run this project locally, ensure you have Python 3 installed.

### Step 1: Install Dependencies
Open your command prompt or terminal in the project directory and install the required Python libraries:
```bash
pip install fastapi uvicorn pandas yfinance requests openpyxl
```

### Step 2: Start the Web Server
Launch the FastAPI backend server:
```bash
python app.py
```

### Step 3: Open the Dashboard
Open your web browser and navigate to:
**[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 📁 Project Directory Structure
*   `app.py` - FastAPI backend application containing data endpoints and NAV calculations.
*   `templates/`
    *   `index.html` - React front-end dashboard with CSS styling.
*   `static/`
    *   `lightweight-charts.js` - Standalone TradingView charting engine.
    *   `react.min.js`, `react-dom.min.js`, `babel.min.js` - Local React runtime dependencies.
*   `watchlist.csv` - Local CSV database file containing parsed stock lists.
*   `README.md` - GitHub markdown documentation.
*   `instructions.txt` - Plain-text notepad guide.
