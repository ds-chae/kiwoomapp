import traceback
import copy

import requests
import json
import os
from datetime import datetime, timedelta, time, date
from dotenv import load_dotenv
from au1001 import get_token, get_key_list, get_one_token
import time as time_module
import threading
from fastapi import FastAPI, HTTPException, status, Cookie, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import uvicorn
from contextlib import asynccontextmanager
import secrets
import socket

from ka10080 import get_bun_chart, get_price_index
from ka10081 import get_day_chart
from ka10100 import get_stockname

now = datetime.now()
today_yyyymmdd = now.strftime("%Y%m%d")

# Interested stocks list
INTERESTED_STOCKS_FILE = 'interested_stocks.json'
interested_stocks = {}

# Jango data file
JANGO_DATA_FILE = 'jango_data.json'

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

# Global storage for previous jango data (simplified format: {stock_code: amount})
previous_jango_data_simplified = {}

# Global storage for miche data (updated by timer handler)
stored_miche_data = {}

# Global flag to track if cleanup has run today at 20:30
cleanup_run_today = False

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
        #print('get_jango => Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
        #print('get_jango => Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON ÀÀ´äÀ» ÆÄ½ÌÇÏ¿© Ãâ·Â
        #print('get_jango => Finish:')
        #print('')

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
def get_jango(market = 'KRX'):
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
    return start <= now.time() <= end

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
            log_print(stk_cd, 'calling fn_ka1007 in get_upper_limit succeeded')
            rstk_cd = response.get('stk_cd', ' ')
            if rstk_cd[0] == 'A':
                rstk_cd = rstk_cd[1:]
            if stk_cd == rstk_cd:
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


def cancel_different_sell_order(now, ACCT, stk_cd, stk_nm, new_price):
    global stored_miche_data
    cancel_count = 0
    miche = []
    if ACCT in stored_miche_data:
        if 'oso' in stored_miche_data[ACCT]:
            miche = stored_miche_data[ACCT]['oso']
    for m in miche:
        #print('io_tp_nm=', m['io_tp_nm'])
        if m['stk_cd'] == stk_cd and m['io_tp_nm']  == '-매도' :
            oqty = m['ord_qty']
            oqp = int(m['ord_pric'])
            if oqp != new_price:
                result = cancel_order_main(now, jango_token[ACCT], m['stex_tp_txt'], m['ord_no'], stk_cd)
                log_print(stk_cd, '{} cancel_different_sell_order {} {} old price={}, new price={}, result={}'.format(
                          now, stk_cd, stk_nm, oqp, new_price, result))
                cancel_count += 1
    if cancel_count != 0:
        log_print(stk_cd, 'cancel_different_sell_order {} {} {} {} returns {}.'.format(ACCT, stk_cd, stk_nm, new_price, cancel_count))
    return cancel_count


def get_low_after_high(chart):
    high_index = 0
    low_index = 0
    high_price = 0
    low_price = 0
    chartlen = len(chart)
    if chartlen < 416 :
        return 0

    prd = 416
    i = 0
    # find high
    while i < prd:
        buntick = chart[i]
        hpc = int(buntick['high_pric'])
        if hpc < 0:
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
    while hidx >= 0:
        tlpc = int(chart[hidx]['low_pric'])
        if tlpc < 0:
            tlpc = -tlpc
        if low_price > tlpc:
            low_price = tlpc
        hidx -= 1
    return low_price

last_get_bun_time = {}
last_cl_price = {}


def calculate_sell_price(MY_ACCESS_TOKEN, pur_pric, sell_cond, stk_cd, stk_nm):
    global bun_prices, last_get_bun_time, last_cl_price

    ord_uv = 0
    if 'sellprice' in sell_cond:
        ord_uv = sell_cond['sellprice']
    if ord_uv != '0':
        return int(ord_uv)

    sellrate = float(sell_cond.get('sellrate', '0.0'))
    if sellrate != 0.0 :
        # sellrate is stored as-is (percentage), divide by 100 for calculation
        s_rate_percent = sellrate
        s_rate = s_rate_percent / 100.0
        s_price = pur_pric * (1.0 + s_rate)
        s_price = round_trunc(s_price)
        return s_price

    sellgap = float(sell_cond.get('sellgap', '0.0')) / 100.
    if sellgap != 0.0 :
        if stk_cd in last_get_bun_time:
            last_bun_time = last_get_bun_time[stk_cd]
            seconds = (now - last_bun_time).total_seconds()
            if seconds < 15 :
                return last_cl_price.get(stk_cd, 0)

        last_get_bun_time[stk_cd] = now
        if not stk_cd in gap_prices:
            gap_prices[stk_cd] = get_gap_price(MY_ACCESS_TOKEN, stk_cd)
        gap_price = gap_prices[stk_cd]
        log_print(stk_cd, '{} before get_low_after_high'.format(now))
        bun_chart = get_bun_chart(MY_ACCESS_TOKEN, stk_cd, stk_nm)
        lowest = get_low_after_high(bun_chart)
        log_print(stk_cd, '{} get_low_after_high {} returns {}'.format(now, stk_nm, lowest))
        if lowest != 0 :
            gap = float(gap_price['gap']) * 2
            cl_price = round_trunc(int(lowest + gap * sellgap))
            last_cl_price[stk_cd] = cl_price
            log_print(stk_cd, '{} cl_price for {} {} is {}, gap={}, lowest={}, gaprate={}'.format(now, stk_cd, stk_nm, cl_price, gap, lowest, sellgap))
            return cl_price

    return 0


