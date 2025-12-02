import requests
import json

from au1001 import get_key_list, get_token


# 주식 매수주문
def fn_kt10000(token, data, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	#host = 'https://mockapi.kiwoom.com' # 모의투자
	host = 'https://api.kiwoom.com' # 실전투자
	endpoint = '/api/dostk/ordr'
	url =  host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'kt10000', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력


import requests
import json


# 주식 매도주문
def fn_kt10001(token, data, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	#host = 'https://mockapi.kiwoom.com' # 모의투자
	host = 'https://api.kiwoom.com' # 실전투자
	endpoint = '/api/dostk/ordr'
	url =  host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'kt10001', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력

	return response.json()

def sell_order(MY_ACCESS_TOKEN, dmst_stex_tp='KRX', stk_cd='', ord_qty='0', ord_uv='0', trde_tp='0',cond_uv=''):
	# 2. 요청 데이터
	params = {
		'dmst_stex_tp': dmst_stex_tp,
		'stk_cd': stk_cd,
		'ord_qty': ord_qty,
		'ord_uv': ord_uv,
		'trde_tp': trde_tp,
		'cond_uv': cond_uv
	}

	# 3. API 실행
	ret_status = fn_kt10001(token=MY_ACCESS_TOKEN, data=params)
	return ret_status

# 실행 구간
def sell_example(MY_ACCESS_TOKEN, dmst_stex_tp='KRX', stk_cd='', ord_qty='0', ord_uv='0', trde_tp='0',cond_uv=''):
	# 2. 요청 데이터
	params = {
		'dmst_stex_tp': dmst_stex_tp,
		'stk_cd': stk_cd,
		'ord_qty': ord_qty,
		'ord_uv': ord_uv,
		'trde_tp': trde_tp,
		'cond_uv': cond_uv
	}

	# 3. API 실행
	fn_kt10001(token=MY_ACCESS_TOKEN, data=params)

	# next-key, cont-yn 값이 있을 경우
	# fn_kt10001(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')


def buy_order(MY_ACCESS_TOKEN, dmst_stex_tp='KRX', stk_cd='', ord_qty='0', ord_uv='0', trde_tp='0',cond_uv=''):
	params = {
		'dmst_stex_tp': dmst_stex_tp, # 'KRX', # 국내거래소구분 KRX,NXT,SOR
		'stk_cd': stk_cd, # '005930', # 종목코드
		'ord_qty': ord_qty, # '1', # 주문수량
		'ord_uv': ord_uv, # '', # 주문단가
		'trde_tp': trde_tp, # '3', # 매매구분 0:보통 , 3:시장가 , 5:조건부지정가 , 81:장마감후시간외 , 61:장시작전시간외, 62:시간외단일가 , 6:최유리지정가 , 7:최우선지정가 , 10:보통(IOC) , 13:시장가(IOC) , 16:최유리(IOC) , 20:보통(FOK) , 23:시장가(FOK) , 26:최유리(FOK) , 28:스톱지정가,29:중간가,30:중간가(IOC),31:중간가(FOK)
		'cond_uv': cond_uv # '', # 조건단가
	}

	# 3. API 실행
	fn_kt10000(token=MY_ACCESS_TOKEN, data=params)


def buy_example(ACCT, AK, SK):
	MY_ACCESS_TOKEN = get_token(AK, SK)  # 접근토큰

	# 2. 요청 데이터
	params = {
		'dmst_stex_tp': 'KRX', # 국내거래소구분 KRX,NXT,SOR
		'stk_cd': '005930', # 종목코드
		'ord_qty': '1', # 주문수량
		'ord_uv': '', # 주문단가
		'trde_tp': '3', # 매매구분 0:보통 , 3:시장가 , 5:조건부지정가 , 81:장마감후시간외 , 61:장시작전시간외, 62:시간외단일가 , 6:최유리지정가 , 7:최우선지정가 , 10:보통(IOC) , 13:시장가(IOC) , 16:최유리(IOC) , 20:보통(FOK) , 23:시장가(FOK) , 26:최유리(FOK) , 28:스톱지정가,29:중간가,30:중간가(IOC),31:중간가(FOK)
		'cond_uv': '', # 조건단가
	}

	# 3. API 실행
	fn_kt10000(token=MY_ACCESS_TOKEN, data=params)


if __name__ == '__main__':
	key_list = get_key_list()
	for key in key_list:
		# 1. 토큰 설정
		ACCT = key['ACCT']
		AK = key['AK']
		SK = key['SK']
		MY_ACCESS_TOKEN = get_token(AK, SK)  # 접근토큰
		print(ACCT, AK, SK, MY_ACCESS_TOKEN)
