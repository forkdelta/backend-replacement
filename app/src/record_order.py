"""
For use with websocket server.
"""

from datetime import datetime
from web3 import Web3

from ..app import App
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
        "expires", "nonce", "user", "state", "v", "r", "s", "date"
    )
    VALUES ($1, $2, $3, $4, $5, $6, $6, $7, $8, $9, $10, $11, $12, $13, $14)
    ON CONFLICT ON CONSTRAINT index_orders_on_signature DO NOTHING
"""
async def record_order(order, block_number=0):
    signature = make_order_hash(order)

    if "r" in order and order["r"] is not None:
        source = OrderSource.OFFCHAIN
        date = datetime.utcnow()
    else:
        source = OrderSource.ONCHAIN
        date = datetime.fromtimestamp(block_timestamp(App().web3, block_number), tz=None)

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
        date
    )

    async with App().db.acquire_connection() as connection:
        insert_retval = await connection.execute(INSERT_ORDER_STMT, *insert_args)
        _, _, did_insert = parse_insert_status(insert_retval)
    return did_insert
