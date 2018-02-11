from app.lib.threaded_wrap_async import threaded_wrap_async
import asyncio
from datetime import datetime
import logging
from web3 import Web3, HTTPProvider

from ..app import App
from ..config import ED_CONTRACT_ADDR, ED_CONTRACT_ABI
from ..src.contract_event_utils import block_timestamp

huey = App().huey
logger = logging.getLogger("tasks.update_order")
logger.setLevel(logging.DEBUG)

@huey.task()
@threaded_wrap_async
async def update_order_by_signature(order_signature):
    logger.debug("Update order by signature={}".format(order_signature))
    order = await fetch_order_by_signature(order_signature)
    await update_order(order)
    return None

@huey.task()
@threaded_wrap_async
async def update_orders_by_maker(maker_addr, token_addr):
    print("Update order by maker={} and token={}".format(maker_addr, token_addr))
    return None

SELECT_ORDER_STMT = """
    SELECT *
    FROM orders
    WHERE signature = $1
"""
async def fetch_order_by_signature(signature):
    async with App().db.acquire_connection() as conn:
        return await conn.fetchrow(SELECT_ORDER_STMT, Web3.toBytes(hexstr=signature))

UPDATE_ORDER_FILL_STMT = """
    UPDATE "orders"
    SET "amount_fill" = GREATEST("amount_fill", $1),
        "state" = (CASE
                    WHEN "state" IN ('FILLED'::orderstate, 'CANCELED'::orderstate) THEN "state"
                    WHEN ("amount_get" <= GREATEST("amount_fill", $1)) THEN 'FILLED'::orderstate
                    ELSE 'OPEN'::orderstate END),
        "updated"  = $2
    WHERE "signature" = $3
"""
async def update_order(order):
    contract = App().web3.eth.contract(ED_CONTRACT_ADDR, abi=ED_CONTRACT_ABI)

    maker = Web3.toHex(order["user"])
    signature = Web3.toBytes(order["signature"])
    updated_at = datetime.fromtimestamp(block_timestamp(App().web3, "latest"), tz=None)

    amount_fill = contract.call().orderFills(maker, signature)

    update_args = (amount_fill, updated_at, signature)
    async with App().db.acquire_connection() as conn:
        await conn.execute(UPDATE_ORDER_FILL_STMT, *update_args)
    logger.info("updated order signature=%s fill=%i", Web3.toHex(signature), amount_fill)
