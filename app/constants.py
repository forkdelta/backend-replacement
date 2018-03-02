from web3 import Web3

# Eternally constant constants

ZERO_ADDR = "0x0000000000000000000000000000000000000000"
ZERO_ADDR_BYTES = Web3.toBytes(hexstr=ZERO_ADDR)



# We might change our mind about these:

FILTER_ORDERS_UNDER_ETH = 0.001
ALLOWED_ORIGIN_SUFFIXES = ('forkdelta.com', 'forkdelta.github.io', 'deltabalances.github.io', 'localhost', 'devd.io')