def call_sell_order(ACCT, MY_ACCESS_TOKEN, market, stk_cd, stk_nm, indv, sell_cond):
    global current_status, working_status

    trde_able_qty = indv.get("trde_able_qty", "0")
    rmnd_qty = indv.get('rmnd_qty', "0")
    pur_pric_str = indv.get('pur_pric', '0')
    pur_pric = float(pur_pric_str) if pur_pric_str else 0.0

    sell_price = calculate_sell_price(MY_ACCESS_TOKEN, pur_pric, sell_cond, stk_cd, stk_nm)

    if sell_price == '0': # price is not calculated
        return
    upperlimit = get_upper_limit(MY_ACCESS_TOKEN, stk_cd)
    if sell_price > upperlimit :
        log_print(stk_cd, '{} {} {} exceed upper limit {}'.format(stk_cd, stk_nm, sell_price, upperlimit))
        return

    # if any cancelled sell order, try next
    cancel_count = cancel_different_sell_order(now, ACCT, stk_cd, stk_nm, sell_price)
    if cancel_count > 0 :
        return

    trde_able_qty_int = int(trde_able_qty) if trde_able_qty else 0
    if trde_able_qty_int == 0:
        return

    working_status = 'call sell_order()'
    trde_tp = '0'  # 매매구분 0:보통 , 3:시장가 , 5:조건부지정가 , 81:장마감후시간외 , 61:장시작전시간외, 62:시간외단일가 , 6:최유리지정가 , 7:최우선지정가 , 10:보통(IOC) , 13:시장가(IOC) , 16:최유리(IOC) , 20:보통(FOK) , 23:시장가(FOK) , 26:최유리(FOK) , 28:스톱지정가,29:중간가,30:중간가(IOC),31:중간가(FOK)
    log_print(stk_cd, 'sell_order({} {} qty={} price={})'.format(stk_cd, stk_nm, trde_able_qty_int, sell_price))
    ret_status = sell_order(MY_ACCESS_TOKEN, dmst_stex_tp=market, stk_cd=stk_cd,
                            ord_qty=str(trde_able_qty_int), ord_uv=str(sell_price), trde_tp=trde_tp, cond_uv='')
    log_print(stk_cd, ret_status)
    test_ret_status(stk_cd, ret_status)


wait_hour_change = False


def test_ret_status(stk_cd, ret_status):
    global now, wait_hour_change
    if not isinstance(ret_status, dict):
        return

    rcde = ret_status.get('return_code')
    rmsg = ret_status.get('return_msg', '')
    if rmsg and len(rmsg) > 13:
        code = rmsg[7:13]
        if code == '507615':
            not_nxt_cd[stk_cd] = True
        if code == '571489':
            set_new_day(False)
            print('No trading day, set new_day to False')
        if code == '505182': # 장개시전입니다.)', 'return_code': 20}
            print(rmsg)
            wait_hour_change = True
        print(now, rcde)


jango_token = {}

def sell_jango(jango, market):
    global auto_sell_enabled, current_status, jango_token, now, working_status
    global new_day
    if not new_day:
        return
    working_status = 'begin sell_jango()'
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
                call_sell_order(ACCT, MY_ACCESS_TOKEN, market, stk_cd, stk_nm, indv, sell_cond)
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
oso 미체결 LIST    N       
- acnt_no   계좌번호    String  N   20  
- ord_no    주문번호    String  N   20  
- mang_empno    관리사번    String  N   20  
- stk_cd    종목코드    String  N   20  
- tsk_tp    업무구분    String  N   20  
- ord_stt   주문상태    String  N   20  
- stk_nm    종목명 String  N   40  
- ord_qty   주문수량    String  N   20  
- ord_pric  주문가격    String  N   20  
- oso_qty   미체결수량   String  N   20  
- cntr_tot_amt  체결누계금액  String  N   20  
- orig_ord_no   원주문번호   String  N   20  
- io_tp_nm  주문구분    String  N   20  
- trde_tp   매매구분    String  N   20  
- tm    시간  String  N   20  
- cntr_no   체결번호    String  N   20  
- cntr_pric 체결가 String  N   20  
- cntr_qty  체결량 String  N   20  
- cur_prc   현재가 String  N   20  
- sel_bid   매도호가    String  N   20  
- buy_bid   매수호가    String  N   20  
- unit_cntr_pric    단위체결가   String  N   20  
- unit_cntr_qty 단위체결량   String  N   20  
- tdy_trde_cmsn 당일매매수수료 String  N   20  
- tdy_trde_tax  당일매매세금  String  N   20  
- ind_invsr 개인투자자   String  N   20  
- stex_tp   거래소구분   String  N   20  0 : 통합, 1 : KRX, 2 : NXT
- stex_tp_txt   거래소구분텍스트    String  N   20  통합,KRX,NXT
- sor_yn    SOR 여부값 String  N   20  Y,N
- stop_pric 스톱가 String  N   20  스톱지정가주문 스톱가
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
    log_print(stk_cd, 'cancel_order_main: ord_no={}'.format(ord_no))
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


def log_print(stk_cd, msg):
    """Append log message to file: logs/yyyymmdd/stock_code_stock_name.txt"""
    global today_yyyymmdd, interested_stocks
    
    try:
        # Get yyyymmdd from global variable
        yyyymmdd = today_yyyymmdd
        
        # Get stock name from interested_stocks if available, otherwise use get_stockname
        stk_nm = ''
        if stk_cd in interested_stocks:
            stk_nm = interested_stocks[stk_cd].get('stock_name', '')
        
        if not stk_nm:
            try:
                stk_nm = get_stockname(stk_cd)
            except:
                stk_nm = stk_cd  # Fallback to stock code if get_stockname fails
        
        # Create directory structure if it doesn't exist
        log_dir = os.path.join('logs', yyyymmdd)
        os.makedirs(log_dir, exist_ok=True)
        
        # Create log file name: stock_code_stock_name.txt
        log_filename = f"{stk_cd}_{stk_nm}.txt"
        log_filepath = os.path.join(log_dir, log_filename)
        
        # Append message to log file with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {msg}\n"
        
        with open(log_filepath, 'a', encoding='utf-8') as f:
            f.write(log_line)
            
    except Exception as e:
        # Don't fail silently, but don't crash the program either
        print(f"Error in log_print for {stk_cd}: {e}")


