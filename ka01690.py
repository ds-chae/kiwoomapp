import traceback

import requests
import json
import os
from datetime import datetime, timedelta, time, date
from dotenv import load_dotenv
from au1001 import get_token, get_key_list, get_one_token
import time as time_module
import threading
from fastapi import FastAPI, HTTPException, status, Cookie, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
from contextlib import asynccontextmanager
import secrets
import socket
from ka10080 import get_bun_chart, get_bun_price, get_price_index, set_low_after_high, get_low_after_high


# Interested stocks list
INTERESTED_STOCKS_FILE = 'interested_stocks.json'
interested_stocks = {}

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
updown_list = {}

key_list = get_key_list()
order_count = {}

# Global variable for tracking previous hour
prev_hour = None
# Global storage for jango data (updated by timer handler)
stored_jango_data = {}

# Global storage for miche data (updated by timer handler)
stored_miche_data = {}

def init_order_count():
	global order_count, key_list

	for key, value in key_list.items():
		ACCT = value['ACCT']
		order_count[ACCT] = {}


init_order_count()



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
	global key_list
	jango = []
	for k, key in key_list.items():
		acct = key['ACCT']
		j = print_acnt(acct, key['AK'], key['SK'])
		j['ACCT'] = acct
		jango[acct] = j

	return jango


import requests
import json


