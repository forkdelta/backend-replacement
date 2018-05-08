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


from asyncio import iscoroutinefunction
from functools import partial
from web3.utils.filters import construct_event_filter_params
from web3.utils.events import get_event_data


class WebsocketFilterSet:
    def __init__(self, contract):
        self.contract = contract
        self.handlers = {}
        self.topic_to_event = {}
        self.topic_filters = []

    async def deliver(self, topic_hash, payload):
        if topic_hash in self.handlers:
            if iscoroutinefunction(self.handlers[topic_hash]):
                await self.handlers[topic_hash](payload)
            else:
                self.handlers[topic_hash](payload)

    def on_event(self, event_name, handler_func=None):
        def decorator(handler_func):
            event_abi = self.contract._find_matching_event_abi(event_name, {})
            _, event_filter_params = construct_event_filter_params(
                event_abi, contract_address=self.contract.address)

            if iscoroutinefunction(handler_func):

                async def decorated(payload):
                    event_data = get_event_data(event_abi, payload)
                    return await handler_func(self.contract, event_name,
                                              event_data)
            else:

                def decorated(payload):
                    event_data = get_event_data(event_abi, payload)
                    return handler_func(self.contract, event_name, event_data)

            self.topic_filters.append(event_filter_params)
            self.handlers[event_filter_params["topics"][0]] = decorated

            return decorated

        if handler_func is None:
            return decorator
        return decorator(handler_func)
