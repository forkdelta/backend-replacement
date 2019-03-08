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

from ..app import App
import asyncio
from app.config import ED_CONTRACT_ADDR, ED_CONTRACT_ABI, ED_WS_SERVERS, STOPPED_TOKENS
from ..src.contract_event_utils import block_timestamp
from datetime import datetime
from decimal import Decimal, localcontext
import json
import logging
from ..src.order_enums import OrderSource, OrderState
from ..src.order_hash import make_order_hash
from pprint import pformat
from queue import Queue, Empty as QueueEmpty
from random import sample
from ..src.socketio_client import SocketIOClient
from time import time
from ..src.utils import parse_insert_status
from web3 import Web3
from websockets.exceptions import ConnectionClosed, InvalidStatusCode
from ..src.order_message_validator import OrderMessageValidatorEtherdelta
from ..src.order_signature import order_signature_valid
from ..constants import ZERO_ADDR

logger = logging.getLogger('etherdelta_observer')
logger.setLevel(logging.DEBUG)

CHECK_TOKENS_PER_PONG = 4
market_queue = Queue()


def fill_queue():
    for token in App().tokens():
        token_addr = token["addr"].lower()
        if token_addr not in STOPPED_TOKENS:
            market_queue.put(token_addr)
    logger.info("%i tokens added to market queue", market_queue.qsize())


fill_queue()

web3 = App().web3
contract = web3.eth.contract(ED_CONTRACT_ADDR, abi=ED_CONTRACT_ABI)


async def on_connect(io_client, event):
    logger.info("ED API client connected to %s", io_client.ws_url)


async def on_error(io_client, event, error):
    logger.critical("ED API client (connected to %s) error: %s",
                    io_client.ws_url, error)


async def on_disconnect(io_client, event):
    logger.info("ED API client disconnected from %s", io_client.ws_url)


def validate_order(order, current_block=None):
    """
    Validates an order dictionary. Returns True if the order is valid, False otherwise.
    """

    v = OrderMessageValidatorEtherdelta()
    if not v.validate(order):
        error_msg = "Invalid message format"
        details_dict = dict(data=order, errors=v.errors)
        logger.warning("ED order rejected: %s: %s", error_msg, details_dict)
        return False

    order_validated = v.document  # Get data with validated and coerced values

    # Require one side of the order to be base currency
    if order_validated["tokenGet"] != ZERO_ADDR and order_validated["tokenGive"] != ZERO_ADDR:
        error_msg = "Cannot post order with pair {}-{}: neither is a base currency".format(
            order_validated["tokenGet"], order_validated["tokenGive"])
        logger.warning("ED order rejected: %s", error_msg)
        return

    # Require order to be non-expired
    if current_block and order_validated["expires"] <= current_block:
        error_msg = "Cannot record order because it has already expired"
        details_dict = {
            "blockNumber": current_block,
            "expires": order_validated["expires"],
            "date": datetime.utcnow().isoformat()
        }
        logger.warning("ED Order rejected: %s: %s", error_msg, details_dict)
        return False

    # Require a valid signature
    if not order_signature_valid(order_validated):
        logger.warning(
            "ED Order rejected: Invalid signature: raw_order = %s, order = %s",
            order, order_validated)
        return False

    # Observe stopped tokens
    if order_validated["tokenGet"] in STOPPED_TOKENS or order_validated["tokenGive"] in STOPPED_TOKENS:
        error_msg = "Cannot post order with pair {}-{}: order book is stopped".format(
            order_validated["tokenGet"], order_validated["tokenGive"])
        logger.warning("ED Order rejected: %s", error_msg)
        return False
    return True


from functools import partial


async def process_orders(orders):
    current_block = web3.eth.blockNumber  # TODO: Introduce a strict timeout here; on failure allow order (todo copied from websocket_server.py)

    not_deleted_filter = lambda order: "deleted" not in order or not order["deleted"]
    invalid_orders_filter = partial(
        validate_order, current_block=current_block)

    logger.info("Processing %i orders", len(orders))
    orders = list(
        filter(invalid_orders_filter, filter(not_deleted_filter, orders)))
    logger.debug("Filtered orders: %i", len(orders))

    for order in orders:
        try:
            await record_order(order)
        except Exception as e:
            logger.critical("Error while processing order '%s'", order)
            raise e


