"""Create Orders table

Revision ID: e322b26b2593
Revises: 7b76793c971f
Create Date: 2018-01-14 22:07:22.911300

"""
from alembic import op
from sqlalchemy import Column, Integer, text

import os.path, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common_types import SA_TYPE_ADDR, SA_TYPE_TXHASH, SA_TYPE_VALUE, UUID

# revision identifiers, used by Alembic.
revision = 'e322b26b2593'
down_revision = '7b76793c971f'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""create EXTENSION if not EXISTS "uuid-ossp";""")
    op.create_table(
        "orders",
        Column("token_give", SA_TYPE_ADDR),
        Column("amount_give", SA_TYPE_VALUE),
        Column("token_get", SA_TYPE_ADDR),
        Column("amount_get", SA_TYPE_VALUE))


def downgrade():
    pass
