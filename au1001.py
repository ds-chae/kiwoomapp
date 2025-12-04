import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load KIWOOM_SK and KIWOOM_AK from environment variables
KIWOOM_SK = os.getenv('KIWOOM_SK')
KIWOOM_AK = os.getenv('KIWOOM_AK')

SK_0130 = os.getenv('SK_0130')
AK_0130 = os.getenv('AK_0130')

key_9136 = {}
key_9136['ACCT'] = '9136'
key_9136['SK'] = KIWOOM_SK
key_9136['AK'] = KIWOOM_AK


key_0130 = {}
key_0130['ACCT'] = '0130'
key_0130['SK'] = SK_0130
key_0130['AK'] = AK_0130

key_list = [ key_0130, key_9136]


def get_key_list():
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

    return response.json()['token']




def get_token(KIWOOM_AK, KIWOOM_SK):
    # 1. 요청 데이터
    params = {
        'grant_type': 'client_credentials',  # grant_type
        'appkey': KIWOOM_AK,  # 앱키
        'secretkey': KIWOOM_SK,  # 시크릿키
    }

    # 2. API 실행
    token = fn_au10001(data=params)
    return token

# 실행 구간
if __name__ == '__main__':
    token = get_token(KIWOOM_AK, KIWOOM_SK)
    print(f"token={token}")
