"""Initial database schema for ADC

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-19 02:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('display_name', sa.String(length=128), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('avatar_url', sa.String(length=512), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # 1b. user_sessions
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('session_token_hash', sa.String(length=64), nullable=False),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_activity', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_sessions_session_token_hash'), 'user_sessions', ['session_token_hash'], unique=True)
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)

    # 2. machines
    op.create_table(
        'machines',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('installation_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('public_key', sa.Text(), nullable=False),
        sa.Column('platform', sa.String(length=64), nullable=True),
        sa.Column('active_role', sa.String(length=32), nullable=False, server_default='none'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='offline'),
        sa.Column('is_online', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lease_token', sa.String(length=128), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paired_user_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['paired_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_machines_installation_id'), 'machines', ['installation_id'], unique=True)
    op.create_index(op.f('ix_machines_paired_user_id'), 'machines', ['paired_user_id'], unique=False)

    # 3. machine_credentials
    op.create_table(
        'machine_credentials',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('machine_id', sa.Uuid(), nullable=False),
        sa.Column('credential_type', sa.String(length=32), nullable=False, server_default='ed25519'),
        sa.Column('public_key', sa.Text(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=True),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_reason', sa.String(length=255), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_machine_credentials_machine_id'), 'machine_credentials', ['machine_id'], unique=False)

    # 4. pairing_challenges
    op.create_table(
        'pairing_challenges',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('machine_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('challenge_code', sa.String(length=32), nullable=False),
        sa.Column('nonce', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('selected_role', sa.String(length=32), nullable=False, server_default='worker'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pairing_challenges_challenge_code'), 'pairing_challenges', ['challenge_code'], unique=True)
    op.create_index(op.f('ix_pairing_challenges_machine_id'), 'pairing_challenges', ['machine_id'], unique=False)
    op.create_index(op.f('ix_pairing_challenges_user_id'), 'pairing_challenges', ['user_id'], unique=False)

    # 5. projects
    op.create_table(
        'projects',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('training_objective', sa.Text(), nullable=False, server_default=''),
        sa.Column('model_architecture', sa.String(length=128), nullable=False, server_default=''),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='online'),
        sa.Column('visibility', sa.String(length=32), nullable=False, server_default='public'),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('training_strategy', sa.String(length=64), nullable=False, server_default='independent_jobs'),
        sa.Column('workers_needed', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('min_cpu_cores', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('min_ram_gb', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('gpu_recommended', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('min_vram_gb', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expected_duration', sa.String(length=64), nullable=False, server_default='Unknown'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_owner_id'), 'projects', ['owner_id'], unique=False)

    # 6. project_codes
    op.create_table(
        'project_codes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.String(length=16), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_project_codes_code'), 'project_codes', ['code'], unique=True)
    op.create_index(op.f('ix_project_codes_project_id'), 'project_codes', ['project_id'], unique=False)

    # 7. project_memberships
    op.create_table(
        'project_memberships',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('machine_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='idle'),
        sa.Column('contribution_status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('cpu_cores_contributed', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('ram_contributed_gb', sa.Float(), nullable=False, server_default='4.0'),
        sa.Column('gpu_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('selected_gpu', sa.String(length=128), nullable=False, server_default=''),
        sa.Column('storage_budget_gb', sa.Float(), nullable=False, server_default='20.0'),
        sa.Column('network_preference', sa.String(length=32), nullable=False, server_default='unlimited'),
        sa.Column('steps_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_batch', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'machine_id', name='uq_project_machine')
    )
    op.create_index(op.f('ix_project_memberships_machine_id'), 'project_memberships', ['machine_id'], unique=False)
    op.create_index(op.f('ix_project_memberships_project_id'), 'project_memberships', ['project_id'], unique=False)
    op.create_index(op.f('ix_project_memberships_user_id'), 'project_memberships', ['user_id'], unique=False)

    # 8. datasets
    op.create_table(
        'datasets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('format', sa.String(length=32), nullable=False, server_default='zip'),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=False),
        sa.Column('is_validated', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('validation_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_datasets_project_id'), 'datasets', ['project_id'], unique=False)

    # 9. model_packages
    op.create_table(
        'model_packages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('entrypoint', sa.String(length=128), nullable=False, server_default='train.py'),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=False),
        sa.Column('manifest_json', sa.Text(), nullable=True),
        sa.Column('is_validated', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('validation_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_packages_project_id'), 'model_packages', ['project_id'], unique=False)

    # 10. training_configurations
    op.create_table(
        'training_configurations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('batch_size', sa.Integer(), nullable=False, server_default='16'),
        sa.Column('total_steps', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('learning_rate', sa.String(length=32), nullable=False, server_default='0.0001'),
        sa.Column('optimizer', sa.String(length=32), nullable=False, server_default='adamw'),
        sa.Column('precision', sa.String(length=16), nullable=False, server_default='fp16'),
        sa.Column('checkpoint_interval', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('gradient_accumulation_steps', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('extra_args_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_training_configurations_project_id'), 'training_configurations', ['project_id'], unique=False)

    # 11. training_runs
    op.create_table(
        'training_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('run_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('current_step', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_steps', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('current_loss', sa.Float(), nullable=True),
        sa.Column('training_speed', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_training_runs_project_id'), 'training_runs', ['project_id'], unique=False)

    # 12. training_tasks
    op.create_table(
        'training_tasks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('assigned_machine_id', sa.Uuid(), nullable=True),
        sa.Column('task_type', sa.String(length=32), nullable=False, server_default='batch'),
        sa.Column('step_start', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('step_end', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('lease_token', sa.String(length=128), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('result_summary', sa.Text(), nullable=True),
        sa.Column('error_details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_machine_id'], ['machines.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['training_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_training_tasks_assigned_machine_id'), 'training_tasks', ['assigned_machine_id'], unique=False)
    op.create_index(op.f('ix_training_tasks_project_id'), 'training_tasks', ['project_id'], unique=False)
    op.create_index(op.f('ix_training_tasks_run_id'), 'training_tasks', ['run_id'], unique=False)

    # 13. training_metrics
    op.create_table(
        'training_metrics',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('step', sa.Integer(), nullable=False),
        sa.Column('loss', sa.Float(), nullable=False),
        sa.Column('speed', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cluster_cpu_util', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cluster_gpu_util', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('ram_util_gb', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['training_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_training_metrics_project_id'), 'training_metrics', ['project_id'], unique=False)
    op.create_index(op.f('ix_training_metrics_run_id'), 'training_metrics', ['run_id'], unique=False)
    op.create_index(op.f('ix_training_metrics_step'), 'training_metrics', ['step'], unique=False)

    # 14. checkpoints
    op.create_table(
        'checkpoints',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('step', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=False),
        sa.Column('is_validated', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('metrics_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['training_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_checkpoints_project_id'), 'checkpoints', ['project_id'], unique=False)
    op.create_index(op.f('ix_checkpoints_run_id'), 'checkpoints', ['run_id'], unique=False)
    op.create_index(op.f('ix_checkpoints_step'), 'checkpoints', ['step'], unique=False)

    # 15. artifacts
    op.create_table(
        'artifacts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=True),
        sa.Column('artifact_type', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['training_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_artifacts_project_id'), 'artifacts', ['project_id'], unique=False)
    op.create_index(op.f('ix_artifacts_run_id'), 'artifacts', ['run_id'], unique=False)

    # 16. worker_resource_snapshots
    op.create_table(
        'worker_resource_snapshots',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('machine_id', sa.Uuid(), nullable=False),
        sa.Column('cpu_model', sa.String(length=128), nullable=False, server_default='Unknown'),
        sa.Column('cpu_cores_total', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('cpu_usage_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('ram_total_gb', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('ram_available_gb', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('ram_usage_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('gpu_model', sa.String(length=128), nullable=False, server_default='None'),
        sa.Column('gpu_memory_total_gb', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('gpu_memory_used_gb', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('gpu_utilization_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('disk_available_gb', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_worker_resource_snapshots_machine_id'), 'worker_resource_snapshots', ['machine_id'], unique=False)
    op.create_index(op.f('ix_worker_resource_snapshots_timestamp'), 'worker_resource_snapshots', ['timestamp'], unique=False)

    # 17. resource_allocations
    op.create_table(
        'resource_allocations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('machine_id', sa.Uuid(), nullable=False),
        sa.Column('cpu_cores', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('ram_gb', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('gpu_indices', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('storage_gb', sa.Float(), nullable=False, server_default='10.0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='reserved'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resource_allocations_machine_id'), 'resource_allocations', ['machine_id'], unique=False)
    op.create_index(op.f('ix_resource_allocations_project_id'), 'resource_allocations', ['project_id'], unique=False)

    # 18. machine_contribution_settings
    op.create_table(
        'machine_contribution_settings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('machine_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('cpu_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('cpu_cores', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('ram_budget_gb', sa.Float(), nullable=False, server_default='4.0'),
        sa.Column('gpu_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('selected_gpu', sa.String(length=128), nullable=False, server_default=''),
        sa.Column('storage_budget_gb', sa.Float(), nullable=False, server_default='20.0'),
        sa.Column('network_preference', sa.String(length=32), nullable=False, server_default='unlimited'),
        sa.Column('global_paused', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_machine_contribution_settings_machine_id'), 'machine_contribution_settings', ['machine_id'], unique=True)
    op.create_index(op.f('ix_machine_contribution_settings_user_id'), 'machine_contribution_settings', ['user_id'], unique=False)

    # 19. audit_events
    op.create_table(
        'audit_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('machine_id', sa.Uuid(), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('resource_type', sa.String(length=64), nullable=True),
        sa.Column('resource_id', sa.String(length=128), nullable=True),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_events_action'), 'audit_events', ['action'], unique=False)
    op.create_index(op.f('ix_audit_events_machine_id'), 'audit_events', ['machine_id'], unique=False)
    op.create_index(op.f('ix_audit_events_timestamp'), 'audit_events', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_events_user_id'), 'audit_events', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('machine_contribution_settings')
    op.drop_table('resource_allocations')
    op.drop_table('worker_resource_snapshots')
    op.drop_table('artifacts')
    op.drop_table('checkpoints')
    op.drop_table('training_metrics')
    op.drop_table('training_tasks')
    op.drop_table('training_runs')
    op.drop_table('training_configurations')
    op.drop_table('model_packages')
    op.drop_table('datasets')
    op.drop_table('project_memberships')
    op.drop_table('project_codes')
    op.drop_table('projects')
    op.drop_table('pairing_challenges')
    op.drop_table('machine_credentials')
    op.drop_table('machines')
    op.drop_table('user_sessions')
    op.drop_table('users')
