from ..app import App
from ..tasks.update_order import update_order_by_signature

print("Huey is starting")
huey = App().huey
