import requests
import json
import pandas as pd

from au1001 import get_one_token

def get_price_index(color):
	if color == 'R': # 빨 Red
		return 2
	if color == 'O': # 주 Orange
		return 3
	if color == 'Y': # 노 Yellow
		return 4
	if color == 'G': # 초 Green
		return 5
	if color == 'B': # 파 Blue
		return 6
	if color == 'D': # 남 Dark Blue
		return 7
	if color == 'V': # 보 Violet
		return 8
	return 9
# [2] -> R, [3] -> O


def get_bun_price(stk_cd, stk_nm, chart ):
	bun_price = {}
	bun_price['stk_cd'] = stk_cd
	bun_price['stk_nm'] = stk_nm
	high_index = 0
	low_index = 0
	high_price = 0
	low_price = 0
	chartlen = len(chart)
	if chartlen < 416:
		bun_price['high_price'] = 0
		bun_price['low_price'] = 0
		return bun_price
	prd = 416
	i = 0
	# find high
	while i < prd :
		buntick = chart[i]
		hpc = int(buntick['high_pric'])
		if hpc < 0 :
			hpc = -hpc
		if hpc > high_price:
			high_index = i
			high_price = hpc
		i += 1
	i = high_index

	# find lowest price after high price
	hidx = high_index - 1
	low_price = int(chart[high_index]['low_pric'])
	if low_price < 0:
		low_price = -low_price
	while hidx >= 0 :
		tlpc = int(chart[hidx]['low_pric'])
		if tlpc < 0 :
			tlpc = -tlpc
		if low_price > tlpc:
			low_price = tlpc
		hidx -= 1

	if (i + prd) >= chartlen:
		bun_price['high_price'] = 0
		bun_price['low_price'] = 0
		return bun_price
	index_386 = i + prd
	low_price = high_price
	while i < index_386:
		buntick = chart[i]
		lpc = int(buntick['low_pric'])
		if lpc < 0 :
			lpc = -lpc
		if lpc < low_price:
			low_price = lpc
			low_time = buntick['cntr_tm']
		i += 1
	bun_price['high_price'] = high_price
	bun_price['low_price'] = low_price
	gap = (high_price - low_price) / 10
	bun_price['gap'] = gap
	bun_price['price'] = [high_price - gap * i for i in range(10)]
	return bun_price
	# [2] -> R, [3] -> O

# 주식분봉차트조회요청
def fn_ka10080(token, data, cont_yn='N', next_key=''):
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
		'api-id': 'ka10080', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	dump_chart = False
	if dump_chart:
		# 4. 응답 상태 코드와 데이터 출력
		print('Code:', response.status_code)
		print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
		print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력

	return response.json()['stk_min_pole_chart_qry']


def get_bun_chart(MY_ACCESS_TOKEN, stk_cd, stk_nm):
	params = {
		'stk_cd': stk_cd, # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
		'tic_scope': '15', # 틱범위 1:1분, 3:3분, 5:5분, 10:10분, 15:15분, 30:30분, 45:45분, 60:60분
		'upd_stkpc_tp': '1', # 수정주가구분 0 or 1
	}
	print('get_bun_chart:{} {}'.format(stk_cd, stk_nm))
	# 3. API 실행
	return fn_ka10080(token=MY_ACCESS_TOKEN, data=params)


# 실행 구간
if __name__ == '__main__':
	# 1. 토큰 설정
	MY_ACCESS_TOKEN = get_one_token()

	stk_cd = '105840'
	stk_nm = '우진'
	# 2. 요청 데이터
	params = {
		'stk_cd': stk_cd, # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
		'tic_scope': '15', # 틱범위 1:1분, 3:3분, 5:5분, 10:10분, 15:15분, 30:30분, 45:45분, 60:60분
		'upd_stkpc_tp': '1', # 수정주가구분 0 or 1
	}

	# 3. API 실행
	bun_chart = fn_ka10080(token=MY_ACCESS_TOKEN, data=params)
	print(bun_chart)

	bun_price = get_bun_price(stk_cd, stk_nm, bun_chart)
	print(bun_price)

	# next-key, cont-yn 값이 있을 경우
	# fn_ka10080(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')