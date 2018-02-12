"""Add available_volume to Orders

Revision ID: 7719b4610d7e
Revises: 4ce9876eea54
Create Date: 2018-02-11 19:00:06.334874

"""
from alembic import op
from sqlalchemy import Column, Integer

import os.path, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common_types import SA_TYPE_VALUE


# revision identifiers, used by Alembic.
revision = '7719b4610d7e'
down_revision = '4ce9876eea54'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", Column("available_volume", SA_TYPE_VALUE))

def downgrade():
    op.drop_column("orders", "available_volume")
