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

	#print(f"ACCT={ACCT}")
	# 3. API 실행
	acct = fn_ka01690(token=MY_ACCESS_TOKEN, data=params)
	acct['TOKEN'] = MY_ACCESS_TOKEN

	return acct

# next-key, cont-yn 값이 있을 경우
	# fn_ka01690(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')

def old_get_jango():
	key_list = get_key_list()
	jango = []
	for key in key_list:
		j = print_acnt(key['ACCT'], key['AK'], key['SK'])
		j['ACCT'] = key['ACCT']
		jango.append(j)

	return jango


import requests
import json


# Gyeja pyungga jango
def fn_kt00018(token, data, cont_yn='N', next_key=''):
	# 1. ¿äÃ»ÇÒ API URL
	#host = 'https://mockapi.kiwoom.com' # ¸ðÀÇÅõÀÚ
	host = 'https://api.kiwoom.com' # ½ÇÀüÅõÀÚ
	endpoint = '/api/dostk/acnt'
	url =  host + endpoint

	# 2. header µ¥ÀÌÅÍ
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # ÄÁÅÙÃ÷Å¸ÀÔ
		'authorization': f'Bearer {token}', # Á¢±ÙÅäÅ«
		'cont-yn': cont_yn, # ¿¬¼ÓÁ¶È¸¿©ºÎ
		'next-key': next_key, # ¿¬¼ÓÁ¶È¸Å°
		'api-id': 'kt00018', # TR¸í
	}

	# 3. http POST ¿äÃ»
	response = requests.post(url, headers=headers, json=data)

	# 4. ÀÀ´ä »óÅÂ ÄÚµå¿Í µ¥ÀÌÅÍ Ãâ·Â
	#print('Code:', response.status_code)
	#print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	#print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON ÀÀ´äÀ» ÆÄ½ÌÇÏ¿© Ãâ·Â

	return response.json()

def get_jango(market = 'KRX'):
	key_list = get_key_list()
	jango = []
	for key in key_list:
		MY_ACCESS_TOKEN = get_token(key['AK'], key['SK'])  # 접근토큰
		j = call_fn_kt00018(market, key['ACCT'], MY_ACCESS_TOKEN)
		j['ACCT'] = key['ACCT']
		j['MY_ACCESS_TOKEN'] = MY_ACCESS_TOKEN
		jango.append(j)
	return jango

def call_fn_kt00018(market, ACCT, MY_ACCESS_TOKEN):
	params = {
		'qry_tp': '2', # 1:Hapsan, 2:Gaebyul
		'dmst_stex_tp': market, # KRX, NXT
	}
	return fn_kt00018(token=MY_ACCESS_TOKEN, data=params)

	# next-key, cont-yn °ªÀÌ ÀÖÀ» °æ¿ì
	# fn_kt00018(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')


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
			ord_uv = '10560'
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

