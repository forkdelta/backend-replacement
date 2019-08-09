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

import asyncio
from datetime import datetime
import logging

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from web3 import Web3, HTTPProvider

from ..app import App
from ..config import ED_CONTRACT_ADDR, ED_CONTRACT_ABI
from ..lib.threaded_wrap_async import threaded_wrap_async
from ..src.contract_event_utils import block_timestamp

huey = App().huey
logger = logging.getLogger("tasks.update_order")
logger.setLevel(logging.DEBUG)

TASK_RETRIES = 3
TASK_RETRY_DELAY = 30


@huey.task(TASK_RETRIES, TASK_RETRY_DELAY)
@threaded_wrap_async
async def update_order_by_signature(order_signature):
    """
    Updates the fill of a single order given its signature.

    Arguments:
    order_signature: Order signature as a 0x-prefixed hex string
    """
    await internal_update_orders_by_signature([order_signature])
    return None


@huey.task(TASK_RETRIES, TASK_RETRY_DELAY)
@threaded_wrap_async
async def update_orders_by_signature(order_signatures):
    """
    Updates the fill of a single order given its signature.

    Arguments:
    order_signature: A list of 0x-prefixed hex string order signatures
    """
    await internal_update_orders_by_signature(order_signatures)
    return None


async def internal_update_orders_by_signature(signatures):
    logger.debug("Update orders by signatures=%s", signatures)
    orders = await fetch_order_by_signatures(signatures)
    await bulk_update_orders(orders)


@huey.task(TASK_RETRIES, TASK_RETRY_DELAY)
@threaded_wrap_async
async def update_orders_by_maker_and_token(maker_addr, token_addr,
                                           block_number):
    """
    Updates the fill of one or more orders given order maker and a token. The
    token may be on either side of the transaction.

    Arguments:
    marker_addr: Ethereum address of the order maker as a 0x-prefixed hex string
    token_addr: Address of the token on either side of the order as a 0x-prefixed hex string
    block_number: Limit updates to orders that expire after `block_number`
    """

    await internal_update_by_maker_and_tokens(maker_addr, [token_addr],
                                              block_number)
    return None


@huey.task(TASK_RETRIES, TASK_RETRY_DELAY)
@threaded_wrap_async
async def update_orders_by_maker_and_tokens(maker_addr, token_addrs,
                                            block_number):
    """
    Updates the fill of one or more orders given order maker and a token. The
    token may be on either side of the transaction.

    Arguments:
    marker_addr: Ethereum address of the order maker as a 0x-prefixed hex string
    token_addrs: A list of 0x-prefixed hex string token addresses on either side of the order
    block_number: Limit updates to orders that expire after `block_number`
    """
    await internal_update_by_maker_and_tokens(maker_addr, token_addrs,
                                              block_number)
    return None


async def internal_update_by_maker_and_tokens(maker, tokens, block_number):
    logger.debug("Update orders by maker=%s and tokens=%s, expires >= %i",
                 maker, tokens, block_number)
    orders = await fetch_orders_by_maker_and_tokens(maker, tokens,
                                                    block_number)

    if len(orders) > 0:
        logger.debug("updating up to %i orders", len(orders))
        await bulk_update_orders(orders)
        logger.info(
            "Updated up to %i orders by maker=%s and tokens=%s, expires >= %i",
            len(orders), maker, tokens, block_number)
    else:
        logger.warn("No orders found for maker=%s and tokens=%s", maker,
                    str(tokens))


SELECT_ORDER_STMT = """
    SELECT *
    FROM orders
    WHERE signature = any($1::bytea[])
"""


async def fetch_order_by_signatures(signatures):
    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            SELECT_ORDER_STMT,
            [Web3.toBytes(hexstr=signature) for signature in signatures])


FETCH_ORDERS_BY_MAKER_AND_TOKENS_STMT = """
    SELECT *
    FROM orders
    WHERE "user" = $1
        AND ("token_give" = any($2::bytea[]) OR "token_get" = any($2::bytea[]))
        AND "expires" >= $3
        AND "state" = 'OPEN'::orderstate
"""


async def fetch_orders_by_maker_and_tokens(maker, tokens, expires_at):
    tokens_as_bytes = [Web3.toBytes(hexstr=t) for t in tokens]
    async with App().db.acquire_connection() as conn:
        return await conn.fetch(FETCH_ORDERS_BY_MAKER_AND_TOKENS_STMT,
                                Web3.toBytes(hexstr=maker), tokens_as_bytes,
                                expires_at)


UPDATE_ORDER_FILL_STMT = """
    UPDATE "orders"
    SET "amount_fill" = GREATEST("amount_fill", $1),
        "available_volume" = $2,
        "state" = (CASE
                    WHEN "state" IN ('FILLED'::orderstate, 'CANCELED'::orderstate) THEN "state"
                    WHEN ("amount_get" <= GREATEST("amount_fill", $1)) THEN 'FILLED'::orderstate
                    ELSE 'OPEN'::orderstate END),
        "updated"  = $3
    WHERE "signature" = $4 AND ("updated" IS NULL OR "updated" <= $3)
"""

MAX_ORDER_SERVICE_CHUNK = 250


async def bulk_update_orders(orders):
    for i in range(0, len(orders), MAX_ORDER_SERVICE_CHUNK):
        sub_orders = orders[i:i + MAX_ORDER_SERVICE_CHUNK]
        state = await refresh_order_state(sub_orders)

        update_block_number = int(state["blockNumber"])
        updated_at = datetime.fromtimestamp(
            block_timestamp(App().web3, update_block_number), tz=None)

        updated_orders = state["orders"]
        update_many_args = [(
            Web3.toInt(new_order_state["amountFilled"])
            if "amountFilled" in new_order_state else None,
            Web3.toInt(new_order_state["availableVolume"])
            if "availableVolume" in new_order_state else None,
            updated_at,
            order["signature"],
        ) for (order, new_order_state) in ((
            order,
            updated_orders[Web3.toHex(order["signature"])],
        ) for order in sub_orders)]

        async with App().db.acquire_connection() as conn:
            await conn.executemany(UPDATE_ORDER_FILL_STMT, update_many_args)


async def refresh_order_state(orders):
    data = dict(
        contractAddr=ED_CONTRACT_ADDR,
        orders={
            Web3.toHex(order["signature"]): list(
                map(str, order_as_args(order)))
            for order in orders
        },
    )

    s = requests.Session()
    retries = Retry(
        total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    s.mount('http://', HTTPAdapter(max_retries=retries))
    r = s.post("http://order_refresh:3000", json=data, timeout=(3, 15))
    return r.json()


EMPTY_BYTES32 = b'0' * 32


def order_as_args(order):
    order = dict(order)
    return (
        Web3.toHex(order["token_get"]),
        Web3.toInt(order["amount_get"]),
        Web3.toHex(order["token_give"]),
        Web3.toInt(order["amount_give"]),
        Web3.toInt(order["expires"]),
        Web3.toInt(order["nonce"]),
        Web3.toHex(order["user"]),
        order.get("v") or 0,
        Web3.toHex(order.get("r") or EMPTY_BYTES32),
        Web3.toHex(order.get("s") or EMPTY_BYTES32),
    )
