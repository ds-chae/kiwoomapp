import asyncio
import json

import websockets

from au1001 import get_one_token

WS_URL = 'wss://api.kiwoom.com:10000/api/dostk/websocket'
WS_TIMEOUT_SEC = 30


def _normalize_return_code(value):
    if value is None:
        return None
    return str(value)


def _extract_stock_from_item(item):
    if not isinstance(item, dict):
        return None

    stk_cd = (
        item.get('9001')
        or item.get('stk_cd')
        or item.get('code')
        or item.get('jongmok_cd')
        or ''
    )
    stk_cd = str(stk_cd).strip()
    if not stk_cd:
        return None
    if stk_cd[0] == 'A':
        stk_cd = stk_cd[1:]

    stk_nm = (
        item.get('302')
        or item.get('stk_nm')
        or item.get('name')
        or item.get('jongmok_nm')
        or ''
    )
    return {'stk_cd': stk_cd, 'stk_nm': str(stk_nm).strip()}


def _extract_stocks_from_message(data):
    stocks = []
    payload = data.get('data')
    if isinstance(payload, list):
        for item in payload:
            stock = _extract_stock_from_item(item)
            if stock:
                stocks.append(stock)
    elif isinstance(payload, dict):
        stock = _extract_stock_from_item(payload)
        if stock:
            stocks.append(stock)
    return stocks


async def _ws_recv_json(ws):
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=WS_TIMEOUT_SEC)
        data = json.loads(raw)
        trnm = data.get('trnm')
        if trnm == 'PING':
            await ws.send(json.dumps(data))
            continue
        return data


async def _ws_login(ws, token):
    await ws.send(json.dumps({'trnm': 'LOGIN', 'token': token}))
    while True:
        data = await _ws_recv_json(ws)
        if data.get('trnm') != 'LOGIN':
            continue
        if _normalize_return_code(data.get('return_code')) != '0':
            raise RuntimeError(f"WebSocket LOGIN failed: {data.get('return_msg', data)}")
        return


async def _ws_request(ws, message):
    await ws.send(json.dumps(message))
    return await _ws_recv_json(ws)


async def _find_condition_seq(ws, condition_name):
    data = await _ws_request(ws, {'trnm': 'CNSRLST'})
    if data.get('trnm') != 'CNSRLST':
        raise RuntimeError(f"Unexpected response for CNSRLST: {data}")
    if _normalize_return_code(data.get('return_code')) not in (None, '0'):
        raise RuntimeError(f"CNSRLST failed: {data.get('return_msg', data)}")

    for item in data.get('data') or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name', '')).strip()
        if name == condition_name:
            seq = str(item.get('seq', '')).strip()
            if seq:
                return seq

    available = [
        str(item.get('name', '')).strip()
        for item in (data.get('data') or [])
        if isinstance(item, dict)
    ]
    raise RuntimeError(f"Condition '{condition_name}' not found. Available: {available}")


async def _search_condition(ws, seq):
    stocks = []
    next_key = ''
    cont_yn = 'N'

    while True:
        message = {
            'trnm': 'CNSRREQ',
            'seq': seq,
            'search_type': '0',
            'stex_tp': 'K',
            'cont_yn': cont_yn,
            'next_key': next_key,
        }
        data = await _ws_request(ws, message)
        if data.get('trnm') != 'CNSRREQ':
            raise RuntimeError(f"Unexpected response for CNSRREQ: {data}")
        if _normalize_return_code(data.get('return_code')) not in (None, '0'):
            raise RuntimeError(f"CNSRREQ failed: {data.get('return_msg', data)}")

        stocks.extend(_extract_stocks_from_message(data))

        cont_yn = str(data.get('cont_yn', 'N')).upper()
        next_key = str(data.get('next_key', '') or '')
        if cont_yn != 'Y' or not next_key:
            break
        cont_yn = 'Y'

    deduped = {}
    for stock in stocks:
        deduped[stock['stk_cd']] = stock
    return list(deduped.values())


