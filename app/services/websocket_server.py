# ForkDelta Backend
# https://github.com/forkdelta/backend-replacement
# Copyright (C) 2018, Arseniy Ivanov and ForkDelta Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from aiohttp import web
import asyncio
from datetime import datetime
from decimal import getcontext
import logging
from time import time
import socketio
from web3 import Web3
import websockets

from ..app import App
from ..config import ALLOWED_ORIGIN_SUFFIXES, ED_CONTRACT_ADDR, HTTP_ORDERS_ENDPOINT_SECRET, STOPPED_TOKENS
from ..src.erc20_token import ERC20Token
from ..src.order_enums import OrderState
from ..constants import ZERO_ADDR, ZERO_ADDR_BYTES, MAX_ORDERS_PER_USER
from ..lib import rapidjson

sio_logger = logging.getLogger('socketio.AsyncServer')
sio_logger.setLevel(logging.DEBUG)
sio = socketio.AsyncServer(logger=sio_logger, json=rapidjson)
app = web.Application()
routes = web.RouteTableDef()
sio.attach(app)

logger = logging.getLogger('websocket_server')
logger.setLevel(logging.DEBUG)

getcontext().prec = 10

from urllib.parse import urlparse


def is_origin_allowed(origin):
    """
    Returns True if the origin has hostname suffix in the allowed origins list.
    Additionally, returns True if the origin has `file` scheme.
    Otherwise, returns False.

    Eg.:
    is_origin_allowed("https://forkdelta.github.io") => True
    is_origin_allowed("https://forkdelta.com/") => True
    is_origin_allowed("https://api.forkdelta.com/") => True
    is_origin_allowed("http://localhost:3000/") => True
    is_origin_allowed("http://localhost:8080/") => True
    is_origin_allowed("wss://api.forkdelta.com/") => True
    is_origin_allowed("ws://localhost:3001/") => True
    is_origin_allowed("file://") => False
    is_origin_allowed("https://forkdelta.bs/") => False
    is_origin_allowed("https://forkscamster.github.io/") => False
    """
    parsed = urlparse(origin)
    if parsed.scheme in ('http', 'https', 'ws', 'wss'):
        return isinstance(parsed.hostname, str) and any([
            parsed.hostname.endswith(suffix)
            for suffix in ALLOWED_ORIGIN_SUFFIXES
        ])
    elif parsed.scheme == "file":
        return True
    return False


def safe_list_render(records, render_func):
    """
    Safely render a list of records given a render_func.

    Arguments:
    - records: a list of records compatible with the formatter
    - render_func: a function mapping records to desired format
    Returns: a list of objects
    """
    import logging

    def safe_render_func(record):
        try:
            return render_func(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            logging.exception(
                "Exception while trying to render a record with %s",
                repr(render_func))
            return None

    return list(filter(None, map(safe_render_func, records)))


sid_environ = {}

current_block = None


def get_current_block(ignore_cache=False):
    global current_block
    if not current_block or ignore_cache:
        current_block = App().web3.eth.blockNumber
    return current_block


@sio.on('connect')
def connect(sid, environ):
    logger.debug("event=connect sid=%s ip=%s", sid,
                 environ.get('HTTP_X_REAL_IP'))
    sid_environ[sid] = environ
    if "HTTP_ORIGIN" in environ and not is_origin_allowed(
            environ["HTTP_ORIGIN"]):
        logger.info("Connection denied: Origin %s not allowed, environ=%s",
                    environ["HTTP_ORIGIN"], environ)
        return False


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
    where = '(("token_give" = $1 AND "token_get" = $2) OR ("token_get" = $1 AND "token_give" = $2))'
    placeholder_args = [Web3.toBytes(hexstr=token_hexstr), ZERO_ADDR_BYTES]
    if user_hexstr:
        where += ' AND ("addr_give" = $3 OR "addr_get" = $3)'
        placeholder_args.append(Web3.toBytes(hexstr=user_hexstr))

    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM trades
            WHERE {}
            ORDER BY block_number DESC, date DESC
            LIMIT 100
            """.format(where), *placeholder_args)


async def get_new_trades(created_after):
    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM trades
            WHERE ("date" > $1) AND ("token_give" = $2 OR "token_get" = $2)
            ORDER BY block_number DESC, date DESC
            """, created_after, ZERO_ADDR_BYTES)


