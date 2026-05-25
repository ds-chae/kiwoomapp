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
