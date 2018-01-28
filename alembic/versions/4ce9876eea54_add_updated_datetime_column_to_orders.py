"""Add updated datetime column to Orders

Revision ID: 4ce9876eea54
Revises: 47c6d9c6fd29
Create Date: 2018-01-22 19:27:51.969849

"""
from alembic import op
from sqlalchemy import Column, DateTime


# revision identifiers, used by Alembic.
revision = '4ce9876eea54'
down_revision = '47c6d9c6fd29'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", Column("updated", DateTime))

def downgrade():
    op.drop_column("orders", "updated")
