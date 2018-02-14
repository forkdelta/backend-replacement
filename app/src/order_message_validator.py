import cerberus
from eth_utils import is_hex_address, is_0x_prefixed, to_normalized_address
from web3 import Web3

hexstr_to_bytes = lambda value: Web3.toBytes(hexstr=value)

def validate_0x_prefixed_hex_address(field, value, error):
    if not is_hex_address(value) or not is_0x_prefixed(value):
        error(field, 'must be a 0x-prefixed hex Ethereum address')

ORDER_MESSAGE_SCHEMA = {
    "contractAddr": { "type": "string", "required": True, "coerce": to_normalized_address, "validator": validate_0x_prefixed_hex_address },
    "tokenGet": { "type": "string", "required": True, "coerce": to_normalized_address, "validator": validate_0x_prefixed_hex_address },
    "amountGet": { "type": "integer", "required": True, "coerce": Web3.toInt, "min": 0 },
    "tokenGive": { "type": "string", "required": True, "coerce": to_normalized_address, "validator": validate_0x_prefixed_hex_address },
    "amountGive": { "type": "integer", "required": True, "coerce": Web3.toInt, "min": 0 },
    "expires": { "type": "integer", "required": True, "coerce": Web3.toInt, "min": 0 },
    "nonce": { "type": "integer", "required": True, "coerce": Web3.toInt, "min": 0 },
    "user": { "type": "string", "required": True, "coerce": to_normalized_address, "validator": validate_0x_prefixed_hex_address },
    "v": { "type": "integer", "required": True },
    "r": { "type": "binary", "required": True, "coerce": hexstr_to_bytes, "minlength": 32, "maxlength": 32 },
    "s": { "type": "binary", "required": True, "coerce": hexstr_to_bytes, "minlength": 32, "maxlength": 32 },
}

class OrderMessageValidator(cerberus.Validator):
    def __init__(self, *args, **kwargs):
        super().__init__(ORDER_MESSAGE_SCHEMA, *args, **kwargs)
