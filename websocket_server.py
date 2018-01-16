#!/usr/bin/env python

from aiohttp import web
from app import App
import asyncio
from erc20_token import ERC20Token
import logging
from time import time
import socketio
from web3 import Web3
import websockets

sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app)

ZERO_ADDR = "0x0000000000000000000000000000000000000000"
ZERO_ADDR_BYTES = Web3.toBytes(hexstr=ZERO_ADDR)

@sio.on('connect')
def connect(sid, environ):
    print("connect ", sid)

def format_trade(trade):
    contract_give = ERC20Token(trade["token_give"])
    contract_get = ERC20Token(trade["token_get"])

    side = "buy" if trade["token_get"] == ZERO_ADDR_BYTES else "sell"
    if side == "buy":
        token = trade["token_give"]
        amount_coin = contract_give.denormalize_value(trade["amount_give"])
        amount_base = contract_get.denormalize_value(trade["amount_get"])
        buyer = trade["addr_give"]
        seller = trade["addr_get"]
    else:
        token = trade["token_get"]
        amount_coin = contract_get.denormalize_value(trade["amount_get"])
        amount_base = contract_give.denormalize_value(trade["amount_give"])
        buyer = trade["addr_get"]
        seller = trade["addr_give"]
    price = (amount_base / amount_coin) if amount_coin > 0 else 0.0


    return {
            "txHash": Web3.toHex(trade["transaction_hash"]),
            "date": trade["date"].isoformat(),
            "price": str(price).lower(),
            "side": side,
            "amount": str(amount_coin).lower(),
            "amountBase": str(amount_base).lower(),
            "buyer": Web3.toHex(buyer),
            "seller": Web3.toHex(seller),
            "tokenAddr": Web3.toHex(token)
        }

async def get_trades(token_hexstr, user_hexstr=None):
    where = '("token_give" = $1 OR "token_get" = $1)'
    placeholder_args = [Web3.toBytes(hexstr=token_hexstr), ]
    if user_hexstr:
        where += ' AND ("addr_give" = $2 OR "addr_get" = $2)'
        placeholder_args.append(Web3.toBytes(hexstr=user_hexstr))

    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM trades
            WHERE {}
            ORDER BY block_number DESC, date DESC
            LIMIT 300
            """.format(where),
            *placeholder_args)

def format_transfer(transfer):
    contract = ERC20Token(transfer["token"])
    return {
        "txHash": Web3.toHex(transfer["transaction_hash"]),
        "tokenAddr": Web3.toHex(transfer["token"]),
        "user": Web3.toHex(transfer["user"]),
        "kind": transfer["direction"],
        "amount": str(contract.denormalize_value(transfer["amount"])),
        "balance": str(contract.denormalize_value(transfer["balance_after"])),
        "date": transfer["date"].isoformat()
    }

async def get_transfers(token_hexstr, user_hexstr):
    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM transfers
            WHERE "user" = $1 AND ("token" = $2 OR "token" = $3)
            ORDER BY block_number DESC, date DESC
            LIMIT 300
            """,
            Web3.toBytes(hexstr=user_hexstr),
            Web3.toBytes(hexstr=token_hexstr),
            Web3.toBytes(hexstr=ZERO_ADDR))

@sio.on('getMarket')
async def get_market(sid, data):
    print("getMarket", data)

    token_specified = "token" in data and Web3.isAddress(data["token"])
    user_specified = "token" in data and Web3.isAddress(data["token"])

    trades = []
    my_trades = []
    my_funds = []
    if token_specified:
        trades = await get_trades(data["token"])
        if user_specified:
            my_trades = await get_trades(data["token"], data["user"])
            my_funds = await get_transfers(data["token"], data["user"])

    response = {
        "trades": [format_trade(trade) for trade in trades],
        "myTrades": [format_trade(trade) for trade in my_trades],
        "myFunds": [format_transfer(transfer) for transfer in my_funds],
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
