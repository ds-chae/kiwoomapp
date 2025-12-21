import json
import time
import os
import traceback
from datetime import datetime, timedelta
from ka10081 import get_day_chart
from ka10080 import get_bun_chart
from au1001 import get_one_token

# Configuration
# Determine the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Define chart data directory: chart_data/day
CHART_DIR = os.path.join(BASE_DIR, 'chart_data', 'day')
INTERESTED_STOCKS_FILE = os.path.join(BASE_DIR, 'interested_stocks.json')

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
    print(f"Starting daily data gathering at {datetime.now()}")
    
    # 1. Get Token
    try:
        token = get_one_token()
        if not token:
            print("Failed to obtain access token.")
            return
    except Exception as e:
        print(f"Error getting token: {e}")
        return

    # 2. Load Stocks
    stocks = load_interested_stocks()
    if not stocks:
        print("No interested stocks to process.")
        return
    
    print(f"Found {len(stocks)} stocks to process.")
    
    # 3. Process each stock - Daily charts only
    print(f"\n=== Gathering daily charts ===")
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
            else:
                print(f"No chart data found in response for {stock_code}")
                
            # Be polite to the API rate limits
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Exception processing {stock_code}: {e}")
            traceback.print_exc()

    # 4. Gather minute charts independently by scanning directory
    gather_minute_charts(token, stocks)
    
    print(f"Daily job finished at {datetime.now()}")

if __name__ == "__main__":
    ensure_chart_dir()
    print("datagather.py service started.")
    
    # Run once on startup
    print("Running initial data gathering...")
    run_daily_job()

    print("Waiting for execution time (21:00 daily)...")
    
    while True:
        now = datetime.now()
        
        # Check if it's 21:00 (9 PM)
        if now.hour == 21 and now.minute == 0:
            run_daily_job()
            # Sleep for 61 seconds to ensure we don't match the condition again today
            time.sleep(61)
        else:
            # Sleep for 30 seconds before checking again
            time.sleep(30)
