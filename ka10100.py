import requests
import json
import os

from au1001 import get_one_token

# 종목정보 조회
def fn_ka10100(token, data, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	#host = 'https://mockapi.kiwoom.com' # 모의투자
	host = 'https://api.kiwoom.com' # 실전투자
	endpoint = '/api/dostk/stkinfo'
	url =  host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'ka10100', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력
	return response.json()


# Configuration
# Determine the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Define chart data directory: chart_data/day
STOCKNAMES_FILE = os.path.join(BASE_DIR, 'stocknames.json')


def load_stocknames():
    """Load interested stocks from JSON file."""
    if not os.path.exists(STOCKNAMES_FILE):
        print(f"Interested stocks file not found: {STOCKNAMES_FILE}")
        return {}

    try:
        with open(STOCKNAMES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {STOCKNAMES_FILE}: {e}")
        return {}

stocknames = load_stocknames()

def save_stocknames(stocknames):
    try:
        with open(STOCKNAMES_FILE, 'w', encoding='utf-8') as f:
            json.dump(stocknames, f, indent=2, ensure_ascii=False)
        print(f"Saved stocknames to {STOCKNAMES_FILE}")
        return True
    except Exception as e:
        print(f"Error saving stocknames: {e}")
        return False


# 실행 구간
def get_stockname(stk_cd):
    global stocknames

    if stk_cd in stocknames:
        return stocknames[stk_cd]

    print('in get_stockname')
    MY_ACCESS_TOKEN = get_one_token()
    # 2. 요청 데이터
    params = {
        'stk_cd': stk_cd, # 종목코드
    }

    print('calling fn_ka10100')
    # 3. API 실행
    json = fn_ka10100(token=MY_ACCESS_TOKEN, data=params)
    if 'name' in json:
        stocknames[stk_cd] = json['name']
        save_stocknames(stocknames)
        return json['name']

    print('No name field in fn_ka10100 result')
    return ''