async def search_condition_by_name_async(condition_name):
    token = get_one_token()
    async with websockets.connect(WS_URL) as ws:
        await _ws_login(ws, token)
        seq = await _find_condition_seq(ws, condition_name)
        return await _search_condition(ws, seq)


def search_condition_by_name(condition_name):
    return asyncio.run(search_condition_by_name_async(condition_name))

import asyncio
import websockets
import json

# socket 정보
# SOCKET_URL = 'wss://mockapi.kiwoom.com:10000/api/dostk/websocket'  # 모의투자 접속 URL
SOCKET_URL = 'wss://api.kiwoom.com:10000/api/dostk/websocket'  # 접속 URL
ACCESS_TOKEN = '사용자 AccessToken'  # 고객 Access Token

class WebSocketClient:
	def __init__(self, uri):
		self.uri = uri
		self.websocket = None
		self.connected = False
		self.keep_running = True

	# WebSocket 서버에 연결합니다.
	async def connect(self):
		try:
			self.websocket = await websockets.connect(self.uri)
			self.connected = True
			print("서버와 연결을 시도 중입니다.")

			# 로그인 패킷
			param = {
				'trnm': 'LOGIN',
				'token': ACCESS_TOKEN
			}

			print('실시간 시세 서버로 로그인 패킷을 전송합니다.')
			# 웹소켓 연결 시 로그인 정보 전달
			await self.send_message(message=param)

		except Exception as e:
			print(f'Connection error: {e}')
			self.connected = False

	# 서버에 메시지를 보냅니다. 연결이 없다면 자동으로 연결합니다.
	async def send_message(self, message):
		if not self.connected:
			await self.connect()  # 연결이 끊어졌다면 재연결
		if self.connected:
			# message가 문자열이 아니면 JSON으로 직렬화
			if not isinstance(message, str):
				message = json.dumps(message)

		await self.websocket.send(message)
		print(f'Message sent: {message}')

	# 서버에서 오는 메시지를 수신하여 출력합니다.
	async def receive_messages(self):
		while self.keep_running:
			try:
				# 서버로부터 수신한 메시지를 JSON 형식으로 파싱
				response = json.loads(await self.websocket.recv())

				# 메시지 유형이 LOGIN일 경우 로그인 시도 결과 체크
				if response.get('trnm') == 'LOGIN':
					if response.get('return_code') != 0:
						print('로그인 실패하였습니다. : ', response.get('return_msg'))
						await self.disconnect()
					else:
						print('로그인 성공하였습니다.')
						print('조건검색 목록조회 패킷을 전송합니다.')
						# 로그인 패킷
						param = {
							'trnm': 'CNSRLST'
						}
						await self.send_message(message=param)

				# 메시지 유형이 PING일 경우 수신값 그대로 송신
				elif response.get('trnm') == 'PING':
					await self.send_message(response)

				if response.get('trnm') != 'PING':
					print(f'실시간 시세 서버 응답 수신: {response}')

			except websockets.ConnectionClosed:
				print('Connection closed by the server')
				self.connected = False
				await self.websocket.close()

	# WebSocket 실행
	async def run(self):
		await self.connect()
		await self.receive_messages()

	# WebSocket 연결 종료
	async def disconnect(self):
		self.keep_running = False
		if self.connected and self.websocket:
			await self.websocket.close()
			self.connected = False
			print('Disconnected from WebSocket server')

async def main():
	# WebSocketClient 전역 변수 선언
	websocket_client = WebSocketClient(SOCKET_URL)

	# WebSocket 클라이언트를 백그라운드에서 실행합니다.
	receive_task = asyncio.create_task(websocket_client.run())

	# 실시간 항목 등록
	await asyncio.sleep(1)
	await websocket_client.send_message({
		'trnm': 'CNSRREQ', # 서비스명
		'seq': '4', # 조건검색식 일련번호
		'search_type': '0', # 조회타입
		'stex_tp': 'K', # 거래소구분
		'cont_yn': 'N', # 연속조회여부
		'next_key': '', # 연속조회키
	})

	# 수신 작업이 종료될 때까지 대기
	await receive_task

# asyncio로 프로그램을 실행합니다.
if __name__ == '__main__':
	asyncio.run(main())
