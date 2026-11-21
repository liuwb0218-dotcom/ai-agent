"""add order flow fields (quantity/product_id/status timestamps)

Revision ID: a1b2c3d4e5f6
Revises: 985d819395d0
Create Date: 2026-08-13 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '985d819395d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('orders', sa.Column('quantity', sa.Integer(), server_default='1', nullable=False, comment='购买数量'))
    op.add_column('orders', sa.Column('product_id', sa.String(length=20), nullable=True, comment='商品 ID'))
    op.add_column('orders', sa.Column('paid_at', sa.DateTime(), nullable=True, comment='支付时间'))
    op.add_column('orders', sa.Column('shipped_at', sa.DateTime(), nullable=True, comment='发货时间'))
    op.add_column('orders', sa.Column('completed_at', sa.DateTime(), nullable=True, comment='完成时间'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('orders', 'completed_at')
    op.drop_column('orders', 'shipped_at')
    op.drop_column('orders', 'paid_at')
    op.drop_column('orders', 'product_id')
    op.drop_column('orders', 'quantity')
