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


from ..config import ED_CONTRACT_ADDR
from decimal import Decimal
from eth_utils import add_0x_prefix, remove_0x_prefix
from hashlib import sha256
from web3 import Web3
from web3.utils.encoding import hex_encode_abi_type, to_bytes


def sha256_like_solidity(type_value_tuples):
    hex_string = add_0x_prefix(''.join(
        remove_0x_prefix(hex_encode_abi_type(abi_type, value))
        for abi_type, value in type_value_tuples))

    return add_0x_prefix(sha256(to_bytes(hexstr=hex_string)).hexdigest())


def make_order_hash(order, contract_addr=ED_CONTRACT_ADDR):
    hash_parts = [('address', contract_addr), ('address', order["tokenGet"]),
                  ('uint256', Web3.toInt(Decimal(order["amountGet"]))),
                  ('address',
                   order["tokenGive"]), ('uint256',
                                         Web3.toInt(
                                             Decimal(order["amountGive"]))),
                  ('uint256', Web3.toInt(Decimal(
                      order["expires"]))), ('uint256',
                                            Web3.toInt(
                                                Decimal(order["nonce"])))]

    return sha256_like_solidity(hash_parts)
