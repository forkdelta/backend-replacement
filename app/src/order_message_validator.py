import cerberus
from decimal import Decimal
from eth_utils import is_hex_address, is_0x_prefixed, to_normalized_address
from web3 import Web3

hexstr_to_bytes = lambda value: Web3.toBytes(hexstr=value)

def str_to_decimal_to_int(value):
    """
    Converts a string to Decimal, handling potential exponential notation in
    the string, then converts to plain int.
    """
    return Web3.toInt(Decimal(value))

def validate_0x_prefixed_hex_address(field, value, error):
    if not is_hex_address(value) or not is_0x_prefixed(value):
        error(field, 'must be a 0x-prefixed hex Ethereum address')

ORDER_MESSAGE_SCHEMA = {
    "contractAddr": { "type": "string", "required": True, "coerce": to_normalized_address, "validator": validate_0x_prefixed_hex_address },
    "tokenGet": { "type": "string", "required": True, "coerce": to_normalized_address, "validator": validate_0x_prefixed_hex_address },
    "amountGet": { "type": "integer", "required": True, "coerce": str_to_decimal_to_int, "min": 1 },
    "tokenGive": { "type": "string", "required": True, "coerce": to_normalized_address, "validator": validate_0x_prefixed_hex_address },
    "amountGive": { "type": "integer", "required": True, "coerce": str_to_decimal_to_int, "min": 1 },
    "expires": { "type": "integer", "required": True, "coerce": Web3.toInt, "min": 0 },
    "nonce": { "type": "integer", "required": True, "coerce": Web3.toInt, "min": 0 },
    "user": { "type": "string", "required": True, "coerce": to_normalized_address, "validator": validate_0x_prefixed_hex_address },
    "v": { "type": "integer", "required": True },
    "r": { "type": "binary", "required": True, "coerce": hexstr_to_bytes, "minlength": 32, "maxlength": 32 },
    "s": { "type": "binary", "required": True, "coerce": hexstr_to_bytes, "minlength": 32, "maxlength": 32 },
}

ORDER_MESSAGE_SCHEMA_ETHERDELTA = {
    "tokenGet": { "type": "string", "required": True, "coerce": to_normalized_address, "validator": validate_0x_prefixed_hex_address },
    "amountGet": { "type": "integer", "required": True, "coerce": str_to_decimal_to_int, "min": 1 },
    "tokenGive": { "type": "string", "required": True, "coerce": to_normalized_address, "validator": validate_0x_prefixed_hex_address },
    "amountGive": { "type": "integer", "required": True, "coerce": str_to_decimal_to_int, "min": 1 },
    "expires": { "type": "integer", "required": True, "coerce": Web3.toInt, "min": 0 },
    "nonce": { "type": "integer", "required": True, "coerce": Web3.toInt, "min": 0 },
    "user": { "type": "string", "required": True, "coerce": to_normalized_address, "validator": validate_0x_prefixed_hex_address },
    "v": { "type": "integer", "required": True },
    "r": { "type": "binary", "required": True, "coerce": hexstr_to_bytes, "minlength": 32, "maxlength": 32 },
    "s": { "type": "binary", "required": True, "coerce": hexstr_to_bytes, "minlength": 32, "maxlength": 32 },
}

class OrderMessageValidatorBase(cerberus.Validator):
    def __init__(self, schema, *args, **kwargs):
        super().__init__(schema, *args, **kwargs)

class OrderMessageValidator(OrderMessageValidatorBase):
    def __init__(self, *args, **kwargs):
        super().__init__(ORDER_MESSAGE_SCHEMA, *args, **kwargs)

class OrderMessageValidatorEtherdelta(OrderMessageValidatorBase):
    def __init__(self, *args, **kwargs):
        super().__init__(ORDER_MESSAGE_SCHEMA_ETHERDELTA, *args, **kwargs)
        self.allow_unknown = True
