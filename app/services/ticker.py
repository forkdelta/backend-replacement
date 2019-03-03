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

import asyncio
from datetime import datetime
from decimal import getcontext, InvalidOperation, DivisionByZero
import logging
from queue import Queue, Empty as QueueEmpty
from web3 import Web3
from ..app import App
from ..src.erc20_token import ERC20Token
from ..config import STOPPED_TOKENS
from ..constants import ZERO_ADDR, ZERO_ADDR_BYTES, FILTER_ORDERS_UNDER_ETH

logger = logging.getLogger('services.ticker')
logger.setLevel(logging.DEBUG)

getcontext().prec = 10

tokens_queue = Queue()

FETCH_RECENTLY_TRADED_TOKENS = """
SELECT token_addr
FROM (
SELECT token_get AS token_addr, SUM(amount_give) AS volume FROM trades WHERE "date" >= NOW() - '1 year'::INTERVAL AND token_get <> $1 GROUP BY token_get
UNION SELECT token_give AS token_addr, SUM(amount_get) AS volume FROM trades WHERE "date" >= NOW() - '1 year'::INTERVAL AND token_give <> $1 GROUP BY token_give
) t GROUP BY 1 ORDER BY SUM(volume) DESC LIMIT 250;
"""


async def fill_queue():
    async with App().db.acquire_connection() as conn:
        active_tokens = list(
            Web3.toHex(token_addr_row["token_addr"])
            for token_addr_row in (await conn.fetch(
                FETCH_RECENTLY_TRADED_TOKENS, Web3.toBytes(hexstr=ZERO_ADDR))))

    for token_addr in active_tokens:
        if not token_addr in STOPPED_TOKENS:
            tokens_queue.put(token_addr)

    return tokens_queue.qsize()


async def get_trades_volume(token_hexstr):
    """
    Given a token address, return the volume of trades for that token in the past
    24 hrs from the instant of calling this function. Volume excludes certain
    trades.

    Returns a Record object with two columns: quote_volume and base_volume.
    """

    async with App().db.acquire_connection() as conn:
        return await conn.fetchrow(
            """
            SELECT COALESCE(SUM(t.base_volume), 0) AS base_volume, COALESCE(SUM(t.quote_volume), 0) AS quote_volume
            FROM (
              WITH tmpt AS (
                SELECT "addr_get", "addr_give",
                  COALESCE(SUM(CASE WHEN "token_get" = $1 THEN "amount_give" ELSE "amount_get" END), 0) AS quote_volume,
                  COALESCE(SUM(CASE WHEN "token_get" = $1 THEN "amount_get" ELSE "amount_give" END), 0) AS base_volume
                FROM trades
                WHERE (("token_get" = $1 AND "token_give" = $2)
                        OR ("token_give" = $1 AND "token_get" = $2))
                        AND "date" >= NOW() - '1 day'::INTERVAL
                GROUP BY "addr_get", "addr_give"
              )
              SELECT tmpt.addr_get, tmpt.addr_give,
                SUM(tmpt.base_volume) - COALESCE(SUM(topp.base_volume), 0) AS base_volume,
                SUM(tmpt.quote_volume) - COALESCE(SUM(topp.quote_volume), 0) AS quote_volume
              FROM tmpt
              LEFT JOIN tmpt AS topp ON (tmpt.addr_get = topp.addr_give AND tmpt.addr_give = topp.addr_get)
              GROUP BY tmpt.addr_get, tmpt.addr_give
            ) t
            """, Web3.toBytes(hexstr=ZERO_ADDR),
            Web3.toBytes(hexstr=token_hexstr))


async def get_last_trade(token_hexstr):
    """
    Given a token address, returns the latest trade for that token.
    """

    async with App().db.acquire_connection() as conn:
        return await conn.fetchrow(
            """
            SELECT *
            FROM trades
            WHERE (("token_get" = $1 AND "token_give" = $2)
                    OR ("token_give" = $1 AND "token_get" = $2))
                AND ("amount_get" > 0 AND "amount_give" > 0)
                AND ("addr_get" != "addr_give")
            ORDER BY "date" DESC
            LIMIT 1
            """, Web3.toBytes(hexstr=ZERO_ADDR),
            Web3.toBytes(hexstr=token_hexstr))


async def get_market_spread(token_hexstr, current_block):
    """
    Given a token address, returns the lowest ask and the highest bid.
    """
    async with App().db.acquire_connection() as conn:
        return await conn.fetchrow(
            """
            SELECT
                (SELECT MAX(amount_give / amount_get::numeric)
                    FROM orders
                    WHERE ("token_give" = $1 AND "token_get" = $2)
                        AND "state" = 'OPEN'::orderstate
                        AND "expires" > $3
                        AND ("amount_get" > 0 AND "amount_give" > 0)
                        AND ("available_volume" IS NULL OR "available_volume" > 0)
                        AND (COALESCE("available_volume", "amount_get") * amount_give * 10 ^ -18 / amount_get::numeric) > $4
                    ) AS bid,
                (SELECT MIN(amount_get / amount_give::numeric)
                    FROM orders
                    WHERE ("token_give" = $2 AND "token_get" = $1)
                        AND "state" = 'OPEN'::orderstate
                        AND "expires" > $3
                        AND ("amount_get" > 0 AND "amount_give" > 0)
                        AND ("available_volume" IS NULL OR "available_volume" > 0)
                        AND (COALESCE("available_volume", "amount_get") * 10 ^ -18) > $4
                    ) AS ask
            """, ZERO_ADDR_BYTES, Web3.toBytes(hexstr=token_hexstr),
            current_block, 10.0 * FILTER_ORDERS_UNDER_ETH)


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
            """, Web3.toBytes(hexstr=ticker_info["token_address"]),
            ticker_info["quote_volume"], ticker_info["base_volume"],
            ticker_info["last"], ticker_info["bid"], ticker_info["ask"],
            datetime.utcnow())


async def update_ticker(token_addr):
    current_block = App().web3.eth.blockNumber
    coin_contract = ERC20Token(token_addr)
    base_contract = ERC20Token(ZERO_ADDR)

    ticker_info = {"token_address": token_addr}

    volumes = await get_trades_volume(token_addr)
    ticker_info.update({
        "quote_volume":
        coin_contract.denormalize_value(volumes["quote_volume"]),
        "base_volume":
        base_contract.denormalize_value(volumes["base_volume"]),
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
            logger.debug(
                "Failed to compute price: token=%s side=%s txid=%s logidx=%i amount_get=%s amount_give=%s",
                token_addr, side, Web3.toHex(trade["transaction_hash"]),
                trade["log_index"], trade["amount_get"], trade["amount_give"])
            ticker_info["last"] = None
        else:
            ticker_info["last"] = price
    else:  # No last price available
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
    from time import sleep as sync_sleep
    queue_size = await fill_queue()
    logger.info("%i tokens added to ticker queue", queue_size)

    while True:
        try:
            token = tokens_queue.get_nowait()
        except QueueEmpty:
            queue_size = await fill_queue()
            if queue_size == 0:
                logger.warning(
                    "No tokens added to ticker queue: pausing for 5 minutes")
                sync_sleep(300)  # Prevent busy loops
        else:
            try:
                await update_ticker(token)
            except:
                logger.exception("Exception while processing token addr=%s",
                                 token)
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
