#!/usr/bin/env python

from aiohttp import web
from app import App
import asyncio
import logging
from time import time
import socketio
from web3 import Web3
import websockets

sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app)

ZERO_ADDR_BYTES = Web3.toBytes(hexstr="0x0000000000000000000000000000000000000000")

@sio.on('connect')
def connect(sid, environ):
    print("connect ", sid)

import datetime
def datetime_from_uuid(uuid1):
    """Convert the uuid1 timestamp to a standard posix timestamp
    """
    assert uuid1.version == 1, ValueError('only applies to type 1')
    t = uuid1.time
    t = t - 0x01b21dd213814000
    t = t / 1e7
    return datetime.datetime.fromtimestamp(t, tz=datetime.timezone.utc)

def format_trade(trade_record):
    trade = dict(trade_record)
    side = "buy" if trade["token_get"] == ZERO_ADDR_BYTES else "sell"
    token = trade["token_give"] if side == "buy" else trade["token_get"]
    amount_coin = trade["amount_give"] if side == "buy" else trade["amount_get"]
    amount_base = trade["amount_get"] if side == "buy" else trade["amount_give"]
    buyer = trade["addr_give"] if side == "buy" else trade["addr_get"]
    seller = trade["addr_get"] if side == "buy" else trade["addr_give"]
    price = (amount_base / amount_coin) if amount_coin > 0 else 0.0

    return {
            "txHash": Web3.toHex(trade["transaction_hash"]),
            "date": trade_record["date"].isoformat(),
            "price": str(price).lower(),
            "side": side,
            "amount": str(Web3.fromWei(amount_coin, 'ether')).lower(),
            "amountBase": str(Web3.fromWei(amount_base, 'ether')).lower(),
            "buyer": Web3.toHex(buyer),
            "seller": Web3.toHex(seller),
            "tokenAddr": Web3.toHex(token)
        }

async def get_token_trades(token_hexstr):
    token_bytes = Web3.toBytes(hexstr=token_hexstr)

    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM trades
            WHERE "token_give" = $1 OR "token_get" = $1
            ORDER BY id DESC
            LIMIT 300
            """,
            token_bytes)


@sio.on('getMarket')
async def get_market(sid, data):
    print("getMarket", data)

    if "token" in data and Web3.isAddress(data["token"]):
        trades = await get_token_trades(data["token"])
    else:
        trades = []

    response = {
        "trades": [format_trade(trade) for trade in trades],
        "orders": { "buys": [], "sells": []}
    }

    await sio.emit('market', response, room=sid)

@sio.on('disconnect')
def disconnect(sid):
    print('disconnect ', sid)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(App().db.establish_connection())
    web.run_app(app)