# Gyeja pyungga jango
def fn_kt00018(log_jango, token, data, cont_yn='N', next_key=''):
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
	if log_jango:
		print('get_jango => Code:', response.status_code)
		print('get_jango => Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
		print('get_jango => Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON ÀÀ´äÀ» ÆÄ½ÌÇÏ¿© Ãâ·Â
		print('get_jango => Finish:')
		print('')

	return response.json()

get_jango_count = 0


'''
	{
			"stk_cd": "A005930",
			"stk_nm": "삼성전자",
			"evltv_prft": "-00000000196888",
			"prft_rt": "-52.71",
			"pur_pric": "000000000124500",
			"pred_close_pric": "000000045400",
			"rmnd_qty": "000000000000003",
			"trde_able_qty": "000000000000003",
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
'''
def get_jango(now, market = 'KRX'):
	global get_jango_count, key_list, jango_token

	log_jango = (get_jango_count == 0)

	get_jango_count += 1
	if get_jango_count >= 10 :
		get_jango_count = 0

	jango = {}
	for k, key in key_list.items():
		acct = key['ACCT']
		MY_ACCESS_TOKEN = get_token(key['AK'], key['SK'])  # 접근토큰
		jango_token[acct] = MY_ACCESS_TOKEN
		j = call_fn_kt00018(log_jango, market, acct, MY_ACCESS_TOKEN)
		j['ACCT'] = acct
		jango[acct] = j

	# set lowest using jango cur_pric
	for acct, j in jango.items():
		acnt_evlt_remn_indv_tot = j.get("acnt_evlt_remn_indv_tot", [])

		for indv in acnt_evlt_remn_indv_tot:
			stk_cd = indv.get('stk_cd', '')
			stk_nm = indv.get('stk_nm', '')
			if stk_cd[0] == 'A':
				stk_cd = stk_cd[1:]
			cur_prc = int(indv.get('cur_prc','0'))
			if cur_prc < 0 :
				cur_prc = -cur_prc
			set_low_after_high(stk_cd, stk_nm, int(cur_prc))

	return jango

def call_fn_kt00018(log_jango, market, ACCT, MY_ACCESS_TOKEN):
	params = {
		'qry_tp': '2', # 1:Hapsan, 2:Gaebyul
		'dmst_stex_tp': market, # KRX, NXT
	}
	return fn_kt00018(log_jango, token=MY_ACCESS_TOKEN, data=params)

	# next-key, cont-yn °ªÀÌ ÀÖÀ» °æ¿ì
	# fn_kt00018(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')


from fn_kt10000 import sell_order, buy_order

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

from ka10007 import fn_ka10007

def get_upper_limit(MY_ACCESS_TOKEN, stk_cd):
	global updown_list
	if not stk_cd in updown_list:
		params = {
			'stk_cd': stk_cd,  # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
		}
		try:
			response = fn_ka10007(token=MY_ACCESS_TOKEN, data=params)
			print('calling fn_ka1007 in get_upper_limit succeeded')
			if stk_cd == response['stk_cd']:
				updown_list[stk_cd] = response
			else:
				print('calling fn_ka1007 in get_upper_limit mismatch')
				print('stk_cd in response is {}'.format(response['stk_cd']))
		except Exception as ex:
			print('calling fn_ka1007 in get_upper_limit failed')
			print(ex)
			return
	stk_data = updown_list[stk_cd]
	try:
		uplimit = stk_data['upl_pric']
		return int(uplimit)
	except:
		return 0


def cancel_different_sell_order(now, ACCT, stk_cd, stk_nm, ord_uv):
	global stored_miche_data
	cancel_count = 0
	int_uv = int(ord_uv)
	miche = []
	if ACCT in stored_miche_data:
		if 'oso' in stored_miche_data[ACCT]:
			miche = stored_miche_data[ACCT]['oso']
	for m in miche:
		#print('io_tp_nm=', m['io_tp_nm'])
		if m['stk_cd'] == stk_cd and m['io_tp_nm']  == '-매도' :
			oqty = m['ord_qty']
			oqp = int(m['ord_pric'])
			if oqp != int_uv:
				result = cancel_order_main(now, jango_token[ACCT], m['stex_tp_txt'], m['ord_no'], stk_cd)
				print('cancel_different_sell_order ', result)
				cancel_count += 1
	print('cancel_different_sell_order {} {} {} {} returns {}.'.format(ACCT, stk_cd, stk_nm, ord_uv, cancel_count))
	return cancel_count



def calculate_sell_price(pur_pric, sell_cond, stk_cd):
	ord_uv = '0'
	if 'sellprice' in sell_cond:
		ord_uv = sell_cond['sellprice']
	if ord_uv != '0':
		return ord_uv

	sellrate = float(sell_cond.get('sellrate', '0.0'))
	if sellrate != 0.0 :
		# sellrate is stored as-is (percentage), divide by 100 for calculation
		s_rate_percent = sellrate
		s_rate = s_rate_percent / 100.0
		s_price = pur_pric * (1.0 + s_rate)
		s_price = round_trunc(s_price)
		ord_uv = str(s_price)
		return ord_uv

	sellgap = float(sell_cond.get('sellgap', '0.0')) / 100.
	if sellgap != 0.0 :
		bun_price = bun_prices[stk_cd]
		lowest = get_low_after_high(stk_cd)
		if lowest != 0 :
			gap = float(bun_price['gap'])
			cl_price = lowest + gap * sellgap
			return str(cl_price)

	return '0'


def call_sell_order(now, ACCT, MY_ACCESS_TOKEN, market, stk_cd, stk_nm, indv, sell_cond):
	global current_status, working_status

	trde_able_qty = indv.get("trde_able_qty", "0")
	rmnd_qty = indv.get('rmnd_qty', "0")
	pur_pric_str = indv.get('pur_pric', '0')
	pur_pric = float(pur_pric_str) if pur_pric_str else 0.0

	ord_uv = calculate_sell_price(pur_pric, sell_cond, stk_cd)

	if ord_uv == '0': # price is not calculated
		return
	upperlimit = get_upper_limit(MY_ACCESS_TOKEN, stk_cd)
	if int(ord_uv) > upperlimit :
		print('{} {} {} exceed upper limit {}'.format(stk_cd, stk_nm, ord_uv, upperlimit))
		return

	# if any cancelled sell order, try next
	cancel_count = cancel_different_sell_order(now, ACCT, stk_cd, stk_nm, ord_uv)
	if cancel_count > 0 :
		return

	trde_able_qty_int = int(trde_able_qty) if trde_able_qty else 0
	if trde_able_qty_int == 0:
		return
	if isinstance(trde_able_qty, str) and len(trde_able_qty) > 4:
		trde_able_qty = trde_able_qty[4:]

	working_status = 'call sell_order()'
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


jango_token = {}

def sell_jango(now, jango, market):
	global auto_sell_enabled, current_status, jango_token

	for ACCT, j in jango.items():
		try:
			# Check auto sell enabled for this specific account
			# Mode can be NONE, BUY, SELL, BOTH
			mode = auto_sell_enabled.get(ACCT, 'NONE')
			# sell_jango runs if mode is SELL or BOTH
			if mode not in ['SELL', 'BOTH']:
				continue

			MY_ACCESS_TOKEN = jango_token[ACCT]

			acnt_evlt_remn_indv_tot = j.get("acnt_evlt_remn_indv_tot", [])

			for indv in acnt_evlt_remn_indv_tot:
				stk_cd = indv.get('stk_cd', '')
				stk_nm = indv.get('stk_nm', '')
				if stk_cd and len(stk_cd) > 0 and stk_cd[0] == 'A':
					stk_cd = stk_cd[1:]
					
				if stk_cd in not_nxt_cd and market == 'NXT':
					continue
					
				if stk_cd not in interested_stocks:
					continue

				sell_cond = interested_stocks[stk_cd]
				working_status = 'before call_sell_order {} {} {}'.format(market, stk_cd, stk_nm)
				call_sell_order(now, ACCT, MY_ACCESS_TOKEN, market, stk_cd, stk_nm, indv, sell_cond)
		except Exception as ex:
			print('at 314 {}'.format(working_status))
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
	global get_miche_failed, key_list

	miche = {}
	for k, key in key_list.items():
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

		if 'oso' in m:
			for order in m['oso']:
				cur_prc = order.get('cur_prc', '0')
				if cur_prc[0] == '-':
					order['cur_prc'] = cur_prc[1:]
		miche[ACCT] = m

	if get_miche_failed:
		get_miche_failed = False
		print(f"get_miche recovered.")

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
	for m in miche.values():
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
krx_start_time = time(8,52)
krx_end_time = time(15,30)
nxt_fin_time = time(20, 0)

new_day = False
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




def buy_cl(now):
	global order_count, interested_stocks, bun_prices, bun_charts
	global stored_jango_data, stored_miche_data, key_list

	for ACCT, key in key_list.items():
		# Check auto sell enabled for this specific account
		# Mode can be NONE, BUY, SELL, BOTH
		mode = auto_sell_enabled.get(ACCT, 'NONE')
		# buy_cl runs if mode is BUY or BOTH
		if mode not in ['BUY', 'BOTH']:
			continue

		#ACCT = key['ACCT']
		MY_ACCESS_TOKEN = get_token(key['AK'], key['SK'])  # 접근토큰
		buy_cl_by_account(ACCT, MY_ACCESS_TOKEN)


def buy_cl_by_account(ACCT, MY_ACCESS_TOKEN):
	global order_count, working_status

	working_status = 'in buy_cl_by_account'
	for stk_cd in interested_stocks:
		int_stock = interested_stocks[stk_cd]
		btype = int_stock.get('btype', '')
		if btype == 'CL':
			buy_cl_stk_cd(ACCT, MY_ACCESS_TOKEN, stk_cd, int_stock)
	pass


def buy_cl_stk_cd(ACCT, MY_ACCESS_TOKEN, stk_cd, int_stock):
	global working_status, order_count
	working_status = 'in buy_cl_stk_cd'
	ordered = order_count[ACCT]
	if stk_cd in ordered and ordered[stk_cd] >= 2:
		return
	stk_nm = int_stock['stock_name']
	bamount = int(int_stock.get('bamount', '0'))
	if bamount <= 0 :
		return

	bsum = 0
	myjango = stored_jango_data[ACCT] if (ACCT in stored_jango_data) else {}
	acnt_evlt_remn_indv_tot = myjango['acnt_evlt_remn_indv_tot']
	for eachjango in acnt_evlt_remn_indv_tot:
		each_cd = eachjango['stk_cd']
		if each_cd[0] == 'A':
			each_cd = each_cd[1:]
		if each_cd == stk_cd:
			bsum += int(eachjango['pur_amt'])
	miche = []
	if ACCT in stored_miche_data:
		if 'oso' in stored_miche_data[ACCT]:
			miche = stored_miche_data[ACCT]['oso']
	for m in miche:
		#print('io_tp_nm=', m['io_tp_nm'])
		if m['stk_cd'] == stk_cd and m['io_tp_nm']  == '+매수' :
			oqty = m['ord_qty']
			oqp = m['ord_pric']
			bsum += int(oqty)*int(oqp)
	if bsum >= bamount * 2 * 0.85:
		ordered[stk_cd] = 2
	elif bsum >= bamount * 1 * 0.85:
		ordered[stk_cd] = 1
	else:
		ordered[stk_cd] = 0
	print('ordered count for {} {} {} is {}, bsum={}'.format(ACCT, stk_cd, stk_nm, ordered[stk_cd], bsum))
	if ordered[stk_cd] >= 2:
		return

	if not stk_cd in bun_charts:
		print('getting bun_chart for {} {}'.format(stk_cd, stk_nm))
		bun_charts[stk_cd] = get_bun_chart(MY_ACCESS_TOKEN, stk_cd, stk_nm)
	if not stk_cd in bun_prices:
		print('getting bun_price for {} {} from bun_chart'.format(stk_cd, stk_nm))
		bun_prices[stk_cd] = get_bun_price(stk_cd, stk_nm, bun_charts[stk_cd])
	print(bun_prices)
	if not stk_cd in bun_prices:
		print('getting bun_chart or bun_price for {} {} failed'.format(stk_cd, stk_nm));
		return

	bun_price = bun_prices[stk_cd]
	price_index = get_price_index(int_stock['color'])
	stex = 'KRX'
	trde_tp = '0'
	if ordered[stk_cd] < 1 :
		bp = bun_price['price'][price_index]
		ord_price = round_trunc(bp)
		ord_qty = bamount // ord_price
		#ret_status = buy_order(MY_ACCESS_TOKEN, stex, stk_cd, str(ord_qty), str(ord_price), trade_tp=trde_tp, cond_uv='')
		ret_status = buy_order(MY_ACCESS_TOKEN, stex, stk_cd, '1', str(ord_price), trde_tp=trde_tp, cond_uv='')
		print('1_buy_order_result: {}'.format(ret_status))
		ordered[stk_cd] += 1
		print('price:{} current buy order for {} {} {} is {}'.format(ord_price, ACCT, stk_cd, stk_nm, ordered[stk_cd]))
	if ordered[stk_cd] < 2:
		bp = bun_price['price'][price_index+1]
		ord_price = round_trunc(bp)
		ord_qty = bamount // ord_price
		#ret_status = buy_order(MY_ACCESS_TOKEN, stex, stk_cd, str(ord_qty), str(ord_price), trade_tp=trde_tp, cond_uv='')
		ret_status = buy_order(MY_ACCESS_TOKEN, stex, stk_cd, '1', str(ord_price), trde_tp=trde_tp, cond_uv='')
		print('2_buy_order_result: {}'.format(ret_status))
		ordered[stk_cd] += 1
		print('price:{} current buy order for {} {} {} is {}'.format(ord_price, ACCT, stk_cd, stk_nm, ordered[stk_cd]))

	pass


current_status = ''
working_status = 'initial'
get_miche_failed = True

def daily_work(now):
	global new_day, krx_first, current_status
	global nxt_start_time, nxt_end_time, krx_start_time,nxt_cancelled, krx_end_time, nxt_fin_time
	global stored_jango_data, stored_miche_data, get_miche_failed, working_status

	stored_jango_data = get_jango(now)
	if is_between(now, nxt_start_time, nxt_end_time):
		current_status = 'NXT'
		try:
			stored_miche_data = get_miche()
		except Exception as e:
			get_miche_failed = True
			print(f"Error updating miche data: {e}")

		sell_jango(now, stored_jango_data, 'NXT')
	elif is_between(now, nxt_end_time, krx_start_time):
		current_status = 'NXT->KRX'
		if not nxt_cancelled:
			nxt_cancelled = True
			cancel_nxt_trade(now)
	elif is_between(now, krx_start_time, nxt_fin_time):
		try:
			stored_miche_data = get_miche()
		except Exception as e:
			get_miche_failed = True
			print(f"Error updating miche data: {e}")
		if is_between(now, krx_start_time, krx_end_time):
			current_status = 'KRX'
			if not krx_first:
				print('{} krx_first get_jango and sell_jango.'.format(now))
				krx_first = True
			sell_jango(now, stored_jango_data, 'KRX')
			working_status='calling buy_cl'
			buy_cl(now)
		else:
			current_status = 'NXT'
	else:
		if (new_day):
			current_status = 'OFF'
			new_day = False
			print('{} {} Setting new day=False'.format(cur_date(), now))


def set_new_day():
	global new_day, waiting_shown, no_working_shown, nxt_cancelled, ktx_first, current_status
	global updown_list, access_token

	if new_day:
		return
	print('Setting new_day=True, clearing variables.')
	now = datetime.now().time()
	print('{} {} Setting new day=True'.format(cur_date(), now))
	new_day = True
	waiting_shown = False
	no_working_shown = False
	nxt_cancelled = False
	ktx_first = False
	current_status = 'NEW'
	not_nxt_cd = {}
	updown_list = {}
	init_order_count()
	access_token = {}


# Global flag for auto sell - dictionary keyed by account
AUTO_SELL_FILE = 'auto_sell_enabled.json'
auto_sell_enabled = {}

def load_dictionaries_from_json():
	"""Load auto_sell_enabled, and interested_stocks from JSON files"""
	global auto_sell_enabled, interested_stocks

	# Load auto_sell_enabled
	if os.path.exists(AUTO_SELL_FILE):
		try:
			with open(AUTO_SELL_FILE, 'r', encoding='utf-8') as f:
				auto_sell_enabled = json.load(f)
			
			# Migration: Convert boolean values to strings
			modified_migration = False
			for acct, val in auto_sell_enabled.items():
				if isinstance(val, bool):
					auto_sell_enabled[acct] = 'SELL' if val else 'NONE'
					modified_migration = True
			
			if modified_migration:
				save_auto_sell_to_json()
				print(f"Migrated auto_sell_enabled boolean values to strings")
				
			print(f"Loaded auto_sell_enabled from {AUTO_SELL_FILE}: {auto_sell_enabled}")
		except Exception as e:
			print(f"Error loading auto_sell_enabled: {e}")
			auto_sell_enabled = {}
	else:
		auto_sell_enabled = {}
		print(f"Created new auto_sell_enabled dictionary")

	# Load interested_stocks
	if os.path.exists(INTERESTED_STOCKS_FILE):
		try:
			with open(INTERESTED_STOCKS_FILE, 'r', encoding='utf-8') as f:
				interested_stocks = json.load(f)
			print(f"Loaded interested_stocks from {INTERESTED_STOCKS_FILE}: {interested_stocks}")
		except Exception as e:
			print(f"Error loading interested_stocks: {e}")
			interested_stocks = {}
	else:
		interested_stocks = {}
		print(f"Created new interested_stocks dictionary")

	try:
		modified = False
		for stk in interested_stocks:
			print('istk, stk={}'.format(stk))
			stock = interested_stocks[stk]
			stk_nm = stock.get('stock_name', '')
			print('interested stock_name={}'.format(stk_nm))
			if stk_nm == '':
				print('getting stock name for {}'.format(stk))
				stk_nm = get_stockname(stk)
				stock['stock_name'] = stk_nm
				modified = True
			if 'color' in stock:
				stock['color'] = color_kor_to_eng(stock['color'])
			print('in istk', stock)

		if modified:
			save_interested_stocks_to_json()
			print('interested_stocks is modified, thus saved')
	except Exception as ex:
		print('783', ex)
		exit(0)



bun_charts = {}
bun_prices = {}

# fill minutes chart if btype is 'CL'
def fill_charts_for_CL(MY_ACCESS_TOKEN):
	global bun_charts, interested_stocks
	try:
		for stk_cd, stock in interested_stocks.items():
			btype = stock.get('btype', '')
			if btype != 'CL':
				continue
			if stk_cd in bun_charts:
				continue
			stk_nm = stock['stock_name']
			bun_charts[stk_cd] = get_bun_chart(MY_ACCESS_TOKEN, stk_cd, stk_nm)
	except Exception as ex:
		print('806', ex)
		exit(0)


def calculate_bun_prices(MY_ACCESS_TOKEN):
	global bun_prices, bun_charts, interested_stocks
	for stk_cd in interested_stocks:
		if stk_cd in bun_prices:
			continue
		if stk_cd in bun_charts:
			continue
		chart = bun_charts[stk_cd]
		bun_prices[stk_cd] = get_bun_price(chart)


def save_auto_sell_to_json():
	"""Save auto_sell_enabled to JSON file"""
	global auto_sell_enabled
	try:
		with open(AUTO_SELL_FILE, 'w', encoding='utf-8') as f:
			json.dump(auto_sell_enabled, f, indent=2, ensure_ascii=False)
		print(f"Saved auto_sell_enabled to {AUTO_SELL_FILE}")
		return True
	except Exception as e:
		print(f"Error saving auto_sell_enabled: {e}")
		return False

def save_interested_stocks_to_json():
	"""Save interested_stocks to JSON file"""
	global interested_stocks
	try:
		with open(INTERESTED_STOCKS_FILE, 'w', encoding='utf-8') as f:
			json.dump(interested_stocks, f, indent=2, ensure_ascii=False)
		print(f"Saved interested_stocks to {INTERESTED_STOCKS_FILE}")
		return True
	except Exception as e:
		print(f"Error saving interested_stocks: {e}")
		return False



# Background thread for periodic timer handler
background_thread = None
thread_stop_event = threading.Event()

def background_timer_thread():
	"""Background thread that calls periodic_timer_handler every 1 second"""
	global thread_stop_event
	while not thread_stop_event.is_set():
		try:
			periodic_timer_handler()
		except Exception as e:
			print(f"Error in periodic_timer_handler: {e}")

		# Sleep for 1 second, but check stop event periodically
		for _ in range(10):  # Check every 0.1 seconds for 1 second total
			if thread_stop_event.is_set():
				break
			time_module.sleep(0.1)

@asynccontextmanager
async def lifespan(app: FastAPI):
	"""Lifespan event handler for startup and shutdown"""
	global stored_jango_data, stored_miche_data, background_thread, thread_stop_event

	# Startup
	print("Starting application...")
	try:
		load_dictionaries_from_json()
		print("Dictionaries loaded successfully")
	except Exception as e:
		print(f"Error loading dictionaries: {e}")

	fill_charts_for_CL(get_one_token())

	# Initialize stored jango data by calling once immediately (non-blocking, allow failure)
	print("Initializing jango data...")
	now = datetime.now().time()
	try:
		stored_jango_data = get_jango(now, 'KRX')
		print("KRX jango data initialized")
	except Exception as e:
		print(f"Error initializing KRX jango data: {e}")
		stored_jango_data = {}
	
	# Initialize stored miche data by calling once immediately (non-blocking, allow failure)
	print("Initializing miche data...")
	try:
		stored_miche_data = get_miche()
		print("Miche data initialized")
	except Exception as e:
		get_miche_failed = True
		print(f"Error initializing miche data: {e}")
		stored_miche_data = []

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
	global prev_hour, new_day, stored_jango_data, stored_miche_data, working_status
	
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
			traceback.print_exc()
			print('currrent status={}'.format(working_status))

def format_account_data():
	"""Format account data for display in UI"""
	global stored_jango_data
	try:
		# Determine which market is active based on current time
		now = datetime.now().time()

		# Get holdings from stored data for active market only
		all_jango = stored_jango_data
		if isinstance(all_jango, dict):
			iterator = all_jango.values()
		else:
			iterator = all_jango
			
		formatted_data = []
		seen_keys = set()  # Track unique combinations of account and stock_code
		
		for account in iterator:
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
				
				cur_prc = int(stock.get('cur_prc', '0'))
				if cur_prc < 0 :
					cur_prc = -cur_prc
				cur_prc_float = float(cur_prc)
				
				prft_rt = stock.get('prft_rt', '0')
				prft_rt_float = float(prft_rt) if prft_rt else 0.0
				
				# Get preset sell price and rate from sell_prices dictionary
				price_part = '-'
				rate_part = '-'
				
				if stk_cd_clean in interested_stocks:
					sell_cond = interested_stocks[stk_cd_clean]
					
					if 'sellprice' in sell_cond:
						try:
							price_val = int(sell_cond['sellprice'])
							price_part = f"{price_val}"
						except (ValueError, TypeError):
							pass
					
					if 'sellrate' in sell_cond:
						try:
							# sellrate is stored as-is (percentage), display directly
							rate_val = float(sell_cond['sellrate'])
							rate_part = f"{rate_val:+.2f}%"
						except (ValueError, TypeError):
							pass

				# Combine price and rate
				preset_prc_rate = f"{price_part} / {rate_part}"
				
				# Create unique key from account and stock_code
				unique_key = f"{acct_no}_{stk_cd_clean}"
				
				# Only add if not already seen (deduplicate by account and stock_code)
				if unique_key not in seen_keys:
					seen_keys.add(unique_key)
					# Format avg_buy_price / cur_prc
					if pur_pric_float > 0 and cur_prc_float > 0:
						avg_buy_price_display = f"{pur_pric_float:,.0f} / {cur_prc_float:,.0f}"
					elif pur_pric_float > 0:
						avg_buy_price_display = f"{pur_pric_float:,.0f} / -"
					elif cur_prc_float > 0:
						avg_buy_price_display = f"- / {cur_prc_float:,.0f}"
					else:
						avg_buy_price_display = '-'
					
					formatted_data.append({
						'account': acct_no,
						'stock_code': stk_cd_clean,
						'stock_name': stk_nm,
						'tradeable_qty': trde_able_qty,
						'rmnd_qty': rmnd_qty,
						'avg_buy_price': avg_buy_price_display,
						'profit_rate': f"{prft_rt_float:+.2f}%",
						'preset_prc_rate': preset_prc_rate
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
			<h1>Login</h1>
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
				border-right: 1px solid rgba(255, 255, 255, 0.3);
			}
			th:last-child {
				border-right: none;
			}
			th:first-child,
			td:first-child {
				width: 110px;
				white-space: nowrap;
			}
			td {
				padding: 15px;
				border-bottom: 1px solid #e0e0e0;
				border-right: 1px solid #e0e0e0;
			}
			td:last-child {
				border-right: none;
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
			#interested-stock-code-input {
				width: 120px;
			}
			#interested-stock-bamount-input {
				width: 120px;
			}
			#interested-stock-price-input {
				width: 120px;
			}
			#interested-stock-rate-input {
				width: 80px;
			}
			#interested-stock-gaprate-input {
				width: 80px;
			}
			#interested-stock-btype-input {
				width: 80px;
			}
			#interested-stock-color-input {
				width: 80px;
			}
			/* Remove spinner arrows from number inputs */
			#interested-stock-bamount-input::-webkit-outer-spin-button,
			#interested-stock-bamount-input::-webkit-inner-spin-button,
			#interested-stock-price-input::-webkit-outer-spin-button,
			#interested-stock-price-input::-webkit-inner-spin-button,
			#interested-stock-rate-input::-webkit-outer-spin-button,
			#interested-stock-rate-input::-webkit-inner-spin-button,
			#interested-stock-gaprate-input::-webkit-outer-spin-button,
			#interested-stock-gaprate-input::-webkit-inner-spin-button {
				-webkit-appearance: none;
				margin: 0;
			}
			#interested-stock-bamount-input[type=number],
			#interested-stock-price-input[type=number],
			#interested-stock-rate-input[type=number],
			#interested-stock-gaprate-input[type=number] {
				-moz-appearance: textfield;
			}
			.form-group input:focus {
				outline: none;
				border-color: #667eea;
			}
			.form-group select {
				padding: 10px;
				border: 1px solid #ddd;
				border-radius: 4px;
				font-size: 14px;
				height: auto;
			}
			.form-group select:focus {
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
				display: flex;
				justify-content: space-between;
				align-items: center;
			}
			.account-group-header h2 {
				margin: 0;
				font-size: 1.2em;
			}
			.account-auto-sell-btn {
				background: rgba(255, 255, 255, 0.2);
				color: white;
				border: 1px solid rgba(255, 255, 255, 0.3);
				padding: 6px 15px;
				border-radius: 4px;
				cursor: pointer;
				font-size: 12px;
				font-weight: 600;
				transition: background-color 0.2s;
			}
			.account-auto-sell-btn:hover {
				background: rgba(255, 255, 255, 0.3);
			}
			.account-auto-sell-btn.enabled {
				background: #27ae60;
				border-color: #27ae60;
			}
			.account-auto-sell-btn.disabled {
				background: rgba(255, 255, 255, 0.1);
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
			.interested-stocks-section {
				margin-top: 40px;
				padding-top: 30px;
				border-top: 2px solid #e0e0e0;
			}
			.interested-stocks-section h2 {
				color: #333;
				margin-bottom: 20px;
				font-size: 1.5em;
			}
			.add-interested-form {
				background: #f8f9fa;
				padding: 20px;
				border-radius: 8px;
				margin-bottom: 20px;
			}
			.add-interested-form h3 {
				margin-bottom: 15px;
				color: #333;
				font-size: 1.2em;
			}
			.add-interested-form-content {
				display: flex;
				gap: 15px;
				align-items: flex-end;
				flex-wrap: wrap;
			}
			.btn-add-interested {
				background: #3498db;
				color: white;
				border: none;
				padding: 10px 20px;
				border-radius: 4px;
				cursor: pointer;
				font-size: 14px;
				font-weight: 600;
			}
			.btn-add-interested:hover {
				background: #2980b9;
			}
			.btn-buy-interested {
				background: #27ae60;
				color: white;
				border: none;
				padding: 6px 12px;
				border-radius: 4px;
				cursor: pointer;
				font-size: 12px;
				font-weight: 600;
				transition: background-color 0.2s;
			}
			.btn-buy-interested:hover {
				background: #229954;
			}
			.btn-remove-interested {
				background: #e74c3c;
				color: white;
				border: none;
				padding: 4px 8px;
				border-radius: 4px;
				cursor: pointer;
				font-size: 12px;
				font-weight: 600;
			}
			.btn-remove-interested:hover {
				background: #c0392b;
			}
			.color-select {
				padding: 4px 8px;
				border: 1px solid #ddd;
				border-radius: 4px;
				font-size: 14px;
				cursor: pointer;
			}
			.color-select:focus {
				outline: none;
				border-color: #667eea;
			}
			#interested-stocks-container tbody tr {
				cursor: pointer;
			}
			#interested-stocks-container tbody tr:hover {
				background-color: #f5f5f5;
			}
			#interested-stocks-container tbody tr.selected {
				background-color: #e3f2fd;
				border-left: 4px solid #667eea;
			}
			#interested-stocks-container tbody tr.selected:hover {
				background-color: #bbdefb;
			}
			#interested-stocks-container {
				overflow-x: auto;
				-webkit-overflow-scrolling: touch;
			}
			#interested-stocks-container table {
				min-width: 600px;
			}
			@media screen and (max-width: 768px) {
				#interested-stocks-container {
					overflow-x: auto;
					width: 100%;
					-webkit-overflow-scrolling: touch;
				}
				#interested-stocks-container table {
					min-width: 600px;
					width: 100%;
				}
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
			.btn-delete-row {
				background: #e74c3c;
				color: white;
				border: none;
				padding: 4px 8px;
				border-radius: 4px;
				cursor: pointer;
				font-size: 14px;
				transition: background-color 0.2s;
			}
			.btn-delete-row:hover {
				background: #c0392b;
			}
			.miche-row:hover {
				background-color: #f5f5f5;
			}
			.miche-row.selected {
				background-color: #e3f2fd;
				border-left: 4px solid #667eea;
			}
			.miche-row.selected:hover {
				background-color: #bbdefb;
			}
			#miche-container {
				overflow-x: auto;
				-webkit-overflow-scrolling: touch;
			}
			#miche-container table {
				width: auto !important;
			}
			#miche-container table th:nth-child(1),
			#miche-container table td:nth-child(1) {
				width: 80px;
			}
			#miche-container table th:nth-child(2),
			#miche-container table td:nth-child(2) {
				width: 80px;
			}
			#miche-container table th:nth-child(4),
			#miche-container table td:nth-child(4) {
				width: 80px;
			}
			#miche-container table th:nth-child(5),
			#miche-container table td:nth-child(5) {
				width: 160px;
			}
			#miche-container table th:nth-child(7),
			#miche-container table td:nth-child(7) {
				width: 80px;
			}
			#miche-container table th:nth-child(6),
			#miche-container table td:nth-child(6) {
				width: 150px;
			}
			#miche-container table th:nth-child(8),
			#miche-container table td:nth-child(8) {
				width: 60px;
			}
			#miche-container table th:nth-child(9),
			#miche-container table td:nth-child(9) {
				width: 60px;
			}
			@media screen and (max-width: 768px) {
				#miche-container {
					overflow-x: auto;
					width: 100%;
					-webkit-overflow-scrolling: touch;
				}
				#miche-container table {
					min-width: 600px;
					width: 100%;
				}
			}
			.auto-sell-control {
				display: flex;
				align-items: center;
				gap: 10px;
			}
			.auto-sell-select {
				padding: 6px;
				border-radius: 4px;
				border: 1px solid #ddd;
				font-weight: 600;
			}
			.btn-apply-auto-sell {
				background: #34495e;
				color: white;
				border: none;
				padding: 6px 12px;
				border-radius: 4px;
				cursor: pointer;
				font-size: 14px;
				transition: background-color 0.2s;
			}
			.btn-apply-auto-sell:hover {
				background: #2c3e50;
			}
		</style>
	</head>
	<body>
		<div class="container">
			<div class="header">
				<div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
					<div>
						<h1 id="headline-time">Account -</h1>
						<p>Stock Holdings and Trading Information</p>
					</div>
					<button class="btn-logout" onclick="logout()">Logout</button>
				</div>
			</div>
			<div class="table-container" id="table-container">
				<div class="empty-state">
					<h2>Loading...</h2>
					<p>Loading account holdings...</p>
				</div>
			</div>
			<div class="miche-section" id="miche-section">
				<div id="miche-container">
					<div class="account-group">
						<div class="account-group-header">
							<h2>Unexecuted Orders</h2>
						</div>
						<table>
							<thead>
								<tr>
									<th>Code</th>
									<th>Name</th>
									<th>Order Type</th>
									<th>Order Qty</th>
									<th>Order / Current</th>
									<th>REMAIN</th>
									<th>Exchange</th>
									<th>Time</th>
									<th>Action</th>
								</tr>
							</thead>
							<tbody>
								<tr>
									<td colspan="9" style="text-align: center; padding: 20px; color: #7f8c8d;">
										Loading...
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</div>
			<div class="interested-stocks-section" id="interested-stocks-section">
				<h2>Int Stocks</h2>
				<div class="add-interested-form">
					<div class="add-interested-form-content">
						<div class="form-group">
							<label for="interested-stock-code-input">Code</label>
							<input type="text" id="interested-stock-code-input" placeholder="e.g., 005930" />
						</div>
						<div class="form-group">
							<input type="text" id="interested-stock-name-input" placeholder="e.g., Samsung Electronics" />
						</div>
						<div class="form-group">
							<select id="interested-stock-btype-input">
								<option value="">Btype</option>
								<option value="CL">CL</option>
								<option value="PCL">PCL</option>
								<option value="HCL">HCL</option>
								<option value="SCL">SCL</option>
							</select>
						</div>
						<div class="form-group">
							<select id="interested-stock-color-input">
								<option value="">Color</option>
								<option value="R">빨 (Red)</option>
								<option value="O">주 (Orange)</option>
								<option value="Y">노 (Yellow)</option>
								<option value="G">초 (Green)</option>
								<option value="B">파 (Blue)</option>
								<option value="D">남 (Navy)</option>
								<option value="V">보 (Purple)</option>
							</select>
						</div>
						<div class="form-group">
							<input type="number" id="interested-stock-bamount-input" placeholder="BAmount" step="1" />
						</div>
						<div class="form-group">
							<input type="number" id="interested-stock-price-input" placeholder="Price" step="0.01" />
						</div>
						<div class="form-group">
							<input type="number" id="interested-stock-rate-input" placeholder="Rate (%)" step="0.01" />
						</div>
						<div class="form-group">
							<input type="number" id="interested-stock-gaprate-input" placeholder="GapRate" step="0.01" />
						</div>
						<button class="btn-add-interested" onclick="addInterestedStock()">Add/Update</button>
						<button class="btn-delete" onclick="deleteInterestedStockFromForm()">Delete</button>
					</div>
				</div>
				<div id="interested-stocks-container">
					<div class="account-group">
						<table>
							<thead>
								<tr>
									<th>Code</th>
									<th>Name</th>
									<th>Action</th>
								</tr>
							</thead>
							<tbody>
								<tr>
									<td colspan="3" style="text-align: center; padding: 20px; color: #7f8c8d;">
										Loading...
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
				<div class="buy-section" id="buy-section" style="margin-top: 20px; padding: 20px; background: #f8f9fa; border-radius: 8px;">
					<h3>Buy Order</h3>
					<div class="add-interested-form-content">
						<div class="form-group">
							<label for="buy-stock-code-input">Code</label>
							<input type="text" id="buy-stock-code-input" placeholder="e.g., 005930" />
						</div>
						<div class="form-group">
							<label for="buy-stock-name-input">Name</label>
							<input type="text" id="buy-stock-name-input" placeholder="e.g., Samsung Electronics" />
						</div>
						<div class="form-group">
							<label for="buy-price-input">Price</label>
							<input type="number" id="buy-price-input" placeholder="Price" step="0.01" min="0" />
						</div>
						<div class="form-group">
							<label for="buy-amount-input">Amount</label>
							<input type="number" id="buy-amount-input" placeholder="amount" step="1" min="1" />
						</div>
						<button class="btn-buy-interested" onclick="buyStock()" title="Buy stock">
							Buy
						</button>
					</div>
				</div>
			</div>
	"""
	
	html_content += """
			</div>
		</div>
		<button class="refresh-btn" onclick="updateTable()">Refresh</button>
		<script>
		
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
			
			// Get stock code, stock name, sell price, and sell rate from row
			const stockCode = rowElement.getAttribute('data-stock-code');
			const stockName = rowElement.getAttribute('data-stock-name') || '';
			const sellPrice = rowElement.getAttribute('data-sell-price') || '';
			const sellRate = rowElement.getAttribute('data-sell-rate') || '';
			
			// Fill buy section
			document.getElementById('buy-stock-code-input').value = stockCode;
			document.getElementById('buy-stock-name-input').value = stockName;
			document.getElementById('buy-price-input').value = '';
			document.getElementById('buy-amount-input').value = '';
			
			// Fill int stocks section
			document.getElementById('interested-stock-code-input').value = stockCode;
			document.getElementById('interested-stock-name-input').value = stockName;
			if (sellPrice && sellPrice !== '-') {
				const priceValue = sellPrice.replace(/,/g, '');
				document.getElementById('interested-stock-price-input').value = priceValue;
			} else {
				document.getElementById('interested-stock-price-input').value = '';
			}
			// Fill int stocks section
			document.getElementById('interested-stock-code-input').value = stockCode;
			document.getElementById('interested-stock-name-input').value = stockName;
			if (sellPrice && sellPrice !== '-') {
				const priceValue = sellPrice.replace(/,/g, '');
				document.getElementById('interested-stock-price-input').value = priceValue;
			} else {
				document.getElementById('interested-stock-price-input').value = '';
			}
			if (sellRate && sellRate !== '-') {
				// Extract percentage value (from Account Holdings table format like "5.5%")
				const rateMatch = sellRate.match(/([\d.+-]+)%/);
				if (rateMatch) {
					// Store percentage as-is (no conversion)
					document.getElementById('interested-stock-rate-input').value = rateMatch[1];
				} else {
					document.getElementById('interested-stock-rate-input').value = '';
				}
			} else {
				document.getElementById('interested-stock-rate-input').value = '';
			}
			document.getElementById('interested-stock-gaprate-input').value = '';
			
			// Scroll to update section
		}
		
		function deleteRowSellPrice(stockCode, stockName) {
			if (!stockCode) {
				showMessage('Stock code is missing', 'error');
				return;
			}
			
			if (!confirm(`Delete sell price/rate for ${stockName || stockCode}?`)) {
				return;
			}
			
			fetch('./api/sell-prices/' + encodeURIComponent(stockCode), {
				method: 'DELETE',
				headers: {
					'Content-Type': 'application/json',
				}
			})
			.then(response => response.json())
			.then(result => {
				if (result.status === 'success') {
					showMessage('Sell price/rate deleted successfully!', 'success');
					// Refresh the tables immediately
					updateTable();
					updateSellPrices();
				} else {
					showMessage('Error: ' + result.message, 'error');
				}
			})
			.catch(error => {
				showMessage('Error deleting sell price/rate: ' + error, 'error');
			});
		}
		
		function selectMicheRow(rowElement) {
			// Remove selected class from all miche rows
			document.querySelectorAll('.miche-row').forEach(tr => {
				tr.classList.remove('selected');
			});
			
			// Remove selected class from all holdings rows
			document.querySelectorAll('tbody tr:not(.miche-row)').forEach(tr => {
				tr.classList.remove('selected');
			});
			
			// Add selected class to clicked row
			rowElement.classList.add('selected');
			
			// Get stock code, stock name, and order price from row
			const stockCode = rowElement.getAttribute('data-stock-code');
			const stockName = rowElement.getAttribute('data-stock-name') || '';
			const orderPrice = rowElement.getAttribute('data-order-price') || '';
			
			// Fill buy section
			document.getElementById('buy-stock-code-input').value = stockCode;
			document.getElementById('buy-stock-name-input').value = stockName;
			if (orderPrice && orderPrice !== '0' && orderPrice !== '') {
				document.getElementById('buy-price-input').value = orderPrice;
			} else {
				document.getElementById('buy-price-input').value = '';
			}
			document.getElementById('buy-amount-input').value = '';
			
			// Fill int stocks section
			document.getElementById('interested-stock-code-input').value = stockCode;
			document.getElementById('interested-stock-name-input').value = stockName;
			if (orderPrice && orderPrice !== '0' && orderPrice !== '') {
				document.getElementById('interested-stock-price-input').value = orderPrice;
			} else {
				document.getElementById('interested-stock-price-input').value = '';
			}
			document.getElementById('interested-stock-rate-input').value = '';
			document.getElementById('interested-stock-gaprate-input').value = '';
		}
		
		function updateTable() {
			// Fetch both account data and auto sell status in parallel
			Promise.all([
				fetch('./api/account-data').then(r => {
					if (r.status === 401) {
						window.location.reload();
						return Promise.reject('Unauthorized');
					}
					return r.json();
				}),
				fetch('./api/auto-sell').then(r => {
					if (r.status === 401) {
						window.location.reload();
						return Promise.reject('Unauthorized');
					}
					return r.json();
				})
			])
				.then(([accountResult, autoSellResult]) => {
					if (accountResult.status === 'success') {
						// Update headline with timestamp and status
						if (accountResult.timestamp) {
							const headlineTime = document.getElementById('headline-time');
							if (headlineTime) {
								let headlineText = 'Account ' + accountResult.timestamp;
								if (accountResult.current_status) {
									headlineText += ' (' + accountResult.current_status + ')';
								}
								headlineTime.textContent = headlineText;
							}
						}
						const data = accountResult.data || [];
						const tableContainer = document.getElementById('table-container');
						
						// Get auto sell status data
						const autoSellData = (autoSellResult.status === 'success' && autoSellResult.data) ? autoSellResult.data : {};
						
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
							if (!tableContainer.querySelector('.empty-state')) {
								tableContainer.innerHTML = `
									<div class="empty-state">
										<h2>No Holdings Found</h2>
										<p>No account holdings are currently available.</p>
									</div>
								`;
							}
							return;
						}

						// Remove empty state if exists
						const emptyState = tableContainer.querySelector('.empty-state');
						if (emptyState) emptyState.remove();
						
						const sortedAccounts = Object.keys(accountGroups).sort();
						
						// 1. Remove accounts that no longer exist in data
						const existingGroups = tableContainer.querySelectorAll('.account-group');
						existingGroups.forEach(group => {
							const id = group.id.replace('account-group-', '');
							if (!accountGroups[id]) group.remove();
						});

						// 2. Update or Create accounts
						for (const acctNo of sortedAccounts) {
							let group = document.getElementById('account-group-' + acctNo);
							const stocks = accountGroups[acctNo] || [];
							
							// Get auto sell status
							let cleanMode = autoSellData[acctNo] || 'NONE';
							if (typeof cleanMode === 'boolean') cleanMode = cleanMode ? 'SELL' : 'NONE';
							if (!['NONE', 'BUY', 'SELL', 'BOTH'].includes(cleanMode)) cleanMode = 'NONE';
							
							// If group doesn't exist, create it
							if (!group) {
								group = document.createElement('div');
								group.className = 'account-group';
								group.id = 'account-group-' + acctNo;
								
								// Generate options
								const options = ['NONE', 'BUY', 'SELL', 'BOTH'].map(mode => 
									`<option value="${mode}" ${mode === cleanMode ? 'selected' : ''}>${mode}</option>`
								).join('');
								
								group.innerHTML = `
									<div class="account-group-header">
										<h2>Account: ${acctNo}</h2>
										<div class="auto-sell-control">
											<select id="select-auto-sell-${acctNo}" class="auto-sell-select">
												${options}
											</select>
											<button class="btn-apply-auto-sell" onclick="applyAccountAutoSell('${acctNo}')">Apply</button>
										</div>
									</div>
									<table>
										<thead>
											<tr>
												<th>Code</th>
												<th>Name</th>
												<th>Qty</th>
												<th>Avg Buy Price</th>
												<th>Profit Rate</th>
												<th>PRESET PRC/RATE</th>
											</tr>
										</thead>
										<tbody></tbody>
									</table>
								`;
								// Insert in sorted order could be complex, assume appending is fine or handled by sort order if we clear. 
								// Since we update in order, appending is fine for new ones. 
								// To strictly maintain order for interleaved additions:
								// Find successor
								const successorId = sortedAccounts.find(a => a > acctNo && document.getElementById('account-group-' + a));
								if (successorId) {
									tableContainer.insertBefore(group, document.getElementById('account-group-' + successorId));
								} else {
									tableContainer.appendChild(group);
								}
							}
							
							// Update Select Box if not focused
							const selectBox = group.querySelector(`#select-auto-sell-${acctNo}`);
							if (selectBox && document.activeElement !== selectBox) {
								if (selectBox.value !== cleanMode) {
									selectBox.value = cleanMode;
								}
							}

							// Update Rows
							const tbody = group.querySelector('tbody');
							const existingRows = Array.from(tbody.rows);
							const rowMap = new Map();
							existingRows.forEach(r => rowMap.set(r.getAttribute('data-row-id'), r));
							const processedIds = new Set();
							
							// Sort stocks ? Logic just iterates data order.
							
							for (const item of stocks) {
								const rowId = item.account + '_' + item.stock_code;
								processedIds.add(rowId);
								
								const profitClass = getProfitClass(item.profit_rate);
								const rmndQty = item.rmnd_qty || '0';
								const presetPrcRate = item.preset_prc_rate || '- / -';
								
								// Extract parts
								let sellPrice = '', sellRate = '';
								const parts = presetPrcRate.split(' / ');
								if (parts.length === 2) {
									sellPrice = parts[0].trim() !== '-' ? parts[0].trim().replace(/,/g, '') : '';
									sellRate = parts[1].trim() !== '-' ? parts[1].trim().replace('%', '') : '';
								}
								
								const cellContent = `
									<td><strong>${item.stock_code}</strong></td>
									<td>${item.stock_name}</td>
									<td>${item.tradeable_qty} / ${rmndQty}</td>
									<td>${item.avg_buy_price}</td>
									<td class="${profitClass}">${item.profit_rate}</td>
									<td>${presetPrcRate}</td>
								`;
								
								let row = rowMap.get(rowId);
								if (row) {
									// Update existing row if content changed
									// Comparing innerHTML might be expensive but robust.
									// Or just set it.
									if (row.innerHTML !== cellContent) {
										row.innerHTML = cellContent;
									}
									// Update attributes always to be safe or check them
									if (row.getAttribute('data-sell-price') !== sellPrice) row.setAttribute('data-sell-price', sellPrice);
									if (row.getAttribute('data-sell-rate') !== sellRate) row.setAttribute('data-sell-rate', sellRate);
									if (row.getAttribute('data-profit-rate') !== item.profit_rate) row.setAttribute('data-profit-rate', item.profit_rate); // if used elsewhere
									// onclick persists
								} else {
									// Create new row
									row = document.createElement('tr');
									row.setAttribute('data-row-id', rowId);
									row.setAttribute('data-stock-code', item.stock_code);
									row.setAttribute('data-stock-name', item.stock_name);
									row.setAttribute('data-sell-price', sellPrice);
									row.setAttribute('data-sell-rate', sellRate);
									row.setAttribute('onclick', 'selectRow(this)');
									row.innerHTML = cellContent;
									tbody.appendChild(row);
								}
							}
							
							// Remove Deleted Rows
							for (const [id, r] of rowMap) {
								if (!processedIds.has(id)) r.remove();
							}
						}
					}
				})
				.catch(error => {
					console.error('Error updating table:', error);
					const tableContainer = document.getElementById('table-container');
					if (tableContainer) {
						tableContainer.innerHTML = `
							<div class="empty-state error-state" style="border: 2px solid #e74c3c; background-color: #fadbd8; padding: 20px; border-radius: 8px; text-align: center;">
								<h2 style="color: #c0392b; margin-bottom: 10px;">Backend is down. Retrying...</h2>
								<p style="color: #7f8c8d;">Connection to the server failed. Will try again automatically.</p>
							</div>
						`;
					}
				});
		}
		
		function loadAccountAutoSellStatus() {
			fetch('./api/auto-sell')
				.then(response => response.json())
				.then(result => {
					if (result.status === 'success' && result.data) {
						const autoSellData = result.data;
						// Update each account button
						for (const account in autoSellData) {
							updateAccountAutoSellSelect(account, autoSellData[account]);
						}
					}
				})
				.catch(error => {
					console.error('Error loading account auto sell status:', error);
				});
		}
		
		function updateAccountAutoSellSelect(account, mode) {
			const select = document.getElementById('select-auto-sell-' + account);
			if (select) {
				// Normalize mode
				const validModes = ['NONE', 'BUY', 'SELL', 'BOTH'];
				if (typeof mode === 'boolean') {
					mode = mode ? 'SELL' : 'NONE';
				}
				if (!validModes.includes(mode)) {
					mode = 'NONE';
				}
				select.value = mode;
			}
		}
		
		function applyAccountAutoSell(account) {
			const select = document.getElementById('select-auto-sell-' + account);
			if (!select) return;
			
			const selectedMode = select.value;
			
			fetch('./api/auto-sell', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({ account: account, enabled: selectedMode })
			})
			.then(response => response.json())
			.then(result => {
				if (result.status === 'success') {
					updateAccountAutoSellSelect(account, result.enabled);
					showMessage(result.message || `Auto trade mode set to ${result.enabled} for account ${account}`, 'success');
				} else {
					showMessage('Error: ' + (result.message || 'Failed to update auto sell status'), 'error');
				}
			})
			.catch(error => {
				console.error('Error applying account auto sell:', error);
				showMessage('Error applying auto sell: ' + error.message, 'error');
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
		
		function showMessage(message, type) {
			// Simple alert for now since update-message div is removed
			alert(message);
		}
		
		function updateMiche() {
			fetch('./api/miche-data')
				.then(response => response.json())
				.then(result => {
					if (result.status === 'success') {
						const micheData = result.data || [];
						const micheContainer = document.getElementById('miche-container');
						const micheSection = document.getElementById('miche-section');
						
						// Collect all orders into a single list
						const allOrders = [];
						const micheValues = Array.isArray(micheData) ? micheData : Object.values(micheData);
						for (const item of micheValues) {
							const acctNo = item.ACCT || '';
							// Extract oso (unexecuted orders) from each account
							if (item.oso && Array.isArray(item.oso)) {
								for (const order of item.oso) {
									// Add ACCT to each order for cancellation
									const orderWithAcct = {
										...order,
										ACCT: acctNo
									};
									allOrders.push(orderWithAcct);
								}
							}
						}
						
						// Check if we have any data
						const hasData = allOrders.length > 0;
						
						// Always show miche section
						micheSection.style.display = 'block';
						
						// Build HTML for grouped miche orders
						let htmlContent = '';
						
						if (!hasData) {
							// Show table with headers but empty tbody
							htmlContent += `
								<div class="account-group">
									<div class="account-group-header">
										<h2>Orders</h2>
									</div>
									<table>
										<thead>
											<tr>
												<th>Account</th>
												<th>Code</th>
												<th>Name</th>
												<th>Order Type</th>
												<th>Order Qty</th>
												<th>Order / Current</th>
												<th>REMAIN</th>
												<th>Time</th>
												<th>Action</th>
											</tr>
										</thead>
										<tbody>
											<tr>
												<td colspan="9" style="text-align: center; padding: 20px; color: #7f8c8d;">
													No unexecuted orders available
												</td>
											</tr>
										</tbody>
									</table>
								</div>
							`;
						} else {
							// Sort orders: Account -> Stock Code -> Order Type
							allOrders.sort((a, b) => {
								// Sort by Account
								const acctA = a.ACCT || '';
								const acctB = b.ACCT || '';
								if (acctA < acctB) return -1;
								if (acctA > acctB) return 1;
								
								// Sort by Stock Code
								const codeA = a.stk_cd || '';
								const codeB = b.stk_cd || '';
								// Remove 'A' for comparison if present
								const cleanCodeA = codeA.startsWith('A') ? codeA.substring(1) : codeA;
								const cleanCodeB = codeB.startsWith('A') ? codeB.substring(1) : codeB;
								if (cleanCodeA < cleanCodeB) return -1;
								if (cleanCodeA > cleanCodeB) return 1;
								
								// Sort by Order Type (Buy first, then Sell)
								const typeA = a.io_tp_nm || '';
								const typeB = b.io_tp_nm || '';
								if (typeA.includes('매수') && !typeB.includes('매수')) return -1;
								if (!typeA.includes('매수') && typeB.includes('매수')) return 1;
								return 0;
							});
							
							// Single table with one header
							htmlContent += `
								<div class="account-group">
									<div class="account-group-header">
										<h2>Orders</h2>
									</div>
									<table>
										<thead>
											<tr>
												<th>Account</th>
												<th>Code</th>
												<th>Name</th>
												<th>Order Type</th>
												<th>Order Qty</th>
												<th>Order / Current</th>
												<th>REMAIN</th>
												<th>Time</th>
												<th>Action</th>
											</tr>
										</thead>
										<tbody>
							`;
							
							for (const order of allOrders) {
								const stkCd = order.stk_cd || '';
								const stkCdClean = stkCd && stkCd[0] === 'A' ? stkCd.substring(1) : stkCd;
								let ordQty = 0;
								if (order.ord_qty) {
									const ordQtyStr = order.ord_qty.toString().replace(/^0+/, '') || '0';
									ordQty = parseInt(ordQtyStr) || 0;
									if (isNaN(ordQty)) ordQty = 0;
								}
								let osoQty = 0;
								if (order.oso_qty) {
									const osoQtyStr = order.oso_qty.toString().replace(/^0+/, '') || '0';
									osoQty = parseInt(osoQtyStr) || 0;
									if (isNaN(osoQty)) osoQty = 0;
								}
								// Parse ord_pric field - handle zero-padded strings
								let ordPric = 0;
								if (order.ord_pric) {
									const ordPricStr = order.ord_pric.toString().replace(/^0+/, '') || '0';
									ordPric = parseInt(ordPricStr) || 0;
									if (isNaN(ordPric)) ordPric = 0;
								}
								let curPrc = 0;
								if (order.cur_prc) {
									const curPrcStr = order.cur_prc.toString().replace(/^0+/, '') || '0';
									curPrc = parseInt(curPrcStr) || 0;
									if (isNaN(curPrc)) curPrc = 0;
								}
								const ordNo = order.ord_no || '';
								const stexTp = order.stex_tp || '0';
								
								// Format order price / current price
								let priceDisplay = '-';
								if (ordPric > 0 && curPrc > 0) {
									priceDisplay = ordPric.toLocaleString() + ' / ' + curPrc.toLocaleString();
								} else if (ordPric > 0) {
									priceDisplay = ordPric.toLocaleString() + ' / -';
								} else if (curPrc > 0) {
									priceDisplay = '- / ' + curPrc.toLocaleString();
								}
								
								htmlContent += `
									<tr class="miche-row" 
										data-stock-code="${stkCdClean}" 
										data-stock-name="${order.stk_nm || ''}" 
										data-order-price="${ordPric || ''}"
										onclick="selectMicheRow(this)"
										style="cursor: pointer;">
										<td>${order.ACCT}</td>
										<td><strong>${stkCdClean}</strong></td>
										<td>${order.stk_nm || '-'}</td>
										<td>${order.io_tp_nm || '-'}</td>
										<td>${ordQty > 0 ? ordQty.toLocaleString() : '0'}</td>
										<td>${priceDisplay}</td>
										<td><strong>${osoQty > 0 ? osoQty.toLocaleString() : '0'}</strong></td>
										<td>${order.tm || '-'}</td>
										<td>
											<button class="btn-cancel" 
												data-acct="${order.ACCT || ''}"
												data-stex-tp="${stexTp}"
												data-ord-no="${ordNo}"
												data-stk-cd="${stkCd}"
												onclick="event.stopPropagation(); cancelOrder(this)">
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
						// Show empty table even on API error
						const micheSection = document.getElementById('miche-section');
						const micheContainer = document.getElementById('miche-container');
						micheSection.style.display = 'block';
						micheContainer.innerHTML = `
							<div class="account-group">
								<div class="account-group-header">
									<h2>Orders</h2>
								</div>
								<table>
									<thead>
									<tr>
										<th>Code</th>
										<th>Name</th>
										<th>Order Type</th>
										<th>Order Qty</th>
										<th>Order / Current</th>
										<th>REMAIN</th>
										<th>Time</th>
										<th>Action</th>
									</tr>
								</thead>
								<tbody>
									<tr>
										<td colspan="8" style="text-align: center; padding: 20px; color: #7f8c8d;">
											Error loading unexecuted orders
										</td>
									</tr>
									</tbody>
								</table>
							</div>
						`;
					}
				})
				.catch(error => {
					console.error('Error updating miche:', error);
					const micheSection = document.getElementById('miche-section');
					const micheContainer = document.getElementById('miche-container');
					micheSection.style.display = 'block';
					micheContainer.innerHTML = `
						<div class="account-group">
							<div class="account-group-header">
								<h2>Unexecuted Orders</h2>
							</div>
							<table>
								<thead>
									<tr>
										<th>Code</th>
										<th>Name</th>
										<th>Order Type</th>
										<th>Order Qty</th>
										<th>Order / Current</th>
										<th>REMAIN</th>
										<th>Time</th>
										<th>Action</th>
									</tr>
								</thead>
								<tbody>
									<tr>
										<td colspan="8" style="text-align: center; padding: 20px; color: #7f8c8d;">
											Error loading unexecuted orders
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					`;
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
		
		
		function updateSellPrices() {
			// Function disabled - All Sell Prices & Rates section removed
			return;
			// Add cache-busting parameter to ensure fresh data
			const timestamp = new Date().getTime();
			fetch('./api/sell-prices?t=' + timestamp)
				.then(response => response.json())
				.then(result => {
					if (result.status === 'success') {
						const sellPricesData = result.data || {};
						const sellPricesContainer = document.getElementById('sell-prices-container');
						const sellPricesSection = document.getElementById('sell-prices-section');
						
						// Always show sell prices section
						sellPricesSection.style.display = 'block';
						
						// Get all stock codes and filter out entries without price/rate
						const allStockCodes = Object.keys(sellPricesData).sort();
						const validStockCodes = [];
						
						for (const stockCode of allStockCodes) {
							const sellCond = sellPricesData[stockCode];
							// Only include entries that have price or rate
							if (sellCond.price || (sellCond.rate !== undefined && sellCond.rate !== null)) {
								validStockCodes.push(stockCode);
							}
						}
						
						if (validStockCodes.length === 0) {
							sellPricesContainer.innerHTML = `
								<div class="account-group">
									<div class="account-group-header">
										<h2>Sell Prices & Rates</h2>
									</div>
									<table>
										<thead>
											<tr>
												<th>Code</th>
												<th>Name</th>
												<th>Sell Price</th>
												<th>Sell Rate</th>
												<th>Action</th>
											</tr>
										</thead>
										<tbody>
											<tr>
												<td colspan="5" style="text-align: center; padding: 20px; color: #7f8c8d;">
													No sell prices/rates configured
												</td>
											</tr>
										</tbody>
									</table>
								</div>
							`;
							return;
						}
						
						let htmlContent = `
							<div class="account-group">
								<div class="account-group-header">
									<h2>Sell Prices & Rates</h2>
								</div>
								<table>
									<thead>
										<tr>
											<th>Code</th>
											<th>Name</th>
											<th>Sell Price</th>
											<th>Sell Rate</th>
											<th>Action</th>
										</tr>
									</thead>
									<tbody>
						`;
						
						for (const stockCode of validStockCodes) {
							const sellCond = sellPricesData[stockCode];
							
							const stockName = sellCond.stock_name || '-';
							
							let sellPrice = '-';
							if (sellCond.price) {
								try {
									const priceNum = parseFloat(sellCond.price);
									if (!isNaN(priceNum) && priceNum > 0) {
										sellPrice = priceNum.toLocaleString();
									}
								} catch (e) {
									sellPrice = sellCond.price;
								}
							}
							
							let sellRate = '-';
							if (sellCond.rate !== undefined && sellCond.rate !== null) {
								try {
									sellRate = (parseFloat(sellCond.rate) * 100).toFixed(2) + '%';
								} catch (e) {
									sellRate = '-';
								}
							}
							
							htmlContent += `
								<tr data-stock-code="${stockCode}" data-stock-name="${stockName}" data-sell-price="${sellCond.price || ''}" data-sell-rate="${sellCond.rate || ''}" onclick="selectSellPriceRow(this)">
									<td><strong>${stockCode}</strong></td>
									<td>${stockName}</td>
									<td>${sellPrice}</td>
									<td>${sellRate}</td>
									<td>
										<button class="btn-delete-row" onclick="event.stopPropagation(); deleteRowSellPrice('${stockCode}', '${stockName}')" title="Delete sell price/rate">
											Del️
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
						
						sellPricesContainer.innerHTML = htmlContent;
					} else {
						// Show error state
						const sellPricesContainer = document.getElementById('sell-prices-container');
						const sellPricesSection = document.getElementById('sell-prices-section');
						sellPricesSection.style.display = 'block';
						sellPricesContainer.innerHTML = `
							<div class="account-group">
								<div class="account-group-header">
									<h2>Sell Prices & Rates</h2>
								</div>
								<table>
									<thead>
										<tr>
											<th>Code</th>
											<th>Name</th>
											<th>Sell Price</th>
											<th>Sell Rate</th>
											<th>Action</th>
										</tr>
									</thead>
									<tbody>
										<tr>
											<td colspan="5" style="text-align: center; padding: 20px; color: #7f8c8d;">
												Error loading sell prices/rates
											</td>
										</tr>
									</tbody>
								</table>
							</div>
						`;
					}
				})
				.catch(error => {
					console.error('Error updating sell prices:', error);
					const sellPricesContainer = document.getElementById('sell-prices-container');
					const sellPricesSection = document.getElementById('sell-prices-section');
					sellPricesSection.style.display = 'block';
					sellPricesContainer.innerHTML = `
						<div class="account-group">
							<div class="account-group-header">
								<h2>Sell Prices & Rates</h2>
							</div>
							<table>
								<thead>
									<tr>
										<th>Code</th>
										<th>Name</th>
										<th>Sell Price</th>
										<th>Sell Rate</th>
										<th>Action</th>
									</tr>
								</thead>
								<tbody>
									<tr>
										<td colspan="5" style="text-align: center; padding: 20px; color: #7f8c8d;">
											Error loading sell prices/rates
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					`;
				});
		}
		
		function selectSellPriceRow(rowElement) {
			// Remove selected class from all rows
			document.querySelectorAll('#sell-prices-container tbody tr').forEach(tr => {
				tr.classList.remove('selected');
			});

			// Add selected class to clicked row
			rowElement.classList.add('selected');

			// Get stock code, stock name, sell price, and sell rate from row
			const stockCode = rowElement.getAttribute('data-stock-code');
			const stockName = rowElement.getAttribute('data-stock-name') || '';
			const sellPrice = rowElement.getAttribute('data-sell-price') || '';
			const sellRate = rowElement.getAttribute('data-sell-rate') || '';

			// Fill buy section
			document.getElementById('buy-stock-code-input').value = stockCode;
			document.getElementById('buy-stock-name-input').value = stockName;
			document.getElementById('buy-price-input').value = '';
			document.getElementById('buy-amount-input').value = '';

			// Fill int stocks section
			document.getElementById('interested-stock-code-input').value = stockCode;
			document.getElementById('interested-stock-name-input').value = stockName;
			if (sellPrice && sellPrice !== '-') {
				const priceValue = sellPrice.replace(/,/g, '');
				document.getElementById('interested-stock-price-input').value = priceValue;
			} else {
				document.getElementById('interested-stock-price-input').value = '';
			}
			if (sellRate && sellRate !== '-') {
				// Extract percentage value from "5.5%" format or use as-is
				const rateMatch = sellRate.match(/([\d.+-]+)%/);
				if (rateMatch) {
					// Store percentage as-is (no conversion)
					document.getElementById('interested-stock-rate-input').value = rateMatch[1];
				} else {
					// Use as-is (no conversion)
					document.getElementById('interested-stock-rate-input').value = sellRate;
				}
			} else {
				document.getElementById('interested-stock-rate-input').value = '';
			}
			document.getElementById('interested-stock-gaprate-input').value = '';
			
			// Scroll to update section
		}
		
		function updateInterestedStocks() {
			const timestamp = new Date().getTime();
			fetch('./api/interested-stocks?t=' + timestamp)
				.then(response => response.json())
				.then(result => {
					if (result.status === 'success') {
						const interestedStocksData = result.data || {};
						const interestedStocksContainer = document.getElementById('interested-stocks-container');
						const interestedStocksSection = document.getElementById('interested-stocks-section');
						
						// Always show interested stocks section
						interestedStocksSection.style.display = 'block';
						
						// Get all stock codes
						const stockCodes = Object.keys(interestedStocksData).sort();
						
						if (stockCodes.length === 0) {
							interestedStocksContainer.innerHTML = `
								<div class="account-group">
									<table>
										<thead>
											<tr>
												<th>Code</th>
												<th>Name</th>
												<th>COLOR</th>
												<th>BType</th>
												<th>BAmount</th>
												<th>SellPrice</th>
												<th>SellRate</th>
												<th>SellGap</th>
												<th>Action</th>
											</tr>
										</thead>
										<tbody>
											<tr>
												<td colspan="9" style="text-align: center; padding: 20px; color: #7f8c8d;">
													No interested stocks added yet
												</td>
											</tr>
										</tbody>
									</table>
								</div>
							`;
							return;
						}
						
						let htmlContent = `
							<div class="account-group">
								<table>
									<thead>
										<tr>
											<th>Code</th>
											<th>Name</th>
											<th>COLOR</th>
											<th>BType</th>
											<th>BAmount</th>
											<th>SellPrice</th>
											<th>SellRate</th>
											<th>SellGap</th>
											<th>Action</th>
										</tr>
									</thead>
									<tbody>
						`;
						
						// Color mapping: R=빨, O=주, Y=노, G=초, B=파, D=남, V=보
						const colorMap = {
							'R': '빨',
							'O': '주',
							'Y': '노',
							'G': '초',
							'B': '파',
							'D': '남',
							'V': '보'
						};
						
						for (const stockCode of stockCodes) {
							const stockInfo = interestedStocksData[stockCode];
							const stockName = stockInfo.stock_name || '-';
							const stockColor = stockInfo.color || '';
							const stockBtype = stockInfo.btype || '';
							const stockBamount = stockInfo.bamount || '';
							const stockPrice = stockInfo.sellprice || '0';
							const stockRate = stockInfo.sellrate || '0';
							const stockGaprate = stockInfo.sellgap || '0';
							const colorDisplay = stockColor && colorMap[stockColor] ? colorMap[stockColor] : '-';
							
							// Format values for display
							let priceDisplay = '-';
							if (stockPrice && stockPrice !== '0') {
								const priceNum = parseFloat(stockPrice);
								if (!isNaN(priceNum) && priceNum > 0) {
									priceDisplay = priceNum.toLocaleString();
								}
							}
							// Display sellrate as-is from backend (no conversion)
							const rateDisplay = stockRate && stockRate !== '0' ? stockRate : '-';
							let gaprateDisplay = '-';
							if (stockGaprate && stockGaprate !== '0') {
								const gaprateNum = parseFloat(stockGaprate);
								if (!isNaN(gaprateNum) && gaprateNum !== 0) {
									gaprateDisplay = gaprateNum.toLocaleString();
								}
							}
							
							htmlContent += `
								<tr data-stock-code="${stockCode}" data-stock-name="${stockName}" data-stock-color="${stockColor}" data-stock-btype="${stockBtype}" data-stock-bamount="${stockBamount}" data-stock-price="${stockPrice}" data-stock-rate="${stockRate}" data-stock-gaprate="${stockGaprate}" onclick="selectInterestedStockRow(this)">
									<td><strong>${stockCode}</strong></td>
									<td>${stockName}</td>
									<td>${colorDisplay}</td>
									<td>${stockBtype || '-'}</td>
									<td>${stockBamount || '-'}</td>
									<td>${priceDisplay}</td>
									<td>${rateDisplay}</td>
									<td>${gaprateDisplay}</td>
									<td>
										<button class="btn-remove-interested" onclick="event.stopPropagation(); removeInterestedStock('${stockCode}', '${stockName}')" title="Remove from interested list">
											Remove
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
						
						interestedStocksContainer.innerHTML = htmlContent;
					} else {
						// Show error state
						const interestedStocksContainer = document.getElementById('interested-stocks-container');
						const interestedStocksSection = document.getElementById('interested-stocks-section');
						interestedStocksSection.style.display = 'block';
						interestedStocksContainer.innerHTML = `
							<div class="account-group">
								<table>
									<thead>
										<tr>
											<th>Code</th>
											<th>Name</th>
											<th>COLOR</th>
											<th>BType</th>
											<th>BAmount</th>
											<th>SellPrice</th>
											<th>SellRate</th>
											<th>SellGap</th>
											<th>Action</th>
										</tr>
									</thead>
									<tbody>
										<tr>
											<td colspan="9" style="text-align: center; padding: 20px; color: #7f8c8d;">
												Error loading interested stocks
											</td>
										</tr>
									</tbody>
								</table>
							</div>
						`;
					}
				})
				.catch(error => {
					console.error('Error updating interested stocks:', error);
					const interestedStocksContainer = document.getElementById('interested-stocks-container');
					const interestedStocksSection = document.getElementById('interested-stocks-section');
					interestedStocksSection.style.display = 'block';
					interestedStocksContainer.innerHTML = `
						<div class="account-group">
							<table>
								<thead>
									<tr>
										<th>Code</th>
										<th>Name</th>
										<th>COLOR</th>
										<th>BType</th>
										<th>BAmount</th>
										<th>SellPrice</th>
										<th>SellRate</th>
										<th>SellGap</th>
										<th>Action</th>
									</tr>
								</thead>
								<tbody>
									<tr>
										<td colspan="9" style="text-align: center; padding: 20px; color: #7f8c8d;">
											Error loading interested stocks
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					`;
				});
		}
		
		function addInterestedStock() {
			const stockCode = document.getElementById('interested-stock-code-input').value.trim();
			const stockName = document.getElementById('interested-stock-name-input').value.trim();
			const stockColor = document.getElementById('interested-stock-color-input').value.trim();
			const stockBtype = document.getElementById('interested-stock-btype-input').value.trim();
			const stockBamount = document.getElementById('interested-stock-bamount-input').value.trim();
			const stockPrice = document.getElementById('interested-stock-price-input').value.trim();
			const stockRate = document.getElementById('interested-stock-rate-input').value.trim();
			const stockGaprate = document.getElementById('interested-stock-gaprate-input').value.trim();
			
			if (!stockCode) {
				showMessage('Please enter a stock code', 'error');
				return;
			}
			
			// Store sellrate as decimal (user enters decimal, store as-is)
			const data = {
				stock_code: stockCode,
				stock_name: stockName || null,
				color: stockColor || null,
				btype: stockBtype || null,
				bamount: stockBamount ? parseInt(stockBamount) : null,
				sellprice: stockPrice || '0',
				sellrate: stockRate || '0',
				sellgap: stockGaprate || '0'
			};
			
			fetch('./api/interested-stocks', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(data)
			})
			.then(response => response.json())
			.then(result => {
				if (result.status === 'success') {
					showMessage('Stock added/updated in interested list successfully!', 'success');
					document.getElementById('interested-stock-code-input').value = '';
					document.getElementById('interested-stock-name-input').value = '';
					document.getElementById('interested-stock-color-input').value = '';
					document.getElementById('interested-stock-btype-input').value = '';
					document.getElementById('interested-stock-bamount-input').value = '';
					document.getElementById('interested-stock-price-input').value = '';
					document.getElementById('interested-stock-rate-input').value = '';
					document.getElementById('interested-stock-gaprate-input').value = '';
					// Update immediately
					updateInterestedStocks();
				} else {
					showMessage('Error: ' + result.message, 'error');
				}
			})
			.catch(error => {
				showMessage('Error adding stock: ' + error, 'error');
			});
		}
		
		function deleteInterestedStockFromForm() {
			const stockCode = document.getElementById('interested-stock-code-input').value.trim();
			const stockName = document.getElementById('interested-stock-name-input').value.trim();
			
			if (!stockCode) {
				showMessage('Please enter a stock code', 'error');
				return;
			}
			
			removeInterestedStock(stockCode, stockName);
		}
		
		function updateInterestedStockColor(stockCode, color) {
			if (!stockCode) {
				return;
			}
			
			const row = document.querySelector(`tr[data-stock-code="${stockCode}"]`);
			const stockName = row?.getAttribute('data-stock-name') || '';
			const stockBtype = row?.getAttribute('data-stock-btype') || '';
			const stockBamount = row?.getAttribute('data-stock-bamount') || '';
			
			const data = {
				stock_code: stockCode,
				stock_name: stockName || null,
				color: color || null,
				btype: stockBtype || null,
				bamount: stockBamount ? parseInt(stockBamount) : null
			};
			
			fetch('./api/interested-stocks', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(data)
			})
			.then(response => response.json())
			.then(result => {
				if (result.status === 'success') {
					// Update immediately
					updateInterestedStocks();
				} else {
					showMessage('Error updating color: ' + result.message, 'error');
				}
			})
			.catch(error => {
				showMessage('Error updating color: ' + error, 'error');
			});
		}
		
		function removeInterestedStock(stockCode, stockName) {
			if (!stockCode) {
				showMessage('Stock code is missing', 'error');
				return;
			}
			
			if (!confirm(`Remove ${stockName || stockCode} from interested list?`)) {
				return;
			}
			
			fetch('./api/interested-stocks/' + encodeURIComponent(stockCode), {
				method: 'DELETE',
				headers: {
					'Content-Type': 'application/json',
				}
			})
			.then(response => response.json())
			.then(result => {
				if (result.status === 'success') {
					showMessage('Stock removed from interested list successfully!', 'success');
					// Update immediately
					updateInterestedStocks();
				} else {
					showMessage('Error: ' + result.message, 'error');
				}
			})
			.catch(error => {
				showMessage('Error removing stock: ' + error, 'error');
			});
		}
		
		function selectInterestedStockRow(rowElement) {
			// Remove selected class from all rows
			document.querySelectorAll('#interested-stocks-container tbody tr').forEach(tr => {
				tr.classList.remove('selected');
			});
			
			// Add selected class to clicked row
			rowElement.classList.add('selected');
			
			// Get stock code, name, color, btype, and bamount from row
			const stockCode = rowElement.getAttribute('data-stock-code');
			const stockName = rowElement.getAttribute('data-stock-name') || '';
			const stockColor = rowElement.getAttribute('data-stock-color') || '';
			const stockBtype = rowElement.getAttribute('data-stock-btype') || '';
			const stockBamount = rowElement.getAttribute('data-stock-bamount') || '';
			const stockPrice = rowElement.getAttribute('data-stock-price') || '';
			const stockRate = rowElement.getAttribute('data-stock-rate') || '';
			const stockGaprate = rowElement.getAttribute('data-stock-gaprate') || '';
			
			// Fill the interested stocks form fields
			document.getElementById('interested-stock-code-input').value = stockCode;
			document.getElementById('interested-stock-name-input').value = stockName;
			document.getElementById('interested-stock-color-input').value = stockColor;
			document.getElementById('interested-stock-btype-input').value = stockBtype;
			document.getElementById('interested-stock-bamount-input').value = stockBamount;
			document.getElementById('interested-stock-price-input').value = stockPrice !== '0' ? stockPrice : '';
			// Display sellrate as-is from backend (no conversion)
			document.getElementById('interested-stock-rate-input').value = stockRate && stockRate !== '0' ? stockRate : '';
			document.getElementById('interested-stock-gaprate-input').value = stockGaprate !== '0' ? stockGaprate : '';
			
			// Fill buy section
			document.getElementById('buy-stock-code-input').value = stockCode;
			document.getElementById('buy-stock-name-input').value = stockName;
			document.getElementById('buy-price-input').value = '';
			document.getElementById('buy-amount-input').value = '';
			
			// Scroll to interested stocks section
			document.getElementById('interested-stocks-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
		}
		
		function updateInterestedStockBtype(stockCode, btype) {
			if (!stockCode) {
				return;
			}
			
			const row = document.querySelector(`tr[data-stock-code="${stockCode}"]`);
			const stockName = row?.getAttribute('data-stock-name') || '';
			const stockColor = row?.getAttribute('data-stock-color') || '';
			const stockBamount = row?.getAttribute('data-stock-bamount') || '';
			
			const data = {
				stock_code: stockCode,
				stock_name: stockName || null,
				color: stockColor || null,
				btype: btype || null,
				bamount: stockBamount ? parseInt(stockBamount) : null
			};
			
			fetch('./api/interested-stocks', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(data)
			})
			.then(response => response.json())
			.then(result => {
				if (result.status === 'success') {
					// Update immediately
					updateInterestedStocks();
				} else {
					showMessage('Error updating btype: ' + result.message, 'error');
				}
			})
			.catch(error => {
				showMessage('Error updating btype: ' + error, 'error');
			});
		}
		
		function buyStock() {
			const stockCode = document.getElementById('buy-stock-code-input').value.trim();
			const stockName = document.getElementById('buy-stock-name-input').value.trim();
			const price = document.getElementById('buy-price-input').value.trim();
			const amount = document.getElementById('buy-amount-input').value.trim();
			
			if (!stockCode) {
				showMessage('Please enter a stock code', 'error');
				return;
			}
			
			if (!amount || amount === '' || parseInt(amount) <= 0) {
				showMessage('Please enter a valid amount', 'error');
				return;
			}
			
			if (!price || price === '' || parseFloat(price) <= 0) {
				showMessage('Please enter a valid price', 'error');
				return;
			}
			
			// Call buy order API
			const buyData = {
				stock_code: stockCode,
				stock_name: stockName,
				price: price,
				amount: amount
			};
			
			fetch('./api/buy-order', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(buyData)
			})
			.then(response => response.json())
			.then(result => {
				if (result.status === 'success') {
					showMessage(result.message || `Buy order placed: ${amount} shares of ${stockName || stockCode} at ${price}`, 'success');
					// Clear the inputs after successful buy
					document.getElementById('buy-price-input').value = '';
					document.getElementById('buy-amount-input').value = '';
				} else {
					showMessage('Error: ' + result.message, 'error');
				}
			})
			.catch(error => {
				showMessage('Error placing buy order: ' + error, 'error');
			});
		}
		
		function updateInterestedStockBamount(stockCode, bamount) {
			if (!stockCode) {
				return;
			}
			
			const row = document.querySelector(`tr[data-stock-code="${stockCode}"]`);
			const stockName = row?.getAttribute('data-stock-name') || '';
			const stockColor = row?.getAttribute('data-stock-color') || '';
			const stockBtype = row?.getAttribute('data-stock-btype') || '';
			
			const data = {
				stock_code: stockCode,
				stock_name: stockName || null,
				color: stockColor || null,
				btype: stockBtype || null,
				bamount: bamount ? parseInt(bamount) : null
			};
			
			fetch('./api/interested-stocks', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(data)
			})
			.then(response => response.json())
			.then(result => {
				if (result.status === 'success') {
					// Update immediately
					updateInterestedStocks();
				} else {
					showMessage('Error updating bamount: ' + result.message, 'error');
				}
			})
			.catch(error => {
				showMessage('Error updating bamount: ' + error, 'error');
			});
		}
		
		// Auto-update every 1 second
		setInterval(function() {
			updateTable();
			updateMiche();
			updateSellPrices();
			updateInterestedStocks();
		}, 1000);
		
		// Initial update after page load
		updateTable();
		updateMiche();
		updateSellPrices();
		updateInterestedStocks();
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
	global stored_miche_data
	current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	return {"status": "success", "data": stored_miche_data, "timestamp": current_time}

@app.post("/api/cancel-order")
@app.post("/stock/api/cancel-order")
async def cancel_order_api(request: dict, proxy_path: str = "", token: str = Cookie(None)):
	global key_list
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
		access_token = None
		for k, key in key_list.items():
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


def cancel_related_buy_order(stk_cd):
	global stored_miche_data, jango_token
	now = datetime.now().time()
	cancel_count = 0
	for ACCT, miche in stored_miche_data.items():
		if 'oso' in miche:
			oso = miche['oso']
			for m in oso:
				#print('io_tp_nm=', m['io_tp_nm'])
				if m['stk_cd'] == stk_cd and m['io_tp_nm']  == '+매수' :
					result = cancel_order_main(now, jango_token[ACCT], m['stex_tp_txt'], m['ord_no'], stk_cd)
					print('cancel_related_buy_order ', result)
					cancel_count += 1
	print('cancel_related_buy_order {} returns {}.'.format(stk_cd, cancel_count))
	return cancel_count


def issue_buy_order(stk_cd, ord_uv, ord_qty, stex, trde_tp):
	global key_list
	access_token = None
	for k, key in key_list.items():
		access_token = get_token(key['AK'], key['SK'])

		if not access_token:
			return {"status": "error", "message": "Unable to retrieve token"}

		# Convert price and amount to strings (as expected by buy_order)
		ord_uv_str = str(ord_uv)
		ord_qty_str = str(ord_qty)

		print('issue buy order ', ord_uv_str, ord_uv, ord_qty, stex, trde_tp)

		# Place buy order
		ret_status = buy_order(
			MY_ACCESS_TOKEN=access_token,
			dmst_stex_tp=stex,
			stk_cd=stk_cd,
			ord_qty=ord_qty_str,
			ord_uv=ord_uv_str,
			trde_tp=trde_tp,
			cond_uv=''
		)

		print('buy_order_result: {}'.format(ret_status))

		# Check return status
		if isinstance(ret_status, dict):
			rcde = ret_status.get('return_code')
			rmsg = ret_status.get('return_msg', '')
			if rcde and rcde != '0000':
				return {"status": "error", "message": f"Buy order failed: {rmsg}", "return_code": rcde}
	return ret_status


@app.post("/api/buy-order")
@app.post("/stock/api/buy-order")
async def buy_order_api(request: dict, proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to place a buy order"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	try:
		stk_cd = request.get('stock_code')
		stk_nm = request.get('stock_name')
		ord_uv = int(request.get('price'))  # Order price
		ord_amount = int(request.get('amount'))
		ord_qty = ord_amount // ord_uv

		print('buy_order_api: stk_cd={}, stk_nm={}, ord_uv={}, amount={}'.format(
			stk_cd, stk_nm, ord_uv, ord_amount))
		
		if not all([stk_cd, ord_uv, ord_qty]):
			return {"status": "error", "message": "Missing required parameters: stock_code, price, amount"}
		
		# Validate price and amount
		if ord_uv <= 0:
				return {"status": "error", "message": "Price must be greater than 0"}
		if ord_qty <= 0:
				return {"status": "error", "message": "Amount must be greater than 0"}

		# Remove 'A' prefix from stock code if present
		if stk_cd and stk_cd[0] == 'A':
			stk_cd = stk_cd[1:]
		
		# Retrieve token from first account in key_list
		stex = 'KRX'
		trde_tp = '0'

		ret_status = issue_buy_order(stk_cd, ord_uv, ord_qty, stex, trde_tp)

	except Exception as e:
		print('buy_order_api exception: {}'.format(e))
		return {"status": "error", "message": str(e)}

	return {"status": "success", "message": f"Buy order placed: {ord_qty} shares of {stk_nm or stk_cd} at {ord_uv}", "data": ret_status}


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
	sell_prices = {}
	current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	return {"status": "success", "data": sell_prices, "timestamp": current_time}

@app.delete("/api/sell-prices/{stock_code}")
@app.delete("/{proxy_path:path}/api/sell-prices/{stock_code}")
async def delete_sell_prices_api(stock_code: str, proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to delete sell price/rate entry completely"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	global interested_stocks
	print('2797')
	try:
		if not stock_code:
			return {"status": "error", "message": "stock_code is required"}

		print('2802')
		# Delete the entire entry regardless of its contents
		if stock_code in interested_stocks:
			interested_stocks[stock_code]['sellprice'] = '0'
			interested_stocks[stock_code]['sellrate'] = '0'

			# Save to file
			if save_interested_stocks_to_json():
				return {"status": "success", "message": f"Sell price/rate deleted for {stock_code}"}
			else:
				return {"status": "error", "message": "Failed to save to file"}
		else:
			return {"status": "error", "message": f"Stock code {stock_code} not found"}
	except Exception as e:
		print('2814')
		return {"status": "error", "message": str(e)}

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

	try:
		stock_code = request.get('stock_code')
		stock_name = request.get('stock_name')
		price = request.get('price')
		rate = request.get('rate')
		
		if not stock_code:
			return {"status": "error", "message": "stock_code is required"}

		return set_interested_rate(stock_code, stock_name=stock_name, sellprice=price, sellrate=rate)
	except Exception as e:
		return {"status": "error", "message": str(e)}

@app.get("/api/auto-sell")
@app.get("/stock/api/auto-sell")
async def get_auto_sell_api(proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to get auto sell flag status for all accounts"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	global auto_sell_enabled
	return {"status": "success", "data": auto_sell_enabled}

@app.post("/api/auto-sell")
@app.post("/stock/api/auto-sell")
async def set_auto_sell_api(request: dict, proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to set auto sell flag for a specific account"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	global auto_sell_enabled
	try:
		account = request.get('account')
		enabled = request.get('enabled')
		
		if account is None:
			return {"status": "error", "message": "Missing 'account' parameter"}
		if enabled is None:
			return {"status": "error", "message": "Missing 'enabled' parameter"}
		
		# Validate mode
		valid_modes = ['NONE', 'BUY', 'SELL', 'BOTH']
		if enabled not in valid_modes:
			return {"status": "error", "message": f"Invalid mode. Must be one of {valid_modes}"}
			
		auto_sell_enabled[account] = enabled
		# Save to file
		if save_auto_sell_to_json():
			return {"status": "success", "enabled": auto_sell_enabled[account], "message": f"Auto trade set to {auto_sell_enabled[account]} for account {account}"}
		else:
			return {"status": "error", "message": "Failed to save auto sell status to file"}
	except Exception as e:
		return {"status": "error", "message": str(e)}

@app.get("/api/interested-stocks")
@app.get("/{proxy_path:path}/api/interested-stocks")
async def get_interested_stocks_api(proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to get interested stocks list"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	global interested_stocks
	current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	return {"status": "success", "data": interested_stocks, "timestamp": current_time}


'''
@app.middleware("http")
async def print_all_headers(request: Request, call_next):
	headers_dict = dict(request.headers)

	print("===== REQUEST HEADERS =====")
	print(headers_dict)
	print("===========================")
	body_bytes = await request.body()

	if body_bytes:
		try:
			body = json.loads(body_bytes)
			print("===== REQUEST JSON BODY =====")
			print(body)
			print("============================")
		except json.JSONDecodeError:
			print("===== REQUEST BODY (non-JSON) =====")
			print(body_bytes)

	async def receive():
		return {
			"type": "http.request",
			"body": body_bytes,
			"more_body": False,
		}

	request._receive = receive
	return await call_next(request)
'''


def  color_kor_to_eng(color):
	if color == '빨':
		return 'R'
	if color == '주':
		return 'O'
	if color == '노':
		return 'Y'
	if color == '초':
		return 'G'
	if color == '파':
		return 'B'
	if color == '남':
		return 'D'
	if color == '보':
		return 'V'

	return color


def set_interested_rate(stock_code, stock_name='', color=None,
                    btype='', bamount='0',
                    stime='', yyyymmdd='', sellprice='0',
                    sellrate='0', sellgap='0'):
	global interested_stocks
	try:
		if color and color == 'DELETE':
			if stock_code in interested_stocks:
				del interested_stocks[stock_code]
				cancel_related_buy_order(stock_code)
		else:
			if not stock_name or stock_name == '':
				stock_name = get_stockname(stock_code)

			# Add or update the stock in interested list
			if stock_code not in interested_stocks:
				stock = {}
			else:
				stock = interested_stocks[stock_code]

			stock['stock_name'] = stock_name.strip()
			if color :
				color = color_kor_to_eng(color)
				stock['color'] = color.strip()

			if btype :
				stock['btype'] = btype.strip()

			if bamount is not None:
				try:
					bamount_int = int(bamount)
					stock['bamount'] = bamount_int
				except (ValueError, TypeError):
					pass

			if stime:
				stock['stime'] = stime.strip()

			if yyyymmdd:
				stock['yyyymmdd'] = yyyymmdd.strip()

			stock['sellprice'] = sellprice
			stock['sellrate'] = sellrate
			stock['sellgap'] = sellgap
			if not 'clprice' in stock:
				stock['clprice'] = '0'

			interested_stocks[stock_code] = stock

	# Save to file
		if save_interested_stocks_to_json():
			return {"status": "success", "message": f"Stock {stock_code} added/updated in interested list",
	    	    "data": interested_stocks}
		else:
			return {"status": "error", "message": "Failed to save to file"}
	except Exception as ex :
		traceback.print_exc()
		return {"status": "error", "message": str(ex) }


@app.post("/api/interested-stocks")
@app.post("/{proxy_path:path}/api/interested-stocks")
async def add_interested_stock_api(request: dict, proxy_path: str = "",
								   token: str = Cookie(None),
								   pctoken: str | None = Cookie(default=None),):
	"""API endpoint to add a stock to interested stocks list"""
	f = False
	# Check authentication
	if f:
		if token:
			print('token={}'.format(token))
		if pctoken:
			print('pctoken={}'.format(pctoken))

	if pctoken and pctoken == 'allow_interest_pc':
		pass
	else:
		if not token or not verify_token(token):
			raise HTTPException(
				status_code=status.HTTP_401_UNAUTHORIZED,
				detail="Not authenticated"
			)

	global interested_stocks
	try:
		stock_code = request.get('stock_code')
		stock_name = request.get('stock_name')
		color = request.get('color')
		btype = request.get('btype')
		bamount = request.get('bamount')
		stime = request.get('stime')
		yyyymmdd = request.get('yyyymmdd')
		sellprice = request.get('sellprice', '0')
		sellrate = request.get('sellrate', '0')
		sellgap = request.get('sellgap', '0')

		print('stime = {}, yyyymmdd = {}'.format(stime, yyyymmdd))

		if not stock_code:
			return {"status": "error", "message": "stock_code is required"}

		return set_interested_rate(stock_code, stock_name, color=color,
		                    btype = btype, bamount = bamount,
		                    stime = stime, yyyymmdd = yyyymmdd, sellprice = sellprice,
		                    sellrate = sellrate, sellgap = sellgap)
	except Exception as e:
		print('Exception-> {}'.format(e))
		return {"status": "error", "message": str(e)}

@app.delete("/api/interested-stocks/{stock_code}")
@app.delete("/{proxy_path:path}/api/interested-stocks/{stock_code}")
async def delete_interested_stock_api(stock_code: str, proxy_path: str = "", token: str = Cookie(None)):
	"""API endpoint to remove a stock from interested stocks list"""
	# Check authentication
	if not token or not verify_token(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Not authenticated"
		)
	global interested_stocks
	try:
		if not stock_code:
			return {"status": "error", "message": "stock_code is required"}
		
		# Remove the stock from interested list
		if stock_code in interested_stocks:
			del interested_stocks[stock_code]
			# Save to file
			if save_interested_stocks_to_json():
				return {"status": "success", "message": f"Stock {stock_code} removed from interested list"}
			else:
				return {"status": "error", "message": "Failed to save to file"}
		else:
			return {"status": "error", "message": f"Stock code {stock_code} not found in interested list"}
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



import requests
import json

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


# 실행 구간
def get_stockname(stk_cd):
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
		return json['name']

	print('No name field in fn_ka10100 result')
	return ''


# 실행 구간
if __name__ == '__main__':
	set_new_day()
	uvicorn.run(app, host="0.0.0.0", port=8006, access_log=False)