#!/usr/bin/env python

from app import App
import asyncio
from config import ED_CONTRACT_ADDR, ED_CONTRACT_ABI, HTTP_PROVIDER_URL, WS_PROVIDER_URL
from contract_event_recorders import record_cancel, record_deposit, record_trade, record_withdraw
from enum import IntEnum
from functools import partial
import json
import logging
from os import environ
from web3 import Web3, HTTPProvider
from websockets import connect
from websocket_filter_set import WebsocketFilterSet

ZERO_ADDR = "0x0000000000000000000000000000000000000000"

web3 = App().web3
contract = web3.eth.contract(ED_CONTRACT_ADDR, abi=ED_CONTRACT_ABI)

async def process_trade(event_name, event):
    logger = logging.getLogger("contract_observer")
    await record_trade(event_name, event)

    # Get a list of potentially affected orders (any order from this maker and non-base token)
    # Order maker side is recorded in `get`
    order_maker = event["args"]["get"]
    if event["args"]["tokenGive"] != ZERO_ADDR:
        coin_addr = event["args"]["tokenGive"]
    else:
        coin_addr = event["args"]["tokenGet"]

    async with App().db.acquire_connection() as conn:
        affected_orders = await conn.fetch(
            """
            SELECT "id", "user", "signature", "amount_get", "amount_give"
            FROM orders
            WHERE "user" = $1
                AND ("token_give" = $2 OR "token_get" = $2)
                AND "expires" >= $3
            """,
            Web3.toBytes(hexstr=order_maker), Web3.toBytes(hexstr=coin_addr),
            Web3.toInt(hexstr=event["blockNumber"]) if isinstance(event["blockNumber"], str) else event["blockNumber"])

    if len(affected_orders) > 0:
        print("for order_maker={} and token={}".format(order_maker, coin_addr))
        print("trade amount amount_get={}, amount_give={}".format(
            event["args"]["amountGet"], event["args"]["amountGive"]))
        for order in affected_orders:
            print(
                Web3.toHex(order["signature"]),
                    "amount get", order["amount_get"],
                    "give", order["amount_give"],
                    "fill", contract.call().orderFills(
                        Web3.toHex(order["user"]),
                        Web3.toBytes(order["signature"]))
                )
        print("that's all")
    else:
        logger.warn("No orders found for user='%s' and token='%s'", order_maker, coin_addr)


filter_set = WebsocketFilterSet(contract)
filter_set.on_event('Trade', process_trade)
filter_set.on_event('Deposit', record_deposit)
filter_set.on_event('Withdraw', record_withdraw)
filter_set.on_event('Cancel', record_cancel)

def make_eth_subscribe(topic_filter):
    return { "method":"eth_subscribe",
             "params":["logs", topic_filter],
             "id":1,
             "jsonrpc":"2.0" }

async def main():
    logger = logging.getLogger("contract_observer")
    logger.setLevel(logging.INFO)

    last_block_number = None
    last_block_ts = None
    async with connect(WS_PROVIDER_URL) as ws:
        print("Contract observer connected")
        filters = []
        for topic_filter in filter_set.topic_filters:
            subscription_request = make_eth_subscribe(topic_filter)
            await ws.send(json.dumps(subscription_request))
            subscription_response = await ws.recv()
            filters.append(json.loads(subscription_response)["result"])

        while True:
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=20)
            except asyncio.TimeoutError:
                # No data in 20 seconds, check the connection.
                try:
                    pong_waiter = await ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=10)
                except asyncio.TimeoutError:
                    # No response to ping in 10 seconds, disconnect.
                    logger.critical("socket timeout")
                    break
            else:
                subscription_result = json.loads(message)["params"]["result"]
                await filter_set.deliver(subscription_result["topics"][0], subscription_result)
        print("Contract observer disconnected")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(App().db.establish_connection())
    while True:
        loop.run_until_complete(main())
