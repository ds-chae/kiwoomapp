#
# 상하한가 간 종목을 표시해준다. 현재 가격에서 상한가가 얼마인지는 말해주지 않는다.
#
#
import requests
import json
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
import os

# Load environment variables from .env file
load_dotenv()

# Load KIWOOM_SK and KIWOOM_AK from environment variables
KIWOOM_SK = os.getenv('KIWOOM_SK')
KIWOOM_AK = os.getenv('KIWOOM_AK')

SK_0130 = os.getenv('SK_0130')
AK_0130 = os.getenv('AK_0130')

# 상하한가요청
def fn_ka10017(token, data, cont_yn='N', next_key=''):
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
		'api-id': 'ka10017', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력

# 실행 구간
if __name__ == '__main__':
	# 1. 토큰 설정
	key_list = get_key_list()
	jango = []
	for key in key_list:
		MY_ACCESS_TOKEN = get_token(key['AK'], key['SK'])  # 접근토큰
		break

	# 2. 요청 데이터
	params = {
		'mrkt_tp': '000', # 시장구분 000:전체, 001:코스피, 101:코스닥
		'updown_tp': '1', # 상하한구분 1:상한, 2:상승, 3:보합, 4: 하한, 5:하락, 6:전일상한, 7:전일하한
		'sort_tp': '1', # 정렬구분 1:종목코드순, 2:연속횟수순(상위100개), 3:등락률순
		'stk_cnd': '0', # 종목조건 0:전체조회,1:관리종목제외, 3:우선주제외, 4:우선주+관리종목제외, 5:증100제외, 6:증100만 보기, 7:증40만 보기, 8:증30만 보기, 9:증20만 보기, 10:우선주+관리종목+환기종목제외
		'trde_qty_tp': '0000', # 거래량구분 00000:전체조회, 00010:만주이상, 00050:5만주이상, 00100:10만주이상, 00150:15만주이상, 00200:20만주이상, 00300:30만주이상, 00500:50만주이상, 01000:백만주이상
		'crd_cnd': '0', # 신용조건 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4:신용융자D군, 7:신용융자E군, 9:신용융자전체
		'trde_gold_tp': '0', # 매매금구분 0:전체조회, 1:1천원미만, 2:1천원~2천원, 3:2천원~3천원, 4:5천원~1만원, 5:1만원이상, 8:1천원이상
		'stex_tp': '1', # 거래소구분 1:KRX, 2:NXT 3.통합
	}

	# 3. API 실행
	fn_ka10017(token=MY_ACCESS_TOKEN, data=params)

	# next-key, cont-yn 값이 있을 경우
	# fn_ka10017(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')
