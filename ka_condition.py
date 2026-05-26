import asyncio
import json
import sys

import websockets

from au1001 import get_one_token

SOCKET_URL = 'wss://api.kiwoom.com:10000/api/dostk/websocket'
WS_TIMEOUT_SEC = 30


def _close_event_loop(loop):
    try:
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        if hasattr(loop, 'shutdown_default_executor'):
            loop.run_until_complete(loop.shutdown_default_executor())
    except Exception:
        pass


def run_async(coro):
    """Run coroutine from sync code (works on Windows and Linux worker threads)."""
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # asyncio.run() can fail when called from background threads on Linux.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        _close_event_loop(loop)
        asyncio.set_event_loop(None)
        loop.close()


def _normalize_return_code(value):
    if value is None:
        return None
    return str(value)


async def _ws_recv_json(ws):
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=WS_TIMEOUT_SEC)
        data = json.loads(raw)
        if data.get('trnm') == 'PING':
            await ws.send(json.dumps(data))
            continue
        return data


async def _ws_send_json(ws, message):
    await ws.send(json.dumps(message))


async def _ws_login(ws, token):
    await _ws_send_json(ws, {'trnm': 'LOGIN', 'token': token})
    while True:
        data = await _ws_recv_json(ws)
        if data.get('trnm') != 'LOGIN':
            continue
        if _normalize_return_code(data.get('return_code')) != '0':
            raise RuntimeError(f"LOGIN failed: {data.get('return_msg', data)}")
        print('로그인 성공하였습니다.')
        return


async def _request_condition_list(ws):
    await _ws_send_json(ws, {'trnm': 'CNSRLST'})
    data = await _ws_recv_json(ws)
    if data.get('trnm') != 'CNSRLST':
        raise RuntimeError(f"Unexpected CNSRLST response: {data}")
    if _normalize_return_code(data.get('return_code')) not in (None, '0'):
        raise RuntimeError(f"CNSRLST failed: {data.get('return_msg', data)}")
    print(f'조건 검색 목록 응답 수신: {data}')
    return data


def _find_condition_seq(search_list, condition_name):
    data = search_list.get('data') or []
    for item in data:
        if isinstance(item, dict):
            seq = str(item.get('seq', '')).strip()
            name = str(item.get('name', '')).strip()
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            seq = str(item[0]).strip()
            name = str(item[1]).strip()
        else:
            continue
        if name == condition_name:
            return seq
    return ''


def _find_p3_seq(search_list):
    return _find_condition_seq(search_list, 'P3')


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


async def _request_condition_search(ws, seq):
    await _ws_send_json(ws, {
        'trnm': 'CNSRREQ',
        'seq': str(seq),
        'search_type': '0',
        'stex_tp': 'K',
        'cont_yn': 'N',
        'next_key': '',
    })
    data = await _ws_recv_json(ws)
    if data.get('trnm') != 'CNSRREQ':
        raise RuntimeError(f"Unexpected CNSRREQ response: {data}")
    if _normalize_return_code(data.get('return_code')) not in (None, '0'):
        raise RuntimeError(f"CNSRREQ failed: {data.get('return_msg', data)}")
    print(f'조건 검색 결과 응답 수신: {data}')
    return data


async def main_async():
    print('getting token')
    token = get_one_token()
    print(f'token={token}')
    async with websockets.connect(
        SOCKET_URL,
        open_timeout=WS_TIMEOUT_SEC,
        close_timeout=WS_TIMEOUT_SEC,
    ) as ws:
        print('서버와 연결을 시도 중입니다.')
        await _ws_login(ws, token)

        search_list = await _request_condition_list(ws)
        p3_seq = _find_p3_seq(search_list)
        if not p3_seq:
            print('Cannot find P3')
            return search_list, None

        print(f'Index for P3 = {p3_seq}')
        search_result = await _request_condition_search(ws, p3_seq)
        return search_list, search_result


async def search_condition_by_name_async(condition_name):
    token = get_one_token()
    async with websockets.connect(
        SOCKET_URL,
        open_timeout=WS_TIMEOUT_SEC,
        close_timeout=WS_TIMEOUT_SEC,
    ) as ws:
        await _ws_login(ws, token)
        search_list = await _request_condition_list(ws)
        seq = _find_condition_seq(search_list, condition_name)
        if not seq:
            raise RuntimeError(f"Condition '{condition_name}' not found")
        search_result = await _request_condition_search(ws, seq)
        return _extract_stocks_from_message(search_result)


def search_condition_by_name(condition_name):
    return run_async(search_condition_by_name_async(condition_name))


if __name__ == '__main__':
    search_list, search_result = run_async(main_async())
    if search_result is not None:
        print(f'result={search_result}')
