"""Create Trades table

Revision ID: 7b76793c971f
Revises:
Create Date: 2018-01-14 14:29:46.093992

"""

from alembic import op
from sqlalchemy import Column, DateTime, Integer, text

import os.path, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common_types import SA_TYPE_ADDR, SA_TYPE_TXHASH, SA_TYPE_VALUE, UUID

# revision identifiers, used by Alembic.
revision = "7b76793c971f"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""create EXTENSION if not EXISTS "uuid-ossp";""")
    op.create_table(
        "trades",
        Column("id", UUID(), primary_key=True, server_default=text("uuid_generate_v1mc()")),
        Column("block_number", Integer, nullable=False),
        Column("transaction_hash", SA_TYPE_TXHASH, nullable=False),
        Column("log_index", Integer, nullable=False),
        Column("token_give", SA_TYPE_ADDR, nullable=False),
        Column("amount_give", SA_TYPE_VALUE, nullable=False),
        Column("token_get", SA_TYPE_ADDR, nullable=False),
        Column("amount_get", SA_TYPE_VALUE, nullable=False),
        Column("addr_give", SA_TYPE_ADDR, nullable=False),
        Column("addr_get", SA_TYPE_ADDR, nullable=False),
        Column("date", DateTime, nullable=False)
    )

    op.create_unique_constraint("index_trades_on_event_identifier", "trades", ["transaction_hash", "log_index"])
    op.create_index("index_trades_on_token_give", "trades", ["token_give"])
    op.create_index("index_trades_on_token_get", "trades", ["token_get"])
    op.create_index("index_trades_on_addr_give", "trades", ["addr_give"])
    op.create_index("index_trades_on_addr_get", "trades", ["addr_get"])



def downgrade():
    op.drop_table("trades")
