from eth_utils import to_normalized_address
from web3 import Web3

from ..lib.ecrecover import ecrecover
from .order_hash import make_order_hash
def order_signature_valid(message):
    """
    Performs the black magic ritual of verifying order signatures.

    Reverse engineered from frontend and contract.

    Returns True if the spirits say "yes", and False otherwise.
    """

    eth_signature_prefix = Web3.toBytes(text="\x19Ethereum Signed Message:\n32")
    hash_bytes = Web3.toBytes(hexstr=make_order_hash(message))

    signature_base = Web3.sha3(hexstr=Web3.toHex(eth_signature_prefix + hash_bytes))

    recovered_address = ecrecover(
        Web3.toBytes(hexstr=signature_base),
        message["v"],
        Web3.toInt(hexstr=Web3.toHex(message["r"])), # Convert from bytes to hex because sending bytes to toInt is deprecated behaviour, apparently
        Web3.toInt(hexstr=Web3.toHex(message["s"])))

    return to_normalized_address(recovered_address) == to_normalized_address(message["user"])
