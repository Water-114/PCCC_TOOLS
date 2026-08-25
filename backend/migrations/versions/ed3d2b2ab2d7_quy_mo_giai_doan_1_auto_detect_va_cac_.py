"""Quy mo Giai doan 1 - auto-detect va cac field moi

Revision ID: ed3d2b2ab2d7
Revises: 4503ab6017ba
Create Date: 2026-08-13 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed3d2b2ab2d7'
down_revision = '4503ab6017ba'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ho_so_session', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quy_mo_scan_attempted_at', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('ho_so_session_quy_mo', schema=None) as batch_op:
        batch_op.alter_column('source', existing_type=sa.String(length=10), type_=sa.String(length=30), existing_nullable=False)
        batch_op.add_column(sa.Column('chieu_cao_ke_hang', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('co_be_xang_dau_ngoai_troi', sa.Boolean(), nullable=True))


def downgrade():
    with op.batch_alter_table('ho_so_session_quy_mo', schema=None) as batch_op:
        batch_op.drop_column('co_be_xang_dau_ngoai_troi')
        batch_op.drop_column('chieu_cao_ke_hang')
        batch_op.alter_column('source', existing_type=sa.String(length=30), type_=sa.String(length=10), existing_nullable=False)

    with op.batch_alter_table('ho_so_session', schema=None) as batch_op:
        batch_op.drop_column('quy_mo_scan_attempted_at')
