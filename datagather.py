import json
import time
import os
import traceback
import threading
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from ka10081 import get_day_chart
from ka10080 import get_bun_chart
from au1001 import get_one_token

# Configuration
# Determine the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Define chart data directory: chart_data/day
CHART_DIR = os.path.join(BASE_DIR, 'chart_data', 'day')
INTERESTED_STOCKS_FILE = os.path.join(BASE_DIR, 'interested_stocks.json')

# Global status tracking
status_info = {
    'last_run': None,
    'next_run': None,
    'status': 'initializing',
    'daily_charts_processed': 0,
    'minute_charts_processed': 0,
    'errors': []
}
status_lock = threading.Lock()

# Background thread control
thread_stop_event = threading.Event()
background_thread = None

def ensure_chart_dir():
    """Ensure the chart data directory exists."""
    if not os.path.exists(CHART_DIR):
        try:
            os.makedirs(CHART_DIR)
            print(f"Created directory: {CHART_DIR}")
        except OSError as e:
            print(f"Error creating directory {CHART_DIR}: {e}")

def load_interested_stocks():
    """Load interested stocks from JSON file."""
    if not os.path.exists(INTERESTED_STOCKS_FILE):
        print(f"Interested stocks file not found: {INTERESTED_STOCKS_FILE}")
        return {}
    
    try:
        with open(INTERESTED_STOCKS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {INTERESTED_STOCKS_FILE}: {e}")
        return {}

def save_chart_data(stock_code, date_str, data_list):
    """
    Save chart data to file with date-based filename.
    Filename format: YYYYMMDD_stockcode.json
    No merging - each date gets its own file.
    """
    file_path = os.path.join(CHART_DIR, f"{date_str}_{stock_code}.json")
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4, ensure_ascii=False)
        
        print(f"[{stock_code}] Saved chart data for {date_str}. Total records: {len(data_list)}")
            
    except Exception as e:
        print(f"Error saving file for {stock_code} on {date_str}: {e}")

def chart_file_exists(stock_code, date_str):
    """
    Check if chart file already exists for the given stock and date.
    Only compares the date part (YYYYMMDD).
    """
    file_path = os.path.join(CHART_DIR, f"{date_str}_{stock_code}.json")
    return os.path.exists(file_path)

def save_minute_chart_data(stock_code, date_str, new_data_list):
    """
    Save minute chart data to file with date-based filename.
    Filename format: YYYYMMDD_stockcode_min.json
    Merges with existing data if file exists.
    """
    file_path = os.path.join(CHART_DIR, f"{date_str}_{stock_code}_min.json")
    
    existing_data = []
    
    # Load existing data if file exists
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"Error reading existing minute chart data for {stock_code}: {e}")
    
    # Merge logic: Deduplicate based on full record content
    existing_set = set()
    for record in existing_data:
        try:
            record_str = json.dumps(record, sort_keys=True)
            existing_set.add(record_str)
        except TypeError:
            continue
    
    merged_data = existing_data[:]
    added_count = 0
    
    for record in new_data_list:
        try:
            record_str = json.dumps(record, sort_keys=True)
            if record_str not in existing_set:
                merged_data.append(record)
                existing_set.add(record_str)
                added_count += 1
        except TypeError:
            continue
    
    # Save merged data
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, indent=4, ensure_ascii=False)
        
        if added_count > 0:
            print(f"[{stock_code}] Minute chart for {date_str}: Added {added_count} new records. Total: {len(merged_data)}")
        else:
            print(f"[{stock_code}] Minute chart for {date_str}: No new records. Total: {len(merged_data)}")
    except Exception as e:
        print(f"Error saving minute chart for {stock_code} on {date_str}: {e}")

def should_fetch_minute_chart(update_date_str, current_date_str):
    """
    Determine if minute chart should be fetched based on date difference.
    Returns True if current date is within 10 days after update date.
    """
    try:
        update_date = datetime.strptime(update_date_str, "%Y%m%d")
        current_date = datetime.strptime(current_date_str, "%Y%m%d")
        
        days_diff = (current_date - update_date).days
        
        # Fetch if within 10 days (0 to 10 days inclusive)
        return 0 <= days_diff <= 10
    except Exception as e:
        print(f"Error calculating date difference: {e}")
        return False

def get_daily_chart_files():
    """
    Scan the chart directory and return a list of daily chart files.
    Returns list of tuples: (stock_code, date_str, file_path)
    """
    daily_charts = []
    
    if not os.path.exists(CHART_DIR):
        return daily_charts
    
    try:
        for filename in os.listdir(CHART_DIR):
            # Skip minute chart files
            if filename.endswith('_min.json'):
                continue
            
            # Parse daily chart filename: YYYYMMDD_stockcode.json
            if filename.endswith('.json'):
                parts = filename[:-5].split('_')  # Remove .json and split
                if len(parts) == 2:
                    date_str, stock_code = parts
                    if len(date_str) == 8 and date_str.isdigit():
                        file_path = os.path.join(CHART_DIR, filename)
                        daily_charts.append((stock_code, date_str, file_path))
    except Exception as e:
        print(f"Error scanning chart directory: {e}")
    
    return daily_charts

def gather_minute_charts(token, stocks):
    """
    Scan for daily chart files and gather minute charts for those within 10-day limit.
    Independent from daily chart gathering.
    """
    print(f"\n=== Starting minute chart gathering at {datetime.now()} ===")
    
    current_date_str = datetime.now().strftime("%Y%m%d")
    daily_charts = get_daily_chart_files()
    
    if not daily_charts:
        print("No daily chart files found in directory.")
        return
    
    print(f"Found {len(daily_charts)} daily chart files.")
    
    # Process each daily chart file
    for stock_code, date_str, file_path in daily_charts:
        # Check if within 10-day limit
        if not should_fetch_minute_chart(date_str, current_date_str):
            print(f"[{stock_code}] Daily chart {date_str} is beyond 10-day limit. Skipping minute chart.")
            continue
        
        # Get stock name from interested_stocks if available
        stock_name = stock_code
        if stock_code in stocks:
            stock_name = stocks[stock_code].get('stock_name', stock_code)
        
        print(f"[{stock_code}] Daily chart {date_str} is within 10-day limit. Fetching minute chart...")
        
        try:
            minute_data = get_bun_chart(token, stock_code, stock_name)
            if minute_data and isinstance(minute_data, list):
                save_minute_chart_data(stock_code, date_str, minute_data)
            else:
                print(f"[{stock_code}] No minute chart data returned")
            
            # Be polite to the API rate limits
            time.sleep(0.2)
            
        except Exception as e:
            print(f"[{stock_code}] Error fetching minute chart: {e}")
            traceback.print_exc()
    
    print(f"=== Minute chart gathering finished at {datetime.now()} ===\n")

