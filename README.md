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

during merge minutes chart data and daily chart data, overwrite existing same datetime record by new downloaded chart data.

when make csv file, follow this instruction.
trace daily chart from old to new. test if that day's high price is 16 days highest price.
if not highest, continue to next day.
if highest, then test if that day's trading amount is larger then 150000.
if not larger, continue to next day. if yes, then test bounce from that day using minutes chart. 
if that date do not have corresponding minutes chart data including that data and consecutive 4 days, continue to next day.
before test bounce get the difference between low and high price
during 16 days to that day. calculatel the difference high minus low as dif16. name high price as h16, low price as l16.
calculate (high - dif16/2) as touch_price. calculate (high-low)/5 as gap, then during 2 days after that day trace minutes chart to find low price go under touch_price.
if low price do not go under touch_price in 2 days after high date, do not record this high date and continue to next day.
if low price go down under touch_price in 2 days, call that low price as low_bounce. trace next minutes chart for 3 days that consequent high price go over (low_bounce + gap)
and the high price go over touch_price. if the two go over conditions are met, tag that date as success, otherwise false.
now save the stock code, success/failure, highest date, trading amount, gap/dif16,
5 days moving average closing price of daily chart as ma5, 
10 days moving average closing price of daily chart as ma10,
20 days moving average closing price of daily chart as ma20, 
60 days moving average closing price of daily chart as ma60, 
120 days moving average closing price of daily chart as ma120.
save ma5 / ma10 as ma5_10,
save ma10 / ma20 as ma10_20,
save ma20 / ma60 as ma20_60,
save ma60 / ma120 as ma60_120.


in making csv, do not merge all daily chart into one daily chart for one stock. just make csv per each daily chart, each stock code. do not merge all minutes into one minutes chart. use minutes chart with corresponding date part in file name.

to make csv, days count is not calendar days, but count of data items. so, corresponding minutes chart data shod get from those date value in data. not in calendar days count.


add one button "Look CSV" in /stock/data page. when user click that button, show a page simillar to charts page. the origianl charts page display all stocks chart under /char_data/day directory. but this look page shows csv file list to select. and when user select a csv file, it list stock code and name at left pane. then show chart at right pane. on right page, display daily chart in upper area, display minutes chart at lower page. as the csv file contain daily chart file name and minutes chart file name. thus the backend should read those files. in chart area draw a vertical lie at left of highest date in daily chart. and display S on success, F on failure at the left of the vertical line. in minutes chart fill the background of minutes chart that have highest date date value in cntr_tm. one day amount of minutes chart. on success background is light yellow, on failure light blue. do not add other actions not provided.

modify autotr.py. save jango data when its content is changed. load jango data at initial startup. when jango data change, test if existing holdings are removed, that is sold. if sold, then change btype of that stock code in interested_stocks to 'SCL' if its previous btype is 'CL'. when change btype to 'SCL', cancel buy orders of that stock code.

when compare jango data, do not compare deeply. compare stock code and amount are enough. do not save price, profit rate, etc.

previoud jango should be updated when jango is changed.

previous_jango_data_simplified is initialized at startup and dail_work iis called after that. why test if previous_jango_data_simplified is none every time?

ui에 uploads/image를 image list로 볼 수 있는 button을 추가한다. 목록은 화면 너비에 따라서 타일 형식으로 보여준다.  이미지 파일 이름으로 오름차순 또는 내림차순으로 정렬 가능하다.

uploads/image를  popup으로 보여주지 않는다. 다른 페이지로 이동해서 보여준다. 이동해서 보여주는 화면에는 이전화면 버튼을 추가한다.

이미지 그리드에서 이미지를 클릭하면 원래 크기로 보여주는 기능 추가

이미지 그리드는 화면 전체 너비를 사용하도록 한다. 각각의 셀의 폭은 현재의 두 배로 한다. 각가의 셀에 파일 이름을 표시한다.

in mobile environment, layout of  buttons "data", "Images", "Logout", etc. should be responsive.

