from time import time

block_timestamp_cache = {}
def block_timestamp(web3, block_number):
    global block_timestamp_cache
    if not isinstance(block_number, int) or block_number not in block_timestamp_cache:
        block = web3.eth.getBlock(block_number)
        if block != None:
            block_timestamp_cache[block_number] = block["timestamp"]
        else:
            # Race condition seen with geth where the WS-RPC returns an event from a 
            # new block, but this block is not yet available through the HTTP-RPC API.
            # => Assume current time, but don't cache that in block_timestamp_cache.
            return time()

    return block_timestamp_cache[block_number]