def format_transfer(transfer):
    contract = ERC20Token(transfer["token"])

    return {
        "txHash": Web3.toHex(transfer["transaction_hash"]),
        "tokenAddr": Web3.toHex(transfer["token"]),
        "user": Web3.toHex(transfer["user"]),
        "kind": transfer["direction"].title(),
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
            LIMIT 100
            """,
            Web3.toBytes(hexstr=user_hexstr),
            Web3.toBytes(hexstr=token_hexstr),
            Web3.toBytes(hexstr=ZERO_ADDR))


async def get_new_transfers(created_after):
    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM transfers
            WHERE ("date" > $1)
            ORDER BY block_number DESC, date DESC
            """, created_after)


async def get_orders(token_give_hexstr,
                     token_get_hexstr,
                     user_hexstr=None,
                     expires_after=None,
                     state=None,
                     with_available_volume=False,
                     sort=None,
                     limit=300):
    assert isinstance(limit,
                      int), "expected limit to be an integer, got {}".format(
                          limit.__class__.__name__)

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

    if with_available_volume:
        where += ' AND ("available_volume" IS NULL OR "available_volume" > 0)'

    order_by = ['expires ASC']
    if sort is not None:
        order_by.insert(0, sort)

    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM orders
            WHERE {}
            ORDER BY {}
            LIMIT {}
            """.format(where, ", ".join(order_by), limit), *placeholder_args)


async def get_updated_orders(updated_after,
                             token_give_hexstr=None,
                             token_get_hexstr=None):
    """
    Returns a list of order Records created or updated after a given datetime,
    filtered by at most one of token_give_hexstr, token_get_hexstr.

    Arguments:
    - updated_after: a datetime object.
    - token_give_hexstr: 0x-prefixed hex encoding Ethereum address, optional.
    - token_get_hexstr: 0x-prefixed hex encoding Ethereum address, optional.
    """

    where = '("date" >= $1 OR "updated" >= $1)'
    placeholder_args = [updated_after]

    if token_give_hexstr:
        where += ' AND ("token_give" = $2)'
        placeholder_args.append(Web3.toBytes(hexstr=token_give_hexstr))
    elif token_get_hexstr:
        where += ' AND ("token_get" = $2)'
        placeholder_args.append(Web3.toBytes(hexstr=token_get_hexstr))

    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM orders
            WHERE {}
            ORDER BY updated ASC, date ASC
            """.format(where), *placeholder_args)


def format_order_simple(record):
    return {
        "hash": Web3.toHex(record["signature"]),
        "user": Web3.toHex(record["user"]),
        "tokenGet": Web3.toHex(record["token_get"]),
        "amountGet": str(int(record["amount_get"])),
        "tokenGive": Web3.toHex(record["token_give"]),
        "amountGive": str(int(record["amount_give"])),
        "expires": str(int(record["expires"])),
        "nonce": str(int(record["nonce"])),

        # Signature: null on on-chain orders
        "v": record["v"],
        "r": Web3.toHex(record["r"]) if record["r"] else None,
        "s": Web3.toHex(record["s"]) if record["s"] else None,
        "date": record["date"].isoformat(),
    }