async def on_orders(io_client, event, payload=None):
    await process_orders([*payload["buys"], *payload["sells"]])


async def on_market(io_client, event, payload):
    if "orders" not in payload:
        # The beautiful market API
        return

    await process_orders(
        [*payload["orders"]["buys"], *payload["orders"]["sells"]])


async def on_pong(io_client, event):
    logger.info("Connection to %s alive: pong received", io_client.ws_url)
    # await io_client.emit("getMarket", { "token": ZERO_ADDR })
    for _ in range(CHECK_TOKENS_PER_PONG):
        try:
            token = market_queue.get_nowait()
        except QueueEmpty:
            fill_queue()
            break  # better luck next time!
        else:
            logger.info("Query token %s", token)
            await io_client.emit("getMarket", {"token": token})
            await asyncio.sleep(4)


INSERT_ORDER_STMT = """
    INSERT INTO orders
    (
        "source", "signature",
        "token_give", "amount_give", "token_get", "amount_get", "available_volume",
        "expires", "nonce", "user", "state", "v", "r", "s", "date", "sorting_price"
    )
    VALUES ($1, $2, $3, $4, $5, $6, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
    ON CONFLICT ON CONSTRAINT index_orders_on_signature DO NOTHING
"""
from ..tasks.update_order import update_order_by_signature


async def record_order(order):
    order_maker = order["user"]
    signature = make_order_hash(order)

    amount_give = Decimal(order["amountGive"])
    amount_get = Decimal(order["amountGet"])

    # if tokenGive is ZERO_ADDR, sort by (amount_give / amount_get) DESC
    #   => -(amount_give / amount_get) ASC
    # if tokenGet is ZERO_ADDR, sort by (amount_get / amount_give) ASC
    if order["tokenGive"] == ZERO_ADDR:
        with localcontext() as decimal_ctx:
            decimal_ctx.prec = 10
            sorting_price = -amount_give / amount_get
    else:
        with localcontext() as decimal_ctx:
            decimal_ctx.prec = 10
            sorting_price = amount_get / amount_give

    insert_args = (
        OrderSource.OFFCHAIN.name,
        Web3.toBytes(hexstr=signature),
        Web3.toBytes(hexstr=order["tokenGive"]),
        amount_give,
        Web3.toBytes(hexstr=order["tokenGet"]),
        amount_get,
        int(order["expires"]),
        int(order["nonce"]),
        Web3.toBytes(hexstr=order["user"]),
        OrderState.OPEN.name,
        int(order["v"]),
        Web3.toBytes(hexstr=order["r"]),
        Web3.toBytes(hexstr=order["s"]),
        datetime.utcnow(),
        sorting_price,
    )

    async with App().db.acquire_connection() as connection:
        insert_retval = await connection.execute(INSERT_ORDER_STMT,
                                                 *insert_args)
        _, _, did_insert = parse_insert_status(insert_retval)

    if did_insert:
        logger.info("recorded order signature=%s, user=%s, expires=%i",
                    signature, order["user"], int(order["expires"]))
        update_order_by_signature(signature)


async def main(my_id, num_observers):
    ws_url = ED_WS_SERVERS[my_id]
    io_client = SocketIOClient(ws_url)
    io_client.on("orders", on_orders)
    io_client.on("market", on_market)
    io_client.on("pong", on_pong)  # Schedules full refreshes
    io_client.on("connect", on_connect)
    io_client.on("disconnect", on_disconnect)

    last_attempt = None  # TODO: Exponential backoff
    while True:
        try:
            await io_client.start()
        except (ConnectionClosed, InvalidStatusCode) as e:
            logger.warn("Connection with %s lost with %s", ws_url, e)
            await asyncio.sleep(5.0)
            continue
    # Exceptions to handle:
    # - websockets.exceptions.InvalidStatusCode: LIKE Status code not 101: 521
    # - websockets.exceptions.ConnectionClosed: LIKE WebSocket connection is closed: code = 1006 (connection closed abnormally [internal]),


NUM_OBSERVERS = 6
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    tasks = [
        asyncio.ensure_future(main(i, NUM_OBSERVERS))
        for i in range(0, NUM_OBSERVERS)
    ]
    loop.run_until_complete(asyncio.gather(*tasks))
