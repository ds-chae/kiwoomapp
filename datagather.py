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
    for stock_code, stock_info in stocks.items():
        stock_name = stock_info.get('stock_name', stock_code)
        
        # Get update date from stock_info, default to today if not present
        update_date = stock_info.get('yyyymmdd', '')
        if not update_date or len(update_date) != 8:
            update_date = datetime.now().strftime("%Y%m%d")
            print(f"Warning: {stock_code} has no valid yyyymmdd field, using today's date: {update_date}")
        
        print(f"Processing {stock_code} ({stock_name}) for date {update_date}...")
        
        # Check if chart file already exists for this date
        if chart_file_exists(stock_code, update_date):
            print(f"[{stock_code}] Chart file for {update_date} already exists. Skipping.")
            continue
        
        try:
            # Fetch data using ka10081 with the update date
            result = get_day_chart(token, stock_code, date=update_date)
            
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8007)
