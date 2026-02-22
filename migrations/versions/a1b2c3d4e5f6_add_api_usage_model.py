"""AddApiUsageModel

Revision ID: a1b2c3d4e5f6
Revises: 9dd0eed739c5
Create Date: 2026-02-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '9dd0eed739c5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'api_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_key', sa.String(length=255), nullable=False),
        sa.Column('is_vip', sa.Boolean(), nullable=True),
        sa.Column('total_requests', sa.Integer(), nullable=True),
        sa.Column('last_ip', sa.String(length=45), nullable=True),
        sa.Column('last_path', sa.String(length=255), nullable=True),
        sa.Column('last_status', sa.Integer(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_api_usage_api_key', 'api_usage', ['api_key'], unique=False)
    op.create_index('ix_api_usage_is_vip', 'api_usage', ['is_vip'], unique=False)


def downgrade():
    op.drop_index('ix_api_usage_is_vip', table_name='api_usage')
    op.drop_index('ix_api_usage_api_key', table_name='api_usage')
    op.drop_table('api_usage')

