import requests
import json
import os
from datetime import datetime, timedelta, time, date
from dotenv import load_dotenv
from au1001 import get_token, get_key_list
import time as time_module
import threading
from fastapi import FastAPI, HTTPException, status, Cookie, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
from contextlib import asynccontextmanager
import secrets
import socket

# Load environment variables from .env file
load_dotenv()

# Load KIWOOM_SK and KIWOOM_AK from environment variables
KIWOOM_SK = os.getenv('KIWOOM_SK')
KIWOOM_AK = os.getenv('KIWOOM_AK')

SK_0130 = os.getenv('SK_0130')
AK_0130 = os.getenv('AK_0130')

# Authentication configuration
LOGIN_USERNAME = os.getenv('LOGIN_USERNAME')
LOGIN_PASSWORD = os.getenv('LOGIN_PASSWORD')
SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_urlsafe(32))
TOKEN_EXPIRY_HOURS = 24

# In-memory token storage (in production, use Redis or database)
active_tokens = {}


# Get server IP address last digit for title
def get_server_ip_last_digit():
	"""Get the last digit of the server's IP address"""
	try:
		# Connect to a remote address to determine local IP
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(("8.8.8.8", 80))
		ip = s.getsockname()[0]
		s.close()
		# Extract last digit from IP address
		last_digit = ip.split('.')[-1]
		return last_digit
	except Exception:
		# Fallback if unable to get IP
		return "?"

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
		'qry_dt': datetime.now().strftime('%Y%m%d'),  # 조회일자 (오늘 날짜)
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

def call_sell_order(MY_ACCESS_TOKEN, market, stk_cd, stk_nm, indv, sell_cond):
	trde_able_qty = indv.get("trde_able_qty", "0")
	rmnd_qty = indv.get('rmnd_qty', "0")
	pur_pric_str = indv.get('pur_pric', '0')
	pur_pric = float(pur_pric_str) if pur_pric_str else 0.0

	trde_able_qty_int = int(trde_able_qty) if trde_able_qty else 0
	if trde_able_qty_int == 0:
		return
	if isinstance(trde_able_qty, str) and len(trde_able_qty) > 4:
		trde_able_qty = trde_able_qty[4:]

	ord_uv = 'None'
	if 'price' in sell_cond:
		ord_uv = str(sell_cond['price'])
	if ord_uv == 'None':
		if 'rate' in sell_cond:
			s_rate = sell_cond['rate']
			s_price = pur_pric * (1.0 + s_rate)
			s_price = round_trunc(s_price)
			ord_uv = str(s_price)

	if ord_uv == 'None': # price is not calculated
		return

	trde_tp = '0'  # 매매구분 0:보통 , 3:시장가 , 5:조건부지정가 , 81:장마감후시간외 , 61:장시작전시간외, 62:시간외단일가 , 6:최유리지정가 , 7:최우선지정가 , 10:보통(IOC) , 13:시장가(IOC) , 16:최유리(IOC) , 20:보통(FOK) , 23:시장가(FOK) , 26:최유리(FOK) , 28:스톱지정가,29:중간가,30:중간가(IOC),31:중간가(FOK)
	ret_status = sell_order(MY_ACCESS_TOKEN, dmst_stex_tp=market, stk_cd=stk_cd,
	                        ord_qty=trde_able_qty, ord_uv=ord_uv, trde_tp=trde_tp, cond_uv='')
	print('sell_order_result')
	print(ret_status)
	if isinstance(ret_status, dict):
		rcde = ret_status.get('return_code')
		rmsg = ret_status.get('return_msg', '')
		if rmsg and len(rmsg) > 13:
			code = rmsg[7:13]
			if code == '507615':
				not_nxt_cd[stk_cd] = True
		print(rcde)
	print('call_sell_order:{}'.format(stk_nm))


def sell_jango(now, jango, market):
	global auto_sell_enabled
	if not auto_sell_enabled:
		return

	for j in jango:
		try:
			MY_ACCESS_TOKEN = j.get('MY_ACCESS_TOKEN')

			acnt_evlt_remn_indv_tot = j.get("acnt_evlt_remn_indv_tot", [])

			for indv in acnt_evlt_remn_indv_tot:
				stk_cd = indv.get('stk_cd', '')
				stk_nm = indv.get('stk_nm', '')
				if stk_cd and len(stk_cd) > 0 and stk_cd[0] == 'A':
					stk_cd = stk_cd[1:]
					
				if stk_cd in not_nxt_cd and market == 'NXT':
					continue
					
				if stk_cd not in sell_prices:
					continue

				sell_cond = sell_prices[stk_cd]
				call_sell_order(MY_ACCESS_TOKEN, market, stk_cd, stk_nm, indv, sell_cond)
		except Exception as ex:
			print('at 314')
			print(ex)
			exit()
	pass

import requests
import json

log_miche = False

# 미체결요청
def fn_ka10075(token, data, cont_yn='N', next_key=''):
	global log_miche

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
	if log_miche:
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
def fn_kt10003(now, token, data, cont_yn='N', next_key=''):
	print("{} cancel order begin fn_kt10003".format(now))
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
	print("{} cancel order end fn_kt10003".format(now))

	return response.json()

def cancel_order_main(now, access_token, stex, ord_no, stk_cd):
	print('cancel_order_main: ord_no={}'.format(ord_no))
	# 2. 요청 데이터
	params = {
		'dmst_stex_tp': stex, # 'KRX',  # 국내거래소구분 KRX,NXT,SOR
		'orig_ord_no': ord_no,  # 주문번호 (using ord_no as orig_ord_no for cancellation)
		'stk_cd': stk_cd,  # 종목코드
		'cncl_qty': '0',  # 취소수량 '0' 입력시 잔량 전부 취소
	}

	# 3. API 실행
	return fn_kt10003(now, token=access_token, data=params)


# next-key, cont-yn 값이 있을 경우
# fn_kt10003(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')

day_start_time = time(6, 0)  # 07:00
nxt_start_time = time(7, 59)  # 07:00
nxt_end_time = time(8, 49)  # 07:00
krx_start_time = time(8,55)
krx_end_time = time(15,30)
new_day = True
nxt_cancelled = False
krx_first = False
not_nxt_cd = {}

def cur_date():
	# Get today's date
	today = date.today()

	# Format the date as YYYYMMDD
	formatted_date = today.strftime("%Y%m%d")

	# Print the formatted date
	return formatted_date

current_status = ''

def daily_work(now):
	global new_day, krx_first, current_status
	global nxt_start_time, nxt_end_time, krx_start_time,nxt_cancelled, krx_end_time
	stored_jango_data = get_jango()
	if is_between(now, nxt_start_time, nxt_end_time):
		current_status = 'NXT'
		sell_jango(now, stored_jango_data, 'NXT')
	elif is_between(now, nxt_end_time, krx_start_time):
		current_status = 'NXT->KRX'
		if not nxt_cancelled:
			nxt_cancelled = True
			cancel_nxt_trade(now)
	elif is_between(now, krx_start_time, krx_end_time):
		current_status = 'KRX'
		if not krx_first:
			print('{} krx_first get_jango and sell_jango.'.format(now))
			krx_first = True
		sell_jango(now, stored_jango_data, 'KRX')
	else:
		if (new_day):
			current_status = 'OFF'
			new_day = False
			print('{} {} Setting new day=False'.format(cur_date(), now))


