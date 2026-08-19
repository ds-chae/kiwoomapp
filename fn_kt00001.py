import json
import time
import os
import base64
import asyncio
import traceback
import threading
import requests
from datetime import datetime, timedelta, time as dt_time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import uvicorn
import csv
import numpy as np
import cv2

from ka10081 import get_day_chart
from ka10080 import get_bun_chart, fn_ka10080
from au1001 import get_one_token, get_key_list, get_token
from ka10100 import get_stockinfo
from ka_condition import search_condition_by_name

# Configuration
# Determine the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Define chart data directory: chart_data/day
CHART_DIR = os.path.join(BASE_DIR, 'chart_data', 'day')
INTERESTED_STOCKS_FILE = os.path.join(BASE_DIR, 'interested_stocks.json')
LAST_RUN_FILE = os.path.join(BASE_DIR, 'last_gathering_time.json')
P3_POSTED_FILE = os.path.join(BASE_DIR, 'p3_interested_posted.json')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
# Directory where server-rendered (OpenCV) chart PNGs are saved
CHART_IMG_DIR = os.path.join(BASE_DIR, 'chart_images')

# 예수금상세현황요청
def get_yesu_detail(MY_ACCESS_TOKEN):
    # 2. 요청 데이터
    params = {
        'qry_tp': '3'  # 조회구분 3:추정조회, 2:일반조회
    }

    # 예수금상세현황요청
    return fn_kt00001(token=MY_ACCESS_TOKEN, data=params)


def fn_kt00001(token, data, cont_yn='N', next_key=''):
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
        'api-id': 'kt00001' # TR명
    }

    # 3. http POST 요청
    response = requests.post(url, headers=headers, json=data)

    # 4. 응답 상태 코드와 데이터 출력
    print('Code:', response.status_code)
    print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
    print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력
    return response.json()

# 실행 구간

def get_yesu_list():
    key_list = get_key_list()
    yesu_list = []
    for k, key in key_list.items():
        ACCT = key['ACCT']
        MY_ACCESS_TOKEN = get_token(ACCT)  # 접근토큰
        yesu = get_yesu_detail(MY_ACCESS_TOKEN)
        yesu['ACCT'] = ACCT
        yesu_list.append(yesu)
    return yesu_list

if __name__ == "__main__":
    yesu_list = get_yesu_list()
    for y in yesu_list:
        ACCT = y['ACCT']
        entr = y['entr'] # 예수금
        d1_entra = y['d1_entra']	# d+1추정예수금
        d2_entra = y['d2_entra']	# d+2추정예수금
        print(ACCT, entr, d1_entra, d2_entra)
