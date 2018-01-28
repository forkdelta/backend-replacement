"""Add order fill column to Orders table

Revision ID: 47c6d9c6fd29
Revises: 7661fdf74566
Create Date: 2018-01-21 17:12:03.082114

"""
from alembic import op
from decimal import Decimal
from sqlalchemy import Column, Integer

import os.path, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common_types import SA_TYPE_VALUE


# revision identifiers, used by Alembic.
revision = '47c6d9c6fd29'
down_revision = '7661fdf74566'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders",
        Column("amount_fill", SA_TYPE_VALUE))

def downgrade():
    op.drop_column("orders", "amount_fill")