def set_new_day():
	global new_day, waiting_shown, no_working_shown, nxt_cancelled, ktx_first, current_status

	if new_day:
		return
	now = datetime.now().time()
	print('{} {} Setting new day=True'.format(cur_date(), now))
	new_day = True
	waiting_shown = False
	no_working_shown = False
	nxt_cancelled = False
	ktx_first = False
	current_status = 'NEW'
	not_nxt_cd = {}

SELL_PRICES_FILE = 'sell_price_rate.json'
sell_prices = {}

# Global flag for auto sell
auto_sell_enabled = True

def load_dictionaries_from_json():
	"""Load sell_prices and profit_rate from JSON files"""
	global sell_prices

	# Load sell_prices
	if os.path.exists(SELL_PRICES_FILE):
		try:
			with open(SELL_PRICES_FILE, 'r', encoding='utf-8') as f:
				sell_prices = json.load(f)
			print(f"Loaded sell_prices from {SELL_PRICES_FILE}: {sell_prices}")
		except Exception as e:
			print(f"Error loading sell_prices: {e}")
			sell_prices = {}
	else:
		sell_prices = {}
		print(f"Created new sell_prices dictionary")

def save_dictionaries_to_json():
	"""Save sell_prices to JSON file"""
	global sell_prices
	try:
		with open(SELL_PRICES_FILE, 'w', encoding='utf-8') as f:
			json.dump(sell_prices, f, indent=2, ensure_ascii=False)
		print(f"Saved sell_prices to {SELL_PRICES_FILE}")
		return True
	except Exception as e:
		print(f"Error saving sell_prices: {e}")
		return False



# Global variable for tracking previous hour
prev_hour = None
# Global storage for jango data (updated by timer handler)
stored_jango_data = []
# Background thread for periodic timer handler
background_thread = None
thread_stop_event = threading.Event()

def background_timer_thread():
	"""Background thread that calls periodic_timer_handler every 3 seconds"""
	global thread_stop_event
	while not thread_stop_event.is_set():
		try:
			periodic_timer_handler()
		except Exception as e:
			print(f"Error in periodic_timer_handler: {e}")

		# Sleep for 3 seconds, but check stop event periodically
		for _ in range(20):  # Check every 0.1 seconds for 3 seconds total
			if thread_stop_event.is_set():
				break
			time_module.sleep(0.1)

@asynccontextmanager
async def lifespan(app: FastAPI):
	"""Lifespan event handler for startup and shutdown"""
	global stored_jango_data, background_thread, thread_stop_event

	# Startup
	print("Starting application...")
	try:
		load_dictionaries_from_json()
		print("Dictionaries loaded successfully")
	except Exception as e:
		print(f"Error loading dictionaries: {e}")

	# Initialize stored jango data by calling once immediately (non-blocking, allow failure)
	print("Initializing jango data...")
	try:
		stored_jango_data = get_jango('KRX')
		print("KRX jango data initialized")
	except Exception as e:
		print(f"Error initializing KRX jango data: {e}")
		stored_jango_data = []
	
	try:
		stored_jango_data = get_jango('NXT')
		print("NXT jango data initialized")
	except Exception as e:
		print(f"Error initializing NXT jango data: {e}")
		stored_jango_data = []
	
	# Start background thread for periodic timer handler
	print("Starting background timer thread...")
	try:
		thread_stop_event.clear()
		background_thread = threading.Thread(
			target=background_timer_thread,
			daemon=False,  # Non-daemon thread for better debug mode support
			name="PeriodicTimerThread"
		)
		background_thread.start()
		print("Background timer thread started successfully")
	except Exception as e:
		print(f"Error starting background timer thread: {e}")
		# Don't raise - allow app to start even if thread fails
	
	print("Application startup complete")
	yield
	
	# Shutdown
	print("Shutting down application...")
	try:
		if background_thread and background_thread.is_alive():
			print("Stopping background timer thread...")
			thread_stop_event.set()
			background_thread.join(timeout=5.0)  # Wait up to 5 seconds for thread to finish
			if background_thread.is_alive():
				print("Warning: Background thread did not stop within timeout")
			else:
				print("Background timer thread stopped successfully")
	except Exception as e:
		print(f"Error stopping background timer thread: {e}")
	print("Application shutdown complete")

# FastAPI app
app = FastAPI(lifespan=lifespan)

def periodic_timer_handler():
	"""Periodic timer event handler that runs the trading loop logic"""
	global prev_hour, new_day, stored_jango_data
	
	now = datetime.now().time()
	now_hour = now.hour
	if prev_hour is not None and now_hour != prev_hour:
		print('{} Hour change from {} to {}'.format(cur_date(), prev_hour, now_hour))
	prev_hour = now_hour

	if is_between(now, day_start_time, nxt_start_time):
		set_new_day()
	elif new_day:
		try:
			daily_work(now)
		except Exception as ex:
			new_day = False
			print(ex)
			print('{} {} Setting new_day False due to Exception.'.format(cur_date(), now))