def buy_cl(now):
    global order_count, interested_stocks, gap_prices, bun_charts
    global stored_jango_data, stored_miche_data, key_list

    gap_prices = {} # clear on each call

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

gap_prices = {}

def buy_cl_by_account(ACCT, MY_ACCESS_TOKEN):
    global order_count, working_status
    global gap_prices, new_day

    working_status = 'in buy_cl_by_account'
    for stk_cd in interested_stocks:
        int_stock = interested_stocks[stk_cd]
        btype = int_stock.get('btype', '')
        if btype == 'CL':
            if not stk_cd in gap_prices:
                gap_prices[stk_cd] = get_gap_price(MY_ACCESS_TOKEN, stk_cd)

            buy_cl_stk_cd(ACCT, MY_ACCESS_TOKEN, stk_cd, int_stock, gap_prices[stk_cd])
        if not new_day:
            break
    pass


def buy_cl_stk_cd(ACCT, MY_ACCESS_TOKEN, stk_cd, int_stock, gap_price):
    global working_status, order_count, now
    stk_nm = int_stock['stock_name']

    working_status = 'in buy_cl_stk_cd'
    ordered = order_count[ACCT]
    if stk_cd in ordered and ordered[stk_cd] >= 2:
        return
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
    log_print(stk_cd, 'ordered count for {} {} {} is {}, bsum={}'.format(ACCT, stk_cd, stk_nm, ordered[stk_cd], bsum))
    if ordered[stk_cd] >= 2:
        return

    if not stk_cd in gap_prices:
        log_print(stk_cd, 'getting bun_chart or bun_price for {} {} failed'.format(stk_cd, stk_nm));
        return

    price_index = get_price_index(int_stock['color'])
    stex = 'KRX'
    trde_tp = '0'
    if ordered[stk_cd] < 1 :
        bp = gap_price['price'][price_index]
        buy_rate = (float(gap_price.get('current_price', 0))-bp) / bp # 현재 가격과 매수 가격의 차이
        if buy_rate >= 0.05 : # 매수 가격이랑 5%이상 차이가 난다면 매수 하지 않는다,
            log_print(stk_cd, '{} gap over skip for {} {} {} {}'.format(now, stk_cd, stk_nm, bp, buy_rate))
        else:
            ord_price = round_trunc(bp)
            ord_qty = bamount // ord_price
            if ord_qty > 0 :
                #ret_status = buy_order(MY_ACCESS_TOKEN, stex, stk_cd, str(ord_qty), str(ord_price), trade_tp=trde_tp, cond_uv='')
                ret_status = buy_order(MY_ACCESS_TOKEN, stex, stk_cd, str(ord_qty), str(ord_price), trde_tp=trde_tp, cond_uv='')
                log_print(stk_cd, '1_buy_order_result: {}'.format(ret_status))
                test_ret_status(stk_cd, ret_status)
            ordered[stk_cd] += 1
            log_print(stk_cd, 'price:{} current buy order for {} {} {} is {}'.format(ord_price, ACCT, stk_cd, stk_nm, ordered[stk_cd]))
    if ordered[stk_cd] < 2:
        bp = gap_price['price'][price_index+1]
        buy_rate = (float(gap_price.get('current_price', 0))-bp) / bp # 현재 가격과 매수 가격의 차이
        if buy_rate >= 0.05 : # 매수 가격이랑 5%이상 차이가 난다면 매수 하지 않는다,
            log_print(stk_cd, '{} gap over skip for {} {} {} {}'.format(now, stk_cd, stk_nm, bp, buy_rate))
        else:
            ord_price = round_trunc(bp)
            ord_qty = bamount // ord_price
            # ret_status = buy_order(MY_ACCESS_TOKEN, stex, stk_cd, str(ord_qty), str(ord_price), trade_tp=trde_tp, cond_uv='')
            if ord_qty > 0 :
                ret_status = buy_order(MY_ACCESS_TOKEN, stex, stk_cd, str(ord_qty), str(ord_price), trde_tp=trde_tp, cond_uv='')
                log_print(stk_cd, '2_buy_order_result: {}'.format(ret_status))
                test_ret_status(stk_cd, ret_status)
            ordered[stk_cd] += 1
            log_print(stk_cd, 'price:{} current buy order for {} {} {} is {}'.format(ord_price, ACCT, stk_cd, stk_nm, ordered[stk_cd]))

    pass


current_status = ''
working_status = 'initial'
get_miche_failed = True

