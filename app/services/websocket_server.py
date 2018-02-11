from aiohttp import web
from ..app import App
import asyncio
from ..src.erc20_token import ERC20Token
import logging
from ..src.order_enums import OrderState
from time import time
import socketio
from web3 import Web3
import websockets
from datetime import datetime

sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app)

ZERO_ADDR = "0x0000000000000000000000000000000000000000"
ZERO_ADDR_BYTES = Web3.toBytes(hexstr=ZERO_ADDR)

logger = logging.getLogger('websocket_server')

@sio.on('connect')
def connect(sid, environ):
    print("connect ", sid)

# get returnTicker, grabs data from tickers table
async def get_tickers(token_hexstr):

    # init
    where = ''
    placeholder_args = []

    # if token is passed in, add where addr = token
    if token_hexstr:
        where = '("token_address" = $1)'
        placeholder_args = [Web3.toBytes(hexstr=token_hexstr), ]

    # connect to db and grab data from tickers table
    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM tickers
            WHERE {}
            ORDER BY token_address DESC
            """.format(where),
            *placeholder_args)

# format ticker information to camelcase from underscore, sanitize, add modified date
"""
    sample return data:
    ETH_0x8f3470a7388c05ee4e7af3d01d8c722b0ff52374:
   { tokenAddr: '0x8f3470a7388c05ee4e7af3d01d8c722b0ff52374',
     quoteVolume: 1000.1,
     baseVolume: 212.3,
     last: 0.245,
     percentChange: 0.0047,
     bid: 0.243,
     ask: 0.246,
     modified: 2018-01-15T15:53:00},
"""
def format_ticker(ticker):
    contract = ERC20Token(ticker["token_address"])
    return { "{}_{}".format("ETH", Web3.toHex(ticker["token_address"]) : {
        "tokenAddr": Web3.toHex(ticker["token_address"]),
        "quoteVolume": str(contract.denormalize_value(ticker["quote_volume"])),
        "baseVolume": str(contract.denormalize_value(ticker["base_volume"])),
        "last": str(contract.denormalize_value(ticker["last"])),
        "percentChange": str(contract.denormalize_value(ticker["percent_change"])),
        "bid": str(contract.denormalize_value(ticker["bid"])),
        "ask": str(contract.denormalize_value(ticker["ask"])),
        "modified": ticker["modified"]
    }}

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

async def get_orders(token_give_hexstr, token_get_hexstr, user_hexstr=None, expires_after=None, state=None, sort=None):
    where = '("token_give" = $1 AND "token_get" = $2)'
    placeholder_args = [
        Web3.toBytes(hexstr=token_give_hexstr),
        Web3.toBytes(hexstr=token_get_hexstr)
        ]

    if user_hexstr:
        where += ' AND ("user" = ${})'.format(len(placeholder_args) + 1)
        placeholder_args.append(Web3.toBytes(hexstr=user_hexstr))

    if expires_after:
        where += ' AND ("expires" > ${})'.format(len(placeholder_args) + 1)
        placeholder_args.append(expires_after)

    if state:
        where += ' AND ("state" = ${})'.format(len(placeholder_args) + 1)
        placeholder_args.append(state)

    order_by = ['expires ASC']
    if sort is not None:
        order_by.insert(0, sort)

    logger.debug(where)

    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM orders
            WHERE {}
            ORDER BY {}
            LIMIT 500
            """.format(where, ", ".join(order_by)),
            *placeholder_args)

def format_order(record):
    contract_give = ERC20Token(record["token_give"])
    contract_get = ERC20Token(record["token_get"])

    side = "buy" if record["token_give"] == ZERO_ADDR_BYTES else "sell"
    if side == "buy":
        coin_contract = ERC20Token(record["token_get"])
        base_contract = ERC20Token(record["token_give"])

        available_volume = record["amount_get"] - record["amount_fill"]
        eth_available_volume = coin_contract.denormalize_value(available_volume)

        filled_base = record["amount_fill"] * record["amount_give"] / record["amount_get"]
        available_volume_base = record["amount_give"] - filled_base
        eth_available_volume_base = base_contract.denormalize_value(available_volume_base)
    else:
        coin_contract = ERC20Token(record["token_give"])
        base_contract = ERC20Token(record["token_get"])

        available_volume = record["amount_give"] - record["amount_fill"]
        eth_available_volume = coin_contract.denormalize_value(available_volume)

        filled_base = record["amount_fill"] * record["amount_get"] / record["amount_give"]
        available_volume_base = record["amount_get"] - filled_base
        eth_available_volume_base = base_contract.denormalize_value(available_volume_base)

    price = eth_available_volume_base / eth_available_volume if eth_available_volume > 0 else 0.0

    response = {
        "id": "{}_{}".format(Web3.toHex(record["signature"]), side),
        "user": Web3.toHex(record["user"]),

        "tokenGet": Web3.toHex(record["token_get"]),
        "amountGet": str(record["amount_get"]).lower(),
        "tokenGive": Web3.toHex(record["token_give"]),
        "amountGive": str(record["amount_give"]).lower(),
        "expires": str(record["expires"]),
        "nonce": str(record["nonce"]).lower(),

        "availableVolume": str(available_volume).lower(),
        "ethAvailableVolume": str(eth_available_volume).lower(),
        "availableVolumeBase": str(available_volume_base).lower(),
        "ethAvailableVolumeBase": str(eth_available_volume_base).lower(),

        "amount": str(available_volume if side == "sell" else -available_volume).lower(),
        "amountFilled": str(record["amount_fill"]).lower(),
        "price": str(price).lower(),

        "state": record["state"],

        # Signature: null on on-chain orders
        "v": record["v"],
        "r": Web3.toHex(record["r"]),
        "s": Web3.toHex(record["s"]),

        "date": record["date"].isoformat(),
        "updated": record["date"].isoformat() # TODO: Updated time
    }

    return response

@sio.on('getMarket')
async def get_market(sid, data):
    print("getMarket", data)

    current_block = App().web3.eth.getBlock("latest")["number"]
    token = data["token"] if "token" in data and Web3.isAddress(data["token"]) else None
    user = data["user"] if "user" in data and Web3.isAddress(data["user"]) else None

    # response vars
    trades = []
    my_trades = []
    my_funds = []
    
    # get all tickers
    tickers = await get_tickers()
    
    # if token is passed in
    if token:
        
        # get all trades
        trades = await get_trades(token)
        
        # get all buy orders
        orders_buys = await get_orders(ZERO_ADDR, token,
                                        state=OrderState.OPEN.name,
                                        sort="(amount_give / amount_get) DESC",
                                        expires_after=current_block)
        
        # get all sell orders
        orders_sells = await get_orders(token, ZERO_ADDR,
                                        state=OrderState.OPEN.name,
                                        sort="(amount_get / amount_give) ASC",
                                        expires_after=current_block)
        
        # if user is also passed in 
        if user:
            my_trades = await get_trades(token, user)
            my_funds = await get_transfers(token, user)

    # return this variable
    response = {
        "returnTicker": [format_ticker(ticker) for ticker in tickers],
        "trades": [format_trade(trade) for trade in trades],
        "myTrades": [format_trade(trade) for trade in my_trades],
        "myFunds": [format_transfer(transfer) for transfer in my_funds],
        "orders": {
            "buys": [format_order(order) for order in orders_buys],
            "sells": [format_order(order) for order in orders_sells]
        }
    }

    await sio.emit('market', response, room=sid)

@sio.on('disconnect')
def disconnect(sid):
    print('disconnect ', sid)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(App().db.establish_connection())
    web.run_app(app)