def run_daily_job():
    global status_info
    
    with status_lock:
        status_info['status'] = 'running'
        status_info['last_run'] = datetime.now().isoformat()
        status_info['daily_charts_processed'] = 0
        status_info['minute_charts_processed'] = 0
    
    print(f"Starting daily data gathering at {datetime.now()}")
    
    # 1. Get Token
    try:
        token = get_one_token()
        if not token:
            print("Failed to obtain access token.")
            with status_lock:
                status_info['status'] = 'error'
                status_info['errors'].append({'time': datetime.now().isoformat(), 'error': 'Failed to obtain access token'})
            return
    except Exception as e:
        print(f"Error getting token: {e}")
        with status_lock:
            status_info['status'] = 'error'
            status_info['errors'].append({'time': datetime.now().isoformat(), 'error': str(e)})
        return

    # 2. Load Stocks
    stocks = load_interested_stocks()
    if not stocks:
        print("No interested stocks to process.")
        with status_lock:
            status_info['status'] = 'idle'
        return
    
    print(f"Found {len(stocks)} stocks to process.")
    
    # 3. Process each stock - Daily charts only
    print(f"\n=== Gathering daily charts ===")
    daily_count = 0
    current_date_str = datetime.now().strftime("%Y%m%d")

    for stock_code, stock_info in stocks.items():
        stock_name = stock_info.get('stock_name', stock_code)
        
        # Get update date from stock_info, default to today if not present
        update_date = stock_info.get('yyyymmdd', '')
        if not update_date or len(update_date) != 8:
            update_date = datetime.now().strftime("%Y%m%d")
            print(f"Warning: {stock_code} has no valid yyyymmdd field, using today's date: {update_date}")
        
        print(f"Processing {stock_code} ({stock_name}) for date {update_date}...")
        
        try:
            if not should_fetch_minute_chart(update_date, current_date_str):
                print(f"[{stock_code}] Daily chart {update_date} is beyond 10-day limit. Skipping minute chart.")
                continue

            # Fetch data using ka10081 with the update date
            result = get_day_chart(token, stock_code, date=current_date_str)
            
            # Basic validation of result
            if not isinstance(result, dict):
                print(f"Invalid response format for {stock_code}")
                continue
                
            if 'return_code' in result and str(result['return_code']) != '0':
                msg = result.get('return_msg', 'Unknown Error')
                print(f"API Error for {stock_code}: {msg} (Code: {result['return_code']})")
                continue
                
            # Extract data list
            # ka10081 main snippet uses 'stk_dt_pole_chart_qry'
            data_list = result.get('stk_dt_pole_chart_qry')
            
            if data_list is None:
                # Try fallback to 'output' if key differs
                data_list = result.get('output')
            
            if data_list and isinstance(data_list, list):
                save_chart_data(stock_code, update_date, data_list)
                daily_count += 1
            else:
                print(f"No chart data found in response for {stock_code}")
                
            # Be polite to the API rate limits
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Exception processing {stock_code}: {e}")
            traceback.print_exc()
            with status_lock:
                status_info['errors'].append({'time': datetime.now().isoformat(), 'stock': stock_code, 'error': str(e)})

    with status_lock:
        status_info['daily_charts_processed'] = daily_count

    # 4. Gather minute charts independently by scanning directory
    minute_count = gather_minute_charts_with_count(token, stocks)
    
    with status_lock:
        status_info['minute_charts_processed'] = minute_count
        status_info['status'] = 'idle'
        # Keep only last 10 errors
        if len(status_info['errors']) > 10:
            status_info['errors'] = status_info['errors'][-10:]
    
    print(f"Daily job finished at {datetime.now()}")

def gather_minute_charts_with_count(token, stocks):
    """Wrapper for gather_minute_charts that returns count."""
    print(f"\n=== Starting minute chart gathering at {datetime.now()} ===")
    
    current_date_str = datetime.now().strftime("%Y%m%d")
    daily_charts = get_daily_chart_files()
    
    if not daily_charts:
        print("No daily chart files found in directory.")
        return 0
    
    print(f"Found {len(daily_charts)} daily chart files.")
    
    minute_count = 0
    # Process each daily chart file
    for stock_code, date_str, file_path in daily_charts:
        # Check if within 10-day limit
        if not should_fetch_minute_chart(date_str, current_date_str):
            print(f"[{stock_code}] Daily chart {date_str} is beyond 10-day limit. Skipping minute chart.")
            continue
        
        # Get stock name from interested_stocks if available
        stock_name = stock_code
        if stock_code in stocks:
            stock_name = stocks[stock_code].get('stock_name', stock_code)
        
        print(f"[{stock_code}] Daily chart {date_str} is within 10-day limit. Fetching minute chart...")
        
        try:
            minute_data = get_bun_chart(token, stock_code, stock_name)
            if minute_data and isinstance(minute_data, list):
                save_minute_chart_data(stock_code, date_str, minute_data)
                minute_count += 1
            else:
                print(f"[{stock_code}] No minute chart data returned")
            
            # Be polite to the API rate limits
            time.sleep(0.2)
            
        except Exception as e:
            print(f"[{stock_code}] Error fetching minute chart: {e}")
            traceback.print_exc()
    
    print(f"=== Minute chart gathering finished at {datetime.now()} ===\n")
    return minute_count

