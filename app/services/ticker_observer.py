'''
TODO?
After the first time this is run,
we could change it to only grab orders/trades
on an interval so that it only has to process
the new orders/trades from the last time this
was run?
'''

from aiohttp import web
from ..app import App
import asyncio
from ..src.erc20_token import ERC20Token
import logging
from ..src.order_enums import OrderState
from time import time
import socketio
from web3 import Web3
from datetime import datetime

sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app)

ZERO_ADDR = "0x0000000000000000000000000000000000000000"
ZERO_ADDR_BYTES = Web3.toBytes(hexstr=ZERO_ADDR)

logger = logging.getLogger('ticker_observer')

async def get_tickers():

    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM tickers
            """

# Maybe there is a fancy SQL statement here that will make this faster? 
async def get_orders():

    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT token_give, amount_give, token_get, amount_get, expires
            FROM orders
            """

# TODO: Are trades pruned or do I need to add a WHERE here by block number?    
async def get_trades():

    async with App().db.acquire_connection() as conn:
        return await conn.fetch(
            """
            SELECT token_give, amount_give, token_get, amount_get
            FROM trades
            ORDER BY block_number DESC, date DESC
            """

# Scan passed in orders and update the `tickers` table. Bid, Ask, quoteVolume, and baseVolume is updated.
# TODO: quoteVolume, baseVolume
async def parse_orders(tickers, orders): 

    # This is the object we will use to update `tickers` with.
    ticker_updates = {}
    
    for order in orders:
        
        # Check if this is a buy or sell order by seeing if the given token is ETH
        side = "buy" if order["token_give"] == ZERO_ADDR_BYTES else "sell"
        
        if side == "buy":
        
            this_orders_bid = order["amount_give"] / order["amount_get"]
            
            # If ticker updates doesn't already have this token, add it to our object to update.
            if not hasattr(ticker_updates, order["token_get"]):
                
                ticker_updates[order["token_get"]] = {
                    'bid': this_orders_bid.
                }
                
            else:
                # If there isn't a current recorded bid OR current recorded bid is lower than the bid in this order.
                if not has_attr(ticker_updates[order["token_get"]], 'bid') || ticker_updates[order["token_get"]]["bid"] < this_orders_bid:
                    ticker_updates[order["token_get"]]["bid"] = this_orders_bid
            
        else:
            
            this_orders_ask = order["amount_get"] / order["amount_give"]
            
            # If ticker updates doesn't already have this token, add it to our object to update.
            if not hasattr(ticker_updates, order["token_give"]):
                
                ticker_updates[order["token_give"]] = {
                    'ask': this_orders_ask,
                }
                
            else:                    
                # If there is a current recorded ask OR if current recorded ask is higher than the ask in this order.
                if not has_attr(ticker_updates[order["token_give"]], 'ask') || ticker_updates[order["token_give"]]["ask"] > this_orders_ask:
                    ticker_updates[order["token_give"]]["ask"] = this_orders_ask
                
    # TODO: Submit the ticker_updates to `tickers`
    # TODO: Fill modified date with "modified": datetime.now().isoformat()
    
    return

# Scan passed in trades and update the `tickers` table. Last and percentChange is updated.
# TODO: percentChange
async def parse_trades(tickers, trades): 
    
    # This is the object we will use to update `tickers` with.
    ticker_updates = {}
    
    for trade in trades:
        
        # Check if this is a buy or sell order by seeing if the given token is ETH
        side = "buy" if trade["token_give"] == ZERO_ADDR_BYTES else "sell"
        
        if side == "buy"
            
            # If ticker updates doesn't already have this token, add it to our object to update.
            if not hasattr(ticker_updates, trade["token_get"]):
                ticker_updates[trade["token_get"]] = {
                    'last': trade["amount_give"] / trade["amount_get"],
                    'percentChange': '',
                }
            
        else:
            
            # If ticker updates doesn't already have this token, add it to our object to update.
            if not hasattr(ticker_updates, trade["token_give"]):
                ticker_updates[trade["token_give"]] = {
                    'last': trade["amount_get"] / trade["amount_give"],
                    'percentChange': '',
                }
                
    # TODO: Submit the ticker_updates to `tickers`
    # TODO: Fill modified date with "modified": datetime.now().isoformat()
    
    return

# Main function. Grabs orders and trades, then scans through orders and trades to update `tickers`
async def update_tickers():
    
    orders = await get_orders();
    trades = await get_trades();
    tickers = await get_tickers()
    
    parse_orders(tickers, orders);
    parse_trades(tickers, trades);
    