def format_account_data():
	"""Format account data for display in UI"""
	global stored_jango_data
	try:
		# Determine which market is active based on current time
		now = datetime.now().time()

		# Get holdings from stored data for active market only
		all_jango = stored_jango_data

		formatted_data = []
		seen_keys = set()  # Track unique combinations of account and stock_code
		
		for account in all_jango:
			if account.get("return_code") != 0:
				continue
			
			acct_no = account.get('ACCT', '')
			acnt_evlt_remn_indv_tot = account.get("acnt_evlt_remn_indv_tot", [])
			
			for stock in acnt_evlt_remn_indv_tot:
				stk_cd = stock.get('stk_cd', '')
				# Remove 'A' prefix if present
				if stk_cd and stk_cd[0] == 'A':
					stk_cd_clean = stk_cd[1:]
				else:
					stk_cd_clean = stk_cd
				
				stk_nm = stock.get('stk_nm', '')
				trde_able_qty = stock.get('trde_able_qty', '0')
				# Remove leading zeros from trde_able_qty
				try:
					if trde_able_qty and len(trde_able_qty) > 4:
						trde_able_qty = str(int(trde_able_qty[4:].lstrip('0') or '0'))
					else:
						trde_able_qty = str(int(trde_able_qty.lstrip('0') or '0'))
				except:
					trde_able_qty = '0'
				
				rmnd_qty = stock.get('rmnd_qty', '0')
				# Remove leading zeros from rmnd_qty
				try:
					if rmnd_qty and len(rmnd_qty) > 4:
						rmnd_qty = str(int(rmnd_qty[4:].lstrip('0') or '0'))
					else:
						rmnd_qty = str(int(rmnd_qty.lstrip('0') or '0'))
				except:
					rmnd_qty = '0'
				
				pur_pric = stock.get('pur_pric', '0')
				pur_pric_float = float(pur_pric) if pur_pric else 0.0
				
				prft_rt = stock.get('prft_rt', '0')
				prft_rt_float = float(prft_rt) if prft_rt else 0.0
				
				# Get preset sell price from sell_prices dictionary
				price_part = 'None'
				rate_part = 'None'
				
				if stk_cd_clean in sell_prices:
					sell_cond = sell_prices[stk_cd_clean]
					
					if 'price' in sell_cond:
						try:
							price_val = sell_cond['price']
							if price_val and str(price_val).strip() and str(price_val) != 'None':
								price_part = f"{float(price_val):.0f}"
						except (ValueError, TypeError):
							pass
					
					if 'rate' in sell_cond:
						try:
							rate_val = sell_cond['rate']
							if rate_val is not None and str(rate_val).strip() and str(rate_val) != 'None':
								rate_part = f"{float(rate_val)*100:+.2f}%"
						except (ValueError, TypeError):
							pass
					
					# Update stock name in sell_prices if available
					if stk_nm and stk_nm.strip():
						sell_prices[stk_cd_clean]['stock_name'] = stk_nm
				else:
					# Create entry with stock name if stock exists but no sell price entry
					if stk_nm and stk_nm.strip():
						sell_prices[stk_cd_clean] = {'stock_name': stk_nm}
				
				preset_sell_price = f"{price_part} / {rate_part}"
				
				# Create unique key from account and stock_code
				unique_key = f"{acct_no}_{stk_cd_clean}"
				
				# Only add if not already seen (deduplicate by account and stock_code)
				if unique_key not in seen_keys:
					seen_keys.add(unique_key)
					formatted_data.append({
						'account': acct_no,
						'stock_code': stk_cd_clean,
						'stock_name': stk_nm,
						'tradeable_qty': trde_able_qty,
						'rmnd_qty': rmnd_qty,
						'avg_buy_price': f"{pur_pric_float:,.0f}" if pur_pric_float > 0 else '-',
						'profit_rate': f"{prft_rt_float:+.2f}%",
						'preset_sell_price': preset_sell_price
					})
		
		return formatted_data
	except Exception as e:
		print(f"Error formatting account data: {e}")
		return []


# Authentication functions
def create_token() -> str:
	"""Create a new authentication token"""
	token = secrets.token_urlsafe(32)
	expiry = datetime.now() + timedelta(hours=TOKEN_EXPIRY_HOURS)
	active_tokens[token] = {
		'expiry': expiry,
		'created': datetime.now()
	}
	return token

def verify_token(token: str) -> bool:
	"""Verify if a token is valid"""
	if not token or token not in active_tokens:
		return False
	
	token_data = active_tokens[token]
	if datetime.now() > token_data['expiry']:
		# Token expired, remove it
		del active_tokens[token]
		return False
	
	return True

def cleanup_expired_tokens():
	"""Remove expired tokens from memory"""
	now = datetime.now()
	expired_tokens = [token for token, data in active_tokens.items() if now > data['expiry']]
	for token in expired_tokens:
		del active_tokens[token]

async def get_current_user(token: str = Cookie(None)):
	"""Dependency to get current authenticated user"""
	if not token:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated",
			headers={"WWW-Authenticate": "Bearer"},
		)
	
	if not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid or expired token",
			headers={"WWW-Authenticate": "Bearer"},
		)
	
	return {"authenticated": True}


# Login page
@app.get("/login", response_class=HTMLResponse)
@app.get("/login/", response_class=HTMLResponse)
@app.get("/stock/login", response_class=HTMLResponse)
@app.get("/stock/login/", response_class=HTMLResponse)
async def login_page():
	"""Display login page"""
	ip_suffix = get_server_ip_last_digit()
	html_content = """
	<!DOCTYPE html>
	<html lang="ko">
	<head>
		<meta charset="UTF-8">
		<meta name="viewport" content="width=device-width, initial-scale=1.0">
		<title>Login - """ + ip_suffix + """</title>
		<style>
			* {
				margin: 0;
				padding: 0;
				box-sizing: border-box;
			}
			body {
				font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
				background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
				display: flex;
				justify-content: center;
				align-items: center;
				min-height: 100vh;
				padding: 20px;
			}
			.login-container {
				background: white;
				border-radius: 12px;
				box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
				padding: 40px;
				width: 100%;
				max-width: 400px;
			}
			h1 {
				color: #333;
				margin-bottom: 30px;
				text-align: center;
				font-size: 28px;
			}
			.form-group {
				margin-bottom: 20px;
			}
			label {
				display: block;
				margin-bottom: 8px;
				color: #555;
				font-weight: 500;
			}
			input[type="text"],
			input[type="password"] {
				width: 100%;
				padding: 12px;
				border: 2px solid #e0e0e0;
				border-radius: 6px;
				font-size: 16px;
				transition: border-color 0.3s;
			}
			input[type="text"]:focus,
			input[type="password"]:focus {
				outline: none;
				border-color: #667eea;
			}
			.btn-login {
				width: 100%;
				padding: 12px;
				background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
				color: white;
				border: none;
				border-radius: 6px;
				font-size: 16px;
				font-weight: 600;
				cursor: pointer;
				transition: transform 0.2s, box-shadow 0.2s;
			}
			.btn-login:hover {
				transform: translateY(-2px);
				box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
			}
			.btn-login:active {
				transform: translateY(0);
			}
			.error-message {
				background: #fee;
				color: #c33;
				padding: 12px;
				border-radius: 6px;
				margin-bottom: 20px;
				display: none;
			}
			.error-message.show {
				display: block;
			}
		</style>
	</head>
	<body>
		<div class="login-container">
			<h1>🔐 Login</h1>
			<div id="error-message" class="error-message"></div>
			<form id="login-form">
				<div class="form-group">
					<label for="username">Username</label>
					<input type="text" id="username" name="username" required autocomplete="username">
				</div>
				<div class="form-group">
					<label for="password">Password</label>
					<input type="password" id="password" name="password" required autocomplete="current-password">
				</div>
				<button type="submit" class="btn-login">Login</button>
			</form>
		</div>
		<script>
			document.getElementById('login-form').addEventListener('submit', async function(e) {
				e.preventDefault();
				const username = document.getElementById('username').value;
				const password = document.getElementById('password').value;
				const errorDiv = document.getElementById('error-message');
				
				try {
					const response = await fetch('./api/login', {
						method: 'POST',
						headers: {
							'Content-Type': 'application/json',
						},
						body: JSON.stringify({ username: username, password: password })
					});
					
					const result = await response.json();
					
					if (result.status === 'success') {
						// Set cookie and redirect
						document.cookie = `token=${result.token}; path=/; max-age=${24 * 60 * 60}`;
						// Determine redirect path based on current location
						const currentPath = window.location.pathname;
						if (currentPath.includes('/stock/login')) {
							window.location.href = '/stock';
						} else {
							window.location.href = '/stock';
						}
					} else {
						errorDiv.textContent = result.message || 'Login failed';
						errorDiv.classList.add('show');
					}
				} catch (error) {
					errorDiv.textContent = 'Error: ' + error.message;
					errorDiv.classList.add('show');
				}
			});
		</script>
	</body>
	</html>
	"""
	return HTMLResponse(content=html_content)