def daily_work():
    global new_day, krx_first, current_status, now
    global nxt_start_time, nxt_end_time, krx_start_time,nxt_cancelled, krx_end_time, nxt_fin_time
    global stored_jango_data, stored_miche_data, get_miche_failed, working_status
    global previous_jango_data_simplified

    # Get new jango data
    try:
        new_jango_data = get_jango()
    except Exception as e:
        print(f"Error updating jango data: {e}")
        return

    try:
        stored_miche_data = get_miche()
    except Exception as e:
        get_miche_failed = True
        print(f"Error updating miche data: {e}")
        return

    # Extract stock codes and amounts from current jango data
    current_stocks = extract_stock_codes_and_amounts(new_jango_data)
    
    # Check if jango data has changed by comparing stock codes and amounts
    jango_data_changed = (previous_jango_data_simplified != current_stocks)
    
    if jango_data_changed:
        # Save new jango data only when differences are found
        save_jango_data_to_json(new_jango_data)
        
        # Check for sold stocks before updating previous data
        if previous_jango_data_simplified:
            check_and_handle_sold_stocks(previous_jango_data_simplified, new_jango_data)
        
        # Update previous jango data to current for next comparison
        previous_jango_data_simplified = current_stocks.copy()
    
    stored_jango_data = new_jango_data
    if is_between(now, nxt_start_time, nxt_end_time):
        current_status = 'NXT'
        sell_jango(stored_jango_data, 'NXT')
    elif is_between(now, nxt_end_time, krx_start_time):
        current_status = 'NXT->KRX'
        if not nxt_cancelled:
            nxt_cancelled = True
            cancel_nxt_trade(now)
    elif is_between(now, krx_start_time, nxt_fin_time):
        if is_between(now, krx_start_time, krx_end_time):
            current_status = 'KRX'
            if not krx_first:
                print('{} krx_first get_jango and sell_jango.'.format(now))
                krx_first = True
            sell_jango(stored_jango_data, 'KRX')
            working_status='calling buy_cl'
            buy_cl(now)
        else:
            current_status = 'NXT'
    else:
        if (new_day):
            set_new_day(False)
            print('{} {} Setting new day=False'.format(cur_date(), now))


def set_new_day(tf):
    global new_day, waiting_shown, no_working_shown, nxt_cancelled, ktx_first, current_status
    global updown_list, access_token, now, today_yyyymmdd

    if tf:
        if new_day:
            return
        print('{} Setting new_day=True, clearing variables.'.format(now))
        now = datetime.now()
        today_yyyymmdd = now.strftime("%Y%m%d")
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
    else:
        if not new_day:
            return
        print('{} new_day is switching OFF'.format(now))
        new_day = False
        current_status = 'OFF'


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
        current_date = datetime.now().strftime("%Y%m%d")
        for stk in interested_stocks:
            log_print(stk, 'istk, stk={}'.format(stk))
            stock = interested_stocks[stk]
            stk_nm = stock.get('stock_name', '')
            log_print(stk, 'interested stock_name={}'.format(stk_nm))
            if stk_nm == '':
                print('getting stock name for {}'.format(stk))
                stk_nm = get_stockname(stk)
                stock['stock_name'] = stk_nm
                modified = True
            if 'color' in stock:
                stock['color'] = color_kor_to_eng(stock['color'])
            # Add yyyymmdd field if empty or missing
            yyyymmdd = stock.get('yyyymmdd', '')
            if yyyymmdd == '':
                print('adding yyyymmdd={} for {}'.format(current_date, stk))
                stock['yyyymmdd'] = current_date
                modified = True
            log_print(stk, 'in istk {} {} {}'.format(stock.get('btype', 'BT'), stock.get('color', 'NC'), stock.get('yyyymmdd', 'YMD')))

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

def extract_stock_codes_and_amounts(jango_data):
    """Extract stock codes and amounts (quantities) from jango data"""
    stock_data = {}  # {stock_code: total_amount}
    try:
        if isinstance(jango_data, dict):
            iterator = jango_data.values()
        else:
            iterator = jango_data
        
        for account in iterator:
            if account.get("return_code") != 0:
                continue
            
            acnt_evlt_remn_indv_tot = account.get("acnt_evlt_remn_indv_tot", [])
            
            for stock in acnt_evlt_remn_indv_tot:
                stk_cd = stock.get('stk_cd', '')
                # Remove 'A' prefix if present
                if stk_cd and stk_cd[0] == 'A':
                    stk_cd_clean = stk_cd[1:]
                else:
                    stk_cd_clean = stk_cd
                
                if stk_cd_clean:
                    # Get quantity (try rmnd_qty first, then trde_able_qty)
                    qty = int(stock.get('rmnd_qty', '0'))
                    stock_data[stk_cd_clean] = qty
    except Exception as e:
        print(f"Error extracting stock codes and amounts from jango data: {e}")
    
    return stock_data

