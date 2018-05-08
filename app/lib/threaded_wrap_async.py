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
from functools import update_wrapper
import logging
from threading import get_ident, local

thread_local = local()  # get a dictionary that different per-thread contents


def threaded_wrap_async(wrapped):
    """
    Wraps an asyncio coroutine and produces a regular function that can be run
    in a thread.

    Internally, creates or sets an event loop for the thread,
    runs the async function using `run_until_complete`, and returns
    the result of the coroutine or raises an exception.

    Argument is a coroutine object.
    Returns a synchronous function.
    """

    def wrapper(*args, **kwargs):
        # Create an event loop if there isn't one already
        if not hasattr(thread_local, "loop"):
            thread_local.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(thread_local.loop)

        return thread_local.loop.run_until_complete(wrapped(*args, **kwargs))

    # Make wrapper look like the wrapped function (updating its name)
    update_wrapper(wrapper, wrapped)
    return wrapper