def format_order(record):
    contract_give = ERC20Token(record["token_give"])
    contract_get = ERC20Token(record["token_get"])

    side = "buy" if record["token_give"] == ZERO_ADDR_BYTES else "sell"

    response = {
        "id": "{}_{}".format(Web3.toHex(record["signature"]), side),
        "hash": Web3.toHex(record["signature"]),
        "user": Web3.toHex(record["user"]),
        "state": record["state"],
        "tokenGet": Web3.toHex(record["token_get"]),
        "amountGet": str(int(record["amount_get"])),
        "tokenGive": Web3.toHex(record["token_give"]),
        "amountGive": str(int(record["amount_give"])),
        "expires": str(int(record["expires"])),
        "nonce": str(int(record["nonce"])),

        # Signature: null on on-chain orders
        "v": record["v"],
        "r": Web3.toHex(record["r"]) if record["r"] else None,
        "s": Web3.toHex(record["s"]) if record["s"] else None,
        "date": record["date"].isoformat(),
        "updated": (record["updated"] or record["date"]).isoformat()
    }

    if side == "buy":
        coin_contract = ERC20Token(record["token_get"])
        base_contract = ERC20Token(record["token_give"])

        price = base_contract.denormalize_value(
            record["amount_give"]) / coin_contract.denormalize_value(
                record["amount_get"])

        available_volume = record.get("available_volume", record["amount_get"])
        eth_available_volume = coin_contract.denormalize_value(
            available_volume)

        # available base volume = available token volume * price
        available_volume_base = (
            available_volume * record["amount_give"]) / record["amount_get"]
        eth_available_volume_base = base_contract.denormalize_value(
            available_volume_base)
    else:
        coin_contract = ERC20Token(record["token_give"])
        base_contract = ERC20Token(record["token_get"])

        price = base_contract.denormalize_value(
            record["amount_get"]) / coin_contract.denormalize_value(
                record["amount_give"])

        available_volume_base = record.get("available_volume",
                                           record["amount_get"])
        eth_available_volume_base = base_contract.denormalize_value(
            available_volume_base)

        # available token volume = available base volume * price
        available_volume = (available_volume_base *
                            record["amount_give"]) / record["amount_get"]
        eth_available_volume = coin_contract.denormalize_value(
            available_volume)

    response.update({
        "availableVolume":
        str(available_volume).lower(),
        "ethAvailableVolume":
        str(eth_available_volume).lower(),
        "availableVolumeBase":
        str(available_volume_base).lower(),
        "ethAvailableVolumeBase":
        str(eth_available_volume_base).lower(),
        "amount":
        str(available_volume if side == "sell" else -available_volume).lower(),
        "amountFilled":
        str(record["amount_fill"] or 0).lower(),
        "price":
        str(price).lower(),
    })

    # Mark order deleted if it is closed or if available volume is 0
    if record["state"] != OrderState.OPEN.name or \
        (record["available_volume"] and record["available_volume"] == 0):
        response.update({"deleted": True})

    return response


tickers_cache = []


async def get_tickers(ignore_cache=False):
    if len(tickers_cache) == 0 or ignore_cache:
        async with App().db.acquire_connection() as conn:
            return await conn.fetch("""
                SELECT *
                FROM tickers
                """)
    else:
        return tickers_cache


def ticker_key(ticker):
    """
    Given a ticker record, returns a ticker dictionary key.

    The key consists of base name (currently, ETH), an underscore, and 9
    first characters of the contract address.
    """
    return "{}_{}".format("ETH", Web3.toHex(ticker["token_address"])[:9])


def format_ticker(ticker):
    return dict(
        tokenAddr=Web3.toHex(ticker["token_address"]),
        quoteVolume=str(ticker["quote_volume"]).lower(),
        baseVolume=str(ticker["base_volume"]).lower(),
        last=str(ticker["last"]).lower() if ticker["last"] else None,
        bid=str(ticker["bid"]).lower() if ticker["bid"] else None,
        ask=str(ticker["ask"]).lower() if ticker["ask"] else None,
        updated=ticker["updated"].isoformat())


def format_tickers(tickers):
    return {ticker_key(ticker): format_ticker(ticker) for ticker in tickers}


@routes.get('/returnTicker')
async def http_return_ticker(request):
    return web.json_response(
        format_tickers(await get_tickers()), dumps=rapidjson.dumps)


