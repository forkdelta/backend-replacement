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
from ..config import ED_CONTRACT_ADDR, ED_CONTRACT_ABI, HTTP_PROVIDER_URL, WS_PROVIDER_URL
from ..src.contract_event_recorders import record_cancel, record_deposit, process_order, process_trade, record_withdraw
from ..src.contract_event_utils import block_timestamp
import logging
import rapidjson
from time import time
from ..src.utils import coerce_to_int
from websockets import connect
from ..src.websocket_filter_set import WebsocketFilterSet

logger = logging.getLogger("contract_observer")

web3 = App().web3
contract = web3.eth.contract(ED_CONTRACT_ADDR, abi=ED_CONTRACT_ABI)

filter_set = WebsocketFilterSet(contract)
filter_set.on_event('Trade', process_trade)
filter_set.on_event('Deposit', record_deposit)
filter_set.on_event('Withdraw', record_withdraw)
filter_set.on_event('Order', process_order)
filter_set.on_event('Cancel', record_cancel)


def make_eth_subscribe(topic_filter):
    return {
        "method": "eth_subscribe",
        "params": ["logs", topic_filter],
        "id": 1,
        "jsonrpc": "2.0"
    }


AVERAGE_BLOCK_TIME = 13.5
ACCEPTABLE_LATENCY = AVERAGE_BLOCK_TIME + 5


def log_latency(event):
    block_ts = block_timestamp(App().web3, coerce_to_int(event["blockNumber"]))
    latency = time() - block_ts
    if latency < ACCEPTABLE_LATENCY:
        logger.debug("Received event with %is latency", latency)
    elif latency < 2 * ACCEPTABLE_LATENCY:
        logger.info("Received event with %is latency", latency)
    elif latency < 8 * ACCEPTABLE_LATENCY:
        logger.warn("Received event with %is latency", latency)
    else:
        logger.critical("Received event with %is latency", latency)


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
            await ws.send(rapidjson.dumps(subscription_request))
            subscription_response = await ws.recv()
            try:
                result = rapidjson.loads(subscription_response)["result"]
            except (KeyError, ValueError) as error:
                logger.error("Error parsing subscription response: %s", error)
                logger.error(subscription_response)
            else:
                filters.append(result)
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
                subscription_results = rapidjson.loads(message)["params"]["result"]
                if isinstance(subscription_results, list):
                    #Parity websocket returns multiple result at a time: [ {'address': '0x8d12a197cb00d4747a1fe03395095ce2a5cc6819', 'topics': ... }, {'address': '0x8d ... } ]
                    if len(subscription_results) > 0:
                        log_latency(subscription_results[0])
                    for subscription_result in subscription_results:
                        await filter_set.deliver(
                            subscription_result["topics"][0],
                            subscription_result)
                else:
                    #Geth websocket only returns one result at a time: {'address': '0x8d12a197cb00d4747a1fe03395095ce2a5cc6819', 'topics': [... }
                    subscription_result = subscription_results
                    if len(subscription_results) > 0:
                        log_latency(subscription_result)
                        await filter_set.deliver(
                            subscription_result["topics"][0],
                            subscription_result)

        print("Contract observer disconnected")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    while True:
        loop.run_until_complete(main())
