import requests
import json
import os

from au1001 import get_one_token, get_key_list, get_token

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

    if stk_cd == '000000':
        return 'SYSTEMLOG'
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
    print('no name in fn_ka10100 result')

    # no name in fn_ka10100 response
    result = next_getname(stk_cd, MY_ACCESS_TOKEN)
    if 'stk_nm' in result:
        return result['stk_nm']

    print('No name field in next_getname result')
    return ''


def next_getname(stk_cd, MY_ACCESS_TOKEN):
    params = {
        'stk_cd': stk_cd + '_AL',  #  (KRX:039490,NXT:039490_NX,SOR:039490_AL)
    }

    result = fn_ka10001(token=MY_ACCESS_TOKEN, data=params)

def fn_ka10001(token, data, cont_yn='N', next_key=''):
    host = 'https://api.kiwoom.com'
    endpoint = '/api/dostk/stkinfo'
    url = host + endpoint

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'ka10001',
    }

    response = requests.post(url, headers=headers, json=data)

    print('Code:', response.status_code)
    print('Header:',
          json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4,
                     ensure_ascii=False))
    print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON ÀÀ´äÀ» ÆÄ½ÌÇÏ¿© Ãâ·Â
    return response.json()

# 당일매매일지요청
def fn_ka10170(token, data, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	#host = 'https://mockapi.kiwoom.com' # 모의투자
	host = 'https://api.kiwoom.com' # 실전투자
	endpoint = '/api/dostk/acnt'
	url =  host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'ka10170', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	#print('Code:', response.status_code)
	#print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	#print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력
	return response.json()


def call_ka10170(MY_ACCESS_TOKEN, base_dt, ottks_dt='2', ch_crd_tp = '0'):
	# 2. 요청 데이터
	params = {
		'base_dt': base_dt, # 기준일자 YYYYMMDD(공백입력시 금일데이터,최근 2개월까지 제공)
		'ottks_tp': ottks_dt, # 단주구분 1:당일매수에 대한 당일매도,2:당일매도 전체
		'ch_crd_tp': ch_crd_tp, # 현금신용구분 0:전체, 1:현금매매만, 2:신용매매만
	}

	# 3. API 실행
	return fn_ka10170(token=MY_ACCESS_TOKEN, data=params)

	# next-key, cont-yn 값이 있을 경우
	# fn_ka10170(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')



# 일자별종목별실현손익요청_일자
def fn_ka10072(token, data, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	#host = 'https://mockapi.kiwoom.com' # 모의투자
	host = 'https://api.kiwoom.com' # 실전투자
	endpoint = '/api/dostk/acnt'
	url =  host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'ka10072', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	#print('Code:', response.status_code)
	#print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	#print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력
	return response.json()

def call_10072(MY_ACCESS_TOKEN, stk_cd, start_dt):
	# 2. 요청 데이터
	params = {
		'stk_cd': stk_cd, # 종목코드
		'strt_dt': start_dt, # 시작일자 YYYYMMDD
	}

	# 3. API 실행
	return fn_ka10072(token=MY_ACCESS_TOKEN, data=params)

	# next-key, cont-yn 값이 있을 경우
	# fn_ka10072(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')


def get_pl(acct, MY_ACCESS_TOKEN, tdy_dt):
	result_10170 = call_ka10170(MY_ACCESS_TOKEN, tdy_dt, '0')
	tdy_trde_diary = result_10170['tdy_trde_diary']
	pl = 0
	for trde in tdy_trde_diary:
		stk_cd = trde['stk_cd']
		if stk_cd[0] == 'A':
			stk_cd = stk_cd[1:]
		pl_trde = call_10072(MY_ACCESS_TOKEN, stk_cd, tdy_dt)
		dt_stk_div_rlzt_pl = pl_trde['dt_stk_div_rlzt_pl']
		for rlzt in dt_stk_div_rlzt_pl:
			stk_nm = rlzt['stk_nm']
			tdy_sel_pl = int(float(rlzt['tdy_sel_pl']))
			print(f"Account {acct} {stk_nm} {tdy_sel_pl}")
			pl += tdy_sel_pl
	print(f'Total {acct} profit={pl}')


# 실행 구간
if __name__ == '__main__':
	key_list = get_key_list()
	tdy_dt = '20260225'
	for k, key in key_list.items():
		ACCT = key['ACCT']
		MY_ACCESS_TOKEN = get_token(key['AK'], key['SK'])  # 접근토큰
		pl = get_pl(ACCT, MY_ACCESS_TOKEN, tdy_dt)