@routes.get('/returnOrderBook')
async def http_return_order_book(request):
    if request.query.get("secret", None) != HTTP_ORDERS_ENDPOINT_SECRET:
        return web.json_response("Unauthorized", status=403)

    data = request.query
    token = data["token"].lower() if "token" in data and Web3.isAddress(
        data["token"]) else None

    if not token:
        return web.json_response(
            {
                "error": "Invalid request: token not specified"
            }, status=400)

    if token in STOPPED_TOKENS:
        return web.json_response(
            {
                "error": "Cannot return order book for a stopped token"
            },
            status=403)

    orders_buys, orders_sells = await asyncio.gather(
        get_orders(
            ZERO_ADDR,
            token,
            sort="sorting_price",
            expires_after=get_current_block(),
            limit=int(data.get("limit", 300))),
        get_orders(
            token,
            ZERO_ADDR,
            sort="sorting_price",
            expires_after=get_current_block(),
            limit=int(data.get("limit", 300))))

    return web.json_response(
        {
            "buys": safe_list_render(orders_buys, format_order_simple),
            "sells": safe_list_render(orders_sells, format_order_simple)
        },
        dumps=rapidjson.dumps)


@sio.on('getMarket')
async def get_market(sid, data):
    start_time = time()

    if sid not in sid_environ:
        logger.error(
            "received getMarket from sid=%s, but it is not in environs", sid)
        # Force a disconnect
        await sio.disconnect(sid)
        return

    if not isinstance(data, dict):
        logger.warn("event=getMarket sid=%s data='%s'", sid, data)
        await sio.emit(
            'exception', {
                "errorCode": 400,
                "errorMessage": "getMarket payload must be an object"
            },
            room=sid)
        return

    token = data["token"].lower() if "token" in data and Web3.isAddress(
        data["token"]) else None
    user = data["user"].lower() if "user" in data and Web3.isAddress(
        data["user"]) and data["user"].lower() != ED_CONTRACT_ADDR else None

    response = {"returnTicker": format_tickers(await get_tickers())}

    if token:
        trades = await get_trades(token)
        response.update({"trades": safe_list_render(trades, format_trade)})

        if token not in STOPPED_TOKENS:
            orders_buys = await get_orders(
                ZERO_ADDR,
                token,
                state=OrderState.OPEN.name,
                with_available_volume=True,
                sort="sorting_price",
                expires_after=get_current_block())
            orders_sells = await get_orders(
                token,
                ZERO_ADDR,
                state=OrderState.OPEN.name,
                with_available_volume=True,
                sort="sorting_price",
                expires_after=get_current_block())

            response.update({
                "orders": {
                    "buys": safe_list_render(orders_buys, format_order),
                    "sells": safe_list_render(orders_sells, format_order)
                }
            })
        else:
            response.update({"orders": {"buys": [], "sells": []}})

        if user:
            my_trades = await get_trades(token, user)
            my_funds = await get_transfers(token, user)
            my_orders_buys = await get_orders(
                ZERO_ADDR,
                token,
                user_hexstr=user,
                state=OrderState.OPEN.name,
                sort="sorting_price",
                expires_after=get_current_block())
            my_orders_sells = await get_orders(
                token,
                ZERO_ADDR,
                user_hexstr=user,
                state=OrderState.OPEN.name,
                sort="sorting_price",
                expires_after=get_current_block())
            response.update({
                "myTrades":
                safe_list_render(my_trades, format_trade),
                "myFunds":
                safe_list_render(my_funds, format_transfer),
                "myOrders": {
                    "buys": safe_list_render(my_orders_buys, format_order),
                    "sells": safe_list_render(my_orders_sells, format_order)
                }
            })

    await sio.emit('market', response, room=sid)
    logger.debug(
        'event=getMarket sid=%s ip=%s token=%s user=%s current_block=%i duration=%f',
        sid, sid_environ[sid].get('HTTP_X_REAL_IP'), token, user,
        get_current_block(),
        time() - start_time)


TICKER_UPDATE_INTERVAL = 60.0


