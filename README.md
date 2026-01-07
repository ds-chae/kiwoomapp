# Kiwoom Trading Application

A comprehensive stock trading application using Kiwoom.com API with web-based interface for account management, order execution, and chart visualization.

## Features

### Core Functionality
- **Account Holdings Management**: View and manage stock holdings across multiple accounts
- **Order Management**: Place buy orders, view unexecuted orders, and cancel orders
- **Interested Stocks**: Track and manage stocks of interest with custom parameters
- **Auto Trading**: Configure automatic buy/sell modes per account
- **Chart Visualization**: View daily and minute candlestick charts with volume bars
- **Authentication**: Secure token-based authentication system

### UI Features
- **Responsive Design**: Mobile-friendly interface with adaptive layouts
- **Real-time Updates**: Auto-refresh every second for live data
- **Interactive Tables**: Click rows to populate buy/interested stock forms
- **Account Selection**: Multi-account checkbox selection for buy orders
- **Horizontal Scrolling**: Scrollable charts and tables for large datasets

## Project Structure

```
kiwoomapp/
├── autotr.py          # Main backend application (FastAPI)
├── autotr.html        # Main application UI (HTML/JS)
├── login.html         # Login page UI (HTML/JS)
├── datagather.py      # Chart data gathering and visualization service
├── interested_stocks.json  # Interested stocks configuration
├── auto_sell_enabled.json # Auto-sell configuration per account
├── chart_data/        # Chart data storage (daily and minute)
│   └── day/           # Daily and minute chart JSON files
└── README.md          # This file
```

## Recent Modifications

### UI/UX Improvements

#### Mobile Responsiveness
- Added mobile detection based on screen width (≤1600px) and touch capability
- Optimized column widths for mobile devices:
  - Account column: "ACCOUNT" → "ACCNT" (4 digits width)
  - Code column: Fixed to 6 digits
  - Name column: Increased to 200px to prevent wrapping
  - Qty column: Fixed to 8 digits in account holdings
  - TYPE column: Fixed to 6 digits in orders section
  - ORDER/CURRENT column: Adjusted width for better display
- Reduced cell padding to minimize wasted space
- Fixed horizontal scrolling for interested stocks section in mobile

#### Table Improvements
- **Account Holdings Section**:
  - Header changed: "AVG BUY PRICE" → "AVGCUR PRC"
  - PRESET PRC/RATE column width: 10 digits (mobile)
  - Qty column width: 8 digits (mobile)
  - Left padding reduced in mobile environment
  - Account header width increased to prevent wrapping

- **Orders Section**:
  - Header changed: "ORDER TYPE" → "TYPE" (mobile)
  - Header changed: "ORDER QTY" → "QTY" (mobile)
  - Right-justified columns: ORDER QTY, ORDER/CURRENT, REMAIN
  - Fixed column widths for consistent display
  - Increased font size for account cells
  - Reduced header height in mobile

- **Interested Stocks Section**:
  - Column headers: "SELLPRICE" → "PRICE", "SELLRATE" → "RATE", "SELLGAP" → "GAP"
  - Fixed column widths:
    - COLOR: 6 digits
    - BType: 6 digits
    - BAmount: 8 digits
    - PRICE: 8 digits
    - RATE: 5 digits
    - GAP: 4 digits
    - Action: 6 digits
  - Section width: Auto (not full width)
  - Horizontal scrolling enabled in mobile

#### Buy Section
- Section header: "Buy Order" → "Buy"
- Input field width limits:
  - Code: 8 digits
  - Name: 20 digits (read-only in mobile, 16 digits width)
  - Price: 6 digits (8 digits width in mobile)
  - Amount: 8 digits (8 digits width in mobile)
- Account selection: Checkbox-based multi-account selection
- Validation: Requires at least one account to be selected
- Account checkboxes aligned with other form fields

### Code Organization

#### HTML/JavaScript Separation
- **autotr.html**: Extracted all HTML and JavaScript from `autotr.py` main application
  - Size: ~91KB
  - Dynamic content: `{IP_SUFFIX}` placeholder replaced at runtime
  - Reduced `autotr.py` by ~2,700 lines

- **login.html**: Extracted login page HTML and JavaScript
  - Size: ~3.8KB
  - Dynamic content: `{IP_SUFFIX}` placeholder replaced at runtime
  - Reduced `autotr.py` by ~149 lines

- **Benefits**:
  - Easier maintenance of frontend code
  - No need to restart backend when modifying HTML/JS
  - Better separation of concerns
  - Authentication and backend logic remain unaffected

### Backend Improvements

#### Buy Order System
- **Multi-Account Support**: Buy orders can be placed for multiple accounts simultaneously
- **Account Selection**: Frontend sends comma-separated account list
- **Individual Execution**: Backend processes each account order separately
- **Validation**: Ensures at least one account is selected before submission
- **API Endpoint**: `/api/buy-order` accepts `accounts` array parameter

#### Cleanup System
- **Automatic Cleanup**: Removes old entries from `interested_stocks.json`
- **Criteria**: Entries older than 10 days that are not in current account holdings
- **Schedule**: Runs daily at 20:30
- **Implementation**: `cleanup_old_interested_stocks()` function with date-based filtering

#### Account Management
- **Account API**: New endpoint `/api/accounts` returns list of available accounts
- **Account Checkboxes**: Dynamically populated from API
- **Auto-Sell Configuration**: Per-account auto-trading mode (NONE, BUY, SELL, BOTH)

### Chart Features (datagather.py)

