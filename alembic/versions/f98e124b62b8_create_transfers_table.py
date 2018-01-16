"""Create Transfers table

Revision ID: f98e124b62b8
Revises: 7b76793c971f
Create Date: 2018-01-15 23:29:25.460292

"""
from alembic import op
from sqlalchemy import Column, DateTime, Enum, Integer, text

import os.path, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common_types import TransferType, SA_TYPE_ADDR, SA_TYPE_TXHASH, SA_TYPE_VALUE, UUID


# revision identifiers, used by Alembic.
revision = 'f98e124b62b8'
down_revision = '7b76793c971f'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""create EXTENSION if not EXISTS "uuid-ossp";""")
    op.create_table(
        "transfers",
        Column("id", UUID(), primary_key=True, server_default=text("uuid_generate_v1mc()")),
        Column("block_number", Integer, nullable=False),
        Column("transaction_hash", SA_TYPE_TXHASH, nullable=False),
        Column("log_index", Integer, nullable=False),
        Column("direction", Enum(TransferType), nullable=False),
        Column("token", SA_TYPE_ADDR, nullable=False),
        Column("user", SA_TYPE_ADDR, nullable=False),
        Column("amount", SA_TYPE_VALUE, nullable=False),
        Column("balance_after", SA_TYPE_VALUE, nullable=False),
        Column("date", DateTime, nullable=False)
    )

    op.create_unique_constraint("index_transfers_on_event_identifier", "transfers", ["transaction_hash", "log_index"])
    op.create_index("index_transfers_on_user_token", "transfers", ["user", "token"])


def downgrade():
    op.drop_table("transfers")
    op.execute("DROP TYPE transfertype;")
