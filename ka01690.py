import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from au1001 import get_token, get_key_list
import time

# Load environment variables from .env file
load_dotenv()

# Load KIWOOM_SK and KIWOOM_AK from environment variables
KIWOOM_SK = os.getenv('KIWOOM_SK')
KIWOOM_AK = os.getenv('KIWOOM_AK')

SK_0130 = os.getenv('SK_0130')
AK_0130 = os.getenv('AK_0130')

# 일별잔고수익률
def fn_ka01690(token, data, cont_yn='N', next_key=''):
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
		'api-id': 'ka01690', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력

	return response.json()


def print_acnt(ACCT, AK, SK):
	acnt = []
	# 1. 토큰 설정
	MY_ACCESS_TOKEN = get_token(AK, SK) # 접근토큰

	# 2. 요청 데이터
	params = {
		'qry_dt': datetime.datetime.now().strftime('%Y%m%d'),  # 조회일자 (오늘 날짜)
	}

	print(f"ACCT={ACCT}")
	# 3. API 실행
	acct = fn_ka01690(token=MY_ACCESS_TOKEN, data=params)
	acct['TOKEN'] = MY_ACCESS_TOKEN

	return acct

# next-key, cont-yn 값이 있을 경우
	# fn_ka01690(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')

def get_jango():
	key_list = get_key_list()
	jango = []
	for key in key_list:
		j = print_acnt(key['ACCT'], key['AK'], key['SK'])
		j['ACCT'] = key['ACCT']
		jango.append(j)

	return jango

from fn_kt10000 import sell_order

def print_j(j):
	#print(j)
	TOKEN = j['TOKEN']
	day_bal_rt = j['day_bal_rt']
	#print(day_bal_rt)
	for bal_rt in day_bal_rt:
		#print(bal_rt)
		if bal_rt['stk_nm'] == '박셀바이오':
			print(bal_rt)
			rmnd_qty = bal_rt['rmnd_qty']
			ord_uv = '10600'
			if rmnd_qty != '0':
				trde_tp = '0' # 매매구분 0:보통 , 3:시장가 , 5:조건부지정가 , 81:장마감후시간외 , 61:장시작전시간외, 62:시간외단일가 , 6:최유리지정가 , 7:최우선지정가 , 10:보통(IOC) , 13:시장가(IOC) , 16:최유리(IOC) , 20:보통(FOK) , 23:시장가(FOK) , 26:최유리(FOK) , 28:스톱지정가,29:중간가,30:중간가(IOC),31:중간가(FOK)
				ret_status = sell_order(TOKEN, dmst_stex_tp='NXT', stk_cd=bal_rt['stk_cd'], ord_qty=rmnd_qty, ord_uv=ord_uv, trde_tp=trde_tp, cond_uv='')
				print('sell_order_result')
				print(ret_status)
				rcde = ret_status['return_code']
				#code = rmsg[7:13]
				print(rcde)
				if rcde == 0:
					return True
	pass
	return False

import datetime


def is_between(now, start, end):
    return start <= now <= end

def sell_jango():
	tf = False
	jango = get_jango()
	for j in jango:
		tf = print_j(j)
		if tf:
			break
	return tf

# 실행 구간
if __name__ == '__main__':
	#key_list = get_key_list()
	#for key in key_list:
	#	print_acnt(key['ACCT'], key['AK'], key['SK'])
	h6 = datetime.time(7,40)
	start_time = datetime.time(7, 50)  # 07:00
	end_time = datetime.time(9, 10)  # 09:00
	finish_time = datetime.time(20,0)

	new_day = True
	while True:
		# 매 초 혹은 주기적으로 호출하도록 구성 (예: loop 안)
		now = datetime.datetime.now().time()

		if new_day:
			if is_between(now, start_time, end_time):
				tf = sell_jango()
				if tf:
					new_day = False
			elif is_between(now, end_time, finish_time):
				new_day = False
			else:
				print('{} is not working time.'.format(now))
		else:
			if is_between(now, h6, start_time):
				new_day = True
			else:
				print('{} is waiting new day.'.format(now))

		time.sleep(5)