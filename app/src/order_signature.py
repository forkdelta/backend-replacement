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

    eth_signature_prefix = Web3.toBytes(
        text="\x19Ethereum Signed Message:\n32")
    hash_bytes = Web3.toBytes(hexstr=make_order_hash(message))

    signature_base = Web3.sha3(
        hexstr=Web3.toHex(eth_signature_prefix + hash_bytes))

    recovered_address = ecrecover(
        Web3.toBytes(hexstr=signature_base),
        message["v"],
        Web3.toInt(
            hexstr=Web3.toHex(message["r"])
        ),  # Convert from bytes to hex because sending bytes to toInt is deprecated behaviour, apparently
        Web3.toInt(hexstr=Web3.toHex(message["s"])))

    return to_normalized_address(recovered_address) == to_normalized_address(
        message["user"])
