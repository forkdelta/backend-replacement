from app import App
from contract_event_utils import block_timestamp, coerce_to_int, parse_insert_status
from datetime import datetime, timezone
import logging
from pprint import pprint
from web3 import Web3

logger = logging.getLogger("contract_event_recorders")

INSERT_TRADE_STMT = """
    INSERT INTO trades
    (
        "block_number", "transaction_hash", "log_index",
        "token_give", "amount_give", "token_get", "amount_get",
        "addr_give", "addr_get", "date"
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    ON CONFLICT ON CONSTRAINT index_trades_on_event_identifier DO NOTHING;
"""
async def record_trade(event_name, event):
    block_number = coerce_to_int(event["blockNumber"])
    log_index = coerce_to_int(event["logIndex"])
    date = datetime.fromtimestamp(block_timestamp(App().web3, event["blockNumber"]), tz=None)

    insert_args = (
        block_number,
        Web3.toBytes(hexstr=event["transactionHash"]),
        log_index,
        Web3.toBytes(hexstr=event["args"]["tokenGive"]),
        event["args"]["amountGive"],
        Web3.toBytes(hexstr=event["args"]["tokenGet"]),
        event["args"]["amountGet"],
        Web3.toBytes(hexstr=event["args"]["give"]),
        Web3.toBytes(hexstr=event["args"]["get"]),
        date
    )

    async with App().db.acquire_connection() as connection:
        insert_retval = await connection.execute(INSERT_TRADE_STMT, *insert_args)
        _, _, did_insert = parse_insert_status(insert_retval)

    if did_insert:
        logger.debug("recorded trade txid=%s, logidx=%i", event["transactionHash"], log_index)

    return bool(did_insert)

async def record_deposit(event_name, event):
    did_insert = await record_transfer("DEPOSIT", event)
    if did_insert:
        logger.info("recorded deposit txid=%s, logidx=%i", event["transactionHash"], coerce_to_int(event["logIndex"]))
    return did_insert

async def record_withdraw(event_name, event):
    did_insert = await record_transfer("WITHDRAW", event)
    if did_insert:
        logger.info("recorded withdraw txid=%s, logidx=%i", event["transactionHash"], coerce_to_int(event["logIndex"]))
    return did_insert

INSERT_TRANSFER_STMT = """
    INSERT INTO transfers
    (
        "block_number", "transaction_hash", "log_index",
        "direction", "token", "user", "amount", "balance_after", "date"
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    ON CONFLICT ON CONSTRAINT index_transfers_on_event_identifier DO NOTHING;
"""
async def record_transfer(transfer_direction, event):
    block_number = coerce_to_int(event["blockNumber"])
    log_index = coerce_to_int(event["logIndex"])
    date = datetime.fromtimestamp(block_timestamp(App().web3, block_number), tz=None)

    insert_args = (
        block_number,
        Web3.toBytes(hexstr=event["transactionHash"]),
        log_index,
        transfer_direction,
        Web3.toBytes(hexstr=event["args"]["token"]),
        Web3.toBytes(hexstr=event["args"]["user"]),
        event["args"]["amount"],
        event["args"]["balance"],
        date
    )

    async with App().db.acquire_connection() as connection:
        insert_retval = await connection.execute(INSERT_TRANSFER_STMT, *insert_args)
        _, _, did_insert = parse_insert_status(insert_retval)

    return bool(did_insert)

def record_cancel(event_name, event):
    print("record_cancel", event)
