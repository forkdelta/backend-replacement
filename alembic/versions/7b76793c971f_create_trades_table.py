"""Create Trades table

Revision ID: 7b76793c971f
Revises:
Create Date: 2018-01-14 14:29:46.093992

"""

from alembic import op
from sqlalchemy import Column, Integer, text

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
        Column("id", UUID(), primary_key=True, server_default=text("uuid_generate_v1()")),
        Column("block_number", Integer),
        Column("transaction_hash", SA_TYPE_TXHASH),
        Column("log_index", Integer),
        Column("token_give", SA_TYPE_ADDR),
        Column("amount_give", SA_TYPE_VALUE),
        Column("token_get", SA_TYPE_ADDR),
        Column("amount_get", SA_TYPE_VALUE),
        Column("addr_give", SA_TYPE_ADDR),
        Column("addr_get", SA_TYPE_ADDR)
    )

    op.create_index("index_on_event_identifier", "trades", ["transaction_hash", "log_index"], unique=True)
    op.create_index("index_on_token_give", "trades", ["token_give"])
    op.create_index("index_on_token_get", "trades", ["token_get"])


def downgrade():
    pass
