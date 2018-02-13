import asyncio
import asyncpg
import app.config as config
from huey import RedisHuey
import logging
from os import environ
from threading import local
from web3 import Web3, HTTPProvider

class DB:
    def __init__(self, config):
        self.logger = logging.getLogger('App.DB')
        self.logger.setLevel(logging.DEBUG)
        self.config = config
        self.__create_pool()

    def __create_pool(self):
        dsn = "postgres://{}:{}@{}/{}".format(
            self.config.POSTGRES_USER,
            self.config.POSTGRES_PASSWORD,
            self.config.POSTGRES_HOST,
            self.config.POSTGRES_DB)
        # Create a pool object synchronously, skip creating a connection right away
        self.pool = asyncpg.create_pool(dsn=dsn, min_size=0)
        # Declare pool initialized: async part of create_pool is noop when min_size=0
        self.pool._initialized = True
        self.acquire_connection = self.pool.acquire

class App:
    class __App:
        def __init__(self):
            self.config = config
            self.db = DB(config)
            self.huey = RedisHuey(host="redis", result_store=False)
            self.web3 = Web3(HTTPProvider(config.HTTP_PROVIDER_URL))

        def __str__(self):
            return repr(self)

    thread_local = None
    def __init__(self):
        if not App.thread_local:
            App.thread_local = local()

        if not hasattr(App.thread_local, "instance"):
            App.thread_local.instance = App.__App()

    def __getattr__(self, name):
        return getattr(self.thread_local.instance, name)