async def update_tickers_cache():
    while True:
        try:
            tickers_cache = await get_tickers(ignore_cache=True)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            logger.exception("Exception occurred in update_tickers_cache")
        else:
            logger.debug("tickers cache updated")

        await sio.sleep(TICKER_UPDATE_INTERVAL)


STREAM_UPDATES_INTERVAL = 5.0


async def stream_order_updates():
    not_stopped_predicate = lambda order: not (Web3.toHex(order["token_give"]) in STOPPED_TOKENS or Web3.toHex(order["token_get"]) in STOPPED_TOKENS)

    while True:
        updated_after = datetime.utcnow()
        await sio.sleep(STREAM_UPDATES_INTERVAL)

        # Stream updated orders
        orders_buys = list(
            filter(
                not_stopped_predicate, await get_updated_orders(
                    updated_after, token_give_hexstr=ZERO_ADDR)))
        orders_sells = list(
            filter(
                not_stopped_predicate, await get_updated_orders(
                    updated_after, token_get_hexstr=ZERO_ADDR)))
        if orders_buys or orders_sells:  # Emit when there are updates only
            await sio.emit(
                "orders", {
                    "buys": safe_list_render(orders_buys, format_order),
                    "sells": safe_list_render(orders_sells, format_order)
                })


async def stream_new_trades():
    """
    Streams new trades, based on date column. Advances "updates-since" when
    encounters a later timestamp on a record.
    """
    updated_after = datetime.utcnow()
    while True:
        await sio.sleep(STREAM_UPDATES_INTERVAL)
        trades = await get_new_trades(updated_after)
        if trades:  # Emit when there are updates
            await sio.emit("trades", safe_list_render(trades, format_trade))
            # Only advance updated_after after we received new trades, as
            # they come backdated by block timestamp
            updated_after = max(map(lambda t: t["date"], trades))


async def stream_new_transfers():
    """
    Streams new transfers, based on date column. Advances "updates-since" when
    encounters a later timestamp on a record.
    """
    updated_after = datetime.utcnow()
    while True:
        await sio.sleep(STREAM_UPDATES_INTERVAL)
        transfers = await get_new_transfers(updated_after)
        if transfers:  # Emit when there are updates
            await sio.emit("funds", safe_list_render(transfers,
                                                     format_transfer))
            # Only advance updated_after after we received new trades, as
            # they come backdated by block timestamp
            updated_after = max(map(lambda t: t["date"], transfers))


from ..src.order_hash import make_order_hash
from ..src.order_message_validator import OrderMessageValidator
from ..src.order_signature import order_signature_valid
from ..src.record_order import record_order
from ..tasks.update_order import update_order_by_signature


async def count_orders(token_give_hexstr,
                       token_get_hexstr,
                       user_hexstr=None,
                       expires_after=None,
                       state=None):
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

    async with App().db.acquire_connection() as conn:
        return await conn.fetchval(
            """
            SELECT COUNT(*) as order_count
            FROM orders
            WHERE {}
            """.format(where), *placeholder_args)


