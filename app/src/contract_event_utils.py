block_timestamp_cache = {}
def block_timestamp(web3, block_number):
    global block_timestamp_cache
    if not isinstance(block_number, int) or block_number not in block_timestamp_cache:
        block_timestamp_cache[block_number] = web3.eth.getBlock(block_number)["timestamp"]

    return block_timestamp_cache[block_number]
