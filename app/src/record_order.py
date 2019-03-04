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
"""
For use with websocket server.
"""

from datetime import datetime
from decimal import localcontext
from web3 import Web3

from ..app import App
from ..constants import ZERO_ADDR
from app.src.contract_event_utils import block_timestamp
from ..src.order_enums import OrderSource, OrderState
from ..src.order_hash import make_order_hash
from ..src.utils import parse_insert_status
from ..tasks.update_order import update_order_by_signature

INSERT_ORDER_STMT = """
    INSERT INTO orders
    (
        "source", "signature",
        "token_give", "amount_give", "token_get", "amount_get", "available_volume",
        "expires", "nonce", "user", "state", "v", "r", "s", "date", "sorting_price"
    )
    VALUES ($1, $2, $3, $4, $5, $6, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
    ON CONFLICT ON CONSTRAINT index_orders_on_signature DO NOTHING
"""


async def record_order(order, block_number=0):
    signature = make_order_hash(order)

    if "r" in order and order["r"] is not None:
        source = OrderSource.OFFCHAIN
        date = datetime.utcnow()
    else:
        source = OrderSource.ONCHAIN
        date = datetime.fromtimestamp(
            block_timestamp(App().web3, block_number), tz=None)

    # if tokenGive is ZERO_ADDR, sort by (amount_give / amount_get) DESC
    #   => -(amount_give / amount_get) ASC
    # if tokenGet is ZERO_ADDR, sort by (amount_get / amount_give) ASC
    if order["tokenGive"] == ZERO_ADDR:
        with localcontext() as decimal_ctx:
            decimal_ctx.prec = 10
            sorting_price = -order["amountGive"] / order["amountGet"]
    else:
        with localcontext() as decimal_ctx:
            decimal_ctx.prec = 10
            sorting_price = order["amountGet"] / order["amountGive"]

    insert_args = (
        source.name,
        Web3.toBytes(hexstr=signature),
        Web3.toBytes(hexstr=order["tokenGive"]),
        order["amountGive"],
        Web3.toBytes(hexstr=order["tokenGet"]),
        order["amountGet"],
        order["expires"],
        order["nonce"],
        Web3.toBytes(hexstr=order["user"]),
        OrderState.OPEN.name,
        order.get("v"),
        order.get("r"),
        order.get("s"),
        date,
        sorting_price,
    )

    async with App().db.acquire_connection() as connection:
        insert_retval = await connection.execute(INSERT_ORDER_STMT,
                                                 *insert_args)
        _, _, did_insert = parse_insert_status(insert_retval)
    return did_insert