def background_data_gathering():
    """Background thread that runs the data gathering loop."""
    global status_info, thread_stop_event
    
    ensure_chart_dir()
    print("Background data gathering thread started.")
    
    # Run once on startup
    print("Running initial data gathering...")
    run_daily_job()

    print("Waiting for execution time (21:00 daily)...")
    
    while not thread_stop_event.is_set():
        now = datetime.now()
        
        # Calculate next run time
        next_run = datetime(now.year, now.month, now.day, 21, 0, 0)
        if now.hour >= 21:
            next_run += timedelta(days=1)
        
        with status_lock:
            status_info['next_run'] = next_run.isoformat()
        
        # Check if it's 21:00 (9 PM)
        if now.hour == 21 and now.minute == 0:
            run_daily_job()
            # Sleep for 61 seconds to ensure we don't match the condition again today
            time.sleep(61)
        else:
            # Sleep for 30 seconds before checking again, but check stop event
            for _ in range(30):
                if thread_stop_event.is_set():
                    break
                time.sleep(1)
    
    print("Background data gathering thread stopped.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    global background_thread, thread_stop_event, status_info
    
    # Startup
    print("Starting FastAPI application...")
    
    with status_lock:
        status_info['status'] = 'starting'
    
    # Start background thread
    thread_stop_event.clear()
    background_thread = threading.Thread(
        target=background_data_gathering,
        daemon=False,
        name="DataGatheringThread"
    )
    background_thread.start()
    print("Background thread started successfully")
    
    yield
    
    # Shutdown
    print("Shutting down application...")
    thread_stop_event.set()
    if background_thread and background_thread.is_alive():
        print("Waiting for background thread to stop...")
        background_thread.join(timeout=10.0)
        if background_thread.is_alive():
            print("Warning: Background thread did not stop within timeout")
        else:
            print("Background thread stopped successfully")
    print("Application shutdown complete")

# FastAPI app
app = FastAPI(lifespan=lifespan, title="Data Gather Service")

@app.get("/", response_class=HTMLResponse)
@app.get("/stock/data", response_class=HTMLResponse)
@app.get("/stock/data/", response_class=HTMLResponse)
async def root():
    """Display status page."""
    with status_lock:
        status = status_info.copy()
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Data Gather Service</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 1000px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .content {{
                padding: 30px;
            }}
            .status-card {{
                background: #f5f5f5;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 20px;
            }}
            .status-card h2 {{
                margin-bottom: 15px;
                color: #333;
            }}
            .status-item {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #ddd;
            }}
            .status-item:last-child {{
                border-bottom: none;
            }}
            .status-label {{
                font-weight: 600;
                color: #555;
            }}
            .status-value {{
                color: #333;
            }}
            .status-running {{
                color: #4caf50;
                font-weight: bold;
            }}
            .status-idle {{
                color: #2196f3;
                font-weight: bold;
            }}
            .status-error {{
                color: #f44336;
                font-weight: bold;
            }}
            .error-list {{
                max-height: 200px;
                overflow-y: auto;
                background: #fff;
                border-radius: 4px;
                padding: 10px;
            }}
            .error-item {{
                padding: 8px;
                margin-bottom: 8px;
                background: #ffebee;
                border-left: 4px solid #f44336;
                border-radius: 4px;
                font-size: 14px;
            }}
            .btn-charts {{
                background: rgba(255, 255, 255, 0.2);
                color: white;
                border: 2px solid rgba(255, 255, 255, 0.3);
                padding: 12px 24px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 16px;
                font-weight: 600;
                text-decoration: none;
                display: inline-block;
                transition: all 0.3s;
                margin-top: 15px;
            }}
            .btn-charts:hover {{
                background: rgba(255, 255, 255, 0.3);
                border-color: rgba(255, 255, 255, 0.5);
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            }}
        </style>
        <script>
            // Auto-refresh every 10 seconds
            setTimeout(() => location.reload(), 10000);
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Data Gather Service</h1>
                <p>Stock Chart Data Collection System</p>
                <a href="./charts" class="btn-charts">📈 View Charts</a>
            </div>
            <div class="content">
                <div class="status-card">
                    <h2>System Status</h2>
                    <div class="status-item">
                        <span class="status-label">Status:</span>
                        <span class="status-value status-{status['status']}">{status['status'].upper()}</span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">Last Run:</span>
                        <span class="status-value">{status['last_run'] or 'Not yet run'}</span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">Next Run:</span>
                        <span class="status-value">{status['next_run'] or 'Calculating...'}</span>
                    </div>
                </div>
                
                <div class="status-card">
                    <h2>Last Run Statistics</h2>
                    <div class="status-item">
                        <span class="status-label">Daily Charts Processed:</span>
                        <span class="status-value">{status['daily_charts_processed']}</span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">Minute Charts Processed:</span>
                        <span class="status-value">{status['minute_charts_processed']}</span>
                    </div>
                </div>
                
                <div class="status-card">
                    <h2>Recent Errors</h2>
                    <div class="error-list">
                        {''.join([f'<div class="error-item"><strong>{e.get("time", "Unknown time")}</strong><br>{e.get("stock", "")} {e.get("error", "Unknown error")}</div>' for e in status['errors'][-5:]]) if status['errors'] else '<p>No recent errors</p>'}
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/status")
@app.get("/stock/data/api/status")
async def get_status():
    """Get current status as JSON."""
    with status_lock:
        return JSONResponse(content=status_info.copy())

@app.post("/api/trigger")
@app.post("/stock/data/api/trigger")
async def trigger_job():
    """Manually trigger a data gathering job."""
    threading.Thread(target=run_daily_job, daemon=True).start()
    return {"status": "success", "message": "Data gathering job triggered"}

