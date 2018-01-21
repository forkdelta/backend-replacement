from web3 import Web3

block_timestamp_cache = {}
def block_timestamp(web3, block_number):
    global block_timestamp_cache
    if block_number not in block_timestamp_cache:
        block_timestamp_cache[block_number] = web3.eth.getBlock(block_number)["timestamp"]

    return block_timestamp_cache[block_number]

def coerce_to_int(value):
    '''
    Normalizes event values to integers, since WS API returns numbers, and HTTP
     API returns hexstr.
    '''
    if isinstance(value, int):
        return value
    return Web3.toInt(hexstr=value)

def parse_insert_status(status_string):
    '''
    Returns (command, oid, count) tuple from INSERT status string.
    cf. https://stackoverflow.com/q/3835314/215024
    '''
    command, oid, count = status_string.split(" ")
    return (command, oid, int(count))