# Login API endpoint
@app.post("/api/login")
@app.post("/{proxy_path:path}/api/login")
async def login(request: dict, proxy_path: str = ""):
	"""Handle login and issue token"""
	cleanup_expired_tokens()
	
	username = request.get('username', '')
	password = request.get('password', '')
	
	if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
		token = create_token()
		return {
			"status": "success",
			"message": "Login successful",
			"token": token
		}
	else:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid username or password"
		)

# Logout endpoint
@app.post("/api/logout")
@app.post("/{proxy_path:path}/api/logout")
async def logout(token: str = Cookie(None)):
	"""Handle logout by invalidating token"""
	if token and token in active_tokens:
		del active_tokens[token]
	response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
	response.delete_cookie(key="token", path="/")
	return {"status": "success", "message": "Logged out successfully"}

# Root redirect to login
@app.get("/")
async def root_redirect():
	"""Redirect root to login"""
	return RedirectResponse(url="./login", status_code=status.HTTP_302_FOUND)

@app.get("/stock", response_class=HTMLResponse)
@app.get("/stock/", response_class=HTMLResponse)
async def root(token: str = Cookie(None)):
	"""Display account information UI"""
	# Check authentication
	if not token or not verify_token(token):
		# Redirect to login - use /stock/login if accessed through proxy
		return RedirectResponse(url="/stock/login", status_code=status.HTTP_302_FOUND)
	
	account_data = format_account_data()
	ip_suffix = get_server_ip_last_digit()
	
	html_content = """
	<!DOCTYPE html>
	<html lang="ko">
	<head>
		<meta charset="UTF-8">
		<meta name="viewport" content="width=device-width, initial-scale=1.0">
		<title>Account Holdings - """ + ip_suffix + """</title>
		<style>
			* {
				margin: 0;
				padding: 0;
				box-sizing: border-box;
			}
			body {
				font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
				background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
				padding: 20px;
				min-height: 100vh;
			}
			.container {
				max-width: 1400px;
				margin: 0 auto;
				background: white;
				border-radius: 12px;
				box-shadow: 0 10px 40px rgba(0,0,0,0.2);
				overflow: hidden;
			}
			.header {
				background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
				color: white;
				padding: 30px;
				text-align: center;
			}
			.header h1 {
				font-size: 2.5em;
				margin-bottom: 10px;
			}
			.header p {
				font-size: 1.1em;
				opacity: 0.9;
			}
			.table-container {
				padding: 30px;
				overflow-x: auto;
			}
			table {
				width: 100%;
				border-collapse: collapse;
				font-size: 14px;
			}
			thead {
				background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
				color: white;
			}
			th {
				padding: 15px;
				text-align: left;
				font-weight: 600;
				text-transform: uppercase;
				letter-spacing: 0.5px;
				font-size: 12px;
			}
			td {
				padding: 15px;
				border-bottom: 1px solid #e0e0e0;
			}
			tbody tr {
				transition: background-color 0.2s;
			}
			tbody tr {
				cursor: pointer;
			}
			tbody tr:hover {
				background-color: #f5f5f5;
			}
			tbody tr.selected {
				background-color: #e3f2fd;
				border-left: 4px solid #667eea;
			}
			tbody tr.selected:hover {
				background-color: #bbdefb;
			}
			tbody tr:last-child td {
				border-bottom: none;
			}
			.profit-positive {
				color: #e74c3c;
				font-weight: 600;
			}
			.profit-negative {
				color: #3498db;
				font-weight: 600;
			}
			.profit-zero {
				color: #7f8c8d;
			}
			.refresh-btn {
				position: fixed;
				bottom: 30px;
				right: 30px;
				background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
				color: white;
				border: none;
				padding: 15px 30px;
				border-radius: 50px;
				cursor: pointer;
				font-size: 16px;
				box-shadow: 0 4px 15px rgba(0,0,0,0.2);
				transition: transform 0.2s;
			}
			.refresh-btn:hover {
				transform: scale(1.05);
			}
			.empty-state {
				text-align: center;
				padding: 60px 20px;
				color: #7f8c8d;
			}
			.empty-state h2 {
				font-size: 2em;
				margin-bottom: 10px;
			}
			.update-section {
				padding: 30px;
				background: #f8f9fa;
				border-top: 1px solid #e0e0e0;
			}
			.update-section h2 {
				margin-bottom: 20px;
				color: #333;
			}
			.update-form {
				display: flex;
				gap: 15px;
				align-items: flex-end;
				flex-wrap: wrap;
				margin-bottom: 15px;
			}
			.form-group {
				display: flex;
				flex-direction: column;
				gap: 5px;
			}
			.form-group label {
				font-size: 12px;
				font-weight: 600;
				color: #555;
			}
			.form-group input {
				padding: 10px;
				border: 1px solid #ddd;
				border-radius: 4px;
				font-size: 14px;
			}
			.form-group input:focus {
				outline: none;
				border-color: #667eea;
			}
			.btn-update {
				background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
				color: white;
				border: none;
				padding: 10px 20px;
				border-radius: 4px;
				cursor: pointer;
				font-size: 14px;
				font-weight: 600;
			}
			.btn-update:hover {
				opacity: 0.9;
			}
			.btn-delete {
				background: #e74c3c;
				color: white;
				border: none;
				padding: 10px 20px;
				border-radius: 4px;
				cursor: pointer;
				font-size: 14px;
				font-weight: 600;
			}
			.btn-delete:hover {
				opacity: 0.9;
			}
			.btn-logout {
				background: #6c757d;
				color: white;
				border: none;
				padding: 10px 20px;
				border-radius: 4px;
				cursor: pointer;
				font-size: 14px;
				font-weight: 600;
				margin-left: auto;
			}
			.btn-logout:hover {
				opacity: 0.9;
			}
			.btn-auto-sell {
				background: #27ae60;
				color: white;
				border: none;
				padding: 10px 20px;
				border-radius: 4px;
				cursor: pointer;
				font-size: 14px;
				font-weight: 600;
				margin-left: auto;
				margin-right: 10px;
			}
			.btn-auto-sell:hover {
				opacity: 0.9;
			}
			.btn-auto-sell.disabled {
				background: #95a5a6;
			}
			.update-form-header {
				display: flex;
				justify-content: space-between;
				align-items: center;
				width: 100%;
				margin-bottom: 15px;
			}
			.update-form-content {
				display: flex;
				gap: 15px;
				align-items: flex-end;
				flex-wrap: wrap;
				flex: 1;
			}
			.message {
				padding: 10px;
				margin-top: 10px;
				border-radius: 4px;
				display: none;
			}
			.message.success {
				background: #d4edda;
				color: #155724;
				border: 1px solid #c3e6cb;
			}
			.message.error {
				background: #f8d7da;
				color: #721c24;
				border: 1px solid #f5c6cb;
			}
			.account-group {
				margin-bottom: 40px;
			}
			.account-group-header {
				background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
				color: white;
				padding: 15px 20px;
				border-radius: 8px 8px 0 0;
				font-size: 1.3em;
				font-weight: 600;
				margin-bottom: 0;
			}
			.account-group-header h2 {
				margin: 0;
				font-size: 1.2em;
			}
			.account-group table {
				border-radius: 0 0 8px 8px;
				overflow: hidden;
			}
			.account-group table thead {
				background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
			}
			.miche-section {
				margin-top: 40px;
				padding-top: 30px;
				border-top: 2px solid #e0e0e0;
			}
			.miche-section h2 {
				color: #333;
				margin-bottom: 20px;
				font-size: 1.5em;
			}
			.btn-cancel {
				background: #e74c3c;
				color: white;
				border: none;
				padding: 6px 12px;
				border-radius: 4px;
				cursor: pointer;
				font-size: 12px;
				font-weight: 600;
				transition: background-color 0.2s;
			}
			.btn-cancel:hover {
				background: #c0392b;
			}
			.btn-cancel:disabled {
				background: #95a5a6;
				cursor: not-allowed;
			}
		</style>
	</head>
	<body>
		<div class="container">
			<div class="header">
				<h1 id="headline-time">📊 Account -</h1>
				<p>Stock Holdings and Trading Information</p>
			</div>
			<div class="table-container" id="table-container">
				<div class="empty-state">
					<h2>Loading...</h2>
					<p>Loading account holdings...</p>
				</div>
			</div>
			<div class="miche-section" id="miche-section" style="display: none;">
				<h2>📋 Unexecuted Orders (미체결)</h2>
				<div id="miche-container">
					<div class="empty-state">
						<h2>Loading...</h2>
						<p>Loading unexecuted orders...</p>
					</div>
				</div>
			</div>
	"""
	
	html_content += """
			</div>
			<div class="update-section" id="update-section">
				<div class="update-form">
					<div class="update-form-header">
						<div class="update-form-content">
							<div class="form-group">
								<label for="stock-name-display">Stock Name</label>
								<input type="text" id="stock-name-display" readonly style="background-color: #f5f5f5; cursor: not-allowed;" />
							</div>
							<div class="form-group">
								<label for="stock-code-input">Stock Code</label>
								<input type="text" id="stock-code-input" placeholder="e.g., 005930" />
							</div>
							<div class="form-group">
								<label for="sell-price-input">Sell Price (Fixed)</label>
								<input type="number" id="sell-price-input" placeholder="Leave empty for rate" />
							</div>
							<div class="form-group">
								<label for="profit-rate-input">Profit Rate (%)</label>
								<input type="number" step="0.01" id="profit-rate-input" placeholder="e.g., 5.5 for 5.5%" />
							</div>
							<button class="btn-update" onclick="updateSellPrice()">Update</button>
							<button class="btn-delete" onclick="deleteSellPrice()">Delete</button>
						</div>
						<button class="btn-auto-sell" id="btn-auto-sell" onclick="toggleAutoSell()">Auto Sell: OFF</button>
						<button class="btn-logout" onclick="logout()">🚪 Logout</button>
					</div>
				</div>
				<div id="update-message" class="message"></div>
			</div>
		</div>
		<button class="refresh-btn" onclick="updateTable()">🔄 Refresh</button>
		<script>
		// Add event listeners for mutual exclusivity between price and rate
		document.addEventListener('DOMContentLoaded', function() {
			const sellPriceInput = document.getElementById('sell-price-input');
			const profitRateInput = document.getElementById('profit-rate-input');
			
			// When price is entered, clear rate
			if (sellPriceInput) {
				sellPriceInput.addEventListener('input', function() {
					if (this.value.trim() !== '') {
						profitRateInput.value = '';
					}
				});
			}
			
			// When rate is entered, clear price
			if (profitRateInput) {
				profitRateInput.addEventListener('input', function() {
					if (this.value.trim() !== '') {
						sellPriceInput.value = '';
					}
				});
			}
		});
		
		function getProfitClass(profitRate) {
			const profitValue = parseFloat(profitRate.replace('%', '').replace('+', ''));
			if (profitValue > 0) return 'profit-positive';
			if (profitValue < 0) return 'profit-negative';
			return 'profit-zero';
		}
		
		function createRow(item) {
			const rowId = item.account + '_' + item.stock_code;
			const profitClass = getProfitClass(item.profit_rate);
			const rmndQty = item.rmnd_qty || '0';
			return `
				<tr data-row-id="${rowId}" data-stock-code="${item.stock_code}" data-stock-name="${item.stock_name}" data-preset-price="${item.preset_sell_price}" onclick="selectRow(this)">
					<td>${item.account}</td>
					<td><strong>${item.stock_code}</strong></td>
					<td>${item.stock_name}</td>
					<td>${item.tradeable_qty} / ${rmndQty}</td>
					<td>${item.avg_buy_price}</td>
					<td class="${profitClass}">${item.profit_rate}</td>
					<td>${item.preset_sell_price}</td>
				</tr>
			`;
		}
		
		function selectRow(rowElement) {
			// Remove selected class from all rows
			document.querySelectorAll('tbody tr').forEach(tr => {
				tr.classList.remove('selected');
			});
			
			// Add selected class to clicked row
			rowElement.classList.add('selected');
			
			// Get stock code, stock name, and preset price from row
			const stockCode = rowElement.getAttribute('data-stock-code');
			const stockName = rowElement.getAttribute('data-stock-name') || '';
			const presetPrice = rowElement.getAttribute('data-preset-price') || '-';
			
			// Fill stock name (read-only)
			document.getElementById('stock-name-display').value = stockName;
			
			// Fill stock code input
			document.getElementById('stock-code-input').value = stockCode;
			
			// Parse preset price (format: "price / rate%" or "None / rate%" or "price / None")
			if (presetPrice === '-') {
				// No preset price, clear inputs
				document.getElementById('sell-price-input').value = '';
				document.getElementById('profit-rate-input').value = '';
			} else {
				// Check if it contains a slash (has both price and rate)
				const slashMatch = presetPrice.match(/^(.+?)\s*\/\s*(.+)$/);
				if (slashMatch) {
					// Format: "price / rate%" or "None / rate%" or "price / None"
					const pricePart = slashMatch[1].trim();
					const ratePart = slashMatch[2].trim();
					
					// Parse price
					if (pricePart === 'None') {
						document.getElementById('sell-price-input').value = '';
					} else {
						const priceValue = pricePart.replace(/[^\d.]/g, '');
						document.getElementById('sell-price-input').value = priceValue;
					}
					
					// Parse rate
					if (ratePart === 'None') {
						document.getElementById('profit-rate-input').value = '';
					} else {
						const rateMatch = ratePart.match(/([\d.+-]+)%/);
						if (rateMatch) {
							const ratePercent = parseFloat(rateMatch[1]);
							document.getElementById('profit-rate-input').value = ratePercent.toFixed(2);
						}
					}
				} else {
					// Fallback: try to parse as single value (for backward compatibility)
					const rateMatch = presetPrice.match(/([\d.+-]+)%/);
					if (rateMatch) {
						const ratePercent = parseFloat(rateMatch[1]);
						document.getElementById('profit-rate-input').value = ratePercent.toFixed(2);
						document.getElementById('sell-price-input').value = '';
					} else {
						const priceValue = presetPrice.replace(/[^\d.]/g, '');
						if (priceValue) {
							document.getElementById('sell-price-input').value = priceValue;
							document.getElementById('profit-rate-input').value = '';
						}
					}
				}
			}
			
			// Scroll to update section
			document.getElementById('update-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
		}
		
		function updateTable() {
			fetch('./api/account-data')
				.then(response => response.json())
				.then(result => {
					if (result.status === 'success') {
						// Update headline with timestamp and status
						if (result.timestamp) {
							const headlineTime = document.getElementById('headline-time');
							if (headlineTime) {
								let headlineText = '📊 Account ' + result.timestamp;
								if (result.current_status) {
									headlineText += ' (' + result.current_status + ')';
								}
								headlineTime.textContent = headlineText;
							}
						}
						const data = result.data || [];
						const tableContainer = document.getElementById('table-container');
						
						// Group data by account on the frontend
						const accountGroups = {};
						for (const item of data) {
							const acctNo = item.account || '';
							if (!accountGroups[acctNo]) {
								accountGroups[acctNo] = [];
							}
							accountGroups[acctNo].push(item);
						}
						
						// Check if we have any data
						const hasData = Object.keys(accountGroups).length > 0 && 
							Object.values(accountGroups).some(stocks => stocks && stocks.length > 0);
						
						if (!hasData) {
							tableContainer.innerHTML = `
								<div class="empty-state">
									<h2>No Holdings Found</h2>
									<p>No account holdings are currently available.</p>
								</div>
							`;
							return;
						}
						
						// Build HTML for grouped accounts
						let htmlContent = '';
						const sortedAccounts = Object.keys(accountGroups).sort();
						
						for (const acctNo of sortedAccounts) {
							const stocks = accountGroups[acctNo] || [];
							if (stocks.length === 0) continue;
							
							htmlContent += `
								<div class="account-group">
									<div class="account-group-header">
										<h2>Account: ${acctNo}</h2>
									</div>
									<table>
										<thead>
											<tr>
												<th>Stock Code</th>
												<th>Stock Name</th>
												<th>Tradeable Qty</th>
												<th>Avg Buy Price</th>
												<th>Profit Rate</th>
												<th>Preset Sell Price</th>
											</tr>
										</thead>
										<tbody>
							`;
							
							for (const item of stocks) {
								const rowId = item.account + '_' + item.stock_code;
								const profitClass = getProfitClass(item.profit_rate);
								const rmndQty = item.rmnd_qty || '0';
								
								htmlContent += `
									<tr data-row-id="${rowId}" data-stock-code="${item.stock_code}" data-stock-name="${item.stock_name}" data-preset-price="${item.preset_sell_price}" onclick="selectRow(this)">
										<td><strong>${item.stock_code}</strong></td>
										<td>${item.stock_name}</td>
										<td>${item.tradeable_qty} / ${rmndQty}</td>
										<td>${item.avg_buy_price}</td>
										<td class="${profitClass}">${item.profit_rate}</td>
										<td>${item.preset_sell_price}</td>
									</tr>
								`;
							}
							
							htmlContent += `
										</tbody>
									</table>
								</div>
							`;
						}
						
						tableContainer.innerHTML = htmlContent;
					}
				})
				.catch(error => {
					console.error('Error updating table:', error);
				});
		}
		
		function updateSellPrice() {
			const stockCode = document.getElementById('stock-code-input').value.trim();
			const stockName = document.getElementById('stock-name-display').value.trim();
			const sellPrice = document.getElementById('sell-price-input').value.trim();
			const profitRate = document.getElementById('profit-rate-input').value.trim();
			
			if (!stockCode) {
				showMessage('Please enter a stock code', 'error');
				return;
			}
			
			const data = {
				stock_code: stockCode,
				stock_name: stockName || null,
				price: sellPrice || null,
				rate: profitRate ? (parseFloat(profitRate) / 100) : null
			};
			
			fetch('./api/sell-prices', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(data)
			})
			.then(response => response.json())
			.then(result => {
				if (result.status === 'success') {
					showMessage('Sell price updated successfully!', 'success');
					document.getElementById('stock-name-display').value = '';
					document.getElementById('stock-code-input').value = '';
					document.getElementById('sell-price-input').value = '';
					document.getElementById('profit-rate-input').value = '';
					setTimeout(updateTable, 500);
				} else {
					showMessage('Error: ' + result.message, 'error');
				}
			})
			.catch(error => {
				showMessage('Error updating sell price: ' + error, 'error');
			});
		}
		
		function logout() {
			fetch('./api/logout', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				}
			})
			.then(response => response.json())
			.then(result => {
				// Clear cookie and redirect to login
				document.cookie = 'token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
				const currentPath = window.location.pathname;
				if (currentPath.includes('/stock')) {
					window.location.href = '/stock/login';
				} else {
					window.location.href = '/login';
				}
			})
			.catch(error => {
				console.error('Logout error:', error);
				// Still redirect even if API call fails
				document.cookie = 'token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
				const currentPath = window.location.pathname;
				if (currentPath.includes('/stock')) {
					window.location.href = '/stock/login';
				} else {
					window.location.href = '/login';
				}
			});
		}
		
		function logout() {
			fetch('./api/logout', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				}
			})
			.then(response => response.json())
			.then(result => {
				// Clear cookie and redirect to login
				document.cookie = 'token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
				const currentPath = window.location.pathname;
				if (currentPath.includes('/stock')) {
					window.location.href = '/stock/login';
				} else {
					window.location.href = '/login';
				}
			})
			.catch(error => {
				console.error('Logout error:', error);
				// Still redirect even if API call fails
				document.cookie = 'token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
				const currentPath = window.location.pathname;
				if (currentPath.includes('/stock')) {
					window.location.href = '/stock/login';
				} else {
					window.location.href = '/login';
				}
			});
		}
		
		function deleteSellPrice() {
			const stockCode = document.getElementById('stock-code-input').value.trim();
			const stockName = document.getElementById('stock-name-display').value.trim();
			
			if (!stockCode) {
				showMessage('Please enter a stock code', 'error');
				return;
			}
			
			const data = {
				stock_code: stockCode,
				stock_name: stockName || null,
				price: null,
				rate: null
			};
			
			fetch('./api/sell-prices', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(data)
			})
			.then(response => response.json())
			.then(result => {
				if (result.status === 'success') {
					showMessage('Sell price deleted successfully!', 'success');
					document.getElementById('stock-name-display').value = '';
					document.getElementById('stock-code-input').value = '';
					document.getElementById('sell-price-input').value = '';
					document.getElementById('profit-rate-input').value = '';
					setTimeout(updateTable, 500);
				} else {
					showMessage('Error: ' + result.message, 'error');
				}
			})
			.catch(error => {
				showMessage('Error deleting sell price: ' + error, 'error');
			});
		}
		
		function showMessage(message, type) {
			const messageDiv = document.getElementById('update-message');
			messageDiv.textContent = message;
			messageDiv.className = 'message ' + type;
			messageDiv.style.display = 'block';
			setTimeout(() => {
				messageDiv.style.display = 'none';
			}, 3000);
		}
		
		function updateMiche() {
			fetch('./api/miche-data')
				.then(response => response.json())
				.then(result => {
					if (result.status === 'success') {
						const micheData = result.data || [];
						const micheContainer = document.getElementById('miche-container');
						const micheSection = document.getElementById('miche-section');
						
						// Group miche data by account
						const accountGroups = {};
						for (const item of micheData) {
							const acctNo = item.ACCT || '';
							if (!accountGroups[acctNo]) {
								accountGroups[acctNo] = [];
							}
							// Extract oso (unexecuted orders) from each account
							if (item.oso && Array.isArray(item.oso)) {
								for (const order of item.oso) {
									// Add ACCT to each order for cancellation
									const orderWithAcct = {
										...order,
										ACCT: acctNo
									};
									accountGroups[acctNo].push(orderWithAcct);
								}
							}
						}
						
						// Check if we have any data
						const hasData = Object.keys(accountGroups).length > 0 && 
							Object.values(accountGroups).some(orders => orders && orders.length > 0);
						
						if (!hasData) {
							micheContainer.innerHTML = `
								<div class="empty-state">
									<h2>No Unexecuted Orders</h2>
									<p>No unexecuted orders are currently available.</p>
								</div>
							`;
							micheSection.style.display = 'none';
							return;
						}
						
						// Show miche section
						micheSection.style.display = 'block';
						
						// Build HTML for grouped miche orders
						let htmlContent = '';
						const sortedAccounts = Object.keys(accountGroups).sort();
						
						for (const acctNo of sortedAccounts) {
							const orders = accountGroups[acctNo] || [];
							if (orders.length === 0) continue;
							
							htmlContent += `
								<div class="account-group">
									<div class="account-group-header">
										<h2>Account: ${acctNo}</h2>
									</div>
									<table>
										<thead>
											<tr>
												<th>Stock Code</th>
												<th>Stock Name</th>
												<th>Order Type</th>
												<th>Order Qty</th>
												<th>Order Price</th>
												<th>Unexecuted Qty</th>
												<th>Current Price</th>
												<th>Exchange</th>
												<th>Time</th>
												<th>Action</th>
											</tr>
										</thead>
										<tbody>
							`;
							
							for (const order of orders) {
								const stkCd = order.stk_cd || '';
								const stkCdClean = stkCd && stkCd[0] === 'A' ? stkCd.substring(1) : stkCd;
								const ordQty = order.ord_qty ? parseInt(order.ord_qty.replace(/^0+/, '') || '0') : 0;
								const osoQty = order.oso_qty ? parseInt(order.oso_qty.replace(/^0+/, '') || '0') : 0;
								const ordPric = order.ord_pric ? parseInt(order.ord_pric.replace(/^0+/, '') || '0') : 0;
								const curPrc = order.cur_prc ? parseInt(order.cur_prc.replace(/^0+/, '') || '0') : 0;
								const ordNo = order.ord_no || '';
								const stexTp = order.stex_tp || '0';
								
								htmlContent += `
									<tr>
										<td><strong>${stkCdClean}</strong></td>
										<td>${order.stk_nm || '-'}</td>
										<td>${order.io_tp_nm || '-'}</td>
										<td>${ordQty.toLocaleString()}</td>
										<td>${ordPric > 0 ? ordPric.toLocaleString() : '-'}</td>
										<td><strong>${osoQty.toLocaleString()}</strong></td>
										<td>${curPrc > 0 ? curPrc.toLocaleString() : '-'}</td>
										<td>${order.stex_tp_txt || order.stex_tp || '-'}</td>
										<td>${order.tm || '-'}</td>
										<td>
											<button class="btn-cancel" 
												data-acct="${order.ACCT || acctNo}"
												data-stex-tp="${stexTp}"
												data-ord-no="${ordNo}"
												data-stk-cd="${stkCd}"
												onclick="cancelOrder(this)">
												Cancel
											</button>
										</td>
									</tr>
								`;
							}
							
							htmlContent += `
										</tbody>
									</table>
								</div>
							`;
						}
						
						micheContainer.innerHTML = htmlContent;
					} else {
						const micheSection = document.getElementById('miche-section');
						micheSection.style.display = 'none';
					}
				})
				.catch(error => {
					console.error('Error updating miche:', error);
					const micheSection = document.getElementById('miche-section');
					micheSection.style.display = 'none';
				});
		}
		
		function cancelOrder(buttonElement) {
			const acct = buttonElement.getAttribute('data-acct');
			const stexTp = buttonElement.getAttribute('data-stex-tp');
			const ordNo = buttonElement.getAttribute('data-ord-no');
			const stkCd = buttonElement.getAttribute('data-stk-cd');
			
			if (!acct || !ordNo || !stkCd) {
				alert('Missing required information to cancel order');
				return;
			}
			
			if (!confirm('Are you sure you want to cancel this order?')) {
				return;
			}
			
			// Disable button during request
			buttonElement.disabled = true;
			buttonElement.textContent = 'Cancelling...';
			
			fetch('./api/cancel-order', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({
					acct: acct,
					stex: stexTp,
					ord_no: ordNo,
					stk_cd: stkCd
				})
			})
			.then(response => response.json())
			.then(result => {
				if (result.status === 'success') {
					alert('Order cancellation requested successfully');
					// Refresh miche data after a short delay
					setTimeout(updateMiche, 1000);
				} else {
					alert('Error cancelling order: ' + (result.message || 'Unknown error'));
					buttonElement.disabled = false;
					buttonElement.textContent = 'Cancel';
				}
			})
			.catch(error => {
				console.error('Error cancelling order:', error);
				alert('Error cancelling order: ' + error.message);
				buttonElement.disabled = false;
				buttonElement.textContent = 'Cancel';
			});
		}
		
		function loadAutoSellStatus() {
			fetch('./api/auto-sell')
				.then(response => response.json())
				.then(result => {
					if (result.status === 'success') {
						updateAutoSellButton(result.enabled);
					}
				})
				.catch(error => {
					console.error('Error loading auto sell status:', error);
				});
		}
		
		function updateAutoSellButton(enabled) {
			const btn = document.getElementById('btn-auto-sell');
			if (btn) {
				if (enabled) {
					btn.textContent = 'Auto Sell: ON';
					btn.classList.remove('disabled');
					btn.style.background = '#27ae60';
				} else {
					btn.textContent = 'Auto Sell: OFF';
					btn.classList.add('disabled');
					btn.style.background = '#95a5a6';
				}
			}
		}
		
		function toggleAutoSell() {
			const btn = document.getElementById('btn-auto-sell');
			const currentState = !btn.classList.contains('disabled');
			const newState = !currentState;
			
			fetch('./api/auto-sell', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({ enabled: newState })
			})
			.then(response => response.json())
			.then(result => {
				if (result.status === 'success') {
					updateAutoSellButton(result.enabled);
					showMessage(result.message || `Auto sell ${result.enabled ? 'enabled' : 'disabled'}`, 'success');
				} else {
					showMessage('Error: ' + (result.message || 'Failed to update auto sell status'), 'error');
				}
			})
			.catch(error => {
				console.error('Error toggling auto sell:', error);
				showMessage('Error toggling auto sell: ' + error.message, 'error');
			});
		}
		
		// Auto-update every 1 second
		setInterval(function() {
			updateTable();
			updateMiche();
		}, 1000);
		
		// Initial update after page load
		updateTable();
		updateMiche();
		loadAutoSellStatus();
		</script>
	</body>
	</html>
	"""
	
	return html_content