def save_jango_data_to_json(jango_data):
    """Save jango data to JSON file (only stock codes and amounts)"""
    try:
        # Extract only stock codes and amounts
        stock_data = extract_stock_codes_and_amounts(jango_data)
        
        with open(JANGO_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(stock_data, f, indent=2, ensure_ascii=False)
        print(f"Saved jango data (stock codes and amounts) to {JANGO_DATA_FILE}")
        return True
    except Exception as e:
        print(f"Error saving jango data: {e}")
        return False

def load_jango_data_from_json():
    """Load jango data from JSON file (stock codes and amounts format)"""
    try:
        if os.path.exists(JANGO_DATA_FILE):
            with open(JANGO_DATA_FILE, 'r', encoding='utf-8') as f:
                stock_data = json.load(f)
                print(f"Loaded jango data (stock codes and amounts) from {JANGO_DATA_FILE}")
                return stock_data
        else:
            print(f"Jango data file {JANGO_DATA_FILE} does not exist")
            return {}
    except Exception as e:
        print(f"Error loading jango data: {e}")
        return {}

def get_stock_codes_from_jango(jango_data):
    """Extract all stock codes from jango data (for backward compatibility)"""
    stock_data = extract_stock_codes_and_amounts(jango_data)
    return set(stock_data.keys())

def check_and_handle_sold_stocks(previous_jango_data, current_jango_data):
    """Check if any stocks were sold and handle btype changes"""
    global interested_stocks
    
    # previous_jango_data and current_jango_data are dicts of {stock_code: amount}
    # Extract stock codes and amounts from current jango data (full format)
    current_stocks = extract_stock_codes_and_amounts(current_jango_data) if current_jango_data else {}
    
    # previous_jango_data is already in simplified format {stock_code: amount}
    previous_stocks = previous_jango_data if previous_jango_data else {}
    
    # Find stocks that were in previous holdings but not in current (sold)
    # or stocks where amount decreased to 0
    sold_stocks = set()
    for stk_cd, prev_amount in previous_stocks.items():
        current_amount = current_stocks.get(stk_cd, 0)
        if prev_amount > 0 and current_amount == 0:
            sold_stocks.add(stk_cd)
    
    if not sold_stocks:
        return
    
    print(f"Detected sold stocks: {sold_stocks}")
    
    # Check each sold stock
    modified = False
    for stk_cd in sold_stocks:
        if stk_cd in interested_stocks:
            stock_info = interested_stocks[stk_cd]
            previous_btype = stock_info.get('btype', '')
            
            # If previous btype was 'CL', change to 'SCL'
            if previous_btype == 'CL':
                log_print(stk_cd, f"Stock {stk_cd} was sold and had btype='CL', changing to 'SCL'")
                stock_info['btype'] = 'SCL'
                modified = True
                
        # Cancel buy orders for this stock
        cancel_related_buy_order(stk_cd)
    
    # Save if modified
    if modified:
        save_interested_stocks_to_json()
        print("Updated interested_stocks after handling sold stocks")

def get_account_holdings_stock_codes():
    """Get set of all stock codes currently in account holdings"""
    global stored_jango_data
    holdings_stock_codes = set()
    
    try:
        all_jango = stored_jango_data
        if isinstance(all_jango, dict):
            iterator = all_jango.values()
        else:
            iterator = all_jango
        
        for account in iterator:
            if account.get("return_code") != 0:
                continue
            
            acnt_evlt_remn_indv_tot = account.get("acnt_evlt_remn_indv_tot", [])
            
            for stock in acnt_evlt_remn_indv_tot:
                stk_cd = stock.get('stk_cd', '')
                # Remove 'A' prefix if present
                if stk_cd and stk_cd[0] == 'A':
                    stk_cd_clean = stk_cd[1:]
                else:
                    stk_cd_clean = stk_cd
                
                if stk_cd_clean:
                    holdings_stock_codes.add(stk_cd_clean)
    except Exception as e:
        print(f"Error getting account holdings stock codes: {e}")
    
    return holdings_stock_codes

def cleanup_old_interested_stocks():
    """Delete interested stocks that are 10+ days old and not in account holdings"""
    global interested_stocks, cleanup_run_today
    
    try:
        # Get current date
        current_date = datetime.now().date()
        
        # Get all stock codes in account holdings
        holdings_stock_codes = get_account_holdings_stock_codes()
        
        # Track stocks to delete
        stocks_to_delete = []
        
        # Iterate through interested_stocks
        for stock_code, stock_info in interested_stocks.items():
            yyyymmdd = stock_info.get('yyyymmdd', '')
            
            # Skip if yyyymmdd is missing or invalid
            if not yyyymmdd or len(yyyymmdd) != 8 or not yyyymmdd.isdigit():
                continue
            
            # Parse the date
            try:
                stock_date = datetime.strptime(yyyymmdd, '%Y%m%d').date()
            except ValueError:
                print(f"Invalid date format in interested_stocks for {stock_code}: {yyyymmdd}")
                continue
            
            # Calculate days passed
            days_passed = (current_date - stock_date).days
            
            # Check if 10 days have passed
            if days_passed >= 10:
                # Check if stock is NOT in account holdings
                if stock_code not in holdings_stock_codes:
                    stocks_to_delete.append(stock_code)
                    print(f"Marking {stock_code} ({stock_info.get('stock_name', '')}) for deletion: {days_passed} days old, not in holdings")
        
        # Delete marked stocks
        if stocks_to_delete:
            for stock_code in stocks_to_delete:
                del interested_stocks[stock_code]
                print(f"Deleted {stock_code} from interested_stocks (10+ days old, not in holdings)")
            
            # Save if any deletions occurred
            if stocks_to_delete:
                save_interested_stocks_to_json()
                print(f"Cleanup completed: deleted {len(stocks_to_delete)} old interested stocks")
        else:
            print("Cleanup completed: no old interested stocks to delete")
        
        # Mark cleanup as run today
        cleanup_run_today = True
        
    except Exception as e:
        print(f"Error in cleanup_old_interested_stocks: {e}")
        traceback.print_exc()

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
    global previous_jango_data_simplified

    # Startup
    print("Starting application...")
    try:
        load_dictionaries_from_json()
        print("Dictionaries loaded successfully")
    except Exception as e:
        print(f"Error loading dictionaries: {e}")

    fill_charts_for_CL(get_one_token())

    # Initialize stored jango data - first try to load from file, then update
    print("Initializing jango data...")
    now = datetime.now()
    
    # Load previous jango data from file
    previous_jango_data_simplified = load_jango_data_from_json()
    
    try:
        stored_jango_data = get_jango('KRX')
        print("KRX jango data initialized")
        print(stored_jango_data)
        # Extract stock codes and amounts from current jango data
        current_stocks = extract_stock_codes_and_amounts(stored_jango_data)
        
        # Check if jango data has changed by comparing stock codes and amounts
        jango_data_changed = (previous_jango_data_simplified != current_stocks)
        
        if jango_data_changed:
            print('{} jango changed.'.format(now))
            # Save jango data to file only when differences are found
            save_jango_data_to_json(stored_jango_data)
            
            # Check for sold stocks if we had previous data
            if previous_jango_data_simplified:
                check_and_handle_sold_stocks(previous_jango_data_simplified, stored_jango_data)
            
            # Update previous jango data to current for next comparison
            previous_jango_data_simplified = current_stocks.copy()
        else:
            print("Jango data unchanged, skipping save")
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
    global prev_hour, new_day, stored_jango_data, stored_miche_data, working_status, now, cleanup_run_today
    global wait_hour_change

    now = datetime.now()
    now_hour = now.hour
    
    # Check if it's 20:30 and cleanup hasn't run today
    if now_hour == 20 and now.minute == 30 and not cleanup_run_today:
        try:
            print(f"{cur_date()} Running cleanup of old interested stocks at 20:30...")
            cleanup_old_interested_stocks()
        except Exception as e:
            print(f"Error running cleanup at 20:30: {e}")
            traceback.print_exc()
    
    # Reset cleanup flag at midnight (00:00)
    if now_hour == 0 and now.minute == 0:
        cleanup_run_today = False
    
    if prev_hour is not None and now_hour != prev_hour:
        wait_hour_change = False
        print('{} Hour change from {} to {}'.format(cur_date(), prev_hour, now_hour))
    prev_hour = now_hour
    if wait_hour_change: # 장 개시 전이면 한시간씩 기다린다.
        return

    if is_between(now, day_start_time, nxt_start_time):
        set_new_day(True)
    else:
        try:
            daily_work()
        except Exception as ex:
            traceback.print_exc()
            print('currrent status={}'.format(working_status))

def format_account_data():
    """Format account data for display in UI"""
    global stored_jango_data
    try:
        # Determine which market is active based on current time
        now = datetime.now()

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
    print('token={}'.format(token))
    return token

def verify_token(token: str) -> bool:
    """Verify if a token is valid"""
    if not token or token not in active_tokens:
        print('invalid token={}'.format(token))
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

async def get_current_user(token: str = Cookie(None, alias="stoken")):
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


def load_text_file(fn):
    with open(fn, "rt", encoding='utf8') as inf:
        text = inf.read()
        return text


# Login page
@app.get("/login", response_class=HTMLResponse)
@app.get("/login/", response_class=HTMLResponse)
@app.get("/stock/login", response_class=HTMLResponse)
@app.get("/stock/login/", response_class=HTMLResponse)
async def login_page():
    """Display login page"""
    ip_suffix = get_server_ip_last_digit()
    html_content = load_text_file('./login.html')
    html_content = html_content.replace('{IP_SUFFIX}', ip_suffix)
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
        # Set cookie server-side using the SAME token as JSON response
        # This ensures both cookie and JSON have the same token value
        response = JSONResponse(content={
            "status": "success",
            "message": "Login successful",
            "token": token
        })
        response.set_cookie(
            key="stoken",
            value=token,  # Use the SAME token
            path="/",
            max_age=24 * 60 * 60,  # 24 hours
            httponly=False,  # Allow JavaScript access
            samesite="lax"  # Better mobile compatibility
        )
        return response
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

# Logout endpoint
@app.post("/api/logout")
@app.post("/{proxy_path:path}/api/logout")
async def logout(token: str = Cookie(None, alias="stoken")):
    """Handle logout by invalidating token"""
    if token and token in active_tokens:
        del active_tokens[token]
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="stoken", path="/")
    return {"status": "success", "message": "Logged out successfully"}