@sio.on('message')
async def handle_order(sid, data):
    """
    Handles `message` event type. See schema for payload schema.

    On error, emits a `messageResult` event to the originating sid with an array payload, containing:
    1. Error code:
      - 400 if the event payload could not be interpreted due to client error (cf. https://httpstatuses.com/400)
      - 422 if the event payload contained semantic errors (cf. https://httpstatuses.com/422)
    2. A string error message with a brief description of the problem.
    3. An object containing some useful details for debugging.

    On success, emits a `messageResult` event to the originating sid with an array payload, containing:
    1. Success code 202: the order has been accepted.
    2. A brief message confirming success.
    """

    if sid not in sid_environ:
        logger.error("received message from sid=%s, but it is not in environs",
                     sid)
        # Force a disconnect
        await sio.disconnect(sid)
        return

    logger.debug('message %s %s', sid, sid_environ[sid].get('HTTP_X_REAL_IP'))

    v = OrderMessageValidator()
    if not v.validate(data):
        error_msg = "Invalid message format"
        details_dict = dict(data=data, errors=v.errors)
        logger.warning("Order rejected: %s: %s", error_msg, details_dict)
        await sio.emit(
            "messageResult", [400, error_msg, details_dict], room=sid)
        return

    message = v.document  # Get data with validated and coerced values

    # Require new orders are posted to the latest contract
    if message["contractAddr"].lower() != ED_CONTRACT_ADDR.lower():
        error_msg = "Cannot post an order to contract {}".format(
            message["contractAddr"].lower())
        logger.warning("Order rejected: %s", error_msg)
        await sio.emit("messageResult", [422, error_msg], room=sid)
        return

    # Require one side of the order to be base currency
    if message["tokenGet"] != ZERO_ADDR and message["tokenGive"] != ZERO_ADDR:
        error_msg = "Cannot post order with pair {}-{}: neither is a base currency".format(
            message["tokenGet"], message["tokenGive"])
        logger.warning("Order rejected: %s", error_msg)
        await sio.emit("messageResult", [422, error_msg], room=sid)
        return

    # Require new orders to be non-expired
    if message["expires"] <= get_current_block():
        error_msg = "Cannot post order because it has already expired"
        details_dict = {
            "blockNumber": get_current_block(),
            "expires": message["expires"],
            "date": datetime.utcnow().isoformat()
        }
        logger.warning("Order rejected: %s: %s", error_msg, details_dict)
        await sio.emit(
            "messageResult", [422, error_msg, details_dict], room=sid)
        return

    # Oh yes, require orders to have a valid signature
    if not order_signature_valid(message):
        logger.warning("Order rejected: Invalid signature: order = %s",
                       message)
        error_msg = "Cannot post order: invalid signature"
        await sio.emit("messageResult", [422, error_msg], room=sid)
        return

    # Observe stopped tokens
    if message["tokenGet"] in STOPPED_TOKENS or message["tokenGive"] in STOPPED_TOKENS:
        error_msg = "Cannot post order with pair {}-{}: order book is stopped".format(
            message["tokenGet"], message["tokenGive"])
        logger.warning("Order rejected: %s", error_msg)
        await sio.emit("messageResult", [422, error_msg], room=sid)
        return

    # Limit number of orders submitted by a single user
    user_order_count = await count_orders(message["tokenGive"],
                                          message["tokenGet"], message["user"],
                                          get_current_block(), "OPEN")

    if user_order_count >= MAX_ORDERS_PER_USER:
        error_msg = "Too many open orders: maximum of {} open orders permitted at one time".format(
            MAX_ORDERS_PER_USER)
        logger.warning("Order rejected: %s", error_msg)
        await sio.emit("messageResult", [422, error_msg], room=sid)
        return

    # 3. Record order
    did_insert = await record_order(message)
    if did_insert:
        signature = make_order_hash(message)
        logger.info("recorded order signature=%s, user=%s, expires=%i",
                    signature, message["user"], message["expires"])

        # 4. Enqueue a job to refresh available volume
        update_order_by_signature(signature)

    await sio.emit('messageResult', [202, "Good job!"], room=sid)


@sio.on('disconnect')
def disconnect(sid):
    logger.debug('disconnect %s %s', sid,
                 sid_environ[sid].get('HTTP_X_REAL_IP'))
    del sid_environ[sid]


BLOCK_UPDATE_INTERVAL = 6.0


async def update_current_block():
    while True:
        try:
            get_current_block(ignore_cache=True)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            logger.exception("Exception occurred in update_current_block")
        else:
            logger.debug("current_block=%i", get_current_block())

        await sio.sleep(BLOCK_UPDATE_INTERVAL)


app.router.add_routes(routes)
if __name__ == "__main__":
    sio.start_background_task(stream_order_updates)
    sio.start_background_task(stream_new_trades)
    sio.start_background_task(stream_new_transfers)
    sio.start_background_task(update_current_block)
    sio.start_background_task(update_tickers_cache)
    web.run_app(app)
