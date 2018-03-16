#!/usr/bin/env python

from app import App
import asyncio
from config import ED_CONTRACT_ADDR, ED_CONTRACT_ABI
from contract_event_utils import block_timestamp
from datetime import datetime
from decimal import Decimal
import logging
from order_hash import make_order_hash
from utils import parse_insert_status
import sys
from web3 import Web3

logger = logging.getLogger('order_fill_backfill')
logger.setLevel(logging.DEBUG)

ZERO_ADDR = "0x0000000000000000000000000000000000000000"
ZERO_ADDR_BYTES = Web3.toBytes(hexstr=ZERO_ADDR)
SELECT_ORDERS_STMT = """
    SELECT *
    FROM orders
    WHERE ("token_get" = $1 OR "token_give" = $1)
"""
UPDATE_ORDER_FILL_STMT = """
    UPDATE "orders"
    SET "amount_fill" = GREATEST("amount_fill", $1),
        "state" = (CASE
                    WHEN "state" IN ('FILLED'::orderstate, 'CANCELED'::orderstate) THEN "state"
                    WHEN ("amount_get" <= GREATEST("amount_fill", $1)) THEN 'FILLED'::orderstate
                    ELSE 'OPEN'::orderstate END),
        "updated"  = $2
    WHERE "signature" = $3
""" # Totally a duplicate of contract event recorder SQL

web3 = App().web3
contract = web3.eth.contract(ED_CONTRACT_ADDR, abi=ED_CONTRACT_ABI)

async def main(token_addr):
    async with App().db.acquire_connection() as conn:
        orders = await conn.fetch(SELECT_ORDERS_STMT, Web3.toBytes(hexstr=token_addr))

    for order in orders:
        side = "buy" if order["token_give"] == ZERO_ADDR_BYTES else "sell"
        order_maker = order["user"]
        signature = make_order_hash(dict(
            tokenGet=Web3.toHex(order["token_get"]),
            amountGet=order["amount_get"],
            tokenGive=Web3.toHex(order["token_give"]),
            amountGive=order["amount_give"],
            expires=order["expires"],
            nonce=order["nonce"]
        ))

        updated_at = datetime.fromtimestamp(block_timestamp(App().web3, "latest"), tz=None)
        amount_fill = contract.call().orderFills(order_maker, Web3.toBytes(hexstr=signature))
        amount_available = contract.call(v).availableVolume(
            Web3.toHex(order["token_get"]),
            Web3.toInt(order["amount_get"]),
            Web3.toHex(order["token_give"]),
            Web3.toInt(order["amount_give"]),
            Web3.toInt(order["expires"]),
            Web3.toInt(order["nonce"]),
            Web3.toHex(order["user"]),
            order["v"], order["r"], order["s"])

        print("side={}, signature={}, amount={}, fill={}, available={}; amounts match={}".format(
            side, signature, order["amount_get"], amount_fill, Decimal(amount_available),
            amount_fill + amount_available == order["amount_get"]))

        update_args = (amount_fill, updated_at, Web3.toBytes(hexstr=signature))

        # async with App().db.acquire_connection() as conn:
        #     update_retval = await conn.execute(UPDATE_ORDER_FILL_STMT, *update_args)
        #     logger.debug(update_retval)

        # logger.info("update order signature=%s fill=%i", signature, amount_fill)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("order_fill_backfill.py <token_addr>")
        exit(1)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(App().db.establish_connection())

    loop.run_until_complete(main(sys.argv[1]))
