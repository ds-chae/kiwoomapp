import requests
import json

from au1001 import get_one_token

log_day_chart = False

# 주식일봉차트조회요청
def fn_ka10081(token, data, cont_yn='N', next_key=''):
	global log_day_chart
	# 1. 요청할 API URL
	#host = 'https://mockapi.kiwoom.com' # 모의투자
	host = 'https://api.kiwoom.com' # 실전투자
	endpoint = '/api/dostk/chart'
	url =  host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'ka10081', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	if log_day_chart:
		print('Code:', response.status_code)
		print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
		print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력
	return response.json()

from datetime import datetime

def get_day_chart(MY_ACCESS_TOKEN, stk_cd, date=None):
	if not date or date == '' or len(date) != 8 :
		# Get current date and time
		now = datetime.now()
		# Format to YYYYMMDD
		date = now.strftime("%Y%m%d")

	params = {
		'stk_cd': stk_cd, # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
		'base_dt': date, # 기준일자 YYYYMMDD
		'upd_stkpc_tp': '1', # 수정주가구분 0 or 1
	}

	# 3. API 실행
	day_chart = fn_ka10081(token=MY_ACCESS_TOKEN, data=params)
	return day_chart

	# next-key, cont-yn 값이 있을 경우
	# fn_ka10081(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')

# 실행 구간
if __name__ == '__main__':
	# 1. 토큰 설정
	MY_ACCESS_TOKEN = get_one_token()

	log_day_chart = True
	result = get_day_chart(MY_ACCESS_TOKEN, '005930', date=None)
	if result['return_code'] == 0 :
		print(result['stk_dt_pole_chart_qry'])