손절 기능을 구현한다. 주식 보유 화면에서 보유 종목의 행을 클릭하면 나타나는 매도 가격(sell price), 수익률(sell rate), 매도 갭(sell gap)을 구현한 화면 우측에 에 손절 금액 입력 칸과 손절 버튼을 표시한다. 손절 버튼의 caption은 CUT이다. 사용자가 CUT 버튼을 클릭하면 1. sell price, sell rate, sell gap을 모두 0으로 설정한다. 2. 현재 선택한 종목의 매수, 매도 주문을 모두 취소한다. 3. 매수 가격과 현재 가격의 차액과 거래수수료 0.23%로 손절 금액에 따른 매도 수량을 계산하고, 계산된 수량만큼 매도 주문을 수행한다. 매도 관련 수칙가 모두 0이 되어 해당 종목은 별도의 설정이 있기 전에는 자동 매도가 되지 않게 된다.

CUT  기능을 하나의 backend api로 구성하라. 여러개의 backend를 호출하도록 구성하지 않는다.

보유 종목을 클릭해서 나오는 필드에서 Bmount를 제거. Apply 버튼, Cancel 버튼을 Sell Gap 우측으로 이동.  "손절 금액" 레이블 제거.

CUT 관련 입력 창과 버튼을 Sell Price, Rate, Gap과 동일한 에이아웃에 배치

손절 가격을 계산한 후에 매도할 때대에 지정가로 매도하도록 수정

손절 수량 계산은 제미나이에게 일임. - 주식을 손절할 때에 손절할 총 금액을 지정하면 매수 가격과 현재 가격, 그리고 매도 수수료 0.23%를 적용하여 현재 가격에 몇 주를 매도하는지를 계산하는 코드를 파이썬으로 작성하라

cut 실행시에 cur_prc를 이미 받아왔으므로 cur_prc_f로부터 매도 가격을 계산하지 않는다.

손절에 대해서 모든 account에 동일하게 적용하라.

when click cut, "No account had a valid CUT sell target"

add a screen to modify some text file in /home/cds directory. in windows that directory is c:/temp. the user enter this screen thru clicking a button "CONN". the button should be placed at the and of holdings ui. the scrren then read files allowip.txt and allowcon.txt and display them in text input boxes. then a "MODIFY" button exits to modify those texts. build backend api and ui to do these functions.

datagather.py를 수정한다. 오전 11:30부터  오후 15:00까지 5분 간격으로 kiwoom restapi 중에 조건 검색을 조건명 P3에 대해서 실행하고, 그 결과를 https://sojucoin.com/stock//api/interested-stocks를 통하여 interested_stocks에 반영되도록 하라. 한 stock code에 대하여 하루에는 한 번만 호출하도록 한다. 호출 시 변수는 bcolor = "노", btype="CL", bamount=500000, clrate=70, cookie="pctoken=allow_interest_pc" 로 설정한다.  https://sojucoin.com/stock//api/interested-stocks를 분석하여, 부족한 변수는 디폴트 값으로 설정하라. api backend는 autotr.py에 존재한다.

datagather.py를 수정하라. P3 조건 검색 결과를 전송할 때에 logs/yyyymmdd/datagather.log 파일에 상세 내용을 로그로 기록하도록 하라.

실제로 서버는 정상 동작 중이었는데 front end에서 간헐적으로 "Backend is down..." 메시지가 나오면서 자료가 보이지 않는 경우가 있음. 이런 문제가 발생하는 원인을 찾아서 수정하기 바람. 서버가 특정 작업을 하는 동안에 rest api request를 처리하지 못하는 문제가 발생할 수 있는지 점검할 것

frontend에서 보유 종목을 클릭했을 때 아무런 반응이 없을 떄가 있음. 원인을 파악해서 수정하라

orders section 테이블 하단에 queued_buy 내용을 표시할 것. orders request 의 응답 뒷부분에 queued_buy 내용을 추가해서 ui 에서 표시하도록 수정하라

