from app import App
from contract_event_utils import block_timestamp
from datetime import datetime, timezone
from erc20_token import ERC20Token
import logging
from pprint import pprint
from web3 import Web3

async def record_trade(event_name, event):
    logger = logging.getLogger("contract_events")
    insert_statement = """INSERT INTO trades
        (
            "block_number", "transaction_hash", "log_index",
            "token_give", "amount_give", "token_get", "amount_get",
            "addr_give", "addr_get", "date"
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT ON CONSTRAINT index_trades_on_event_identifier DO NOTHING;"""

    insert_args = (
        event["blockNumber"] if isinstance(event["blockNumber"], int) else Web3.toInt(hexstr=event["blockNumber"]),
        Web3.toBytes(hexstr=event["transactionHash"]),
        event["logIndex"] if isinstance(event["logIndex"], int) else Web3.toInt(hexstr=event["logIndex"]),
        Web3.toBytes(hexstr=event["args"]["tokenGive"]),
        event["args"]["amountGive"] * 10 ** (18 - ERC20Token(event["args"]["tokenGive"]).decimals),
        Web3.toBytes(hexstr=event["args"]["tokenGet"]),
        event["args"]["amountGet"] * 10 ** (18 - ERC20Token(event["args"]["tokenGive"]).decimals),
        Web3.toBytes(hexstr=event["args"]["give"]),
        Web3.toBytes(hexstr=event["args"]["get"]),
        datetime.fromtimestamp(block_timestamp(App().web3, event["blockNumber"]), tz=None)
    )

    async with App().db.acquire_connection() as connection:
        await connection.execute(insert_statement, *insert_args)
    logger.debug("recorded trade txid=%s, logidx=%i", event["transactionHash"], event["logIndex"] if isinstance(event["logIndex"], int) else Web3.toInt(hexstr=event["logIndex"]))

async def record_deposit(event_name, event):
    logger = logging.getLogger("contract_observer")
    await record_transfer("DEPOSIT", event)
    logger.info("recorded deposit txid=%s, logidx=%i", event["transactionHash"], event["logIndex"] if isinstance(event["logIndex"], int) else Web3.toInt(hexstr=event["logIndex"]))

async def record_withdraw(event_name, event):
    logger = logging.getLogger("contract_observer")
    await record_transfer("WITHDRAW", event)
    logger.info("recorded deposit txid=%s, logidx=%i", event["transactionHash"], event["logIndex"] if isinstance(event["logIndex"], int) else Web3.toInt(hexstr=event["logIndex"]))

async def record_transfer(transfer_direction, event):

    insert_statement = """
    INSERT INTO transfers
        (
            "block_number", "transaction_hash", "log_index",
            "direction", "token", "user", "amount", "balance_after", "date"
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT ON CONSTRAINT index_transfers_on_event_identifier DO NOTHING;"""

    insert_args = (
        event["blockNumber"] if isinstance(event["blockNumber"], int) else Web3.toInt(hexstr=event["blockNumber"]),
        Web3.toBytes(hexstr=event["transactionHash"]),
        event["logIndex"] if isinstance(event["logIndex"], int) else Web3.toInt(hexstr=event["logIndex"]),
        transfer_direction,
        Web3.toBytes(hexstr=event["args"]["token"]),
        Web3.toBytes(hexstr=event["args"]["user"]),
        event["args"]["amount"] * 10 ** (18 - ERC20Token(event["args"]["token"]).decimals),
        event["args"]["balance"] * 10 ** (18 - ERC20Token(event["args"]["token"]).decimals),
        datetime.fromtimestamp(block_timestamp(App().web3, event["blockNumber"]), tz=None)
    )

    async with App().db.acquire_connection() as connection:
        await connection.execute(insert_statement, *insert_args)

def record_cancel(event_name, event):
    print("record_cancel", event)
