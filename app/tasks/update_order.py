from ..app import App

huey = App().huey

@huey.task()
def update_order_by_signature(order_signature):
    print("Update order by signature={}".format(order_signature))
    return None

@huey.task()
def update_orders_by_maker(maker_addr, token_addr):
    print("Update order by maker={} and token={}".format(maker_addr, token_addr))
    return None