def get_stock_list():
    """Get list of unique stocks from chart_data directory with their names."""
    stocks = {}
    interested_stocks = load_interested_stocks()
    
    if not os.path.exists(CHART_DIR):
        return stocks
    
    try:
        for filename in os.listdir(CHART_DIR):
            # Skip minute chart files
            if filename.endswith('_min.json'):
                continue
            
            # Parse daily chart filename: YYYYMMDD_stockcode.json
            if filename.endswith('.json'):
                parts = filename[:-5].split('_')  # Remove .json and split
                if len(parts) == 2:
                    date_str, stock_code = parts
                    if len(date_str) == 8 and date_str.isdigit():
                        if stock_code not in stocks:
                            # Get stock name from interested_stocks
                            stock_name = stock_code
                            if stock_code in interested_stocks:
                                stock_name = interested_stocks[stock_code].get('stock_name', stock_code)
                            stocks[stock_code] = stock_name
    except Exception as e:
        print(f"Error scanning chart directory: {e}")
    
    return stocks

@app.get("/charts", response_class=HTMLResponse)
@app.get("/stock/data/charts", response_class=HTMLResponse)
@app.get("/stock/data/charts/", response_class=HTMLResponse)
async def charts_page():
    """Display chart viewer page."""
    stocks = get_stock_list()
    
    html_content = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Chart Viewer</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 10px;
                min-height: 100vh;
            }
            .container {
                display: flex;
                height: calc(100vh - 20px);
                gap: 10px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                overflow: hidden;
            }
            .left-pane {
                width: 250px;
                background: #f8f9fa;
                border-right: 2px solid #e0e0e0;
                overflow-y: auto;
                padding: 15px;
            }
            .left-pane h2 {
                margin-bottom: 15px;
                color: #333;
                font-size: 1.2em;
            }
            .stock-item {
                padding: 10px;
                margin-bottom: 8px;
                background: white;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.2s;
                border: 2px solid transparent;
            }
            .stock-item:hover {
                background: #e3f2fd;
                border-color: #667eea;
            }
            .stock-item.selected {
                background: #bbdefb;
                border-color: #667eea;
            }
            .stock-code {
                font-weight: bold;
                font-size: 14px;
                color: #333;
                margin-bottom: 4px;
            }
            .stock-name {
                font-size: 12px;
                color: #666;
            }
            .right-pane {
                flex: 1;
                display: flex;
                flex-direction: column;
                padding: 15px;
                overflow: hidden;
            }
            .chart-container {
                flex: 1;
                margin-bottom: 10px;
                background: white;
                border-radius: 8px;
                padding: 15px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                overflow-x: auto;
                overflow-y: hidden;
                scroll-behavior: smooth;
            }
            .chart-container:last-child {
                margin-bottom: 0;
            }
            .chart-title {
                font-size: 14px;
                font-weight: 600;
                color: #333;
                margin-bottom: 10px;
            }
            .chart-wrapper {
                position: relative;
                width: 100%;
                min-width: 800px;
                height: calc(100% - 30px);
                display: flex;
                flex-direction: column;
            }
            .candlestick-chart {
                flex: 4;
                position: relative;
                width: 100%;
                height: 0; /* Required for flex to work properly */
                overflow: visible;
            }
            .candlestick-chart canvas {
                display: block;
                width: 100%;
                height: 100%;
            }
            .volume-chart {
                flex: 1;
                position: relative;
                width: 100%;
                height: 0; /* Required for flex to work properly */
                border-top: 1px solid #e0e0e0;
                overflow: visible;
            }
            .volume-chart canvas {
                display: block;
                width: 100%;
                height: 100%;
            }
            .empty-state {
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100%;
                color: #999;
                font-size: 16px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="left-pane">
                <h2>Stocks</h2>
                <div id="stock-list">
    """
    
    # Add stock items
    sorted_stocks = sorted(stocks.items())
    for stock_code, stock_name in sorted_stocks:
        html_content += f"""
                    <div class="stock-item" data-stock-code="{stock_code}" onclick="loadStockCharts('{stock_code}')">
                        <div class="stock-code">{stock_code}</div>
                        <div class="stock-name">{stock_name}</div>
                    </div>
        """
    
    html_content += """
                </div>
            </div>
            <div class="right-pane">
                <div class="chart-container">
                    <div class="chart-title">Daily Chart</div>
                    <div class="chart-wrapper">
                        <div class="candlestick-chart">
                            <canvas id="daily-chart"></canvas>
                        </div>
                        <div class="volume-chart">
                            <canvas id="daily-volume-chart"></canvas>
                        </div>
                    </div>
                </div>
                <div class="chart-container">
                    <div class="chart-title">Minute Chart</div>
                    <div class="chart-wrapper">
                        <div class="candlestick-chart">
                            <canvas id="minute-chart"></canvas>
                        </div>
                        <div class="volume-chart">
                            <canvas id="minute-volume-chart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <script>
            let dailyChartData = null;
            let minuteChartData = null;
            
            function selectStock(stockCode) {
                document.querySelectorAll('.stock-item').forEach(item => {
                    item.classList.remove('selected');
                });
                const item = document.querySelector(`[data-stock-code="${stockCode}"]`);
                if (item) {
                    item.classList.add('selected');
                }
            }
            
            function loadStockCharts(stockCode) {
                selectStock(stockCode);
                
                // Load daily chart
                fetch(`./api/chart-data/${stockCode}/daily`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success' && data.data) {
                            dailyChartData = data.data;
                            drawDailyChart(dailyChartData);
                            // drawDailyChart already calls drawVolumeChart internally
                        } else {
                            dailyChartData = null;
                            clearChart('daily-chart');
                            clearChart('daily-volume-chart');
                        }
                    })
                    .catch(error => {
                        console.error('Error loading daily chart:', error);
                        dailyChartData = null;
                        clearChart('daily-chart');
                        clearChart('daily-volume-chart');
                    });
                
                // Load minute chart - independently, not limited by daily chart dates
                fetch(`./api/chart-data/${stockCode}/minute`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success' && data.data) {
                            minuteChartData = data.data;
                            drawMinuteChart(minuteChartData);
                            // drawMinuteChart already calls drawVolumeChart internally
                        } else {
                            minuteChartData = null;
                            clearChart('minute-chart');
                            clearChart('minute-volume-chart');
                        }
                    })
                    .catch(error => {
                        console.error('Error loading minute chart:', error);
                        minuteChartData = null;
                        clearChart('minute-chart');
                        clearChart('minute-volume-chart');
                    });
            }
            
            function parsePrice(priceStr) {
                if (!priceStr) return 0;
                // Remove + sign, minus sign, and parse
                const cleaned = priceStr.toString().replace(/^[+-]/, '').replace(/,/g, '');
                return parseFloat(cleaned) || 0;
            }
            
            function drawPoleChart(canvasId, data, getLabel) {
                const canvas = document.getElementById(canvasId);
                const ctx = canvas.getContext('2d');
                const wrapper = canvas.parentElement;
                
                // Clear canvas
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                if (!data || data.length === 0) {
                    canvas.width = wrapper.clientWidth;
                    canvas.height = wrapper.clientHeight;
                    return;
                }
                
                // Sort data: oldest first (left), latest last (right)
                // API returns data with latest first (reverse=True), so we sort ascending
                // This ensures: index 0 = oldest (leftmost), last index = latest (rightmost)
                const sortedData = [...data].sort((a, b) => {
                    const keyA = getLabel(a) || '';
                    const keyB = getLabel(b) || '';
                    // For dates (YYYYMMDD) and times (YYYYMMDDHHMMSS), string comparison works correctly
                    // Ascending: smaller value (older) comes first, larger value (newer) comes last
                    if (keyA < keyB) return -1;  // A is older, put it first (left)
                    if (keyA > keyB) return 1;  // B is older, put it first (left)
                    return 0;
                });
                
                // Deduplicate: Remove duplicate entries with the same label (date/time)
                // Keep the first occurrence of each unique date/time
                const seen = new Set();
                const deduplicatedData = [];
                for (const item of sortedData) {
                    const label = getLabel(item);
                    if (!seen.has(label)) {
                        seen.add(label);
                        deduplicatedData.push(item);
                    }
                }
                const finalData = deduplicatedData;
                
                // Step 1: Parse all prices and collect ALL price values
                const allPriceValues = [];
                const priceData = finalData.map(item => {
                    const openVal = parsePrice(item.open_pric);
                    const closeVal = parsePrice(item.cur_prc);  // cur_prc is closing price
                    const highVal = parsePrice(item.high_pric);
                    const lowVal = parsePrice(item.low_pric);
                    
                    // Remove minus signs and ensure valid numbers
                    const open = isNaN(openVal) ? 0 : Math.abs(openVal);
                    const close = isNaN(closeVal) ? 0 : Math.abs(closeVal);
                    const high = isNaN(highVal) ? 0 : Math.abs(highVal);
                    const low = isNaN(lowVal) ? 0 : Math.abs(lowVal);
                    
                    // Collect all price values for bounds calculation
                    if (open > 0) allPriceValues.push(open);
                    if (close > 0) allPriceValues.push(close);
                    if (high > 0) allPriceValues.push(high);
                    if (low > 0) allPriceValues.push(low);
                    
                    return {
                        open: open,
                        high: high,
                        low: low,
                        close: close,
                        label: getLabel(item)
                    };
                }).filter(p => p.open > 0 || p.close > 0 || p.high > 0 || p.low > 0);
                
                if (priceData.length === 0) {
                    canvas.width = wrapper.clientWidth;
                    canvas.height = wrapper.clientHeight;
                    return;
                }
                
                // Step 2: Calculate lower and upper bounds from ALL prices in viewport
                let lowerBound = Math.min(...allPriceValues);
                let upperBound = Math.max(...allPriceValues);
                
                // Handle edge case where all prices are the same
                if (lowerBound === upperBound || lowerBound === Infinity || upperBound === -Infinity) {
                    if (priceData.length > 0) {
                        const first = priceData[0];
                        lowerBound = Math.min(first.low, first.open, first.close, first.high);
                        upperBound = Math.max(first.high, first.open, first.close, first.low);
                        if (lowerBound === upperBound) {
                            lowerBound = lowerBound * 0.95;
                            upperBound = upperBound * 1.05;
                        }
                    } else {
                        lowerBound = 0;
                        upperBound = 100;
                    }
                }
                
                // Add padding (5% on each side)
                const priceRange = upperBound - lowerBound;
                const padding = Math.max(priceRange * 0.05, 1);
                lowerBound = lowerBound - padding;
                upperBound = upperBound + padding;
                
                // Chart dimensions
                const poleWidth = 3;
                const poleGap = 1;
                const poleSpacing = poleWidth + poleGap;
                const leftMargin = 60;
                const rightMargin = 20;
                const topMargin = 20;
                const bottomMargin = 40;
                
                // Calculate required width for all poles
                const numPoles = priceData.length;
                const requiredChartWidth = numPoles * poleSpacing;
                const minChartWidth = wrapper.clientWidth - leftMargin - rightMargin;
                const actualChartWidth = Math.max(requiredChartWidth, minChartWidth);
                
                // Set canvas size - use offsetHeight to get the actual rendered height
                canvas.height = wrapper.offsetHeight || wrapper.clientHeight;
                canvas.width = leftMargin + actualChartWidth + rightMargin;
                
                const chartHeight = canvas.height - topMargin - bottomMargin;
                
                // Step 3: Calculate scale factor for relative positioning
                const priceRangeScaled = upperBound - lowerBound;
                const scaleFactor = priceRangeScaled > 0 ? chartHeight / priceRangeScaled : 1;
                
                // Helper function to convert price to Y coordinate using relative values
                // Formula: y = topMargin + chartHeight - ((price - lowerBound) * scaleFactor)
                const priceToY = (price) => {
                    const relativeValue = (price - lowerBound) * scaleFactor;
                    return topMargin + chartHeight - relativeValue;
                };
                
                // Draw axes
                ctx.strokeStyle = '#ccc';
                ctx.lineWidth = 1;
                ctx.beginPath();
                // Y-axis
                ctx.moveTo(leftMargin, topMargin);
                ctx.lineTo(leftMargin, topMargin + chartHeight);
                // X-axis (full width)
                ctx.moveTo(leftMargin, topMargin + chartHeight);
                ctx.lineTo(leftMargin + actualChartWidth, topMargin + chartHeight);
                ctx.stroke();
                
                // Draw price labels on Y-axis
                ctx.fillStyle = '#666';
                ctx.font = '10px Arial';
                ctx.textAlign = 'right';
                ctx.textBaseline = 'middle';
                const numTicks = 10;
                for (let i = 0; i <= numTicks; i++) {
                    const price = upperBound - (upperBound - lowerBound) * (i / numTicks);
                    const y = priceToY(price);
                    ctx.fillText(Math.round(price).toLocaleString(), leftMargin - 5, y);
                }
                
                // Step 4: Draw all poles using relative values
                priceData.forEach((pole, index) => {
                    const x = leftMargin + (index * poleSpacing) + (poleWidth / 2);
                    
                    // Calculate Y positions using relative scaling based on bounds
                    const highY = priceToY(pole.high);
                    const lowY = priceToY(pole.low);
                    const openY = priceToY(pole.open);
                    const closeY = priceToY(pole.close);
                    
                    // Determine color: Red if close >= open, Blue if close < open
                    // Compare the actual numeric values
                    const isRising = pole.close >= pole.open;
                    const color = isRising ? '#ff0000' : '#0000ff';
                    
                    // Draw high-low line
                    ctx.beginPath();
                    ctx.strokeStyle = color;
                    ctx.lineWidth = 1;
                    ctx.moveTo(x, highY);
                    ctx.lineTo(x, lowY);
                    ctx.stroke();
                    
                    // Draw open-close rectangle
                    const rectTop = Math.min(openY, closeY);
                    const rectBottom = Math.max(openY, closeY);
                    const rectHeight = Math.max(1, rectBottom - rectTop);
                    
                    ctx.beginPath();
                    ctx.fillStyle = color;
                    ctx.fillRect(x - poleWidth / 2, rectTop, poleWidth, rectHeight);
                    ctx.fill();
                });
                
                // Draw division line, top line, and bottom line for minute charts (384-period window)
                if (canvasId === 'minute-chart' && priceData.length > 0) {
                    const period = 384;
                    const extensionPeriod = 260; // Extend for 260 candles until new high appears
                    const divisionPoints = [];
                    const topPoints = [];
                    const bottomPoints = [];
                    
                    let previousMax = null;
                    let previousMin = null;
                    let extensionCount = 0;
                    let maxHighSeen = -Infinity; // Track the maximum high price seen so far
                    
                    // Calculate division, top, and bottom values for each point
                    for (let i = 0; i < priceData.length; i++) {
                        const currentHigh = priceData[i].high;
                        
                        // Update maximum high seen
                        if (currentHigh > maxHighSeen) {
                            maxHighSeen = currentHigh;
                        }
                        
                        let minPrice, maxPrice;
                        
                        // Check if we should extend: current high is less than max high seen
                        // AND we have previous values AND extension count is within limit
                        if (currentHigh < maxHighSeen && previousMax !== null && previousMin !== null && extensionCount < extensionPeriod) {
                            // Extend previous window values
                            maxPrice = previousMax;
                            minPrice = previousMin;
                            extensionCount++;
                        } else {
                            // Calculate normally (new high appeared, or extension expired, or first candle)
                            const startIdx = Math.max(0, i - period + 1);
                            const windowData = priceData.slice(startIdx, i + 1);
                            
                            minPrice = Infinity;
                            maxPrice = -Infinity;
                            
                            windowData.forEach(pole => {
                                minPrice = Math.min(minPrice, pole.low, pole.open, pole.close, pole.high);
                                maxPrice = Math.max(maxPrice, pole.high, pole.open, pole.close, pole.low);
                            });
                            
                            // Update previous values
                            previousMax = maxPrice;
                            previousMin = minPrice;
                            
                            // Reset extension count if new high appeared
                            if (currentHigh >= maxHighSeen) {
                                extensionCount = 0;
                            }
                        }
                        
                        const x = leftMargin + (i * poleSpacing) + (poleWidth / 2);
                        
                        // Calculate division as midpoint of min and max
                        const division = (minPrice + maxPrice) / 2;
                        divisionPoints.push({
                            x: x,
                            y: priceToY(division),
                            value: division
                        });
                        
                        // Top line (maximum price)
                        topPoints.push({
                            x: x,
                            y: priceToY(maxPrice),
                            value: maxPrice
                        });
                        
                        // Bottom line (minimum price)
                        bottomPoints.push({
                            x: x,
                            y: priceToY(minPrice),
                            value: minPrice
                        });
                    }
                    
                    // Draw the top line (maximum)
                    if (topPoints.length > 0) {
                        ctx.strokeStyle = '#ff00ff'; // Magenta color for top line
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        
                        topPoints.forEach((point, index) => {
                            if (index === 0) {
                                ctx.moveTo(point.x, point.y);
                            } else {
                                ctx.lineTo(point.x, point.y);
                            }
                        });
                        
                        ctx.stroke();
                    }
                    
                    // Draw the bottom line (minimum)
                    if (bottomPoints.length > 0) {
                        ctx.strokeStyle = '#0000ff'; // Blue color for bottom line
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        
                        bottomPoints.forEach((point, index) => {
                            if (index === 0) {
                                ctx.moveTo(point.x, point.y);
                            } else {
                                ctx.lineTo(point.x, point.y);
                            }
                        });
                        
                        ctx.stroke();
                    }
                    
                    // Draw the division line (midpoint)
                    if (divisionPoints.length > 0) {
                        ctx.strokeStyle = '#00ff00'; // Green color for division line
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        
                        divisionPoints.forEach((point, index) => {
                            if (index === 0) {
                                ctx.moveTo(point.x, point.y);
                            } else {
                                ctx.lineTo(point.x, point.y);
                            }
                        });
                        
                        ctx.stroke();
                    }
                }
                
                // Draw day change lines for minute charts (if timestamp format is YYYYMMDDHHMMSS)
                if (canvasId === 'minute-chart' && priceData.length > 0) {
                    ctx.strokeStyle = '#999';
                    ctx.lineWidth = 1;
                    ctx.setLineDash([2, 2]); // Dashed line
                    
                    for (let i = 1; i < priceData.length; i++) {
                        const prevLabel = priceData[i - 1].label;
                        const currLabel = priceData[i].label;
                        
                        // Extract date part (first 8 characters: YYYYMMDD)
                        const prevDate = prevLabel.length >= 8 ? prevLabel.substring(0, 8) : '';
                        const currDate = currLabel.length >= 8 ? currLabel.substring(0, 8) : '';
                        
                        // If date changed, draw a vertical line
                        if (prevDate && currDate && prevDate !== currDate) {
                            const x = leftMargin + (i * poleSpacing) + (poleWidth / 2);
                            ctx.beginPath();
                            ctx.moveTo(x, topMargin);
                            ctx.lineTo(x, topMargin + chartHeight);
                            ctx.stroke();
                        }
                    }
                    
                    ctx.setLineDash([]); // Reset to solid line
                }
                
                // Draw X-axis labels (show some labels to avoid crowding)
                ctx.fillStyle = '#666';
                ctx.font = '9px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                const labelStep = Math.max(1, Math.floor(numPoles / 20));
                priceData.forEach((pole, index) => {
                    if (index % labelStep === 0 || index === numPoles - 1) {
                        const x = leftMargin + (index * poleSpacing) + (poleWidth / 2);
                        ctx.save();
                        ctx.translate(x, topMargin + chartHeight + 5);
                        ctx.rotate(-Math.PI / 4);
                        ctx.fillText(pole.label, 0, 0);
                        ctx.restore();
                    }
                });
            }
            
            function scrollChartToRight(canvasId) {
                // Scroll to the rightmost (latest) data
                // Find the chart container that contains this canvas
                const canvas = document.getElementById(canvasId);
                if (canvas) {
                    const container = canvas.closest('.chart-container');
                    if (container) {
                        // Scroll to maximum scroll position (rightmost) after a short delay
                        // to ensure canvas width is set
                        setTimeout(() => {
                            container.scrollLeft = container.scrollWidth - container.clientWidth;
                        }, 150);
                    }
                }
            }
            
            function drawDailyChart(data) {
                const getLabel = (item) => item.dt || '';
                // Draw candlestick first
                drawPoleChart('daily-chart', data, getLabel);
                // Draw volume chart with same width as candlestick
                const candlestickCanvas = document.getElementById('daily-chart');
                if (candlestickCanvas) {
                    drawVolumeChart('daily-volume-chart', data, getLabel, candlestickCanvas.width);
                }
                // Scroll to rightmost (latest) data
                scrollChartToRight('daily-chart');
            }
            
            function drawMinuteChart(data) {
                const getLabel = (item) => {
                    // Use timestamp as-is (YYYYMMDDHHMMSS format)
                    return item.cntr_tm || '';
                };
                // Draw candlestick first
                drawPoleChart('minute-chart', data, getLabel);
                // Draw volume chart with same width as candlestick
                const candlestickCanvas = document.getElementById('minute-chart');
                if (candlestickCanvas) {
                    drawVolumeChart('minute-volume-chart', data, getLabel, candlestickCanvas.width);
                }
                // Scroll to rightmost (latest) data
                scrollChartToRight('minute-chart');
            }
            
            function drawVolumeChart(canvasId, data, getLabel, candlestickWidth) {
                const canvas = document.getElementById(canvasId);
                if (!canvas) return;
                
                const ctx = canvas.getContext('2d');
                const wrapper = canvas.parentElement;
                
                // Clear canvas
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                if (!data || data.length === 0) {
                    canvas.width = candlestickWidth || wrapper.clientWidth;
                    canvas.height = wrapper.clientHeight;
                    return;
                }
                
                // Sort data: oldest first (left), latest last (right) - same as candlestick chart
                // API returns data with latest first, so we sort ascending to match candlestick
                const sortedData = [...data].sort((a, b) => {
                    const keyA = getLabel(a) || '';
                    const keyB = getLabel(b) || '';
                    // Ascending: smaller value (older) comes first, larger value (newer) comes last
                    if (keyA < keyB) return -1;  // A is older, put it first (left)
                    if (keyA > keyB) return 1;   // B is older, put it first (left)
                    return 0;
                });
                
                // Deduplicate: Remove duplicate entries with the same label (date/time)
                // Keep the first occurrence of each unique date/time
                const seen = new Set();
                const deduplicatedData = [];
                for (const item of sortedData) {
                    const label = getLabel(item);
                    if (!seen.has(label)) {
                        seen.add(label);
                        deduplicatedData.push(item);
                    }
                }
                const finalData = deduplicatedData;
                
                // Parse volume data
                const volumeData = finalData.map(item => {
                    const qtyStr = item.trde_qty || '0';
                    const qty = parseFloat(qtyStr.toString().replace(/,/g, '')) || 0;
                    return {
                        volume: qty,
                        label: getLabel(item)
                    };
                }).filter(v => v.volume > 0);
                
                if (volumeData.length === 0) {
                    canvas.width = candlestickWidth || wrapper.clientWidth;
                    canvas.height = wrapper.clientHeight;
                    return;
                }
                
                // Find max volume for scaling
                const maxVolume = Math.max(...volumeData.map(v => v.volume));
                
                // Chart dimensions - must match candlestick chart exactly
                const poleWidth = 3;
                const poleGap = 1;
                const poleSpacing = poleWidth + poleGap;
                const leftMargin = 60;
                const rightMargin = 20;
                const topMargin = 5;
                const bottomMargin = 20;
                
                // Set canvas size - width MUST match candlestick chart for synchronized scrolling
                // Use offsetHeight to get the actual rendered height (respects flex sizing)
                canvas.height = wrapper.offsetHeight || wrapper.clientHeight;
                canvas.width = candlestickWidth || (leftMargin + volumeData.length * poleSpacing + rightMargin);
                
                const chartHeight = canvas.height - topMargin - bottomMargin;
                
                // Calculate volume scale
                const volumeScale = maxVolume > 0 ? chartHeight / maxVolume : 1;
                
                // Draw volume bars - use same X positions as candlestick chart
                volumeData.forEach((vol, index) => {
                    const x = leftMargin + (index * poleSpacing) + (poleWidth / 2);
                    const barHeight = vol.volume * volumeScale;
                    const barY = topMargin + chartHeight - barHeight;
                    
                    // Use gray color for volume bars
                    ctx.fillStyle = '#888';
                    ctx.fillRect(x - poleWidth / 2, barY, poleWidth, barHeight);
                });
                
                // Draw day change lines for minute volume charts (if timestamp format is YYYYMMDDHHMMSS)
                if (canvasId === 'minute-volume-chart' && volumeData.length > 0) {
                    ctx.strokeStyle = '#999';
                    ctx.lineWidth = 1;
                    ctx.setLineDash([2, 2]); // Dashed line
                    
                    for (let i = 1; i < volumeData.length; i++) {
                        const prevLabel = volumeData[i - 1].label;
                        const currLabel = volumeData[i].label;
                        
                        // Extract date part (first 8 characters: YYYYMMDD)
                        const prevDate = prevLabel.length >= 8 ? prevLabel.substring(0, 8) : '';
                        const currDate = currLabel.length >= 8 ? currLabel.substring(0, 8) : '';
                        
                        // If date changed, draw a vertical line
                        if (prevDate && currDate && prevDate !== currDate) {
                            const x = leftMargin + (i * poleSpacing) + (poleWidth / 2);
                            ctx.beginPath();
                            ctx.moveTo(x, topMargin);
                            ctx.lineTo(x, topMargin + chartHeight);
                            ctx.stroke();
                        }
                    }
                    
                    ctx.setLineDash([]); // Reset to solid line
                }
                
                // Draw Y-axis labels for volume
                ctx.fillStyle = '#666';
                ctx.font = '9px Arial';
                ctx.textAlign = 'right';
                ctx.textBaseline = 'middle';
                const numTicks = 5;
                for (let i = 0; i <= numTicks; i++) {
                    const volume = maxVolume - (maxVolume * i / numTicks);
                    const y = topMargin + (chartHeight * i / numTicks);
                    ctx.fillText(Math.round(volume).toLocaleString(), leftMargin - 5, y);
                }
            }
            
            function clearChart(canvasId) {
                const canvas = document.getElementById(canvasId);
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
            
            // Handle window resize
            window.addEventListener('resize', () => {
                if (dailyChartData) {
                    drawDailyChart(dailyChartData);
                }
                if (minuteChartData) {
                    drawMinuteChart(minuteChartData);
                }
            });
            
            // Synchronize scrolling between candlestick and volume charts
            function syncScroll(sourceId, targetId) {
                const source = document.getElementById(sourceId);
                const target = document.getElementById(targetId);
                if (source && target) {
                    source.addEventListener('scroll', () => {
                        target.scrollLeft = source.scrollLeft;
                    });
                }
            }
            
            // Set up scroll synchronization after charts are drawn
            setTimeout(() => {
                // The charts are in the same container, so they scroll together automatically
                // But we need to ensure both canvases have the same width
            }, 100);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

@app.get("/api/chart-data/{stock_code}/daily")
@app.get("/stock/data/api/chart-data/{stock_code}/daily")
async def get_daily_chart_data(stock_code: str):
    """Get daily chart data for a stock."""
    try:
        # Find all daily chart files for this stock
        all_data = []
        
        if not os.path.exists(CHART_DIR):
            return JSONResponse(content={"status": "error", "message": "Chart directory not found"})
        
        for filename in os.listdir(CHART_DIR):
            if filename.endswith('_min.json'):
                continue
            
            if filename.endswith('.json'):
                parts = filename[:-5].split('_')
                if len(parts) == 2:
                    date_str, file_stock_code = parts
                    if file_stock_code == stock_code and len(date_str) == 8:
                        file_path = os.path.join(CHART_DIR, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_data = json.load(f)
                                if isinstance(file_data, list):
                                    all_data.extend(file_data)
                        except Exception as e:
                            print(f"Error reading {filename}: {e}")
        
        # Sort by date
        all_data.sort(key=lambda x: x.get('dt', ''), reverse=True)
        
        return JSONResponse(content={"status": "success", "data": all_data})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.get("/api/chart-data/{stock_code}/minute")
@app.get("/stock/data/api/chart-data/{stock_code}/minute")
async def get_minute_chart_data(stock_code: str):
    """Get minute chart data for a stock."""
    try:
        # Find all minute chart files for this stock
        all_data = []
        
        if not os.path.exists(CHART_DIR):
            return JSONResponse(content={"status": "error", "message": "Chart directory not found"})
        
        for filename in os.listdir(CHART_DIR):
            if not filename.endswith('_min.json'):
                continue
            
            # Parse: YYYYMMDD_stockcode_min.json
            if filename.endswith('_min.json'):
                base_name = filename[:-9]  # Remove '_min.json'
                parts = base_name.split('_')
                if len(parts) == 2:
                    date_str, file_stock_code = parts
                    if file_stock_code == stock_code and len(date_str) == 8:
                        file_path = os.path.join(CHART_DIR, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_data = json.load(f)
                                if isinstance(file_data, list):
                                    all_data.extend(file_data)
                        except Exception as e:
                            print(f"Error reading {filename}: {e}")
        
        # Sort by time
        all_data.sort(key=lambda x: x.get('cntr_tm', ''), reverse=True)
        
        return JSONResponse(content={"status": "success", "data": all_data})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8007, access_log=False)
