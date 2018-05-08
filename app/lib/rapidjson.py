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


# rapidjson proxy
# Used for python-socketio / python-engineio, where rapidjson is _almost_
# a drop-in replacement for stdlib json, except for an incompatible (and
# inconsequential) separators key
import rapidjson

def load(*args, **kwargs):
    if "separators" in kwargs:
        del kwargs["separators"]
    return rapidjson.load(*args, **kwargs)

def loads(*args, **kwargs):
    if "separators" in kwargs:
        del kwargs["separators"]
    return rapidjson.loads(*args, **kwargs)

def dump(*args, **kwargs):
    if "separators" in kwargs:
        del kwargs["separators"]
    return rapidjson.dump(*args, **kwargs)

def dumps(*args, **kwargs):
    if "separators" in kwargs:
        del kwargs["separators"]
    return rapidjson.dumps(*args, **kwargs)