@app.get("/api/account-data")
@app.get("/stock/api/account-data")
async def get_account_data_api(proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to get account data as JSON"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	account_data = format_account_data()
	current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	return {"status": "success", "data": account_data, "timestamp": current_time, "current_status": current_status}

@app.get("/api/miche-data")
@app.get("/stock/api/miche-data")
async def get_miche_data_api(proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to get miche (unexecuted orders) data as JSON"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	try:
		miche_data = get_miche()
		current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		return {"status": "success", "data": miche_data, "timestamp": current_time}
	except Exception as e:
		return {"status": "error", "message": str(e)}

@app.post("/api/cancel-order")
@app.post("/stock/api/cancel-order")
async def cancel_order_api(request: dict, proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to cancel an order"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	try:
		acct = request.get('acct')  # Account number
		stex = request.get('stex')  # Exchange type: KRX, NXT, SOR
		ord_no = request.get('ord_no')
		stk_cd = request.get('stk_cd')
		print('cancel_order_api ord_no={}'.format(ord_no))
		if not all([acct, stex, ord_no, stk_cd]):
			return {"status": "error", "message": "Missing required parameters"}
		
		# Validate order number - check if it's not empty or all zeros
		ord_no_clean = ord_no.strip().lstrip('0') if ord_no else ''
		if not ord_no_clean:
			return {"status": "error", "message": "Invalid order number (empty or zeros)"}
		
		# Retrieve token from backend using account number
		key_list = get_key_list()
		access_token = None
		for key in key_list:
			if key['ACCT'] == acct:
				access_token = get_token(key['AK'], key['SK'])
				break
		
		if not access_token:
			return {"status": "error", "message": "Account not found or unable to retrieve token"}
		
		# Remove 'A' prefix from stock code if present
		if stk_cd and stk_cd[0] == 'A':
			stk_cd = stk_cd[1:]
		
		# Map stex_tp to exchange string
		stex_map = {'0': 'KRX', '1': 'KRX', '2': 'NXT'}
		if stex in stex_map:
			stex = stex_map[stex]
		
		now = datetime.now().time()
		cancel_order_main(now, access_token, stex, ord_no, stk_cd)
		
		return {"status": "success", "message": "Order cancellation requested"}
	except Exception as e:
		return {"status": "error", "message": str(e)}

@app.get("/api/sell-prices")
@app.get("/{proxy_path:path}/api/sell-prices")
async def get_sell_prices_api(proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to get sell prices"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	global sell_prices
	current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	return {"status": "success", "data": sell_prices, "timestamp": current_time}

@app.post("/api/sell-prices")
@app.post("/{proxy_path:path}/api/sell-prices")
async def update_sell_prices_api(request: dict, proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to update sell prices"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	global sell_prices
	try:
		stock_code = request.get('stock_code')
		stock_name = request.get('stock_name')
		price = request.get('price')
		rate = request.get('rate')
		
		if not stock_code:
			return {"status": "error", "message": "stock_code is required"}
		
		if stock_code not in sell_prices:
			sell_prices[stock_code] = {}
		
		# Store stock name if provided
		if stock_name and stock_name.strip():
			sell_prices[stock_code]['stock_name'] = stock_name.strip()
		
		# Mutual exclusivity: if price is set, clear rate; if rate is set, clear price
		if price is not None and price != '':
			# Set fixed price and clear rate
			sell_prices[stock_code]['price'] = str(price)
			if 'rate' in sell_prices[stock_code]:
				del sell_prices[stock_code]['rate']
		elif 'price' in sell_prices[stock_code]:
			# Remove price if explicitly set to None/empty
			del sell_prices[stock_code]['price']
		
		if rate is not None and rate != '':
			# Set profit rate and clear price
			sell_prices[stock_code]['rate'] = float(rate)
			if 'price' in sell_prices[stock_code]:
				del sell_prices[stock_code]['price']
		elif 'rate' in sell_prices[stock_code]:
			# Remove rate if explicitly set to None/empty
			del sell_prices[stock_code]['rate']
		
		# Remove entry if both price and rate are missing (but keep stock_name)
		if 'price' not in sell_prices[stock_code] and 'rate' not in sell_prices[stock_code]:
			# Only remove if stock_name is also not present
			if 'stock_name' not in sell_prices[stock_code]:
				del sell_prices[stock_code]
		
		# Save to file
		if save_dictionaries_to_json():
			return {"status": "success", "message": "Sell price updated", "data": sell_prices}
		else:
			return {"status": "error", "message": "Failed to save to file"}
	except Exception as e:
		return {"status": "error", "message": str(e)}

@app.get("/api/auto-sell")
@app.get("/stock/api/auto-sell")
async def get_auto_sell_api(proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to get auto sell flag status"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	global auto_sell_enabled
	return {"status": "success", "enabled": auto_sell_enabled}

@app.post("/api/auto-sell")
@app.post("/stock/api/auto-sell")
async def set_auto_sell_api(request: dict, proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to set auto sell flag"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	global auto_sell_enabled
	try:
		enabled = request.get('enabled')
		if enabled is None:
			return {"status": "error", "message": "Missing 'enabled' parameter"}
		
		auto_sell_enabled = bool(enabled)
		return {"status": "success", "enabled": auto_sell_enabled, "message": f"Auto sell {'enabled' if auto_sell_enabled else 'disabled'}"}
	except Exception as e:
		return {"status": "error", "message": str(e)}

@app.get("/health")
async def health():
	return {"status": "healthy"}

@app.get("/jango")
async def get_jango_endpoint(market: str = 'KRX'):
	"""Get account balance and holdings from stored data"""
	global stored_jango_data
	try:
		result = stored_jango_data
		return {"status": "success", "data": result}
	except Exception as e:
		return {"status": "error", "message": str(e)}

@app.get("/miche")
async def get_miche_endpoint():
	"""Get unexecuted orders"""
	try:
		result = get_miche()
		return {"status": "success", "data": result}
	except Exception as e:
		return {"status": "error", "message": str(e)}

@app.post("/cancel-nxt-trade")
async def cancel_nxt_trade_endpoint():
	"""Cancel NXT trades"""
	try:
		now = datetime.now().time()
		cancel_nxt_trade(now)
		return {"status": "success", "message": "Cancel NXT trade executed"}
	except Exception as e:
		return {"status": "error", "message": str(e)}

# 실행 구간
if __name__ == '__main__':
	uvicorn.run(app, host="0.0.0.0", port=8006)