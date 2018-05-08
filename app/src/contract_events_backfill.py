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
from ..config import ED_CONTRACT_ADDR, ED_CONTRACT_ABI, HTTP_PROVIDER_URL
from .contract_event_recorders import record_cancel, record_deposit, process_order, process_trade, record_withdraw
import sys
from time import time, sleep
from web3 import Web3, HTTPProvider

BLOCK_ALIASES = ("latest", "earliest", "pending")
EVENT_HANDLERS = {
    'Trade': process_trade,
    'Deposit': record_deposit,
    'Withdraw': record_withdraw,
    'Order': process_order,
    'Cancel': record_cancel,
}


async def main():
    if len(sys.argv) != 4:
        print(
            "contract_events_backfill.py <event_name> <from_block> <to_block>")
        exit(1)
    event_name, from_block, to_block = sys.argv[1:]

    web3 = App().web3

    from_block = int(
        from_block) if from_block not in BLOCK_ALIASES else web3.eth.getBlock(
            from_block)['number']
    to_block = int(
        to_block) if to_block not in BLOCK_ALIASES else web3.eth.getBlock(
            to_block)['number']
    block_step = 300 if to_block - from_block > 300 else 1
    print("Backfill", event_name, "from", from_block, "to", to_block, "in",
          block_step, "block step")

    ed_contract = web3.eth.contract(ED_CONTRACT_ADDR, abi=ED_CONTRACT_ABI)
    event_filter = None
    total_events = 0

    last_block_number = None
    last_block_info = None
    for block_number in range(to_block, from_block, -block_step):
        try:
            print(
                int(time()), block_number - block_step, block_number,
                total_events)
            event_filter = ed_contract.on(
                event_name, {
                    'fromBlock': block_number - block_step,
                    'toBlock': block_number
                })
            for event in event_filter.get(only_changes=False):
                await EVENT_HANDLERS[event_name](ed_contract, event_name,
                                                 event)
                total_events += 1
            sleep(3)
        finally:
            if event_filter is not None:
                web3.eth.uninstallFilter(event_filter.filter_id)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
