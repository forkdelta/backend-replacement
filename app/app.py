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

import aioredis
import asyncio
import asyncpg
import app.config as config
from huey import RedisHuey
from .lib.threaded_wrap_async import get_thread_local_loop
import logging
from datetime import datetime
import requests
from os import environ
from threading import local
from web3 import Web3, HTTPProvider


class DB:
    def __init__(self, config, loop=None):
        self.logger = logging.getLogger('App.DB')
        self.logger.setLevel(logging.DEBUG)
        self.config = config
        self.__create_pool(loop)

    def __create_pool(self, loop):
        dsn = "postgres://{}:{}@{}/{}".format(
            self.config.POSTGRES_USER, self.config.POSTGRES_PASSWORD,
            self.config.POSTGRES_HOST, self.config.POSTGRES_DB)
        # Create a pool object synchronously, skip creating a connection right away
        self.pool = asyncpg.create_pool(
            dsn=dsn, min_size=0, max_size=25, loop=loop)
        # Declare pool initialized: async part of create_pool is noop when min_size=0
        self.pool._initialized = True
        self.acquire_connection = self.pool.acquire


class App:
    class __App:
        def __init__(self):
            self.logger = logging.getLogger('App.App')
            self.logger.setLevel(logging.DEBUG)
            self.config = config
            self.loop = get_thread_local_loop()

            self.__initialize_aioredis_pool()
            self.db = DB(config, loop=self.loop)
            self.huey = RedisHuey(host="redis", result_store=False)
            self.web3 = Web3(HTTPProvider(config.HTTP_PROVIDER_URL))
            self._tokens = None
            self.updateTokens()

        def __str__(self):
            return repr(self)

        def updateTokens(self):
            try:
                self._tokensUpdateTime = datetime.utcnow()
                fd_config = requests.get(config.FRONTEND_CONFIG_FILE).json()
                self._tokens = fd_config['tokens']
                self.logger.info("Token list refreshed: %i tokens.",
                                 len(self._tokens))
            except Exception as e:
                # Tolerate failing update if we have tokens from the last update, otherwise raise exception
                if self._tokens == None:
                    self.logger.error("Failed to refresh token list.")
                    raise e
                else:
                    self.logger.warning("Failed to refresh token list.")

        def tokens(self):
            n = datetime.utcnow()
            if (n - self._tokensUpdateTime).total_seconds() > 15 * 60:
                self.updateTokens()
            return self._tokens

        def __initialize_aioredis_pool(self):
            asyncio.run_coroutine_threadsafe(self.__create_aioredis_pool(),
                                             self.loop)

        async def __create_aioredis_pool(self):
            self.aioredis = await aioredis.create_redis_pool(
                'redis://redis', minsize=0, maxsize=10, loop=self.loop)

    thread_local = None

    def __init__(self):
        if not App.thread_local:
            App.thread_local = local()

        if not hasattr(App.thread_local, "instance"):
            App.thread_local.instance = App.__App()

    def __getattr__(self, name):
        return getattr(self.thread_local.instance, name)
