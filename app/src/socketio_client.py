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
import logging
import rapidjson
from time import sleep, time
from websockets import connect
from websockets.exceptions import ConnectionClosed

ENGINEIO_PING_INTERVAL = 25
ENGINEIO_PING_TIMEOUT = 60

ENGINEIO_OPEN = "0"
ENGINEIO_CLOSE = "1"
ENGINEIO_PING = "2"
ENGINEIO_PONG = "3"
ENGINEIO_MESSAGE = "4"
ENGINEIO_IGNORABLE = frozenset([])

SOCKETIO_OPEN = "0"
SOCKETIO_EVENT = "2"
SOCKETIO_IGNORABLE = frozenset((SOCKETIO_OPEN, ))


class SocketIOClient:
    def __init__(self,
                 ws_url,
                 ping_interval=ENGINEIO_PING_INTERVAL,
                 ping_timeout=ENGINEIO_PING_TIMEOUT):
        self.ws_url = ws_url
        self.callbacks = {}

        self.__configure_loggers()
        self.ws = None
        self.last_pong = None
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout

    def on(self, event_name, handler_func=None):
        def set_handler(handler):
            self.callbacks[event_name] = handler
            return handler

        if handler_func is None:
            return set_handler
        return set_handler(handler_func)

    async def start(self):
        logger = logging.getLogger('websockets')
        logger.info("Connecting to %s", self.ws_url)
        try:
            async with connect(self.ws_url) as websocket:
                self.ws = websocket
                if "connect" in self.callbacks:
                    await self.callbacks["connect"](self, "connect")
                async for message in websocket:
                    await self.engineio_consumer(message)
        except ConnectionClosed as err:
            if "disconnect" in self.callbacks:
                await self.callbacks["disconnect"](self, "disconnect")
            logger.error("Connection closed: %s", str(err))

    async def emit(self, event, payload):
        logger = logging.getLogger('socketio')
        json_payload = rapidjson.dumps([event, payload])
        msg = ENGINEIO_MESSAGE + SOCKETIO_EVENT + json_payload
        logger.debug("Send '%s'", msg)
        await self.ws.send(msg)

    async def engineio_consumer(self, message):
        logger = logging.getLogger('engineio')

        if len(message) > 0:
            if message[0] == ENGINEIO_MESSAGE:
                logger.debug("message: '%s'", message[1:65])
                await self.socketio_consumer(message[1:])
            elif message[0] == ENGINEIO_OPEN:
                self.last_pong = None
                asyncio.ensure_future(self.engineio_ping())
                logger.debug("Pinger started")
            elif message[0] == ENGINEIO_PONG:
                logger.debug("Pong received")
                self.last_pong = time()
                if "pong" in self.callbacks:
                    await self.callbacks["pong"](self, "pong")
            elif message[0] in ENGINEIO_IGNORABLE:
                logger.debug(
                    "Ignorable engine.io type '%s' with message '%s...'",
                    message[0], message[:65])
            else:
                logger.warn("Unknown engine.io type '%s' with message '%s...'",
                            message[0], message[:65])
        else:
            logger.debug("Got an empty message")

    async def engineio_ping(self):
        logger = logging.getLogger('engineio')

        while self.ws.open:
            await asyncio.sleep(ENGINEIO_PING_INTERVAL)
            alive = (not self.last_pong) or (
                time() - self.last_pong <
                ENGINEIO_PING_INTERVAL + ENGINEIO_PING_TIMEOUT)
            if alive:
                await self.ws.send(ENGINEIO_PING)
                logger.debug("Ping sent")
            else:
                logger.warn(
                    "Pong timeout: %i seconds since last pong, disconnect",
                    time() - self.last_pong)
                await self.ws.close()

    async def socketio_consumer(self, message):
        logger = logging.getLogger('socketio')
        if len(message) > 0:
            if message[0] == SOCKETIO_EVENT:
                logger.debug("event: '%s'", message[1:65])
                await self.consume_socketio_event(message[1:])
            elif message[0] in SOCKETIO_IGNORABLE:
                logger.debug("ignorable type '%s' with message '%s...'",
                             message[0], message[:65])
            else:
                logger.warn("unknown type '%s' with message '%s...'",
                            message[0], message[:65])
        else:
            logger.debug("Got an empty message")

    async def consume_socketio_event(self, json_payload):
        logger = logging.getLogger('socketio')
        try:
            event_name, payload = rapidjson.loads(json_payload)
        except ValueError as error:
            if "error" in self.callbacks:
                await self.callbacks["error"](self, "error", error)
        else:
            if event_name in self.callbacks:
                await self.callbacks[event_name](self, event_name, payload)
            else:
                logger.debug("Unhandled event '%s'", event_name)

    def __configure_loggers(self):
        for (logger_name, logger_level) in (('websockets', logging.WARN),
                                            ('engineio', logging.WARN),
                                            ('socketio', logging.INFO)):
            logging.getLogger(logger_name).setLevel(logger_level)
