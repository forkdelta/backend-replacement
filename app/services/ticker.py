import asyncio
from datetime import datetime
from decimal import getcontext, InvalidOperation, DivisionByZero
import logging
from queue import Queue, Empty as QueueEmpty
from web3 import Web3
from ..app import App
from ..src.erc20_token import ERC20Token
from ..constants import ZERO_ADDR, ZERO_ADDR_BYTES, FILTER_ORDERS_UNDER_ETH

logger = logging.getLogger('services.ticker')
logger.setLevel(logging.DEBUG)

getcontext().prec = 10

tokens_queue = Queue()
def fill_queue():
    for token in App().tokens():
        tokens_queue.put(token["addr"].lower())
    logger.info("%i tokens added to ticker queue", len(App().tokens()))

fill_queue()

async def get_trades_volume(token_hexstr):
    """
    Given a token address, return the volume of trades for that token in the past
    24 hrs from the instant of calling this function.

    Returns a Record object with two columns: quote_volume and base_volume.
    """

    async with App().db.acquire_connection() as conn:
        return await conn.fetchrow("""
            SELECT
                COALESCE(SUM(CASE WHEN "token_get" = $1 THEN "amount_give" ELSE "amount_get" END), 0) AS quote_volume,
                COALESCE(SUM(CASE WHEN "token_get" = $1 THEN "amount_get" ELSE "amount_give" END), 0) AS base_volume
            FROM trades
            WHERE (("token_get" = $1 AND "token_give" = $2)
                    OR ("token_give" = $1 AND "token_get" = $2))
                AND "date" >= NOW() - '1 day'::INTERVAL
            """,
            Web3.toBytes(hexstr=ZERO_ADDR),
            Web3.toBytes(hexstr=token_hexstr))

async def get_last_trade(token_hexstr):
    """
    Given a token address, returns the latest trade for that token.
    """

    async with App().db.acquire_connection() as conn:
        return await conn.fetchrow("""
            SELECT *
            FROM trades
            WHERE (("token_get" = $1 AND "token_give" = $2)
                    OR ("token_give" = $1 AND "token_get" = $2))
                AND ("amount_get" > 0 AND "amount_give" > 0)
            ORDER BY "date" DESC
            LIMIT 1
            """,
            Web3.toBytes(hexstr=ZERO_ADDR),
            Web3.toBytes(hexstr=token_hexstr))

async def get_market_spread(token_hexstr, current_block):
    """
    Given a token address, returns the lowest ask and the highest bid.
    """
    
    base_contract = ERC20Token(ZERO_ADDR)

    async with App().db.acquire_connection() as conn:
        return await conn.fetchrow("""
            SELECT
                (SELECT MAX(amount_give / amount_get::numeric)
                    FROM orders
                    WHERE ("token_give" = $1 AND "token_get" = $2)
                        AND "state" = 'OPEN'::orderstate
                        AND "expires" > $3
                        AND ("amount_get" > 0 AND "amount_give" > 0)
                        AND ("available_volume" IS NULL OR "available_volume" > 0)
                        AND (CASE WHEN "available_volume" IS NULL THEN
                                amount_get * (amount_give / amount_get::numeric) > $4
                            ELSE
                                available_volume * (amount_give / amount_get::numeric) > $4
                            END)
                    ) AS bid,
                (SELECT MIN(amount_get / amount_give::numeric)
                    FROM orders
                    WHERE ("token_give" = $2 AND "token_get" = $1)
                        AND "state" = 'OPEN'::orderstate
                        AND "expires" > $3
                        AND ("amount_get" > 0 AND "amount_give" > 0)
                        AND ("available_volume" IS NULL OR "available_volume" > 0)
                        AND (CASE WHEN "available_volume" IS NULL THEN
                                amount_give * (amount_get / amount_give::numeric) > $4
                            ELSE
                                available_volume * (amount_get / amount_give::numeric) > $4
                            END)
                    ) AS ask
            """,
            ZERO_ADDR_BYTES,
            Web3.toBytes(hexstr=token_hexstr),
            current_block,
            base_contract.normalize_value(FILTER_ORDERS_UNDER_ETH))

async def save_ticker(ticker_info):
    async with App().db.acquire_connection() as conn:
        return await conn.execute(
            """
            INSERT INTO tickers
            ("token_address", "quote_volume", "base_volume", "last", "bid", "ask", "updated")
            VALUES
            (
                $1, $2, $3, $4, $5, $6, $7
            )
            ON CONFLICT ON CONSTRAINT tickers_pkey DO
                UPDATE SET
                    "quote_volume" = $2,
                    "base_volume" = $3,
                    "last" = $4,
                    "bid" = $5,
                    "ask" = $6,
                    "updated" = $7
                WHERE tickers.token_address = $1
            """,
            Web3.toBytes(hexstr=ticker_info["token_address"]),
            ticker_info["quote_volume"],
            ticker_info["base_volume"],
            ticker_info["last"],
            ticker_info["bid"],
            ticker_info["ask"],
            datetime.utcnow())

async def update_ticker(token_addr):
    current_block = App().web3.eth.blockNumber
    coin_contract = ERC20Token(token_addr)
    base_contract = ERC20Token(ZERO_ADDR)

    ticker_info = { "token_address": token_addr }

    volumes = await get_trades_volume(token_addr)
    ticker_info.update({
        "quote_volume": coin_contract.denormalize_value(volumes["quote_volume"]),
        "base_volume": base_contract.denormalize_value(volumes["base_volume"]),
    })

    trade = await get_last_trade(token_addr)
    if trade:
        side = "buy" if trade["token_get"] == ZERO_ADDR_BYTES else "sell"
        # Compute the price.
        try:
            if side == "buy":
                price = base_contract.denormalize_value(trade["amount_get"]) \
                    / coin_contract.denormalize_value(trade["amount_give"])
            else:
                price = base_contract.denormalize_value(trade["amount_give"]) \
                    / coin_contract.denormalize_value(trade["amount_get"])
        except (InvalidOperation, DivisionByZero):
            # Somewhere, somehow, with all our high-precision math, we still get
            # rounding. Or maybe there are somehow 0-trades.
            logger.debug("Failed to compute price: token=%s side=%s txid=%s logidx=%i amount_get=%s amount_give=%s",
                token_addr, side, Web3.toHex(trade["transaction_hash"]), trade["log_index"], trade["amount_get"], trade["amount_give"])
            ticker_info["last"] = None
        else:
            ticker_info["last"] = price
    else: # No last price available
        ticker_info["last"] = None

    # TODO: percent_change

    spread = await get_market_spread(token_addr, current_block)
    if spread["ask"]:
        # Spread comes back in token/base native values, denormalize it here
        ticker_info["ask"] = spread["ask"] * base_contract.denormalize_value(1.0) \
                                / coin_contract.denormalize_value(1.0)
    else:
        ticker_info["ask"] = None

    if spread["bid"]:
        ticker_info["bid"] = spread["bid"] * base_contract.denormalize_value(1.0) \
                                / coin_contract.denormalize_value(1.0)
    else:
        ticker_info["bid"] = None

    logger.debug(ticker_info)
    await save_ticker(ticker_info)


async def main():
    while True:
        try:
            token = tokens_queue.get_nowait()
        except QueueEmpty:
            fill_queue()            
        else:
            await update_ticker(token)
            await asyncio.sleep(2.0)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
