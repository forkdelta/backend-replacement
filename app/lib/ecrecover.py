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


##
# This module was extracted from pyethereum utils.
# See https://github.com/ethereum/pyethereum/blob/b110fb4/ethereum/utils.py

import coincurve
from rlp.utils import ascii_chr
import sha3
from web3 import Web3


def ecrecover(rawhash, v, r, s):
    """
    Returns signer's Ethereum address as bytes.
    """
    pub = ecrecover_to_pub(rawhash, v, r, s)
    return sha3.keccak_256(to_string(pub)).digest()[-20:]


def ecrecover_to_pub(rawhash, v, r, s):
    """
    Performs Solidity-like ecrecover.

    Arguments:
    - rawhash
    - v, r, s: Parts of the signature

    Returns the public key of the signer.
    """
    try:
        pk = coincurve.PublicKey.from_signature_and_message(
            zpad(bytes(int_to_32bytearray(r)), 32) +
            zpad(bytes(int_to_32bytearray(s)), 32) + ascii_chr(v - 27),
            rawhash,
            hasher=None,
        )
        pub = pk.format(compressed=False)[1:]
    except BaseException:
        pub = b"\x00" * 64
    assert len(pub) == 64
    return pub


def zpad(x, l):
    """ Left zero pad value `x` at least to length `l`.
    >>> zpad('', 1)
    '\x00'
    >>> zpad('\xca\xfe', 4)
    '\x00\x00\xca\xfe'
    >>> zpad('\xff', 1)
    '\xff'
    >>> zpad('\xca\xfe', 2)
    '\xca\xfe'
    """
    return b'\x00' * max(0, l - len(x)) + x


def int_to_32bytearray(i):
    o = [0] * 32
    for x in range(32):
        o[31 - x] = i & 0xff
        i >>= 8
    return o


def to_string(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return bytes(value, 'utf-8')
    if isinstance(value, int):
        return bytes(str(value), 'utf-8')
