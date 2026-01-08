import json
import time
import os
import traceback
import threading
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import uvicorn
import csv

from ka10081 import get_day_chart
from ka10080 import get_bun_chart
from au1001 import get_one_token
from ka10100 import get_stockname

# Configuration
# Determine the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Define chart data directory: chart_data/day
CHART_DIR = os.path.join(BASE_DIR, 'chart_data', 'day')
INTERESTED_STOCKS_FILE = os.path.join(BASE_DIR, 'interested_stocks.json')
LAST_RUN_FILE = os.path.join(BASE_DIR, 'last_gathering_time.json')

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


def save_interested_stocks_to_json(interested_stocks):
	"""Save interested_stocks to JSON file"""
	try:
		with open(INTERESTED_STOCKS_FILE, 'w', encoding='utf-8') as f:
			json.dump(interested_stocks, f, indent=2, ensure_ascii=False)
		print(f"Saved interested_stocks to {INTERESTED_STOCKS_FILE}")
		return True
	except Exception as e:
		print(f"Error saving interested_stocks: {e}")
		return False

def load_last_run_time():
    """Load last gathering time from disk."""
    if not os.path.exists(LAST_RUN_FILE):
        return None
    
    try:
        with open(LAST_RUN_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('last_run')
    except Exception as e:
        print(f"Error loading {LAST_RUN_FILE}: {e}")
        return None

def save_last_run_time():
    """Save last gathering time to disk."""
    try:
        with open(LAST_RUN_FILE, 'w', encoding='utf-8') as f:
            json.dump({'last_run': status_info.get('last_run')}, f, indent=2)
    except Exception as e:
        print(f"Error saving {LAST_RUN_FILE}: {e}")

def should_skip_initial_gathering():
    """Check if initial gathering should be skipped based on last run date."""
    last_run = load_last_run_time()
    if not last_run:
        return False
    
    try:
        # Parse last run time
        last_run_dt = datetime.fromisoformat(last_run)
        last_run_date = last_run_dt.date()
        
        # Get current date
        current_date = datetime.now().date()
        
        # Skip if same date
        return last_run_date == current_date
    except Exception as e:
        print(f"Error checking last run time: {e}")
        return False


def save_chart_data(stock_code, date_str, data_list):
    """
    Save chart data to file with date-based filename.
    Filename format: YYYYMMDD_stockcode.json
    Merges with existing data if file exists.
    Overwrites existing records with same datetime (dt) by new data.
    """
    file_path = os.path.join(CHART_DIR, f"{date_str}_{stock_code}.json")
    
    existing_data = []
    
    # Load existing data if file exists
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"Error reading existing daily chart data for {stock_code}: {e}")
    
    # Create a dictionary keyed by datetime (dt) for efficient lookup and overwrite
    data_dict = {}
    
    # Add existing data to dictionary
    for record in existing_data:
        dt = record.get('dt', '')
        if dt:
            data_dict[dt] = record
    
    # Overwrite with new data (new data takes precedence)
    updated_count = 0
    added_count = 0
    for record in data_list:
        dt = record.get('dt', '')
        if dt:
            if dt in data_dict:
                # Overwrite existing record with same datetime
                data_dict[dt] = record
                updated_count += 1
            else:
                # Add new record
                data_dict[dt] = record
                added_count += 1
    
    # Convert back to list and sort by datetime
    merged_data = list(data_dict.values())
    merged_data.sort(key=lambda x: x.get('dt', ''))
    
    # Save merged data
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, indent=4, ensure_ascii=False)
        
        if updated_count > 0 or added_count > 0:
            print(f"[{stock_code}] Daily chart for {date_str}: Updated {updated_count} records, Added {added_count} new records. Total: {len(merged_data)}")
        else:
            print(f"[{stock_code}] Daily chart for {date_str}: No changes. Total: {len(merged_data)}")
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
    Overwrites existing records with same datetime (cntr_tm) by new data.
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
    
    # Create a dictionary keyed by datetime (cntr_tm) for efficient lookup and overwrite
    data_dict = {}
    
    # Add existing data to dictionary
    for record in existing_data:
        cntr_tm = record.get('cntr_tm', '')
        if cntr_tm:
            data_dict[cntr_tm] = record
    
    # Overwrite with new data (new data takes precedence)
    updated_count = 0
    added_count = 0
    for record in new_data_list:
        cntr_tm = record.get('cntr_tm', '')
        if cntr_tm:
            if cntr_tm in data_dict:
                # Overwrite existing record with same datetime
                data_dict[cntr_tm] = record
                updated_count += 1
            else:
                # Add new record
                data_dict[cntr_tm] = record
                added_count += 1
    
    # Convert back to list and sort by datetime
    merged_data = list(data_dict.values())
    merged_data.sort(key=lambda x: x.get('cntr_tm', ''))
    
    # Save merged data
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, indent=4, ensure_ascii=False)
        
        if updated_count > 0 or added_count > 0:
            print(f"[{stock_code}] Minute chart for {date_str}: Updated {updated_count} records, Added {added_count} new records. Total: {len(merged_data)}")
        else:
            print(f"[{stock_code}] Minute chart for {date_str}: No changes. Total: {len(merged_data)}")
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
    
    # Save last run time to disk
    save_last_run_time()
    
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
    json_modified = False

    for stock_code, stock_info in stocks.items():
        stock_name = stock_info.get('stock_name', stock_code)
        
        # Get update date from stock_info, default to today if not present
        update_date = stock_info.get('yyyymmdd', '')
        if not update_date or len(update_date) != 8:
            update_date = datetime.now().strftime("%Y%m%d")
            print(f"Warning: {stock_code} has no valid yyyymmdd field, using today's date: {update_date}")
            stock_info['yyyymmdd'] = update_date
            json_modified = True

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
    if json_modified:
        save_interested_stocks_to_json(stocks)

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
    
    # Load last run time from disk
    last_run = load_last_run_time()
    if last_run:
        with status_lock:
            status_info['last_run'] = last_run
        print(f"Loaded last run time from disk: {last_run}")
    
    # Check if we should skip initial gathering
    if should_skip_initial_gathering():
        print("Last gathering was today. Skipping initial gathering.")
        with status_lock:
            status_info['status'] = 'idle'
    else:
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
                position: relative;
            }}
            .btn-stock {{
                position: absolute;
                top: 30px;
                right: 30px;
                background: rgba(255, 255, 255, 0.2);
                color: white;
                border: 2px solid rgba(255, 255, 255, 0.3);
                padding: 10px 20px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 600;
                text-decoration: none;
                display: inline-block;
                transition: all 0.3s;
            }}
            .btn-stock:hover {{
                background: rgba(255, 255, 255, 0.3);
                border-color: rgba(255, 255, 255, 0.5);
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
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
            
            function makeCSV() {{
                if (!confirm('Generate bounce analysis CSV file? This may take a while...')) {{
                    return;
                }}
                
                const btn = event.target;
                const originalText = btn.textContent;
                btn.textContent = 'Generating...';
                btn.disabled = true;
                
                fetch('./api/make-bounce-csv', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }}
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.status === 'success') {{
                        alert('CSV file created successfully!\\nFile: ' + data.filename + '\\nRecords: ' + data.record_count);
                    }} else {{
                        alert('Error: ' + (data.message || 'Unknown error'));
                    }}
                }})
                .catch(error => {{
                    console.error('Error making CSV:', error);
                    alert('Error making CSV: ' + error.message);
                }})
                .finally(() => {{
                    btn.textContent = originalText;
                    btn.disabled = false;
                }});
            }}
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <a href="/stock" class="btn-stock">Stock</a>
                <h1>📊 Data Gather Service</h1>
                <p>Stock Chart Data Collection System</p>
                <a href="./charts" class="btn-charts">📈 View Charts</a>
                <a href="./analysis" class="btn-charts" style="margin-left: 10px;">🌳 Bounce Analysis</a>
                <button onclick="makeCSV()" class="btn-charts" style="margin-left: 10px; border: none; cursor: pointer;">📄 Make CSV</button>
                <a href="./lookcsv" class="btn-charts" style="margin-left: 10px;">📋 Look CSV</a>
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
    """Get list of stocks with dates from chart_data directory with their names."""
    stocks = []
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
                        # Get stock name from interested_stocks, or call get_stockname if not found
                        stock_name = stock_code
                        if stock_code in interested_stocks:
                            stock_name = interested_stocks[stock_code].get('stock_name', stock_code)
                        # If stock name is still just the stock code, try to get it from API
                        if stock_name == stock_code:
                            try:
                                stock_name = get_stockname(stock_code)
                                if not stock_name or stock_name == '':
                                    stock_name = stock_code
                            except Exception as e:
                                print(f"Error getting stock name for {stock_code}: {e}")
                                stock_name = stock_code
                        stocks.append({
                            'date': date_str,
                            'stock_code': stock_code,
                            'stock_name': stock_name
                        })
    except Exception as e:
        print(f"Error scanning chart directory: {e}")
    
    # Sort by date (descending, newest first) then by stock code
    stocks.sort(key=lambda x: (x['date'], x['stock_code']), reverse=True)
    
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
            .stock-item-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 4px;
                gap: 8px;
            }
            .stock-date {
                font-size: 12px;
                color: #888;
                width: 80px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .stock-code {
                font-weight: bold;
                font-size: 14px;
                color: #333;
                width: 80px;
                overflow: hidden;
                white-space: nowrap;
            }
            .stock-name {
                font-size: 12px;
                color: #666;
                margin-top: 4px;
                width: 200px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .stock-item-lower {
                display: flex;
                gap: 8px;
                align-items: center;
                cursor: pointer;
            }
            .delete-btn {
                background: #e74c3c;
                color: white;
                border: none;
                padding: 2px 6px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 10px;
                font-weight: 600;
                transition: background-color 0.2s;
                height: 20px;
                line-height: 16px;
                width: 60px;
                flex-shrink: 0;
            }
            .delete-btn:hover {
                background: #c0392b;
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
                overflow-x: scroll; /* Always show scrollbar */
                overflow-y: hidden;
                scroll-behavior: smooth;
            }
            .chart-container::-webkit-scrollbar {
                height: 12px;
                display: block; /* Force scrollbar to always be visible */
            }
            .chart-container::-webkit-scrollbar-track {
                background: #f1f1f1;
                border-radius: 6px;
            }
            .chart-container::-webkit-scrollbar-thumb {
                background: #888;
                border-radius: 6px;
            }
            .chart-container::-webkit-scrollbar-thumb:hover {
                background: #555;
            }
            /* Force scrollbar visibility for Firefox */
            .chart-container {
                scrollbar-width: thin;
                scrollbar-color: #888 #f1f1f1;
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
                overflow-x: visible;
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
                width: auto;
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
                width: auto;
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
    
    # Add stock items (already sorted by date and stock_code)
    for stock in stocks:
        stock_code = stock['stock_code']
        stock_name = stock['stock_name']
        date_str = stock['date']
        # Format date: YYYYMMDD -> YYYY-MM-DD
        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        html_content += f"""
                    <div class="stock-item" data-stock-code="{stock_code}" data-date="{date_str}">
                        <div class="stock-item-header">
                            <div class="stock-date" onclick="loadStockCharts('{stock_code}', '{date_str}')">{formatted_date}</div>
                            <button class="delete-btn" onclick="event.stopPropagation(); deleteChartData('{stock_code}', '{date_str}')" title="Delete chart data">Delete</button>
                        </div>
                        <div class="stock-item-lower" onclick="loadStockCharts('{stock_code}', '{date_str}')">
                            <div class="stock-code">{stock_code}</div>
                            <div class="stock-name">{stock_name}</div>
                        </div>
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
            
            function selectStock(stockCode, dateStr) {
                document.querySelectorAll('.stock-item').forEach(item => {
                    item.classList.remove('selected');
                });
                const item = document.querySelector(`[data-stock-code="${stockCode}"][data-date="${dateStr}"]`);
                if (item) {
                    item.classList.add('selected');
                }
            }
            
            function loadStockCharts(stockCode, dateStr) {
                selectStock(stockCode, dateStr);
                
                // Load daily chart - send both stock code and date
                fetch(`./api/chart-data/${stockCode}/daily?date=${dateStr}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success' && data.data && data.data.length > 0) {
                            dailyChartData = data.data;
                            drawDailyChart(dailyChartData);
                            // drawDailyChart already calls drawVolumeChart internally
                        } else {
                            dailyChartData = null;
                            showNoDataMessage('daily-chart');
                            clearChart('daily-volume-chart');
                        }
                    })
                    .catch(error => {
                        console.error('Error loading daily chart:', error);
                        dailyChartData = null;
                        showNoDataMessage('daily-chart');
                        clearChart('daily-volume-chart');
                    });
                
                // Load minute chart - send both stock code and date
                fetch(`./api/chart-data/${stockCode}/minute?date=${dateStr}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success' && data.data && data.data.length > 0) {
                            minuteChartData = data.data;
                            drawMinuteChart(minuteChartData);
                            // drawMinuteChart already calls drawVolumeChart internally
                        } else {
                            minuteChartData = null;
                            showNoDataMessage('minute-chart');
                            clearChart('minute-volume-chart');
                        }
                    })
                    .catch(error => {
                        console.error('Error loading minute chart:', error);
                        minuteChartData = null;
                        showNoDataMessage('minute-chart');
                        clearChart('minute-volume-chart');
                    });
            }
            
            function showNoDataMessage(canvasId) {
                const canvas = document.getElementById(canvasId);
                if (!canvas) return;
                
                const ctx = canvas.getContext('2d');
                const wrapper = canvas.parentElement;
                
                // Set canvas size
                canvas.width = wrapper.clientWidth;
                canvas.height = wrapper.clientHeight;
                
                // Clear canvas
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                // Draw "No matching data" message
                ctx.fillStyle = '#999';
                ctx.font = '16px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('No matching data', canvas.width / 2, canvas.height / 2);
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
                
                // For daily chart: Calculate statistics for last 16 days
                let maxTrdePrica = 0;
                let maxTrdePricaDate = '';
                let highestHighDate = '';
                let highestHighTrdePrica = 0;
                let highestHigh = 0;
                
                if (canvasId === 'daily-chart' && finalData.length > 0) {
                    // Get last 16 days (rightmost 16 items, since data is sorted oldest to newest)
                    const last16Days = finalData.slice(-16);
                    
                    // Find maximum trde_prica in last 16 days
                    let maxTrdePricaValue = 0;
                    let maxTrdePricaItem = null;
                    
                    // Find date with highest high_pric in last 16 days
                    let highestHighValue = 0;
                    let highestHighItem = null;
                    
                    last16Days.forEach(item => {
                        // Parse trde_prica
                        const trdePricaStr = item.trde_prica || '0';
                        const trdePrica = parseFloat(trdePricaStr.toString().replace(/,/g, '')) || 0;
                        
                        // Parse high_pric
                        const highVal = parsePrice(item.high_pric);
                        const high = isNaN(highVal) ? 0 : Math.abs(highVal);
                        
                        // Track maximum trde_prica
                        if (trdePrica > maxTrdePricaValue) {
                            maxTrdePricaValue = trdePrica;
                            maxTrdePricaItem = item;
                        }
                        
                        // Track highest high_pric
                        if (high > highestHighValue) {
                            highestHighValue = high;
                            highestHighItem = item;
                        }
                    });
                    
                    if (maxTrdePricaItem) {
                        maxTrdePrica = maxTrdePricaValue;
                        maxTrdePricaDate = getLabel(maxTrdePricaItem);
                    }
                    
                    if (highestHighItem) {
                        highestHigh = highestHighValue;
                        highestHighDate = getLabel(highestHighItem);
                        const trdePricaStr = highestHighItem.trde_prica || '0';
                        highestHighTrdePrica = parseFloat(trdePricaStr.toString().replace(/,/g, '')) || 0;
                    }
                }
                
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
                
                // Chart dimensions: candle width 3px, gap 1px, total spacing 4px
                const poleWidth = 3;
                const poleGap = 1;
                const poleSpacing = 4; // Total spacing: 3px candle + 1px gap
                const leftMargin = 60;
                const rightMargin = 20;
                const topMargin = 20;
                const bottomMargin = 40;
                
                // Calculate required width for all poles
                const numPoles = priceData.length;
                const requiredChartWidth = numPoles * poleSpacing;
                
                // Always use the actual required width - don't stretch to fit container
                // If it's larger than container, scrolling will be enabled
                // If it's smaller, just draw with original width (no stretching)
                const actualChartWidth = requiredChartWidth;
                
                // Set canvas size - use offsetHeight to get the actual rendered height
                canvas.height = wrapper.offsetHeight || wrapper.clientHeight;
                // Set canvas width to actual required width (no stretching, may enable scroll if larger)
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
                
                // Draw division line, top line, bottom line, and calculated line for minute charts (384-period window)
                if (canvasId === 'minute-chart' && priceData.length > 0) {
                    const period = 384;
                    const extensionPeriod = 260; // Extend for 260 candles until new high appears
                    const divisionPoints = [];
                    const topPoints = [];
                    const bottomPoints = [];
                    const calculatedPoints = [];
                    
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
                        
                        // Yellow line: high - (high - low) * 4 / 10
                        const calculatedValue = maxPrice - (maxPrice - minPrice) * 4 / 10;
                        calculatedPoints.push({
                            x: x,
                            y: priceToY(calculatedValue),
                            value: calculatedValue
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
                    
                    // Draw the yellow line (high - (high - low) * 4 / 10)
                    if (calculatedPoints.length > 0) {
                        ctx.strokeStyle = '#ffff00'; // Yellow color
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        
                        calculatedPoints.forEach((point, index) => {
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
                
                // For daily chart: Display statistics for last 16 days
                if (canvasId === 'daily-chart' && maxTrdePrica > 0) {
                    ctx.fillStyle = '#000';
                    ctx.font = '12px Arial';
                    ctx.textAlign = 'left';
                    ctx.textBaseline = 'top';
                    
                    // Format date: YYYYMMDD -> YYYY-MM-DD
                    const formatDate = (dateStr) => {
                        if (dateStr && dateStr.length === 8) {
                            return `${dateStr.substring(0,4)}-${dateStr.substring(4,6)}-${dateStr.substring(6,8)}`;
                        }
                        return dateStr;
                    };
                    
                    // Display maximum trading amount in last 16 days
                    const textY1 = topMargin + 5;
                    ctx.fillText(`Max Trde Amount (16d): ${maxTrdePrica.toLocaleString()} (${formatDate(maxTrdePricaDate)})`, leftMargin + 5, textY1);
                    
                    // Display date with highest high_pric and its trde_prica
                    if (highestHighDate && highestHighTrdePrica > 0) {
                        const textY2 = topMargin + 20;
                        ctx.fillText(`Highest High (16d): ${formatDate(highestHighDate)}, Trde Amount: ${highestHighTrdePrica.toLocaleString()}`, leftMargin + 5, textY2);
                    }
                }
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
                // Candle width 3px, gap 1px, total spacing 4px
                const poleWidth = 3;
                const poleGap = 1;
                const poleSpacing = 4; // Total spacing: 3px candle + 1px gap
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
            
            function deleteChartData(stockCode, dateStr) {
                const formattedDate = dateStr ? `${dateStr.substring(0,4)}-${dateStr.substring(4,6)}-${dateStr.substring(6,8)}` : '';
                if (!confirm(`Delete chart data for ${stockCode} (${formattedDate})? This action cannot be undone.`)) {
                    return;
                }
                
                fetch(`./api/chart-data/${stockCode}/${dateStr}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                })
                .then(response => response.json())
                .then(result => {
                    if (result.status === 'success') {
                        // Remove the stock item from the list
                        const stockItem = document.querySelector(`[data-stock-code="${stockCode}"][data-date="${dateStr}"]`);
                        if (stockItem) {
                            stockItem.remove();
                        }
                        // Clear charts if this stock was selected
                        clearChart('daily-chart');
                        clearChart('daily-volume-chart');
                        clearChart('minute-chart');
                        clearChart('minute-volume-chart');
                        dailyChartData = null;
                        minuteChartData = null;
                        // Remove selected state
                        document.querySelectorAll('.stock-item').forEach(item => {
                            item.classList.remove('selected');
                        });
                    } else {
                        alert('Error deleting chart data: ' + (result.message || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error deleting chart data:', error);
                    alert('Error deleting chart data: ' + error);
                });
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

@app.get("/analysis", response_class=HTMLResponse)
@app.get("/stock/data/analysis", response_class=HTMLResponse)
@app.get("/stock/data/analysis/", response_class=HTMLResponse)
async def analysis_page():
    """Display decision tree analysis page."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Decision Tree Analysis</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                min-height: 100vh;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            .header h1 {
                margin-bottom: 10px;
            }
            .header a {
                color: white;
                text-decoration: none;
                margin: 0 10px;
                padding: 8px 16px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                display: inline-block;
                margin-top: 15px;
            }
            .header a:hover {
                background: rgba(255, 255, 255, 0.3);
            }
            .content {
                padding: 30px;
            }
            .info-panel {
                background: #f5f5f5;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 20px;
            }
            .info-panel h2 {
                margin-bottom: 15px;
                color: #333;
            }
            .info-panel p {
                color: #666;
                line-height: 1.6;
                margin-bottom: 10px;
            }
            .tree-container {
                background: white;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 30px;
                min-height: 600px;
                overflow: auto;
                position: relative;
            }
            .tree-node {
                position: relative;
                display: inline-block;
                margin: 20px;
                vertical-align: top;
            }
            .node-box {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px 20px;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                min-width: 200px;
                text-align: center;
                position: relative;
                z-index: 2;
            }
            .node-box.condition {
                background: linear-gradient(135deg, #4caf50 0%, #45a049 100%);
            }
            .node-box.result {
                background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
            }
            .node-box.success {
                background: linear-gradient(135deg, #2196f3 0%, #1976d2 100%);
            }
            .node-box.failure {
                background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
            }
            .node-title {
                font-weight: 600;
                font-size: 14px;
                margin-bottom: 8px;
            }
            .node-value {
                font-size: 16px;
                font-weight: bold;
            }
            .node-label {
                font-size: 12px;
                margin-top: 5px;
                opacity: 0.9;
            }
            .tree-branch {
                position: absolute;
                border: 2px solid #999;
                z-index: 1;
            }
            .tree-branch.horizontal {
                height: 2px;
                background: #999;
            }
            .tree-branch.vertical {
                width: 2px;
                background: #999;
            }
            .tree-level {
                display: flex;
                justify-content: center;
                align-items: flex-start;
                margin: 30px 0;
                position: relative;
            }
            .empty-state {
                text-align: center;
                color: #999;
                padding: 100px 20px;
                font-size: 18px;
            }
            .loading {
                text-align: center;
                color: #667eea;
                padding: 100px 20px;
                font-size: 18px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌳 Decision Tree Analysis</h1>
                <p>Stock Trading Decision Tree Based on Trade Amount, High-Low Difference, and Moving Average</p>
                <a href="./">← Back to Home</a>
                <a href="./charts">📈 View Charts</a>
            </div>
            <div class="content">
                <div class="info-panel">
                    <h2>Bounce Analysis After Peak</h2>
                    <p><strong>Analysis Method:</strong></p>
                    <ul style="margin-left: 20px; color: #666;">
                        <li>Analyze stock price bounce after peak in last 16 days of daily chart</li>
                        <li>Find the date with highest high price in 16 days</li>
                        <li>Calculate bounce range using minute chart data for peak date and next 4 days</li>
                        <li><strong>Success:</strong> Bounce ≥ 2/5 of (highest - lowest) in 16 days</li>
                        <li><strong>Failure:</strong> Bounce < 2/5 of (highest - lowest) in 16 days within 4 days</li>
                    </ul>
                    <div style="margin-top: 15px;">
                        <label for="stock-select" style="font-weight: 600; margin-right: 10px;">Select Stock:</label>
                        <select id="stock-select" style="padding: 8px 12px; border-radius: 4px; border: 1px solid #ddd; font-size: 14px; min-width: 300px;">
                            <option value="">Loading stocks...</option>
                        </select>
                    </div>
                </div>
                <div class="info-panel" id="analysis-details" style="display: none;">
                    <h3>Analysis Details</h3>
                </div>
                <div class="tree-container" id="tree-container">
                    <div class="empty-state">
                        Select a stock from the dropdown above to analyze bounce after peak.<br>
                        The decision tree will show the analysis results.
                    </div>
                </div>
            </div>
        </div>
        <script>
            // Placeholder for decision tree data
            // This will be populated from backend API when ready
            let treeData = null;
            
            // Function to render decision tree
            function renderDecisionTree(data) {
                const container = document.getElementById('tree-container');
                if (!data || !data.nodes || data.nodes.length === 0) {
                    container.innerHTML = '<div class="empty-state">No decision tree data available. Data structure will be added when backend is ready.</div>';
                    return;
                }
                
                // Clear container
                container.innerHTML = '';
                
                // Group nodes by level
                const levels = {};
                data.nodes.forEach(node => {
                    if (!levels[node.level]) {
                        levels[node.level] = [];
                    }
                    levels[node.level].push(node);
                });
                
                // Render each level
                const sortedLevels = Object.keys(levels).sort((a, b) => parseInt(a) - parseInt(b));
                sortedLevels.forEach((level, levelIndex) => {
                    const levelDiv = document.createElement('div');
                    levelDiv.className = 'tree-level';
                    levelDiv.id = `level-${level}`;
                    
                    levels[level].forEach((node, nodeIndex) => {
                        const nodeDiv = document.createElement('div');
                        nodeDiv.className = 'tree-node';
                        nodeDiv.id = `node-${node.id}`;
                        
                        const nodeBox = document.createElement('div');
                        nodeBox.className = `node-box ${node.type || 'condition'}`;
                        
                        const titleDiv = document.createElement('div');
                        titleDiv.className = 'node-title';
                        titleDiv.textContent = node.title || node.condition || 'Node';
                        
                        const valueDiv = document.createElement('div');
                        valueDiv.className = 'node-value';
                        valueDiv.textContent = node.value || node.threshold || '';
                        
                        if (node.label) {
                            const labelDiv = document.createElement('div');
                            labelDiv.className = 'node-label';
                            labelDiv.textContent = node.label;
                            nodeBox.appendChild(labelDiv);
                        }
                        
                        nodeBox.appendChild(titleDiv);
                        nodeBox.appendChild(valueDiv);
                        nodeDiv.appendChild(nodeBox);
                        levelDiv.appendChild(nodeDiv);
                    });
                    
                    container.appendChild(levelDiv);
                });
                
                // Draw branches (connections between nodes)
                if (data.edges && data.edges.length > 0) {
                    data.edges.forEach(edge => {
                        drawBranch(edge.from, edge.to, edge.label);
                    });
                }
            }
            
            // Function to draw branch between nodes
            function drawBranch(fromId, toId, label) {
                const fromNode = document.getElementById(`node-${fromId}`);
                const toNode = document.getElementById(`node-${toId}`);
                
                if (!fromNode || !toNode) return;
                
                const fromRect = fromNode.getBoundingClientRect();
                const toRect = toNode.getBoundingClientRect();
                const containerRect = document.getElementById('tree-container').getBoundingClientRect();
                
                const fromX = fromRect.left + fromRect.width / 2 - containerRect.left;
                const fromY = fromRect.top + fromRect.height - containerRect.top;
                const toX = toRect.left + toRect.width / 2 - containerRect.left;
                const toY = toRect.top - containerRect.top;
                
                // Create branch element
                const branch = document.createElement('div');
                branch.className = 'tree-branch';
                branch.style.position = 'absolute';
                branch.style.left = fromX + 'px';
                branch.style.top = fromY + 'px';
                branch.style.width = '2px';
                branch.style.height = (toY - fromY) + 'px';
                branch.style.background = '#999';
                
                document.getElementById('tree-container').appendChild(branch);
                
                // Add label if provided
                if (label) {
                    const labelDiv = document.createElement('div');
                    labelDiv.style.position = 'absolute';
                    labelDiv.style.left = (fromX + 10) + 'px';
                    labelDiv.style.top = (fromY + (toY - fromY) / 2) + 'px';
                    labelDiv.style.color = '#666';
                    labelDiv.style.fontSize = '12px';
                    labelDiv.textContent = label;
                    document.getElementById('tree-container').appendChild(labelDiv);
                }
            }
            
            // Load stock list
            function loadStockList() {
                fetch('./api/stock-list')
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success' && data.stocks) {
                            const select = document.getElementById('stock-select');
                            select.innerHTML = '<option value="">Select a stock...</option>';
                            data.stocks.forEach(stock => {
                                const option = document.createElement('option');
                                option.value = stock.stock_code;
                                option.textContent = `${stock.stock_code} - ${stock.stock_name} (${stock.date})`;
                                option.dataset.date = stock.date;
                                select.appendChild(option);
                            });
                        }
                    })
                    .catch(error => {
                        console.error('Error loading stock list:', error);
                    });
            }
            
            // Load decision tree data from API
            function loadDecisionTree(stockCode) {
                if (!stockCode) {
                    renderDecisionTree(null);
                    return;
                }
                
                const container = document.getElementById('tree-container');
                container.innerHTML = '<div class="loading">Analyzing bounce after peak...</div>';
                
                fetch(`./api/bounce-analysis/${stockCode}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success' && data.data) {
                            treeData = data.data;
                            renderDecisionTree(data.data);
                            
                            // Display analysis details
                            if (data.data.analysis) {
                                displayAnalysisDetails(data.data.analysis);
                            }
                        } else {
                            container.innerHTML = `<div class="empty-state">Error: ${data.message || 'Unknown error'}</div>`;
                        }
                    })
                    .catch(error => {
                        console.error('Error loading decision tree:', error);
                        container.innerHTML = `<div class="empty-state">Error loading analysis: ${error.message}</div>`;
                    });
            }
            
            // Display analysis details
            function displayAnalysisDetails(analysis) {
                const detailsDiv = document.getElementById('analysis-details');
                if (!detailsDiv) return;
                
                detailsDiv.style.display = 'block';
                detailsDiv.innerHTML = `
                    <h3>Analysis Details</h3>
                    <p><strong>Peak Date:</strong> ${analysis.peak_date}</p>
                    <p><strong>Peak High:</strong> ${analysis.peak_high.toFixed(2)}</p>
                    <p><strong>16-Day Range:</strong> ${analysis.range_16d.toFixed(2)}</p>
                    <p><strong>Threshold (2/5 of range):</strong> ${analysis.threshold.toFixed(2)}</p>
                    <p><strong>Bounce:</strong> ${analysis.bounce.toFixed(2)}</p>
                    <p><strong>Lowest After Peak:</strong> ${analysis.lowest_after_peak.toFixed(2)}</p>
                    <p><strong>Result:</strong> <span style="color: ${analysis.result === 'success' ? '#4caf50' : '#f44336'}; font-weight: bold;">${analysis.result.toUpperCase()}</span></p>
                `;
            }
            
            // Initialize on page load
            window.addEventListener('DOMContentLoaded', () => {
                loadStockList();
                
                // Handle stock selection
                const stockSelect = document.getElementById('stock-select');
                if (stockSelect) {
                    stockSelect.addEventListener('change', (e) => {
                        const stockCode = e.target.value;
                        loadDecisionTree(stockCode);
                    });
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/stock-list")
@app.get("/stock/data/api/stock-list")
async def get_stock_list_api():
    """Get list of stocks with dates for analysis."""
    try:
        stocks = get_stock_list()
        return JSONResponse(content={"status": "success", "stocks": stocks})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.get("/api/chart-data/{stock_code}/daily")
@app.get("/stock/data/api/chart-data/{stock_code}/daily")
async def get_daily_chart_data(stock_code: str, date: str = Query(...)):
    """Get daily chart data for a stock matching both stock code and date."""
    print('get_daily_chart_data {} {}'.format(stock_code, date))
    try:
        # Find daily chart files matching both stock code and date
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
                    # Match both stock code and date
                    if file_stock_code == stock_code and date_str == date and len(date_str) == 8:
                        file_path = os.path.join(CHART_DIR, filename)
                        print('get_daily_chart_data file_path={}'.format(file_path))
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_data = json.load(f)
                                if isinstance(file_data, list):
                                    all_data.extend(file_data)
                        except Exception as e:
                            print(f"Error reading {filename}: {e}")
        
        # Sort by date
        all_data.sort(key=lambda x: x.get('dt', ''), reverse=True)
        
        if len(all_data) == 0:
            print({"status": "error", "message": "No matching data"})
            return JSONResponse(content={"status": "error", "message": "No matching data"})
        
        return JSONResponse(content={"status": "success", "data": all_data})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.get("/api/chart-data/{stock_code}/minute")
@app.get("/stock/data/api/chart-data/{stock_code}/minute")
async def get_minute_chart_data(stock_code: str, date: str = Query(...)):
    print('get_minute_chart_data {} {}'.format(stock_code, date))
    """Get minute chart data for a stock matching both stock code and date."""
    try:
        # Find minute chart files matching both stock code and date
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
                    # Match both stock code and date
                    if file_stock_code == stock_code and date_str == date and len(date_str) == 8:
                        file_path = os.path.join(CHART_DIR, filename)
                        print('get_minute_chart_data {} {} file_path={}'.format(stock_code, date, file_path))
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_data = json.load(f)
                                if isinstance(file_data, list):
                                    all_data.extend(file_data)
                        except Exception as e:
                            print(f"Error reading {filename}: {e}")
        
        # Sort by time
        all_data.sort(key=lambda x: x.get('cntr_tm', ''), reverse=True)
        
        if len(all_data) == 0:
            print({"status": "error", "message": "No matching data"})
            return JSONResponse(content={"status": "error", "message": "No matching data"})

        return JSONResponse(content={"status": "success", "data": all_data})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.get("/lookcsv", response_class=HTMLResponse)
@app.get("/stock/data/lookcsv", response_class=HTMLResponse)
@app.get("/stock/data/lookcsv/", response_class=HTMLResponse)
async def lookcsv_page():
    """Display CSV viewer page."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CSV Viewer - Data Gather Service</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #f5f5f5;
                padding: 0;
                margin: 0;
                height: 100vh;
                overflow: hidden;
            }
            .container {
                width: 100%;
                height: 100vh;
                display: flex;
                flex-direction: column;
            }
            .header {
                padding: 10px 20px;
                background: white;
                border-bottom: 1px solid #ddd;
                flex-shrink: 0;
            }
            .header h1 {
                font-size: 1.5em;
                margin: 0;
                color: #333;
            }
            .two-pane {
                display: flex;
                gap: 10px;
                flex: 1;
                min-height: 0;
                overflow: hidden;
                padding: 10px;
            }
            .left-pane {
                width: 300px;
                background: white;
                padding: 10px;
                overflow-y: auto;
                overflow-x: hidden;
            }
            .right-pane {
                flex: 1;
                background: white;
                padding: 10px;
                overflow-y: auto;
                overflow-x: hidden;
                display: flex;
                flex-direction: column;
            }
            .csv-list {
                margin-bottom: 10px;
            }
            .csv-item {
                padding: 10px;
                margin-bottom: 5px;
                background: #f5f5f5;
                border-radius: 4px;
                cursor: pointer;
                transition: background 0.2s;
            }
            .csv-item:hover {
                background: #e0e0e0;
            }
            .csv-item.selected {
                background: #667eea;
                color: white;
            }
            .stock-list {
                display: none;
            }
            .stock-list.active {
                display: block;
            }
            .stock-item {
                padding: 10px;
                margin-bottom: 5px;
                background: #f5f5f5;
                border-radius: 4px;
                cursor: pointer;
                transition: background 0.2s;
            }
            .stock-item:hover {
                background: #e0e0e0;
            }
            .stock-item.selected {
                background: #667eea;
                color: white;
            }
            .chart-container {
                flex: 1;
                display: flex;
                flex-direction: column;
                min-height: 0;
                margin-bottom: 10px;
            }
            .chart-container:last-child {
                margin-bottom: 0;
            }
            .chart-title {
                display: none;
            }
            .chart-wrapper {
                overflow-x: scroll;
                overflow-y: hidden;
                border: 1px solid #ddd;
                display: flex;
                flex-direction: column;
                flex: 1;
                min-height: 0;
            }
            .candlestick-chart {
                flex: 4;
                height: 0;
                min-height: 0;
            }
            .candlestick-chart canvas {
                display: block;
                width: auto;
                height: 100%;
            }
            .volume-chart {
                flex: 1;
                height: 0;
                min-height: 0;
            }
            .volume-chart canvas {
                display: block;
                width: auto;
                height: 100%;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📋 CSV Viewer</h1>
            </div>
            <div class="two-pane">
                <div class="left-pane">
                    <div class="csv-list">
                        <h3>CSV Files</h3>
                        <div id="csv-list-container"></div>
                    </div>
                    <div class="stock-list" id="stock-list-container">
                        <div id="stock-items-container"></div>
                    </div>
                </div>
                <div class="right-pane">
                    <div class="chart-container">
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
        </div>
        <script>
            let csvData = null;
            let selectedCsvFile = null;
            let dailyChartData = null;
            let minuteChartData = null;
            let highestDate = '';
            let successFailure = '';
            
            // Load CSV file list
            function loadCsvList() {
                fetch('./api/csv-list')
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            const container = document.getElementById('csv-list-container');
                            container.innerHTML = '';
                            data.files.forEach(filename => {
                                const item = document.createElement('div');
                                item.className = 'csv-item';
                                item.textContent = filename;
                                item.onclick = () => selectCsvFile(filename);
                                container.appendChild(item);
                            });
                        }
                    })
                    .catch(error => {
                        console.error('Error loading CSV list:', error);
                    });
            }
            
            function selectCsvFile(filename) {
                selectedCsvFile = filename;
                document.querySelectorAll('.csv-item').forEach(item => {
                    item.classList.remove('selected');
                });
                event.target.classList.add('selected');
                
                // Load CSV data
                fetch(`./api/csv-data/${filename}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            csvData = data.data;
                            displayStockList();
                        }
                    })
                    .catch(error => {
                        console.error('Error loading CSV data:', error);
                    });
            }
            
            function displayStockList() {
                const container = document.getElementById('stock-items-container');
                container.innerHTML = '';
                document.getElementById('stock-list-container').classList.add('active');
                
                // Sort entries by highest date (descending)
                const sortedData = [...csvData].sort((a, b) => {
                    const dateA = parseInt(a['Highest Date'] || '0') || 0;
                    const dateB = parseInt(b['Highest Date'] || '0') || 0;
                    return dateB - dateA;
                });
                
                // Display all entries without numbered suffixes, ordered by highest date
                sortedData.forEach((row, index) => {
                    const code = row['Stock Code'];
                    const name = row['Stock Name'];
                    const highestDate = row['Highest Date'] || '';
                    const displayText = `${code} - ${name} - ${highestDate}`;
                    
                    const item = document.createElement('div');
                    item.className = 'stock-item';
                    item.textContent = displayText;
                    item.onclick = function() {
                        selectStock(code, name, [row], this);
                    };
                    container.appendChild(item);
                });
            }
            
            function selectStock(stockCode, stockName, rows, element) {
                document.querySelectorAll('.stock-item').forEach(item => {
                    item.classList.remove('selected');
                });
                if (element) {
                    element.classList.add('selected');
                }
                
                // Use the first row for chart data (or you could let user select which row)
                const row = rows[0];
                highestDate = row['Highest Date'];
                successFailure = row['Success/Failure'];
                const dailyFile = row['Daily Chart File'];
                const minuteFile = row['Minute Chart File'];
                
                // Load charts using file names
                loadChartsFromFiles(dailyFile, minuteFile);
            }
            
            function loadChartsFromFiles(dailyFile, minuteFile) {
                console.log('Loading charts from files:', dailyFile, minuteFile);
                // Load daily chart
                fetch(`./api/chart-data-from-files?daily_file=${dailyFile}`)
                    .then(response => response.json())
                    .then(data => {
                        console.log('Daily chart response:', data.status, 'data length:', data.data ? data.data.length : 0);
                        if (data.status === 'success' && data.data && data.data.length > 0) {
                            dailyChartData = data.data;
                            // Use setTimeout to ensure DOM is ready
                            setTimeout(() => {
                                drawDailyChart(dailyChartData);
                            }, 100);
                        } else {
                            dailyChartData = null;
                            showNoDataMessage('daily-chart');
                            clearChart('daily-volume-chart');
                        }
                    })
                    .catch(error => {
                        console.error('Error loading daily chart:', error);
                        dailyChartData = null;
                        showNoDataMessage('daily-chart');
                        clearChart('daily-volume-chart');
                    });
                
                // Load minute chart
                fetch(`./api/chart-data-from-files?minute_file=${minuteFile}`)
                    .then(response => response.json())
                    .then(data => {
                        console.log('Minute chart response:', data.status, 'data length:', data.data ? data.data.length : 0);
                        if (data.status === 'success' && data.data && data.data.length > 0) {
                            minuteChartData = data.data;
                            // Use setTimeout to ensure DOM is ready
                            setTimeout(() => {
                                drawMinuteChart(minuteChartData);
                            }, 100);
                        } else {
                            minuteChartData = null;
                            showNoDataMessage('minute-chart');
                            clearChart('minute-volume-chart');
                        }
                    })
                    .catch(error => {
                        console.error('Error loading minute chart:', error);
                        minuteChartData = null;
                        showNoDataMessage('minute-chart');
                        clearChart('minute-volume-chart');
                    });
            }
            
            function showNoDataMessage(canvasId) {
                const canvas = document.getElementById(canvasId);
                if (!canvas) return;
                const ctx = canvas.getContext('2d');
                ctx.imageSmoothingEnabled = false;
                const wrapper = canvas.parentElement;
                canvas.width = wrapper.clientWidth;
                canvas.height = wrapper.clientHeight;
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.fillStyle = '#999';
                ctx.font = '16px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('No matching data', canvas.width / 2, canvas.height / 2);
            }
            
            function clearChart(canvasId) {
                const canvas = document.getElementById(canvasId);
                if (!canvas) return;
                const ctx = canvas.getContext('2d');
                ctx.imageSmoothingEnabled = false;
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
            
            function parsePrice(priceStr) {
                if (!priceStr) return 0;
                const cleaned = priceStr.toString().replace(/^[+-]/, '').replace(/,/g, '');
                return parseFloat(cleaned) || 0;
            }
            
            // Chart drawing functions (adapted from charts page with CSV-specific modifications)
            function drawPoleChartCSV(canvasId, data, getLabel, highestDateValue, successFailureValue) {
                const canvas = document.getElementById(canvasId);
                if (!canvas) return null;
                const ctx = canvas.getContext('2d');
                ctx.imageSmoothingEnabled = false;
                const wrapper = canvas.closest('.chart-wrapper');
                
                if (!wrapper) {
                    console.error('Chart wrapper not found for', canvasId);
                    return null;
                }
                
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                if (!data || data.length === 0) {
                    canvas.width = wrapper.clientWidth;
                    canvas.height = wrapper.clientHeight;
                    return null;
                }
                
                const sortedData = [...data].sort((a, b) => {
                    const keyA = getLabel(a) || '';
                    const keyB = getLabel(b) || '';
                    if (keyA < keyB) return -1;
                    if (keyA > keyB) return 1;
                    return 0;
                });
                
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
                
                const allPriceValues = [];
                const priceData = finalData.map(item => {
                    const openVal = parsePrice(item.open_pric);
                    const closeVal = parsePrice(item.cur_prc);
                    const highVal = parsePrice(item.high_pric);
                    const lowVal = parsePrice(item.low_pric);
                    
                    const open = isNaN(openVal) ? 0 : Math.abs(openVal);
                    const close = isNaN(closeVal) ? 0 : Math.abs(closeVal);
                    const high = isNaN(highVal) ? 0 : Math.abs(highVal);
                    const low = isNaN(lowVal) ? 0 : Math.abs(lowVal);
                    
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
                
                let lowerBound = Math.min(...allPriceValues);
                let upperBound = Math.max(...allPriceValues);
                
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
                
                const priceRange = upperBound - lowerBound;
                const padding = Math.max(priceRange * 0.05, 1);
                lowerBound = lowerBound - padding;
                upperBound = upperBound + padding;
                
                const poleWidth = canvasId === 'daily-chart' ? 5 : 3;
                const poleSpacing = canvasId === 'daily-chart' ? 7 : 4;
                const leftMargin = 60;
                const rightMargin = 20;
                const topMargin = 20;
                const bottomMargin = 40;
                
                const numPoles = priceData.length;
                const requiredChartWidth = numPoles * poleSpacing;
                const actualChartWidth = requiredChartWidth;
                
                // Get wrapper height - use offsetHeight for actual rendered height
                const wrapperHeight = wrapper.offsetHeight || wrapper.clientHeight || 400;
                canvas.height = wrapperHeight;
                canvas.width = leftMargin + actualChartWidth + rightMargin;
                
                const chartHeight = canvas.height - topMargin - bottomMargin;
                
                if (chartHeight <= 0) {
                    console.error('Invalid chart height:', chartHeight, 'wrapper height:', wrapperHeight);
                    return;
                }
                const priceRangeScaled = upperBound - lowerBound;
                const scaleFactor = priceRangeScaled > 0 ? chartHeight / priceRangeScaled : 1;
                
                const priceToY = (price) => {
                    const relativeValue = (price - lowerBound) * scaleFactor;
                    return topMargin + chartHeight - relativeValue;
                };
                
                // Find index of highest date for vertical line
                let highestDateIndex = -1;
                let scrollPosition = null;
                if (highestDateValue && canvasId === 'daily-chart') {
                    highestDateIndex = priceData.findIndex(p => p.label === highestDateValue);
                    if (highestDateIndex >= 0) {
                        // Calculate scroll position for S/F marker
                        const x = leftMargin + (highestDateIndex * poleSpacing);
                        scrollPosition = x - wrapper.clientWidth / 2; // Center the marker
                        if (scrollPosition < 0) scrollPosition = 0;
                    }
                }
                
                // Fill background for highest date in minute chart
                let minuteScrollPosition = null;
                if (canvasId === 'minute-chart' && highestDateValue && successFailureValue) {
                    const bgColor = successFailureValue.toLowerCase() === 'success' ? 'rgba(255, 255, 200, 0.3)' : 'rgba(200, 220, 255, 0.3)';
                    const highestDateStr = highestDateValue.substring(0, 8); // YYYYMMDD
                    
                    let startIndex = -1;
                    let endIndex = -1;
                    
                    priceData.forEach((pole, index) => {
                        const poleDateStr = pole.label.substring(0, 8);
                        if (poleDateStr === highestDateStr) {
                            if (startIndex === -1) startIndex = index;
                            endIndex = index;
                        }
                    });
                    
                    if (startIndex >= 0 && endIndex >= 0) {
                        const startX = leftMargin + (startIndex * poleSpacing);
                        const endX = leftMargin + ((endIndex + 1) * poleSpacing);
                        const bgWidth = endX - startX;
                        
                        ctx.fillStyle = bgColor;
                        ctx.fillRect(startX, topMargin, bgWidth, chartHeight);
                        
                        // Calculate scroll position for background fill (center of the fill area)
                        const centerX = startX + bgWidth / 2;
                        minuteScrollPosition = centerX - wrapper.clientWidth / 2;
                        if (minuteScrollPosition < 0) minuteScrollPosition = 0;
                    }
                }
                
                // Draw axes
                ctx.strokeStyle = '#ccc';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(leftMargin, topMargin);
                ctx.lineTo(leftMargin, topMargin + chartHeight);
                ctx.moveTo(leftMargin, topMargin + chartHeight);
                ctx.lineTo(leftMargin + actualChartWidth, topMargin + chartHeight);
                ctx.stroke();
                
                // Draw price labels
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
                
                // Draw vertical line at highest date (daily chart only)
                if (highestDateIndex >= 0 && canvasId === 'daily-chart') {
                    const x = leftMargin + (highestDateIndex * poleSpacing);
                    ctx.strokeStyle = '#ff0000';
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(x, topMargin);
                    ctx.lineTo(x, topMargin + chartHeight);
                    ctx.stroke();
                    
                    // Draw S/F indicator at left of vertical line
                    ctx.fillStyle = successFailureValue.toLowerCase() === 'success' ? '#00aa00' : '#aa0000';
                    ctx.font = 'bold 16px Arial';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    const indicatorText = successFailureValue.toLowerCase() === 'success' ? 'S' : 'F';
                    ctx.fillText(indicatorText, x - 15, topMargin + 15);
                }
                
                // Draw poles
                priceData.forEach((pole, index) => {
                    const x = leftMargin + (index * poleSpacing) + (poleWidth / 2);
                    const highY = priceToY(pole.high);
                    const lowY = priceToY(pole.low);
                    const openY = priceToY(pole.open);
                    const closeY = priceToY(pole.close);
                    
                    const isRising = pole.close >= pole.open;
                    const color = isRising ? '#ff0000' : '#0000ff';
                    
                    ctx.beginPath();
                    ctx.strokeStyle = color;
                    ctx.lineWidth = 1;
                    ctx.moveTo(x, highY);
                    ctx.lineTo(x, lowY);
                    ctx.stroke();
                    
                    const rectTop = Math.min(openY, closeY);
                    const rectBottom = Math.max(openY, closeY);
                    const rectHeight = Math.max(1, rectBottom - rectTop);
                    
                    ctx.fillStyle = color;
                    ctx.fillRect(x - poleWidth / 2, rectTop, poleWidth, rectHeight);
                });
                
                // Draw yellow line for minute charts (384-period window)
                if (canvasId === 'minute-chart' && priceData.length > 0) {
                    const period = 384;
                    const extensionPeriod = 260; // Extend for 260 candles until new high appears
                    const calculatedPoints = [];
                    
                    let previousMax = null;
                    let previousMin = null;
                    let extensionCount = 0;
                    let maxHighSeen = -Infinity; // Track the maximum high price seen so far
                    
                    // Calculate yellow line values for each point
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
                        
                        // Yellow line: high - (high - low) * 4 / 10
                        const calculatedValue = maxPrice - (maxPrice - minPrice) * 4 / 10;
                        calculatedPoints.push({
                            x: x,
                            y: priceToY(calculatedValue),
                            value: calculatedValue
                        });
                    }
                    
                    // Draw the yellow line
                    if (calculatedPoints.length > 0) {
                        ctx.strokeStyle = '#ffff00'; // Yellow color
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        
                        calculatedPoints.forEach((point, index) => {
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
                
                // Draw X-axis labels
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
                
                // Return scroll position for daily chart (S/F marker) or minute chart (background fill)
                return scrollPosition !== null ? scrollPosition : minuteScrollPosition;
            }
            
            function drawVolumeChartCSV(canvasId, data, getLabel, candlestickWidth) {
                const canvas = document.getElementById(canvasId);
                if (!canvas) return;
                const ctx = canvas.getContext('2d');
                ctx.imageSmoothingEnabled = false;
                const wrapper = canvas.closest('.chart-wrapper');
                
                if (!wrapper) {
                    console.error('Chart wrapper not found for', canvasId);
                    return;
                }
                
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                if (!data || data.length === 0) {
                    canvas.width = candlestickWidth || wrapper.clientWidth;
                    canvas.height = wrapper.clientHeight;
                    return;
                }
                
                const sortedData = [...data].sort((a, b) => {
                    const keyA = getLabel(a) || '';
                    const keyB = getLabel(b) || '';
                    if (keyA < keyB) return -1;
                    if (keyA > keyB) return 1;
                    return 0;
                });
                
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
                
                const maxVolume = Math.max(...volumeData.map(v => v.volume));
                const poleWidth = 3;
                const poleSpacing = 4;
                const leftMargin = 60;
                const rightMargin = 20;
                const topMargin = 5;
                const bottomMargin = 20;
                
                canvas.height = wrapper.offsetHeight || wrapper.clientHeight;
                canvas.width = candlestickWidth || (leftMargin + volumeData.length * poleSpacing + rightMargin);
                
                const chartHeight = canvas.height - topMargin - bottomMargin;
                const volumeScale = maxVolume > 0 ? chartHeight / maxVolume : 1;
                
                volumeData.forEach((vol, index) => {
                    const x = leftMargin + (index * poleSpacing) + (poleWidth / 2);
                    const barHeight = vol.volume * volumeScale;
                    const barY = topMargin + chartHeight - barHeight;
                    
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
            }
            
            function drawDailyChart(data) {
                console.log('Drawing daily chart, data length:', data ? data.length : 0, 'highestDate:', highestDate, 'successFailure:', successFailure);
                const getLabel = (item) => item.dt || '';
                const scrollPos = drawPoleChartCSV('daily-chart', data, getLabel, highestDate, successFailure);
                const candlestickCanvas = document.getElementById('daily-chart');
                if (candlestickCanvas) {
                    drawVolumeChartCSV('daily-volume-chart', data, getLabel, candlestickCanvas.width);
                }
                // Scroll to S/F marker position
                if (scrollPos !== null && scrollPos !== undefined) {
                    const wrapper = candlestickCanvas ? candlestickCanvas.closest('.chart-wrapper') : null;
                    if (wrapper) {
                        setTimeout(() => {
                            const maxScroll = wrapper.scrollWidth - wrapper.clientWidth;
                            wrapper.scrollLeft = Math.min(scrollPos, maxScroll);
                        }, 100);
                    }
                }
            }
            
            function drawMinuteChart(data) {
                console.log('Drawing minute chart, data length:', data ? data.length : 0, 'highestDate:', highestDate, 'successFailure:', successFailure);
                const getLabel = (item) => item.cntr_tm || '';
                const scrollPos = drawPoleChartCSV('minute-chart', data, getLabel, highestDate, successFailure);
                const candlestickCanvas = document.getElementById('minute-chart');
                if (candlestickCanvas) {
                    drawVolumeChartCSV('minute-volume-chart', data, getLabel, candlestickCanvas.width);
                }
                // Scroll to background fill position
                if (scrollPos !== null && scrollPos !== undefined) {
                    const wrapper = candlestickCanvas ? candlestickCanvas.closest('.chart-wrapper') : null;
                    if (wrapper) {
                        setTimeout(() => {
                            const maxScroll = wrapper.scrollWidth - wrapper.clientWidth;
                            wrapper.scrollLeft = Math.min(scrollPos, maxScroll);
                        }, 100);
                    }
                }
            }
            
            // Initialize
            loadCsvList();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/csv-list")
@app.get("/stock/data/api/csv-list")
async def get_csv_list():
    """Get list of CSV files in BASE_DIR."""
    try:
        csv_files = []
        for filename in os.listdir(BASE_DIR):
            if filename.endswith('.csv') and filename.startswith('bounce_analysis_'):
                csv_files.append(filename)
        csv_files.sort(reverse=True)  # Newest first
        return JSONResponse(content={"status": "success", "files": csv_files})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.get("/api/csv-data/{filename}")
@app.get("/stock/data/api/csv-data/{filename}")
async def get_csv_data(filename: str):
    """Get CSV data as JSON."""
    try:
        file_path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(file_path):
            return JSONResponse(content={"status": "error", "message": "File not found"})
        
        csv_data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                csv_data.append(row)
        
        return JSONResponse(content={"status": "success", "data": csv_data})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.get("/api/chart-data-from-files")
@app.get("/stock/data/api/chart-data-from-files")
async def get_chart_data_from_files(daily_file: str = Query(None), minute_file: str = Query(None)):
    """Get chart data from file names."""
    try:
        if daily_file:
            file_path = os.path.join(CHART_DIR, daily_file)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return JSONResponse(content={"status": "success", "data": data})
        
        if minute_file:
            file_path = os.path.join(CHART_DIR, minute_file)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return JSONResponse(content={"status": "success", "data": data})
        
        return JSONResponse(content={"status": "error", "message": "File not found"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.get("/api/bounce-analysis/{stock_code}")
@app.get("/stock/data/api/bounce-analysis/{stock_code}")
async def bounce_analysis(stock_code: str, date: str = Query(None)):
    """Analyze bounce after peak in 16 days daily chart using minute chart data."""
    try:
        # Get all daily chart files for this stock
        all_daily_data = []
        if not os.path.exists(CHART_DIR):
            return JSONResponse(content={"status": "error", "message": "Chart directory not found"})
        
        for filename in os.listdir(CHART_DIR):
            if filename.endswith('_min.json'):
                continue
            if filename.endswith('.json'):
                parts = filename[:-5].split('_')
                if len(parts) == 2:
                    date_str, file_stock_code = parts
                    if file_stock_code == stock_code and len(date_str) == 8 and date_str.isdigit():
                        file_path = os.path.join(CHART_DIR, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                daily_data = json.load(f)
                                if isinstance(daily_data, list):
                                    for item in daily_data:
                                        item['_file_date'] = date_str
                                    all_daily_data.extend(daily_data)
                        except Exception as e:
                            print(f"Error reading {filename}: {e}")
                            continue
        
        if not all_daily_data:
            return JSONResponse(content={"status": "error", "message": "No daily chart data found"})
        
        # Sort by date (oldest first)
        all_daily_data.sort(key=lambda x: x.get('dt', x.get('_file_date', '')))
        
        # Get last 16 days
        last_16_days = all_daily_data[-16:] if len(all_daily_data) >= 16 else all_daily_data
        
        if not last_16_days:
            return JSONResponse(content={"status": "error", "message": "Insufficient data for 16-day analysis"})
        
        # Find date with highest high_pric
        def parse_price(price_str):
            if not price_str:
                return 0
            cleaned = str(price_str).replace('+', '').replace('-', '').replace(',', '')
            return abs(float(cleaned)) if cleaned else 0
        
        highest_high = 0
        peak_date = None
        peak_high = 0
        peak_low = 0
        
        for item in last_16_days:
            high = parse_price(item.get('high_pric', 0))
            low = parse_price(item.get('low_pric', 0))
            if high > highest_high:
                highest_high = high
                peak_date = item.get('dt', item.get('_file_date', ''))
                peak_high = high
                peak_low = low
        
        if not peak_date:
            return JSONResponse(content={"status": "error", "message": "Could not find peak date"})
        
        # Calculate 16-day range (highest - lowest)
        all_highs = [parse_price(item.get('high_pric', 0)) for item in last_16_days]
        all_lows = [parse_price(item.get('low_pric', 0)) for item in last_16_days]
        range_16d = max(all_highs) - min(all_lows)
        threshold = (1.0 / 5.0) * range_16d  # 2/5 of range
        
        # Get minute chart data for peak date and next 4 days
        from datetime import datetime, timedelta
        peak_datetime = datetime.strptime(peak_date, "%Y%m%d")
        minute_data_all = []
        
        for day_offset in range(5):  # Peak day + next 4 days
            check_date = peak_datetime + timedelta(days=day_offset)
            check_date_str = check_date.strftime("%Y%m%d")
            
            minute_filename = f"{check_date_str}_{stock_code}_min.json"
            minute_file_path = os.path.join(CHART_DIR, minute_filename)
            
            if os.path.exists(minute_file_path):
                try:
                    with open(minute_file_path, 'r', encoding='utf-8') as f:
                        minute_data = json.load(f)
                        if isinstance(minute_data, list):
                            for item in minute_data:
                                item['_analysis_date'] = check_date_str
                            minute_data_all.extend(minute_data)
                except Exception as e:
                    print(f"Error reading minute chart {minute_filename}: {e}")
        
        # Sort minute data by timestamp
        minute_data_all.sort(key=lambda x: x.get('cntr_tm', ''))
        
        # Calculate bounce from minute chart
        # Bounce = maximum recovery from low after peak
        # Find the lowest point after peak, then find highest recovery
        peak_minute_high = 0
        lowest_after_peak = float('inf')
        highest_recovery = 0
        
        found_peak = False
        for item in minute_data_all:
            item_date = item.get('_analysis_date', '')
            if item_date == peak_date:
                high = parse_price(item.get('high_pric', 0))
                if high > peak_minute_high:
                    peak_minute_high = high
                found_peak = True
            elif found_peak:
                low = parse_price(item.get('low_pric', 0))
                high = parse_price(item.get('high_pric', 0))
                if low < lowest_after_peak:
                    lowest_after_peak = low
                # Calculate recovery from lowest point
                if lowest_after_peak != float('inf'):
                    recovery = high - lowest_after_peak
                    if recovery > highest_recovery:
                        highest_recovery = recovery
        
        # Determine success/failure
        # Success: bounce >= 2/5 of 16-day range
        # Failure: bounce < 2/5 of 16-day range within 4 days
        is_success = highest_recovery >= threshold
        result_type = "success" if is_success else "failure"
        
        # Build decision tree structure
        decision_tree = {
            "nodes": [
                {
                    "id": "root",
                    "level": 0,
                    "type": "condition",
                    "title": "Peak Analysis",
                    "value": f"Peak Date: {peak_date}",
                    "label": f"Highest High: {highest_high:.2f}"
                },
                {
                    "id": "range",
                    "level": 1,
                    "type": "condition",
                    "title": "16-Day Range",
                    "value": f"{range_16d:.2f}",
                    "label": f"Threshold: {threshold:.2f} (2/5 of range)"
                },
                {
                    "id": "bounce",
                    "level": 2,
                    "type": "condition",
                    "title": "Bounce Calculation",
                    "value": f"{highest_recovery:.2f}",
                    "label": f"From minute chart data"
                },
                {
                    "id": "result",
                    "level": 3,
                    "type": result_type,
                    "title": result_type.upper(),
                    "value": "✓" if is_success else "✗",
                    "label": f"Bounce {'≥' if is_success else '<'} {threshold:.2f}"
                }
            ],
            "edges": [
                {"from": "root", "to": "range", "label": "16-day analysis"},
                {"from": "range", "to": "bounce", "label": "Calculate bounce"},
                {"from": "bounce", "to": "result", "label": f"{'≥' if is_success else '<'} threshold"}
            ],
            "analysis": {
                "peak_date": peak_date,
                "peak_high": peak_high,
                "range_16d": range_16d,
                "threshold": threshold,
                "bounce": highest_recovery,
                "result": result_type,
                "lowest_after_peak": lowest_after_peak if lowest_after_peak != float('inf') else 0
            }
        }
        
        return JSONResponse(content={"status": "success", "data": decision_tree})
        
    except Exception as e:
        print(f"Error in bounce analysis: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.post("/api/make-bounce-csv")
@app.post("/stock/data/api/make-bounce-csv")
async def make_bounce_csv():
    """Generate CSV file with bounce analysis dataset following the specified algorithm."""
    try:
        def parse_price(price_str):
            if not price_str:
                return 0
            cleaned = str(price_str).replace('+', '').replace('-', '').replace(',', '')
            return abs(float(cleaned)) if cleaned else 0
        
        def calculate_moving_average(data, index, period):
            """Calculate moving average for a given index."""
            start_idx = max(0, index - period + 1)
            window = data[start_idx:index + 1]
            if not window:
                return 0
            closes = [parse_price(item.get('cur_prc', 0)) for item in window]
            return sum(closes) / len(closes) if closes else 0

        # Collect daily chart files (each file separately, not merged)
        daily_chart_files = []
        
        if not os.path.exists(CHART_DIR):
            return JSONResponse(content={"status": "error", "message": "Chart directory not found"})
        
        for filename in os.listdir(CHART_DIR):
            if filename.endswith('_min.json'):
                continue
            if filename.endswith('.json'):
                parts = filename[:-5].split('_')
                if len(parts) == 2:
                    date_str, stock_code = parts
                    if len(date_str) == 8 and date_str.isdigit():
                        file_path = os.path.join(CHART_DIR, filename)
                        daily_chart_files.append((stock_code, date_str, file_path))
        
        # Sort by stock code and date
        daily_chart_files.sort(key=lambda x: (x[0], x[1]))
        
        # Load interested stocks to get stock names
        interested_stocks = load_interested_stocks()
        
        # Prepare CSV data
        csv_rows = []
        csv_rows.append([
            'Stock Code',
            'Stock Name',
            'Success/Failure',
            'Highest Date',
            'Enter Date',
            'Enter Count',
            'Daily Chart File',
            'Minute Chart File',
            'Trading Amount',
            'Peak Rate',
            'Gap/Dif16',
            'MA5',
            'MA10',
            'MA20',
            'MA60',
            'MA120',
            'MA5/MA10',
            'MA10/MA20',
            'MA20/MA60',
            'MA60/MA120'
        ])
        
        record_count = 0
        seen_records = set()  # Track duplicate records by (stock_code, current_date)
        
        # Process each daily chart file separately
        for stock_code, file_date_str, file_path in daily_chart_files:
            # calling get_stockname is enough
            stock_name = get_stockname(stock_code)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    daily_data = json.load(f)
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue
            
            if not isinstance(daily_data, list) or len(daily_data) == 0:
                continue
            
            # Sort by date (old to new) - use only this file's data
            daily_data.sort(key=lambda x: x.get('dt', ''))

            # Test 4 & 5: Load minute chart using the date from daily chart filename
            # Use only one minute chart file that matches the date part of the daily chart filename
            minute_filename = f"{file_date_str}_{stock_code}_min.json"
            minute_file_path = os.path.join(CHART_DIR, minute_filename)

            if not os.path.exists(minute_file_path):
                continue  # Skip if minute chart file doesn't exist

            try:
                with open(minute_file_path, 'r', encoding='utf-8') as f:
                    minute_data_all = json.load(f)
            except Exception as e:
                print(f"Error reading minute chart {minute_filename}: {e}")
                continue

            if not isinstance(minute_data_all, list) or len(minute_data_all) == 0:
                continue

            # Sort minute data by timestamp
            minute_data_all.sort(key=lambda x: x.get('cntr_tm', ''))

            min_date_in_minutes = minute_data_all[0].get('cntr_tm', '')[:8]

            # Trace daily chart from old to new within this file
            prev_cur_prc = parse_price(daily_data[15].get('cur_prc', 0))
            for current_idx in range(16, len(daily_data)-1):
                current_item = daily_data[current_idx]
                current_date = current_item.get('dt', '')

                if stock_code == '060370' and current_date=='20251212':
                    pass
                if not current_date or current_date < min_date_in_minutes :
                    continue
                    
                current_high = parse_price(current_item.get('high_pric', 0))
                current_trde_prica = parse_price(current_item.get('trde_prica', 0))
                peak_rate = current_high / prev_cur_prc
                prev_cur_prc = parse_price(current_item.get('cur_prc', 0))
                if peak_rate < 0.12:
                    continue
                # Get 16 days window ending at current day (inclusive)
                window_data = daily_data[current_idx - 15:current_idx + 1]
                
                # Test 1: Check if current day's high price is 16-day highest
                window_highs = [parse_price(item.get('high_pric', 0)) for item in window_data]
                max_high_in_window = max(window_highs) if window_highs else 0
                
                if current_high != max_high_in_window:
                    continue  # Not highest, continue to next day
                
                # Test 2: Check if trading amount > 150000
                if current_trde_prica <= 150000:
                    continue  # Not large enough, continue to next day
                
                # Calculate dif16, h16, l16, touch_price, gap
                window_lows = [parse_price(item.get('low_pric', 0)) for item in window_data]
                h16 = max_high_in_window
                l16 = min(window_lows) if window_lows else 0
                dif16 = h16 - l16
                touch_price = h16 - (dif16 / 10) * 4
                gap = (h16 - l16) / 5
                
                # Test 4: During 2 data items after current day, find low price go under touch_price
                # Get the dates from data items (current_idx + 1 and current_idx + 2)
                if current_idx + 2 >= len(daily_data):
                    continue
                
                # Filter minute data for the 2 data items after (using their date values)
                day_count = 0
                enter_count = 0 # day_count when low price cross touch_price
                enter_date = ''  # date when price crosses below touch_price
                prev_dt_minute = ''
                touched = False
                reached = False
                low_bounce = None
                # Check if high price goes over (low_bounce + gap) AND over touch_price
                condition1_met = False  # high > (low_bounce + gap)
                condition2_met = False  # high > touch_price
                success_time = ''
                for item in minute_data_all:
                    # Extract date from cntr_tm (YYYYMMDDHHMMSS format)
                    cntr_tm = str(item.get('cntr_tm', ''))
                    if len(cntr_tm) >= 8:
                        item_date_str = cntr_tm[:8]
                    if item_date_str <= current_date:
                        continue

                    if item_date_str != prev_dt_minute:
                        prev_dt_minute = item_date_str
                        day_count += 1
                    if day_count >= 5:
                        break
                    low = parse_price(item.get('low_pric', 0))
                    if low_bounce is None or low < low_bounce:
                        low_bounce = low
                    if not touched : # test go below
                        if low < touch_price:
                            enter_count = day_count
                            enter_date = item_date_str  # Store the date when price crosses below touch_price
                            touched = True
                    else: # touched
                        high = parse_price(item.get('high_pric', 0))
                        if high > (low_bounce + gap):
                            condition1_met = True
                        if high > touch_price:
                            condition2_met = True
                        if condition1_met and condition2_met:
                            success_time = cntr_tm
                            break
                if not touched: # price never crossed down, or no minutes data for current_date
                    continue

                # Tag as success if both conditions met, otherwise failure
                is_success = condition1_met and condition2_met
                success_failure = "success" if is_success else "failure"
                
                # Check for duplicate record (same stock_code and current_date)
                record_key = (stock_code, current_date)
                if record_key in seen_records:
                    continue  # Skip duplicate record
                seen_records.add(record_key)
                
                # Calculate moving averages at current day (using only this file's data)
                ma5 = calculate_moving_average(daily_data, current_idx, 5)
                ma10 = calculate_moving_average(daily_data, current_idx, 10)
                ma20 = calculate_moving_average(daily_data, current_idx, 20)
                ma60 = calculate_moving_average(daily_data, current_idx, 60)
                ma120 = calculate_moving_average(daily_data, current_idx, 120)
                
                # Calculate ratios
                ma5_10 = ma5 / ma10 if ma10 > 0 else 0
                ma10_20 = ma10 / ma20 if ma20 > 0 else 0
                ma20_60 = ma20 / ma60 if ma60 > 0 else 0
                ma60_120 = ma60 / ma120 if ma120 > 0 else 0
                
                # Calculate gap/dif16
                gap_dif16 = h16 / l16
                
                # Get file names
                daily_chart_filename = f"{file_date_str}_{stock_code}.json"
                minute_chart_filename = f"{file_date_str}_{stock_code}_min.json"
                
                # Add row to CSV
                csv_rows.append([
                    stock_code,
                    stock_name,
                    success_failure,
                    current_date,
                    enter_date,
                    enter_count,
                    daily_chart_filename,
                    minute_chart_filename,
                    f"{current_trde_prica:.2f}",
                    f"{peak_rate:.6f}",
                    f"{gap_dif16:.6f}",
                    f"{ma5:.2f}",
                    f"{ma10:.2f}",
                    f"{ma20:.2f}",
                    f"{ma60:.2f}",
                    f"{ma120:.2f}",
                    f"{ma5_10:.6f}",
                    f"{ma10_20:.6f}",
                    f"{ma20_60:.6f}",
                    f"{ma60_120:.6f}"
                ])
                record_count += 1
        
        # Write CSV file
        csv_filename = f"bounce_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        csv_filepath = os.path.join(BASE_DIR, csv_filename)
        
        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(csv_rows)
        
        return JSONResponse(content={
            "status": "success",
            "message": "CSV file created successfully",
            "filename": csv_filename,
            "record_count": record_count,
            "download_url": f"./api/download-csv/{csv_filename}"
        })
        
    except Exception as e:
        print(f"Error making bounce CSV: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.get("/api/download-csv/{filename}")
@app.get("/stock/data/api/download-csv/{filename}")
async def download_csv(filename: str):
    """Download generated CSV file."""
    try:
        file_path = os.path.join(BASE_DIR, filename)
        if os.path.exists(file_path):
            return FileResponse(
                path=file_path,
                filename=filename,
                media_type='text/csv'
            )
        else:
            return JSONResponse(content={"status": "error", "message": "File not found"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.delete("/api/chart-data/{stock_code}/{date_str}")
@app.delete("/stock/data/api/chart-data/{stock_code}/{date_str}")
async def delete_chart_data(stock_code: str, date_str: str):
    """Delete chart data files (daily and minute) for a specific stock and date."""
    try:
        if not os.path.exists(CHART_DIR):
            return JSONResponse(content={"status": "error", "message": "Chart directory not found"})
        
        deleted_files = []
        deleted_count = 0
        
        # Delete daily chart file: YYYYMMDD_stockcode.json
        daily_filename = f"{date_str}_{stock_code}.json"
        daily_file_path = os.path.join(CHART_DIR, daily_filename)
        if os.path.exists(daily_file_path):
            try:
                os.remove(daily_file_path)
                deleted_files.append(daily_filename)
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting {daily_filename}: {e}")
        
        # Delete minute chart file: YYYYMMDD_stockcode_min.json
        minute_filename = f"{date_str}_{stock_code}_min.json"
        minute_file_path = os.path.join(CHART_DIR, minute_filename)
        if os.path.exists(minute_file_path):
            try:
                os.remove(minute_file_path)
                deleted_files.append(minute_filename)
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting {minute_filename}: {e}")
        
        if deleted_count > 0:
            return JSONResponse(content={
                "status": "success",
                "message": f"Deleted {deleted_count} chart file(s) for {stock_code} ({date_str})",
                "deleted_files": deleted_files
            })
        else:
            return JSONResponse(content={
                "status": "error",
                "message": f"No chart files found for {stock_code} ({date_str})"
            })
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8007, access_log=False)