"Queued Buy"라는 타이틀과 타이틀 섹션은 제거하라. 테이블의 컬럼 헤더와 내용만 표시하고, 각각의 행에 DELETE 버튼을 추가하라. 백엔드에 Queued_buy에 대한 delete 기능도 구현하라.

get_jango 호출에서 오류가 발생하면 보유 종목이 없어진 것으로 판단해서 btype이 CL에서 SCL로 변경이 되는 오류가 있음. get_jango 호출시에 오류가 발생하면 보유종목 목록에 반영하지 않도록 수정하라.

interested stocks ui를 개선한다. 삭제 버튼 좌측에 "분석" 버튼을 추가한다. 분석 버튼을 클릭하면 해당 종목의 분석 화면으로 이동한다. 분석화면의 ui 는 datagather.py에서 보여주도록 한다. 분석 화면에서는 해당 종목의 일봉 차트와 15분 분봉 차트를 보여준다. 일봉 차트에는 캔들 차트와 이동 평균선을 그려준다.  이동 평균선은 5,20,60,120선으로 그린다. 이동 평균선을 선 그래프로 그린다. 일봉 차트의 UI에 이동 평균선 기간을 편집할 수 있는 입력창과 표시 여부를 지정할 수 있는 체크 박스를 제공한다. 이 편집 박스의 위치는 차트 왼쪽으로 한다. 일봉 차트를 화면 상단에 그리고, 분봉 차트를 화면 하단에 그린다. 일봉 차트와 분봉 차트 사이에 각 이동 평균선을 비교하는 차트를 주가한다. 이 비교 차트에는 120일 이동평균선 값으로 다른 이동 평균선 값을 나눈 수치를 선 그래프로 그린다.

15분 분봉 차트에는 날짜 변경 수직선을 넣어주고, 분봉의 폭을 3픽셀로 그려줘

분봉 차트에 15분 30분 60분 체크 박스를 왼쪽에 넣어주고, 선택하면 해당 분봉 차트를 그려줘

분봉 차트에 15분 30분 60분 체크 박스를 왼쪽에 넣어주고, 선택하면 해당 분봉 차트를 그려줘

그래프를 서버에서 opencv로 그린 다음에 보여주는 방식으로 변경해 봐. 그래프 저장할 때는 png로 저장하고.

차트 이미지가 생성이 되지만 ui에서는 보이지 않음
(원인은 8006을 거쳐서 8007에 요청하므로 8007이 그림을 리턴하면 8006이 { data: } 형식의 json data로 변형하는 것이었음)

서버에서 렌더링 하는 작업이 오래 걸리므로, UI에서 webgl로 차트를 그리도록 수정해

일봉 차트에 10일 간격으로 수직선을 추가할 것. 10일 간격을 실제 갯수를 세지 말고 달력에서 보이는 날짜로 계산할 것. 1,10,20 이런 식으로 30일은 표시하지 말고, 각 달의 첫째 날짜부터 그릴 것. 예를 들어서 2/2,10,20 이렇게 표시할 것

autotr.py를 수정한다. /stock/temperature backend로 post request에 의한 데이터를 받는다. 이 데이터는 fan과 temperatur 두 개이다. ./temperature 디렉토리에 데이터를 받은 시간을 이용하여 yyyymmddhhmmss.txt라는 이 형식의 이름으로 저장한다. 그리고, /stock/temperatur backend를 get method로 호출하면 ./temperature에 저장된 데이커를 읽어서 위쪽에는 temperature를 표시하고, 아래쪽에는 fan을 표시하는 꺾은 선 그래프를 그리도록 한다. fan의 값은 0과 1만 존재한다.

autotr.py를 수정한다.  pc_color, pc_sellrate, pc_bamount를 전역 변수로 선언헌다. 이 전역 변수 세개를 파일로 저장해서 관리한다. 이 값들을 관리하는 화면을 "설정" 버튼을 통해서 진입하도록 한다
