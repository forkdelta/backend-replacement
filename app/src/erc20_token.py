from ..app import App
from ..config import HTTP_PROVIDER_URL
from decimal import Decimal
import json
from web3 import Web3, HTTPProvider
from ..constants import ZERO_ADDR

class ERC20Token:
    cache = {}

    def __init__(self, addr):
        if not ERC20Token.cache:
            ERC20Token.cache = dict([(t["addr"].lower(), t["decimals"])
                                        for t in App().tokens()])

        if isinstance(addr, bytes):
            addr = Web3.toHex(addr)
        self.addr = addr.lower()

    def normalize_value(self, value):
        if not isinstance(value, Decimal):
            value = Decimal(value)
        if value != 0:
            return value * Decimal(10.0 ** self.decimals)
        else:
            return value

    def denormalize_value(self, value):
        if not isinstance(value, Decimal):
            value = Decimal(value)
        if value != 0:
            return value * Decimal(10.0 ** -self.decimals)
        else:
            return value

    @property
    def decimals(self):
        cache = ERC20Token.cache

        if self.addr == ZERO_ADDR:
            return 18 # Not an actual ERC20 token
        elif self.addr not in cache:
            cache[self.addr] = self._call_decimals()

        return cache[self.addr]

    def _call_decimals(self):
        web3 = Web3(HTTPProvider(HTTP_PROVIDER_URL))
        method_hex = Web3.sha3(text="decimals()")[:10]
        retval = web3.eth.call({ "to": self.addr, "data": method_hex })
        if len(retval) != 66:
            error_msg = "Contract {} does not support method".format(self.addr) + \
                "`decimals()', returned '{}'".format(retval)
            raise ValueError(error_msg)
        return Web3.toInt(hexstr=retval)
