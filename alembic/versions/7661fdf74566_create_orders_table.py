"""Create Orders table

Revision ID: 7661fdf74566
Revises: f98e124b62b8
Create Date: 2018-01-17 11:28:11.357744

"""
from alembic import op
from sqlalchemy import Column, DateTime, Enum, Integer, text

import os.path, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common_types import OrderSource, OrderState, SA_TYPE_ADDR, SA_TYPE_SIG, SA_TYPE_TXHASH, SA_TYPE_VALUE, UUID


# revision identifiers, used by Alembic.
revision = '7661fdf74566'
down_revision = 'f98e124b62b8'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""create EXTENSION if not EXISTS "uuid-ossp";""")
    op.create_table(
        "orders",
        Column("id", UUID(), primary_key=True, server_default=text("uuid_generate_v1mc()")),
        Column("source", Enum(OrderSource), nullable=False),
        Column("signature", SA_TYPE_TXHASH, nullable=False),
        Column("token_give", SA_TYPE_ADDR, nullable=False),
        Column("amount_give", SA_TYPE_VALUE, nullable=False),
        Column("token_get", SA_TYPE_ADDR, nullable=False),
        Column("amount_get", SA_TYPE_VALUE, nullable=False),
        Column("expires", SA_TYPE_VALUE, nullable=False),
        Column("nonce", SA_TYPE_VALUE, nullable=False),
        Column("user", SA_TYPE_ADDR, nullable=False),
        Column("state", Enum(OrderState), nullable=False),
        Column("v", Integer),
        Column("r", SA_TYPE_SIG),
        Column("s", SA_TYPE_SIG),
        Column("date", DateTime, nullable=False)
    )

    op.create_unique_constraint("index_orders_on_signature", "orders", ["signature"])
    op.create_index("index_orders_on_expires_token_give_token_get", "orders", ["expires", "token_give", "token_get"])
    op.create_index("index_orders_on_user", "orders", ["user"])

def downgrade():
    op.drop_table("orders")
    op.execute("DROP TYPE ordersource;")
    op.execute("DROP TYPE orderstate;")
