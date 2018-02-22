from gevent import monkey
monkey.patch_all() # cf. http://huey.readthedocs.io/en/latest/troubleshooting.html?highlight=monkey

from ..app import App
from ..tasks.update_order import update_order_by_signature, update_orders_by_maker_and_token

print("Huey is starting")
huey = App().huey
