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
