from web3 import Web3

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