# Root redirect to login
@app.get("/")
async def root_redirect():
    """Redirect root to login"""
    return RedirectResponse(url="./login", status_code=status.HTTP_302_FOUND)

@app.get("/stock", response_class=HTMLResponse)
@app.get("/stock/", response_class=HTMLResponse)
async def root(token: str = Cookie(None, alias="stoken")):
    """Display account information UI"""
    # Check authentication
    if not token or not verify_token(token):
        # Redirect to login - use /stock/login if accessed through proxy
        return RedirectResponse(url="/stock/login", status_code=status.HTTP_302_FOUND)
    
    account_data = format_account_data()
    ip_suffix = get_server_ip_last_digit()
    
    html_content = load_text_file('./autotr.html')
    html_content = html_content.replace('{IP_SUFFIX}', ip_suffix)
    return html_content

@app.get("/api/accounts")
@app.get("/stock/api/accounts")
async def get_accounts_api(proxy_path: str = "", token: str = Cookie(None, alias="stoken")):
    """API endpoint to get list of available accounts"""
    # Check authentication
    if not token or not verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    try:
        accounts = list(key_list.keys())
        return {"status": "success", "data": accounts}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/account-data")
@app.get("/stock/api/account-data")
async def get_account_data_api(proxy_path: str = "", token: str = Cookie(None, alias="stoken")):
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
async def get_miche_data_api(proxy_path: str = "", token: str = Cookie(None, alias="stoken")):
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
async def cancel_order_api(request: dict, proxy_path: str = "", token: str = Cookie(None, alias="stoken")):
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
        log_print(stk_cd, 'cancel_order_api ord_no={}'.format(ord_no))
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
        
        now = datetime.now()
        cancel_order_main(now, access_token, stex, ord_no, stk_cd)
        
        return {"status": "success", "message": "Order cancellation requested"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def cancel_related_buy_order(stk_cd):
    global stored_miche_data, jango_token
    now = datetime.now()
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
    log_print(stk_cd, 'cancel_related_buy_order {} returns {}.'.format(stk_cd, cancel_count))
    return cancel_count


def issue_buy_order(stk_cd, ord_uv, ord_qty, stex, trde_tp, account):
    """Issue buy order for a specific account"""
    global key_list
    
    if not account:
        return {"status": "error", "message": "Account parameter is required"}
    
    # Find specific account
    if account not in key_list:
        return {"status": "error", "message": f"Account {account} not found"}
    
    key = key_list[account]
    access_token = get_token(key['AK'], key['SK'])

    if not access_token:
        return {"status": "error", "message": "Unable to retrieve token"}

    # Convert price and amount to strings (as expected by buy_order)
    ord_uv_str = str(ord_uv)
    ord_qty_str = str(ord_qty)

    log_print(stk_cd, 'issue buy order for account {}: {}, {}, {}, {}, {}'.format(account, ord_uv_str, ord_uv, ord_qty, stex, trde_tp))

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

    log_print(stk_cd, 'buy_order_result for account {}: {}'.format(account, ret_status))

    # Check return status
    if isinstance(ret_status, dict):
        rcde = ret_status.get('return_code')
        rmsg = ret_status.get('return_msg', '')
        if rcde and rcde != '0000':
            return {"status": "error", "message": f"Buy order failed: {rmsg}", "return_code": rcde}
    return ret_status


@app.post("/api/buy-order")
@app.post("/stock/api/buy-order")
async def buy_order_api(request: dict, proxy_path: str = "", token: str = Cookie(None, alias="stoken")):
    """API endpoint to place a buy order for specified accounts"""
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
        accounts = request.get('accounts', [])  # List of accounts
        
        # Ensure accounts is a list (handle case where it might be a string or other type)
        if not isinstance(accounts, list):
            if isinstance(accounts, str):
                # If it's a string, split by comma
                accounts = [acc.strip() for acc in accounts.split(',') if acc.strip()]
            else:
                accounts = []

        log_print(stk_cd, 'buy_order_api: stk_cd={}, stk_nm={}, ord_uv={}, amount={}, accounts={} (type: {})'.format(
            stk_cd, stk_nm, ord_uv, ord_amount, accounts, type(accounts).__name__))
        
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
        
        stex = 'KRX'
        trde_tp = '0'

        # If no accounts specified, use all accounts
        if not accounts or len(accounts) == 0:
            accounts = list(key_list.keys())
        print('buy_order_api accounts={}'.format(accounts))
        # Execute buy order for each account individually
        results = []
        for account in accounts:
            try:
                ret_status = issue_buy_order(stk_cd, ord_uv, ord_qty, stex, trde_tp, account=account)
                results.append({
                    "account": account,
                    "status": "success" if isinstance(ret_status, dict) and ret_status.get('return_code') == '0000' else "error",
                    "data": ret_status
                })
            except Exception as e:
                print('buy_order_api exception for account {}: {}'.format(account, e))
                results.append({
                    "account": account,
                    "status": "error",
                    "message": str(e)
                })
        
        # Check if all orders succeeded
        all_success = all(r.get('status') == 'success' for r in results)
        if all_success:
            return {
                "status": "success",
                "message": f"Buy orders placed for {len(results)} account(s): {ord_qty} shares of {stk_nm or stk_cd} at {ord_uv}",
                "data": results
            }
        else:
            # Some failed
            failed_accounts = [r['account'] for r in results if r.get('status') != 'success']
            return {
                "status": "partial",
                "message": f"Some buy orders failed for accounts: {', '.join(failed_accounts)}",
                "data": results
            }

    except Exception as e:
        print('buy_order_api exception: {}'.format(e))
        return {"status": "error", "message": str(e)}


@app.get("/api/sell-prices")
@app.get("/{proxy_path:path}/api/sell-prices")
async def get_sell_prices_api(proxy_path: str = "", token: str = Cookie(None, alias="stoken")):
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
async def delete_sell_prices_api(stock_code: str, proxy_path: str = "", token: str = Cookie(None, alias="stoken")):
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
async def update_sell_prices_api(request: dict, proxy_path: str = "", token: str = Cookie(None, alias="stoken")):
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
        sellgap = request.get('sellgap', '0')
        
        if not stock_code:
            return {"status": "error", "message": "stock_code is required"}

        return set_interested_rate(stock_code, stock_name=stock_name, sellprice=price, sellrate=rate, sellgap=sellgap)
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/auto-sell")
@app.get("/stock/api/auto-sell")
async def get_auto_sell_api(proxy_path: str = "", token: str = Cookie(None, alias="stoken")):
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
async def set_auto_sell_api(request: dict, proxy_path: str = "", token: str = Cookie(None, alias="stoken")):
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
async def get_interested_stocks_api(proxy_path: str = "", token: str = Cookie(None, alias="stoken")):
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


def clear_ordered_count(stk_cd):
    for key, value in key_list.items():
        ACCT = value['ACCT']
        ordered = order_count[ACCT]
        ordered[stk_cd] = 0


def set_interested_rate(stock_code, stock_name='', color=None,
                    btype='', bamount='0',
                    stime='', yyyymmdd='', sellprice='0',
                    sellrate='0', sellgap='0'):
    global interested_stocks
    try:
        need_cancel_old_buy = False
        need_clear_ordered_count = False

        if color and color == 'DELETE':
            if stock_code in interested_stocks:
                del interested_stocks[stock_code]
                cancel_related_buy_order(stock_code)
        else:
            if not stock_name or stock_name == '':
                stock_name = get_stockname(stock_code)

            # Add or update the stock in interested list
            old_btype = ''
            if stock_code not in interested_stocks:
                stock = {}
            else:
                stock = interested_stocks[stock_code]
                old_btype = stock.get('btype', '')

            stock['stock_name'] = stock_name.strip()
            if color :
                color = color_kor_to_eng(color)
                stock['color'] = color.strip()

            if btype :
                if btype == 'CL':
                    need_clear_ordered_count = True
                else: # btype != 'CL'
                    if old_btype == 'CL':
                        need_cancel_old_buy = True
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
            if need_cancel_old_buy :
                # Cancel buy orders for this stock
                cancel_related_buy_order(stock_code)
            if need_clear_ordered_count :
                clear_ordered_count(stock_code)

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
                                   token: str = Cookie(None, alias="stoken"),
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
async def delete_interested_stock_api(stock_code: str, proxy_path: str = "", token: str = Cookie(None, alias="stoken")):
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


def get_gap_price(token_for_api, stock_code):
    try:
        _day_chart = get_day_chart(token_for_api, stock_code)
        day_data = _day_chart.get('stk_dt_pole_chart_qry', [])
        # Get latest day's closing price
        latest = day_data[0]  # Latest is first in response
        cur_prc = latest.get('cur_prc', '0')
        current_price = abs(int(cur_prc))
    except Exception as e:
        print(f"Error getting day chart for current price: {e}")

    # Get last 16 days
    high_16 = 0
    high_index = 0
    high_date = ''
    if len(day_data) < 16 :
        return {}

    for data_idx in range(16) :
        day = day_data[data_idx]
        high_pric = int(day.get('high_pric', '0'))
        if high_pric < 0:
            high_pric = -high_pric
        if high_pric > high_16:
            high_16 = high_pric
            high_index = data_idx
            high_date = day['dt']

    low_16 = float('inf')
    last_16_days = day_data[high_index:high_index+16]
    for day in last_16_days:
        low_pric = int(day.get('low_pric', '0'))
        if low_pric < 0:
            low_pric = -low_pric
        if low_pric < low_16:
            low_16 = low_pric
            low_date = day['dt']

    # Calculate yellow line price: high - (high - low) * 4 / 10
    gap = (high_16 - low_16) / 10
    yellow_line_price = int(high_16 - gap * 4)

    # Calculate gap rate: (current price - yellow price) / gap
    gap_rate = ((current_price - yellow_line_price) / gap) * 100 if gap > 0 else 0

    gap_price = {}
    gap_price['high_16'] = high_16
    gap_price['low_16'] = low_16
    gap_price['yellow_line_price'] = yellow_line_price
    gap_price['current_price'] = current_price
    gap_price['gap'] = gap
    gap_price['gap_rate'] = gap_rate
    gap_price['high_date'] = high_date
    gap_price['low_date'] = low_date
    gap_price['price'] = [high_16 - gap * i for i in range(10)]

    return gap_price


@app.get("/api/stock-price-info/{stock_code}")
@app.get("/stock/api/stock-price-info/{stock_code}")
async def get_stock_price_info(stock_code: str, token: str = Cookie(None, alias="stoken")):
    """Get 16-day high/low, yellow line price, current price, and gap rate for a stock"""
    # Check authentication
    if not token or not verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Get current price from jango data
    # Get token for API call
    token_for_api = get_one_token()
    gap_price = get_gap_price(token_for_api, stock_code)

    return {
        "status": "success",
        "data": {
            "stock_code": stock_code,
            "high_16": gap_price['high_16'],
            "low_16": gap_price['low_16'],
            "yellow_line_price": gap_price['yellow_line_price'],
            "current_price": gap_price['current_price'],
            "gap": gap_price['gap'],
            "gap_rate": gap_price['gap_rate'],
            "high_date": gap_price['high_date'],
            "low_date": gap_price['low_date'],
        }
    }


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
        now = datetime.now()
        cancel_nxt_trade(now)
        return {"status": "success", "message": "Cancel NXT trade executed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}




# Proxy endpoint for datagather service
@app.api_route("/stock/data/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_datagather(path: str, request: Request):
    """
    Proxy requests from /stock/data/* to datagather service on port 8007.
    Example: /stock/data/api/status -> http://localhost:8007/api/status
    """
    # Target URL for datagather service
    target_url = f"http://localhost:8007/{path}"
    
    # Get query parameters
    query_params = dict(request.query_params)
    
    # Get request body if present
    body = None
    try:
        body = await request.body()
    except:
        pass
    
    # Get headers (excluding host and other problematic headers)
    headers = dict(request.headers)
    headers.pop('host', None)
    headers.pop('content-length', None)
    
    try:
        # Forward the request to datagather service
        if request.method == "GET":
            response = requests.get(target_url, params=query_params, headers=headers, timeout=10)
        elif request.method == "POST":
            response = requests.post(target_url, params=query_params, data=body, headers=headers, timeout=10)
        elif request.method == "PUT":
            response = requests.put(target_url, params=query_params, data=body, headers=headers, timeout=10)
        elif request.method == "DELETE":
            response = requests.delete(target_url, params=query_params, headers=headers, timeout=10)
        elif request.method == "PATCH":
            response = requests.patch(target_url, params=query_params, data=body, headers=headers, timeout=10)
        else:
            return {"status": "error", "message": f"Unsupported method: {request.method}"}
        
        # Return the response from datagather
        # Check if response is HTML
        if 'text/html' in response.headers.get('content-type', ''):
            return HTMLResponse(content=response.text, status_code=response.status_code)
        else:
            # Return JSON or other content
            return JSONResponse(content=response.json() if response.headers.get('content-type', '').startswith('application/json') else {"data": response.text}, status_code=response.status_code)
            
    except requests.exceptions.ConnectionError:
        return JSONResponse(content={"status": "error", "message": "Data gather service is not available"}, status_code=503)
    except requests.exceptions.Timeout:
        return JSONResponse(content={"status": "error", "message": "Request to data gather service timed out"}, status_code=504)
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": f"Proxy error: {str(e)}"}, status_code=500)


# 실행 구간
if __name__ == '__main__':
    set_new_day(True)
    uvicorn.run(app, host="0.0.0.0", port=8006, access_log=False)