from datetime import datetime, timedelta
import threading

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
token_lock = threading.Lock()


def decrease_one_hour(dtstr):
    dt = datetime.strptime(str(dtstr).strip(), '%Y%m%d%H%M%S')
    prior_dt = dt - timedelta(hours=1)
    return prior_dt.strftime('%Y%m%d%H%M%S')


def get_token(ACCT):
    global token_list

    nowstr = datetime.now().strftime('%Y%m%d%H%M%S')
    with token_lock:
        cached = token_list.get(ACCT) or {}
        token = cached.get('token')
        expires_dt = cached.get('expires_dt') or '00000000000000'
        # Refresh 1 hour before the real expires_dt from the API.
        try:
            refresh_at = decrease_one_hour(expires_dt)
        except (TypeError, ValueError):
            refresh_at = '00000000000000'
        if token and refresh_at > nowstr:
            return token

        j = None
        try:
            keys = get_key_list()[ACCT]
            params = {
                'grant_type': 'client_credentials',
                'appkey': keys['AK'],
                'secretkey': keys['SK'],
            }
            j = fn_au10001(data=params)
            print('Refreshing token===')
            print(str(j))
            new_token = j.get('token') if isinstance(j, dict) else None
            new_expires = str(j.get('expires_dt', '')).strip() if isinstance(j, dict) else ''
            if new_token and new_expires:
                decrease_one_hour(new_expires)
                token_list[ACCT] = {
                    'token': new_token,
                    'expires_dt': new_expires,
                }
                return new_token
        except Exception as ex:
            print(f'For {ACCT} token refresh failed: {ex}')

        if token and expires_dt > nowstr:
            print(f'For {ACCT} using cached token after refresh failure')
            return token
        print(f'For {ACCT} no token in response {str(j)}')
        return ''


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