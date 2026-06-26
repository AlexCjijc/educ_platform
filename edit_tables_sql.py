from alembic import op
import sqlalchemy as sa

# замените на реальные идентификаторы вашей миграции
revision = 'add_test_assignment_section_order'
down_revision = '<prev_revision_id>'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('test', schema=None) as batch_op:
        batch_op.add_column(sa.Column('section_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('order_idx', sa.Integer(), server_default='0', nullable=False))
        # внешнюю связь на SQLite можно не создавать: batch_op.create_foreign_key('fk_test_section', 'section', ['section_id'], ['id'])

    with op.batch_alter_table('assignment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('section_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('order_idx', sa.Integer(), server_default='0', nullable=False))
        # batch_op.create_foreign_key('fk_assignment_section', 'section', ['section_id'], ['id'])

    # убрать server_default, чтобы дальше писался явный 0
    with op.batch_alter_table('test', schema=None) as batch_op:
        batch_op.alter_column('order_idx', server_default=None)
    with op.batch_alter_table('assignment', schema=None) as batch_op:
        batch_op.alter_column('order_idx', server_default=None)

def downgrade():
    with op.batch_alter_table('assignment', schema=None) as batch_op:
        batch_op.drop_column('order_idx')
        batch_op.drop_column('section_id')
    with op.batch_alter_table('test', schema=None) as batch_op:
        batch_op.drop_column('order_idx')
        batch_op.drop_column('section_id')
