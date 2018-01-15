#!/usr/bin/env python

import asyncio
from config import ED_CONTRACT_ADDR, ED_CONTRACT_ABI, HTTP_PROVIDER_URL, WS_PROVIDER_URL
import json
import logging
from web3 import Web3
from websockets import connect
from websocket_filter_set import WebsocketFilterSet

instance = Web3([])
contract = instance.eth.contract(ED_CONTRACT_ADDR, abi=ED_CONTRACT_ABI)

filter_set = WebsocketFilterSet(contract)
@filter_set.on_event('Trade')
def record_trade(event_name, trade_event):
    print("record_trade")
    print(trade_event)

@filter_set.on_event('Deposit')
def record_deposit(event_name, deposit_event):
    print("record_deposit", deposit_event)

@filter_set.on_event('Withdraw')
def record_withdraw(event_name, withdrawal_event):
    print("record_withdraw", withdrawal_event)

def make_eth_subscribe(topic_filter):
    return { "method":"eth_subscribe",
             "params":["logs", topic_filter],
             "id":1,
             "jsonrpc":"2.0" }

async def main():
    async with connect(WS_PROVIDER_URL) as ws:
        filters = []
        for topic_filter in filter_set.topic_filters:
            subscription_request = make_eth_subscribe(topic_filter)
            await ws.send(json.dumps(subscription_request))
            subscription_response = await ws.recv()
            filters.append(json.loads(subscription_response)["result"])

        async for message in ws:
            subscription_result = json.loads(message)["params"]["result"]
            filter_set.deliver(subscription_result["topics"][0], subscription_result)


if __name__ == "__main__":
    while True:
        asyncio.get_event_loop().run_until_complete(main())