#### Chart Viewer
- **Stock List**: Displays all available chart data sorted by date and stock code
- **Dual Pane Layout**: Left pane for stock list, right pane for charts
- **Chart Types**:
  - Daily candlestick charts with volume bars
  - Minute candlestick charts with volume bars
- **Chart Features**:
  - Pole chart format (3px width, 1px gap)
  - Color coding: Red (close ≥ open), Blue (close < open)
  - Vertical scaling based on price range
  - Horizontal scrolling with always-visible scrollbar
  - Synchronized scrolling between candlestick and volume charts
  - Rightmost (latest) data visible by default

#### Minute Chart Indicators
- **384-Period Window**: Moving window for price calculations
- **Auxiliary Lines**:
  - Top line (Magenta): Maximum price in window
  - Yellow line: Calculated as `high - (high - low) * 4 / 10`
  - Division line (Green): Midpoint `(minPrice + maxPrice) / 2`
  - Bottom line: Minimum price in window
- **Extension Logic**: Lines extend for 260 candles when no new high appears
- **Day Change Markers**: Vertical dashed lines when date changes

#### Chart Data Management
- **File Organization**: Daily and minute charts stored separately
- **Date Display**: Shows date in stock list for multiple chart files per stock
- **Delete Functionality**: Delete button to remove specific chart data files
- **API Endpoints**:
  - `/api/chart-data/{stock_code}/daily`: Get daily chart data
  - `/api/chart-data/{stock_code}/minute`: Get minute chart data
  - `DELETE /api/chart-data/{stock_code}/{date_str}`: Delete chart data

### Bug Fixes

#### UI Fixes
- Fixed flickering in orders section (mobile/desktop text switching)
- Fixed horizontal scrolling in interested stocks section (mobile)
- Fixed duplicate day candles in daily charts
- Fixed minute chart timestamp display (full YYYYMMDDHHMMSS format)
- Fixed volume chart height (one-fourth of candlestick chart)
- Fixed pole chart color determination (proper open/close comparison)
- Fixed vertical scaling (relative to viewport bounds)

#### Data Handling
- Added deduplication for chart data
- Fixed chronological sorting (oldest left, latest right)
- Fixed price parsing (removed minus signs, handled commas)
- Fixed account holdings price extraction for buy section

## API Endpoints

### Authentication
- `GET /login`, `/stock/login`: Login page
- `POST /api/login`: Authenticate and receive token
- `POST /api/logout`: Logout and invalidate token

### Main Application
- `GET /stock`: Main application page (requires authentication)
- `GET /api/account-data`: Get account holdings data
- `GET /api/miche-data`: Get unexecuted orders
- `GET /api/interested-stocks`: Get interested stocks list
- `GET /api/accounts`: Get list of available accounts
- `GET /api/auto-sell`: Get auto-sell configuration

### Trading Operations
- `POST /api/buy-order`: Place buy order(s) for selected accounts
- `POST /api/cancel-order`: Cancel an unexecuted order
- `POST /api/interested-stocks`: Add/update interested stock
- `DELETE /api/interested-stocks/{stock_code}`: Remove interested stock
- `POST /api/auto-sell`: Update auto-sell configuration

### Chart Data (datagather.py)
- `GET /charts`, `/stock/data/charts`: Chart viewer page
- `GET /api/chart-data/{stock_code}/daily`: Get daily chart data
- `GET /api/chart-data/{stock_code}/minute`: Get minute chart data
- `DELETE /api/chart-data/{stock_code}/{date_str}`: Delete chart data

## Configuration

### Environment Variables
- `KIWOOM_SK`, `KIWOOM_AK`: Kiwoom API credentials
- `SK_0130`, `AK_0130`: Additional account credentials
- `LOGIN_USERNAME`, `LOGIN_PASSWORD`: Web interface login credentials
- `SECRET_KEY`: Token encryption key (auto-generated if not set)

### Data Files
- `interested_stocks.json`: Interested stocks configuration
- `auto_sell_enabled.json`: Auto-sell settings per account
- `chart_data/day/`: Chart data storage directory

## Running the Application

### Backend (autotr.py)
```bash
python autotr.py
```

### Chart Data Service (datagather.py)
```bash
python datagather.py
```

## Technical Details

### Authentication
- Token-based authentication using cookies
- Tokens expire after 24 hours
- Automatic token cleanup for expired tokens

### Data Updates
- Account holdings: Updated every 1 second
- Orders: Updated every 1 second
- Interested stocks: Updated every 1 second
- Charts: Loaded on-demand when stock is selected

### Mobile Detection
- Criteria: Touch device AND screen width ≤ 1600px
- Cached state to prevent flickering
- Dynamic text replacement for mobile-optimized labels

## File Sizes
- `autotr.py`: ~2,200 lines (reduced from ~5,000+ lines)
- `autotr.html`: ~91KB
- `login.html`: ~3.8KB

## Notes
- HTML files use `{IP_SUFFIX}` placeholder which is replaced at runtime
- All API endpoints require authentication except login page
- Chart data is stored in JSON format with timestamp-based filenames
- Mobile optimizations apply to screens ≤1600px width with touch capability

20251228.
let name the analysis as bounce analysis. modify datagather.py. make a csv file that contains bounce analysis dataset. the dataset contains 16 days peak date, high price, low price, its minute bounce low price, bounce high price, daily moving average values at daily paek date, trading amount of peak date. peak dates occur several times in one daily chart. as many peak date occur when 16 days window move. consider the peak date when trde_prica is greater then 150000. this csv building is done when user click 'Make CSV'. add 'Make CSV' button to /stock/data page.

