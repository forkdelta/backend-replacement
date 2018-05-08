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


from gevent import monkey
monkey.patch_all(
)  # cf. http://huey.readthedocs.io/en/latest/troubleshooting.html?highlight=monkey

from ..app import App
from ..tasks.update_order import update_order_by_signature, update_orders_by_maker_and_token

print("Huey is starting")
huey = App().huey