def round_trunc(dp):
	p = int(dp)
	modulus = 1

	if (p < 1000) :
		modulus = 1 # 1, 000¿ø ¹Ì¸¸ 1¿ø 1¿ø 5¿ø
	elif (p < 5000) :
		modulus = 5 # // // 1, 000 ~ 5, 000¿ø ¹Ì¸¸ 5¿ø 5¿ø
	elif (p < 10000) :
		modulus = 10 #// 5, 000 ~ 10, 000¿ø ¹Ì¸¸ 10¿ø 10¿ø 10¿ø
	elif (p < 50000) :
		modulus = 50 # // 10, 000 ~ 50, 000¿ø ¹Ì¸¸ 50¿ø 50¿ø 50¿ø
	elif (p < 100000) :
		modulus = 100 # // 50, 000 ~ 100, 000¿ø ¹Ì¸¸ 100¿ø 100¿ø 100¿ø
	elif (p < 500000) :
		modulus = 500 # // 100, 000 ~ 500, 000¿ø ¹Ì¸¸ 500¿ø 500¿ø
	else :
		modulus = 1000

	p = ( (p // modulus) + 1) * modulus
	return p


def is_between(now, start, end):
    return start <= now <= end

"""				
				{
					"stk_cd": "A005930",
					"stk_nm": "»ï¼ºÀüÀÚ",
					"evltv_prft": "-00000000196888",
					"prft_rt": "-52.71",
					"pur_pric": "000000000124500",
					"pred_close_pric": "000000045400",
					"rmnd_qty": "000000000000003",
					"": "000000000000003",
					"cur_prc": "000000059000",
					"pred_buyq": "000000000000000",
					"pred_sellq": "000000000000000",
					"tdy_buyq": "000000000000000",
					"tdy_sellq": "000000000000000",
					"pur_amt": "000000000373500",
					"pur_cmsn": "000000000000050",
					"evlt_amt": "000000000177000",
					"sell_cmsn": "000000000000020",
					"tax": "000000000000318",
					"sum_cmsn": "000000000000070",
					"poss_rt": "2.12",
					"crd_tp": "00",
					"crd_tp_nm": "",
					"crd_loan_dt": ""
				},
"""

def sell_jango(now, jango, market):
	for j in jango:
		if j["return_code"] != 0 :
			print('return code not 0 for {}'.format(j['ACCT']))
			pass
		else:
			MY_ACCESS_TOKEN = j['MY_ACCESS_TOKEN']
			acnt_evlt_remn_indv_tot = j["acnt_evlt_remn_indv_tot"]
			for indv in acnt_evlt_remn_indv_tot:
				stk_cd=indv['stk_cd']
				if stk_cd[0] == 'A':
					stk_cd = stk_cd[1:]
				trde_able_qty = indv["trde_able_qty"]
				rmnd_qty = indv['rmnd_qty']
				pur_pric = float(indv['pur_pric'])
				if stk_cd in sell_prices: # if indv['stk_nm'] == '박셀바이오':
					sell_cond = sell_prices[stk_cd]
					if int(trde_able_qty) != 0:
						trde_able_qty = trde_able_qty[4:]
						ord_uv = '-'
						if 'price' in sell_cond:
							ord_uv = '' + sell_cond['price']
						if ord_uv == '-':
							if 'rate' in sell_cond:
								s_rate = sell_cond['rate']
								s_price = pur_pric * (1.0 + s_rate)
								s_price = round_trunc(s_price)
								ord_uv = '' + s_price
						if ord_uv != '-' :
							trde_tp = '0'  # 매매구분 0:보통 , 3:시장가 , 5:조건부지정가 , 81:장마감후시간외 , 61:장시작전시간외, 62:시간외단일가 , 6:최유리지정가 , 7:최우선지정가 , 10:보통(IOC) , 13:시장가(IOC) , 16:최유리(IOC) , 20:보통(FOK) , 23:시장가(FOK) , 26:최유리(FOK) , 28:스톱지정가,29:중간가,30:중간가(IOC),31:중간가(FOK)
							ret_status = sell_order(MY_ACCESS_TOKEN, dmst_stex_tp=market, stk_cd=stk_cd,
														ord_qty=trde_able_qty, ord_uv=ord_uv, trde_tp=trde_tp, cond_uv='')
							print('sell_order_result')
							print(ret_status)
							rcde = ret_status['return_code']
							#code = rmsg[7:13]
							print(rcde)
							if rcde == 0:
								return True
						else:
							return False


import requests
import json

# 미체결요청
def fn_ka10075(token, data, cont_yn='N', next_key=''):
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
		'api-id': 'ka10075', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력
	return response.json()


# 실행 구간
def get_miche():
	key_list = get_key_list()
	miche = []
	for key in key_list:
		ACCT = key['ACCT']
		MY_ACCESS_TOKEN = get_token(key['AK'], key['SK'])  # 접근토큰
		# 2. 요청 데이터
		params = {
			'all_stk_tp': '0', # 전체종목구분 0:전체, 1:종목
			'trde_tp': '0', # 매매구분 0:전체, 1:매도, 2:매수
			'stk_cd': '', # 종목코드
			'stex_tp': '0', # 거래소구분 0 : 통합, 1 : KRX, 2 : NXT
		}

		# 3. API 실행
		m = fn_ka10075(token=MY_ACCESS_TOKEN, data=params)
		m['ACCT'] = ACCT
		m['TOKEN'] = MY_ACCESS_TOKEN
		miche.append(m)

	return miche

"""
oso	미체결	LIST	N		
- acnt_no	계좌번호	String	N	20	
- ord_no	주문번호	String	N	20	
- mang_empno	관리사번	String	N	20	
- stk_cd	종목코드	String	N	20	
- tsk_tp	업무구분	String	N	20	
- ord_stt	주문상태	String	N	20	
- stk_nm	종목명	String	N	40	
- ord_qty	주문수량	String	N	20	
- ord_pric	주문가격	String	N	20	
- oso_qty	미체결수량	String	N	20	
- cntr_tot_amt	체결누계금액	String	N	20	
- orig_ord_no	원주문번호	String	N	20	
- io_tp_nm	주문구분	String	N	20	
- trde_tp	매매구분	String	N	20	
- tm	시간	String	N	20	
- cntr_no	체결번호	String	N	20	
- cntr_pric	체결가	String	N	20	
- cntr_qty	체결량	String	N	20	
- cur_prc	현재가	String	N	20	
- sel_bid	매도호가	String	N	20	
- buy_bid	매수호가	String	N	20	
- unit_cntr_pric	단위체결가	String	N	20	
- unit_cntr_qty	단위체결량	String	N	20	
- tdy_trde_cmsn	당일매매수수료	String	N	20	
- tdy_trde_tax	당일매매세금	String	N	20	
- ind_invsr	개인투자자	String	N	20	
- stex_tp	거래소구분	String	N	20	0 : 통합, 1 : KRX, 2 : NXT
- stex_tp_txt	거래소구분텍스트	String	N	20	통합,KRX,NXT
- sor_yn	SOR 여부값	String	N	20	Y,N
- stop_pric	스톱가	String	N	20	스톱지정가주문 스톱가
"""

def cancel_nxt_trade(now):
	miche = get_miche()
	for m in miche:
		if 'oso' in m:
			oso = m['oso']
			for o in oso:
				stex_tp = o['stex_tp']
				ord_no = o['ord_no']
				stk_cd = o['stk_cd']
				if stex_tp == '1': # KRX
					#cancel_order_main(now, m['TOKEN'], 'KRX', ord_no, stk_cd)
					pass
				elif stex_tp == '2': # NXT
					cancel_order_main(now, m['TOKEN'], 'NXT', ord_no, stk_cd)
		pass


# 주식 취소주문
def fn_kt10003(token, data, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	# host = 'https://mockapi.kiwoom.com' # 모의투자
	host = 'https://api.kiwoom.com'  # 실전투자
	endpoint = '/api/dostk/ordr'
	url = host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8',  # 컨텐츠타입
		'authorization': f'Bearer {token}',  # 접근토큰
		'cont-yn': cont_yn,  # 연속조회여부
		'next-key': next_key,  # 연속조회키
		'api-id': 'kt10003',  # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:',
	      json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4,
	                 ensure_ascii=False))
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력


def cancel_order_main(now, access_token, stex, orig_ord_no, stk_cd):
	# 2. 요청 데이터
	params = {
		'dmst_stex_tp': stex, # 'KRX',  # 국내거래소구분 KRX,NXT,SOR
		'orig_ord_no': orig_ord_no,  # 원주문번호
		'stk_cd': stk_cd,  # 종목코드
		'cncl_qty': '0',  # 취소수량 '0' 입력시 잔량 전부 취소
	}

	# 3. API 실행
	fn_kt10003(token=access_token, data=params)


# next-key, cont-yn 값이 있을 경우
# fn_kt10003(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')

day_start_time = datetime.time(6, 0)  # 07:00
nxt_start_time = datetime.time(7, 59)  # 07:00
nxt_end_time = datetime.time(8, 49)  # 07:00
krx_start_time = datetime.time(8,51)
krx_end_time = datetime.time(15,30)
new_day = True
nxt_cancelled = False
krx_first = False

def cur_date():
	# Get today's date
	today = datetime.date.today()

	# Format the date as YYYYMMDD
	formatted_date = today.strftime("%Y%m%d")

	# Print the formatted date
	return formatted_date


def daily_work(now):
	global new_day, krx_first
	global nxt_start_time, nxt_end_time, krx_start_time,nxt_cancelled, krx_end_time
	if is_between(now, nxt_start_time, nxt_end_time):
		jango = get_jango()
		sell_jango(now, jango, 'NXT')
	elif is_between(now, nxt_end_time, krx_start_time):
		if not nxt_cancelled:
			nxt_cancelled = True
			cancel_nxt_trade(now)
	elif is_between(now, krx_start_time, krx_end_time):
		if not krx_first:
			print('{} krx_first get_jango and sell_jango.'.format(now))
			krx_first = True
		jango = get_jango()
		sell_jango(now, jango, 'KRX')
	else:
		if (new_day):
			new_day = False
			print('{} {} Setting new day=False'.format(cur_date(), now))


def set_new_day():
	global new_day, waiting_shown, no_working_shown, nxt_cancelled, ktx_first

	if new_day:
		return
	print('{} {} Setting new day=True'.format(cur_date(), now))
	new_day = True
	waiting_shown = False
	no_working_shown = False
	nxt_cancelled = False
	ktx_first = False

SELL_PRICES_FILE = 'sell_price_rate.json'
sell_prices = {}

def load_dictionaries_from_json():
	"""Load sell_prices and profit_rate from JSON files"""
	global sell_prices

	# Load sell_prices
	if os.path.exists(SELL_PRICES_FILE):
		try:
			with open(SELL_PRICES_FILE, 'r') as f:
				sell_prices = json.load(f)
			print(f"Loaded sell_prices from {SELL_PRICES_FILE}: {sell_prices}")
		except Exception as e:
			print(f"Error loading sell_prices: {e}")
			sell_prices = {}
	else:
		sell_prices = {}
		print(f"Created new sell_prices dictionary")



# 실행 구간
if __name__ == '__main__':
	p = round_trunc(102171)
	print(p)
	now = datetime.datetime.now().time()
	cancel_nxt_trade(now)

	load_dictionaries_from_json()

	#key_list = get_key_list()
	#for key in key_list:
	#	print_acnt(key['ACCT'], key['AK'], key['SK'])

	prev_hour = datetime.datetime.now().time().hour

	# 매 초 혹은 주기적으로 호출하도록 구성 (예: loop 안)
	while True:
		now = datetime.datetime.now().time()
		now_hour = now.hour
		if now_hour != prev_hour:
			print('{} Hour change from {} to {}'.format(cur_date(), prev_hour, now_hour))

		if is_between(now, day_start_time, nxt_start_time):
			set_new_day()
		elif new_day:
			try:
				daily_work(now)
			except Exception as ex:
				new_day = False
				print('{} {} Setting new_day False due to Exception.'.format(cur_date(), now))
				print(ex)

		prev_hour = now_hour
		time.sleep(5)