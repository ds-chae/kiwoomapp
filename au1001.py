from datetime import datetime

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load KIWOOM_SK and KIWOOM_AK from environment variables
SK_9136 = os.getenv('SK_9136')
AK_9136 = os.getenv('AK_9136')

SK_0130 = os.getenv('SK_0130')
AK_0130 = os.getenv('AK_0130')

SK_7942 = os.getenv('SK_7942')
AK_7942 = os.getenv('AK_7942')

EXP_9136 = os.getenv('EXP_9136')
EXP_0130 = os.getenv('EXP_0130')
EXP_7942 = os.getenv('EXP_7942')

key_9136 = {}
key_9136['ACCT'] = '9136'
key_9136['SK'] = SK_9136
key_9136['AK'] = AK_9136
key_9136['EXP'] = EXP_9136

key_0130 = {}
key_0130['ACCT'] = '0130'
key_0130['SK'] = SK_0130
key_0130['AK'] = AK_0130
key_0130['EXP'] = EXP_0130

key_7942 = {}
key_7942['ACCT'] = '7942'
key_7942['SK'] = SK_7942
key_7942['AK'] = AK_7942
key_7942['EXP'] = EXP_7942

env_json = None

def load_env_json():
    global env_json
    with open('env.json', 'r', encoding='utf-8') as f :
        env_json = json.load(f)


key_list = None

def get_key_list():
    global key_list, env_json
    if key_list:
        return key_list
    if not env_json:
        load_env_json()
    key_list = {}
    ACCOUNT = env_json['ACCOUNT']
    for A in ACCOUNT:
        key_list[A['ACCT']] = A
    return key_list


# 접근토큰 발급
def fn_au10001(data):
    # 1. 요청할 API URL
    # host = 'https://mockapi.kiwoom.com' # 모의투자
    host = 'https://api.kiwoom.com'  # 실전투자
    endpoint = '/oauth2/token'
    url = host + endpoint

    # 2. header 데이터
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',  # 컨텐츠타입
    }

    # 3. http POST 요청
    response = requests.post(url, headers=headers, json=data)

    # 4. 응답 상태 코드와 데이터 출력
    print_it = False
    if print_it:
        print('Code:', response.status_code)
        header_keys = ['next-key', 'cont-yn', 'api-id']
        header_data = {key: response.headers.get(key) for key in header_keys}
        # print('Header:', json.dumps(header_data, indent=4, ensure_ascii=False))
        print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력
    return response.json()


token_list = {}

def get_token(ACCT, AK, SK):
    global token_list, token_hour
    now = datetime.now()
    if ACCT in token_list:
        token_pair = token_list[ACCT]
        if now.hour == token_pair['hour'] :
            return token_pair['token']

    # 1. 요청 데이터
    params = {
        'grant_type': 'client_credentials',  # grant_type
        'appkey': AK,  # 앱키
        'secretkey': SK,  # 시크릿키
    }

    # 2. API 실행
    j = fn_au10001(data=params)
    print('Refreshing token===')
    print(str(j))
    if 'token' in j:
        token = j['token']
        token_pair = {}
        token_pair['hour'] = now.hour
        token_pair['token'] = token
        token_list[ACCT] = token_pair
        return token
    else:
        print(f'For {ACCT} non token in response {str(j)}')
        return ''

def clear_token_list():
    global token_list
    token_list = {}


def get_one_token():
    token = get_token('9136', AK_9136, SK_9136)
    return token

# 실행 구간
if __name__ == '__main__':
    token = get_token('9136', AK_9136, SK_9136)
    print(f"token={token}")
    #load_env_json()
    #print(env_json)
    kl = get_key_list()
    print(kl)