import asyncio
import asyncpg
import config
import logging
from os import environ
from web3 import Web3, HTTPProvider

class DB:
    def __init__(self, config):
        self.config = config
        self.pool = None
        self.logger = logging.getLogger('App.DB')

    async def establish_connection(self):
        dsn = "postgres://{}:{}@{}/{}".format(
            self.config.POSTGRES_USER,
            self.config.POSTGRES_PASSWORD,
            self.config.POSTGRES_HOST,
            self.config.POSTGRES_DB)
        self.logger.info("Connecting to %s...", dsn)
        self.pool = await asyncpg.create_pool(dsn=dsn)
        self.logger.info("Connected to %s.", dsn)
        self.acquire_connection = self.pool.acquire

class App:
    class __App:
        def __init__(self):
            self.config = config
            self.db = DB(config)
            self.web3 = Web3(HTTPProvider(config.HTTP_PROVIDER_URL))

        def __str__(self):
            return repr(self)

    instance = None
    def __init__(self):
        if not App.instance:
            App.instance = App.__App()

    def __getattr__(self, name):
        return getattr(self.instance, name)
