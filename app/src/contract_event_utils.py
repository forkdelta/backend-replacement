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


from time import time

block_timestamp_cache = {}


def block_timestamp(web3, block_number):
    global block_timestamp_cache
    if not isinstance(block_number,
                      int) or block_number not in block_timestamp_cache:
        block = web3.eth.getBlock(block_number)
        if block != None:
            block_timestamp_cache[block_number] = block["timestamp"]
        else:
            # Race condition seen with geth where the WS-RPC returns an event from a
            # new block, but this block is not yet available through the HTTP-RPC API.
            # => Assume current time, but don't cache that in block_timestamp_cache.
            return time()

    return block_timestamp_cache[block_number]
