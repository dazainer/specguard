"""Durable curated evaluation targets, jobs, results and worker lease."""
from alembic import op
import sqlalchemy as sa

revision = '0001_evaluations'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('targets', sa.Column('id', sa.String, primary_key=True),
        sa.Column('name', sa.String, nullable=False), sa.Column('subject', sa.String, nullable=False),
        sa.Column('manifest_json', sa.Text, nullable=False), sa.Column('manifest_hash', sa.String, nullable=False),
        sa.Column('created_at', sa.Float, nullable=False))
    op.create_table('runs', sa.Column('id', sa.String, primary_key=True),
        sa.Column('target_id', sa.String, sa.ForeignKey('targets.id'), nullable=False),
        sa.Column('idempotency_key', sa.String, unique=True, nullable=False),
        sa.Column('request_hash', sa.String, nullable=False), sa.Column('options_json', sa.Text, nullable=False),
        sa.Column('status', sa.String, nullable=False), sa.Column('created_at', sa.Float, nullable=False),
        sa.Column('started_at', sa.Float), sa.Column('finished_at', sa.Float),
        sa.Column('heartbeat', sa.Float), sa.Column('owner', sa.String),
        sa.Column('cancel_requested', sa.Integer, nullable=False, server_default='0'),
        sa.Column('max_seconds', sa.Integer, nullable=False), sa.Column('image', sa.String, nullable=False),
        sa.Column('failure_reason', sa.String), sa.Column('report_json', sa.Text),
        sa.Column('timings_json', sa.Text), sa.Column('pruned', sa.Integer, nullable=False, server_default='0'))
    op.create_index('ix_runs_status_created', 'runs', ['status', 'created_at'])
    op.create_table('artifacts', sa.Column('run_id', sa.String, sa.ForeignKey('runs.id'), primary_key=True),
        sa.Column('path', sa.String, primary_key=True), sa.Column('sha256', sa.String, nullable=False),
        sa.Column('size_bytes', sa.Integer, nullable=False), sa.Column('accepted', sa.Integer, nullable=False))
    op.create_table('mutants', sa.Column('run_id', sa.String, sa.ForeignKey('runs.id'), primary_key=True),
        sa.Column('suite', sa.String, primary_key=True), sa.Column('mutant_id', sa.String, primary_key=True),
        sa.Column('status', sa.String, nullable=False), sa.Column('data_json', sa.Text, nullable=False))
    op.create_index('ix_mutants_run_status', 'mutants', ['run_id', 'status'])
    op.create_table('events', sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('run_id', sa.String, sa.ForeignKey('runs.id'), nullable=False),
        sa.Column('stage', sa.String, nullable=False), sa.Column('at', sa.Float, nullable=False))
    op.create_table('workers', sa.Column('id', sa.String, primary_key=True),
        sa.Column('owner', sa.String, nullable=False), sa.Column('heartbeat', sa.Float, nullable=False))


def downgrade():
    for table in ('workers', 'events', 'mutants', 'artifacts', 'runs', 'targets'):
        op.drop_table(table)
