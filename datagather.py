import json
import time
import os
import traceback
from datetime import datetime
from ka10081 import get_day_chart
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

def save_and_merge_chart_data(stock_code, new_data_list):
    """
    Save chart data to file, merging with existing data.
    Preserves existing data and appends new unique records.
    """
    file_path = os.path.join(CHART_DIR, f"{stock_code}.json")
    
    existing_data = []
    
    # Load existing data if file exists
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"Error reading existing chart data for {stock_code}: {e}")
            
    # Merge logic: Deduplicate based on full record content
    # Using json dump as key for stability
    existing_set = set()
    for record in existing_data:
        try:
            # Sort keys to ensure consistent string representation
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
            print(f"[{stock_code}] Saved. Added {added_count} new records. Total: {len(merged_data)}")
        else:
            print(f"[{stock_code}] Saved. No new records found. Total: {len(merged_data)}")
            
    except Exception as e:
        print(f"Error saving file for {stock_code}: {e}")

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
    
    # 3. Process each stock
    for stock_code, stock_info in stocks.items():
        stock_name = stock_info.get('stock_name', stock_code)
        print(f"Processing {stock_code} ({stock_name})...")
        
        try:
            # Fetch data using ka10081
            result = get_day_chart(token, stock_code)
            
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
                save_and_merge_chart_data(stock_code, data_list)
            else:
                print(f"No chart data found in response for {stock_code}")
                
            # Be polite to the API rate limits
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Exception processing {stock_code}: {e}")
            traceback.print_exc()

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
