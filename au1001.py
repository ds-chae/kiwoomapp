from datetime import datetime, timedelta

import requests
import json


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

def get_token(ACCT):
    global token_list, env_json

    expires_dt = '00000000000000'
    token = None
    if ACCT in token_list:
        token_pair = token_list[ACCT]
        expires_dt = token_pair['expires_dt']
        token = token_pair['token']
    # compare expire dt
    nowstr = datetime.now().strftime('%Y%m%d%H%M%S')
    if token and expires_dt > nowstr :
        return token

    # it is expected to be expired in an hour, so refresh
    k_list = get_key_list()
    keys = k_list[ACCT]

    AK = keys['AK']
    SK = keys['SK']
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
        # replace hhmmss to 0s to compare expire.
        expires_dt = j['expires_dt']
        expires_dt = decrease_one_hour(expires_dt)
        token_pair = {}
        token_pair['token'] = token
        token_pair['expires_dt'] = expires_dt
        token_list[ACCT] = token_pair
        return token
    else:
        print(f'For {ACCT} non token in response {str(j)}')
        return ''

def decrease_one_hour(dtstr):
    dt = datetime.strptime(dtstr, '%Y%m%d%H%M%S')
    prior_dt = dt - timedelta(hours = 1)
    output_str = prior_dt.strftime('%Y%m%d%H%M%S')
    return output_str


def get_one_token():
    token = get_token('9136')
    return token

def os_getenv(key):
    global env_json
    if not env_json:
        load_env_json()
    val = env_json[key]
    return val


# 실행 구간
if __name__ == '__main__':
    token = get_token('9136')
    print(f"token={token}")
    #load_env_json()
    #print(env_json)
    kl = get_key_list()
    print(kl)