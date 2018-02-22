"""create ticker table

Revision ID: e032ff832b82
Revises: 4ce9876eea54
Create Date: 2018-02-10 20:04:45.809762

"""
from alembic import op
from sqlalchemy import Column, DateTime, Numeric

import os.path, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common_types import SA_TYPE_ADDR


# revision identifiers, used by Alembic.
revision = 'e032ff832b82'
down_revision = '7719b4610d7e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tickers",
        Column("token_address", SA_TYPE_ADDR, primary_key=True, nullable=False),
        Column("quote_volume", Numeric),
        Column("base_volume", Numeric),
        Column("last", Numeric),
        Column("percent_change", Numeric),
        Column("bid", Numeric),
        Column("ask", Numeric),
        Column("updated", DateTime, nullable=False)
    )


def downgrade():
    op.drop_table("tickers")
