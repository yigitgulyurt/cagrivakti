"""namaz_vakti tablosunu ezan_vakti olarak yeniden adlandır

Revision ID: 11626241702c
Revises: 9dd0eed739c5
Create Date: 2026-03-04 21:03:42.044443

"""
from alembic import op
import sqlalchemy as sa


revision = '11626241702c'
down_revision = '9dd0eed739c5'
branch_labels = None
depends_on = None


def upgrade():
    # Tablo adını değiştir (veri korunur)
    op.rename_table('namaz_vakti', 'ezan_vakti')

    # Index'i yeniden adlandır
    with op.batch_alter_table('ezan_vakti', schema=None) as batch_op:
        batch_op.drop_index('idx_vakit_sehir_ulke_tarih')
        batch_op.create_index('idx_vakit_sehir_ulke_tarih', ['sehir', 'country_code', 'tarih'], unique=False)

    # Guide tablosu değişiklikleri (bunlar güvenli, veri etkilenmez)
    with op.batch_alter_table('guide', schema=None) as batch_op:
        batch_op.alter_column('slug',
               existing_type=sa.VARCHAR(length=200),
               type_=sa.String(length=100),
               existing_nullable=False)
        batch_op.alter_column('description',
               existing_type=sa.VARCHAR(length=500),
               type_=sa.Text(),
               existing_nullable=True)
        batch_op.alter_column('image_url',
               existing_type=sa.VARCHAR(length=300),
               type_=sa.String(length=200),
               existing_nullable=True)
        batch_op.drop_index(batch_op.f('idx_guide_active_date'))
        batch_op.create_index('idx_guide_active', ['is_active'], unique=False)


def downgrade():
    with op.batch_alter_table('guide', schema=None) as batch_op:
        batch_op.drop_index('idx_guide_active')
        batch_op.create_index(batch_op.f('idx_guide_active_date'), ['is_active', 'created_at'], unique=False)
        batch_op.alter_column('image_url',
               existing_type=sa.String(length=200),
               type_=sa.VARCHAR(length=300),
               existing_nullable=True)
        batch_op.alter_column('description',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=500),
               existing_nullable=True)
        batch_op.alter_column('slug',
               existing_type=sa.String(length=100),
               type_=sa.VARCHAR(length=200),
               existing_nullable=False)

    op.rename_table('ezan_vakti', 'namaz_vakti')