"""Initial schema: users, skus, analysis_jobs, analysis_results, audit_events, regulatory_rules

Revision ID: 0001
Revises:
Create Date: 2026-04-06
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ──────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE user_role AS ENUM ('qa_reviewer','regulatory_affairs','local_marketing','admin')")
    op.execute("CREATE TYPE job_status AS ENUM ('queued','running','complete','failed','needs_review','stale_rules')")
    op.execute("CREATE TYPE workflow_state AS ENUM ('draft','ai_reviewed','human_review','approved','rejected')")
    op.execute("CREATE TYPE audit_event_type AS ENUM ('submitted','reviewed','approved','rejected','exported','stale_flagged')")
    op.execute("CREATE TYPE rule_type AS ENUM ('required_element','font_minimum','placement','symbol','structure','language')")

    # ── users ──────────────────────────────────────────────────────────────
    op.create_table("users",
        sa.Column("id",             postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email",          sa.String(255), nullable=False),
        sa.Column("azure_oid",      sa.String(128), nullable=True),
        sa.Column("display_name",   sa.String(255), nullable=True),
        sa.Column("role",           sa.Enum(name="user_role"), nullable=False, server_default="local_marketing"),
        sa.Column("division",       sa.String(100), nullable=True),
        sa.Column("allowed_regions",postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("is_active",      sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_users_email",     "users", ["email"])
    op.create_unique_constraint("uq_users_azure_oid", "users", ["azure_oid"])
    op.create_index("ix_users_email", "users", ["email"])

    # ── skus ───────────────────────────────────────────────────────────────
    op.create_table("skus",
        sa.Column("id",                   postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku_code",             sa.String(100), nullable=False),
        sa.Column("product_name",         sa.String(255), nullable=False),
        sa.Column("active_ingredient",    sa.String(255), nullable=False),
        sa.Column("strength",             sa.String(100), nullable=True),
        sa.Column("dosage_form",          sa.String(100), nullable=True),
        sa.Column("master_label_text",    sa.Text(), nullable=False),
        sa.Column("master_label_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("veeva_document_id",    sa.String(255), nullable=True),
        sa.Column("tenant_id",            postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at",           sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at",           sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_skus_code", "skus", ["sku_code"])
    op.create_index("ix_skus_sku_code", "skus", ["sku_code"])

    # ── analysis_jobs ──────────────────────────────────────────────────────
    op.create_table("analysis_jobs",
        sa.Column("id",                   postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku_id",               postgresql.UUID(as_uuid=True), sa.ForeignKey("skus.id"), nullable=True),
        sa.Column("tenant_id",            postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by",           postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("target_language",      sa.String(50), nullable=False),
        sa.Column("regulatory_region",    sa.String(50), nullable=True),
        sa.Column("status",               sa.Enum(name="job_status"), nullable=False, server_default="queued"),
        sa.Column("workflow_state",       sa.Enum(name="workflow_state"), nullable=False, server_default="draft"),
        sa.Column("master_label_hash",    sa.String(64), nullable=True),
        sa.Column("packaging_file_hash",  sa.String(64), nullable=True),
        sa.Column("packaging_file_path",  sa.String(1024), nullable=True),
        sa.Column("celery_task_id",       sa.String(255), nullable=True),
        sa.Column("created_at",           sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at",           sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at",         sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message",        sa.Text(), nullable=True),
    )
    op.create_index("ix_jobs_sku_id",        "analysis_jobs", ["sku_id"])
    op.create_index("ix_jobs_tenant_id",     "analysis_jobs", ["tenant_id"])
    op.create_index("ix_jobs_status",        "analysis_jobs", ["status"])
    op.create_index("ix_jobs_created_at",    "analysis_jobs", ["created_at"])
    op.create_index("ix_jobs_dedup",         "analysis_jobs", ["master_label_hash", "packaging_file_hash", "target_language"])
    op.create_index("ix_jobs_tenant_status", "analysis_jobs", ["tenant_id", "status"])

    # ── analysis_results ───────────────────────────────────────────────────
    op.create_table("analysis_results",
        sa.Column("id",                   postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id",               postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_jobs.id"), nullable=False),
        sa.Column("compliance_score",     sa.Float(), nullable=False),
        sa.Column("overall_status",       sa.String(50), nullable=False),
        sa.Column("translation_analysis", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("vision_analysis",      postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("agent_log",            postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("summary",              sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at",           sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_results_job_id", "analysis_results", ["job_id"])
    op.create_index("ix_results_job_id", "analysis_results", ["job_id"])

    # ── audit_events (append-only) ─────────────────────────────────────────
    op.create_table("audit_events",
        sa.Column("id",         postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id",     postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_jobs.id"), nullable=False),
        sa.Column("user_id",    postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_type", sa.Enum(name="audit_event_type"), nullable=False),
        sa.Column("timestamp",  sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("comment",    sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("metadata",   postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_audit_job_id",   "audit_events", ["job_id"])
    op.create_index("ix_audit_job_time", "audit_events", ["job_id", "timestamp"])

    # ── regulatory_rules ───────────────────────────────────────────────────
    op.create_table("regulatory_rules",
        sa.Column("id",              postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("region",          sa.String(50), nullable=False),
        sa.Column("rule_type",       sa.Enum(name="rule_type"), nullable=False),
        sa.Column("rule_key",        sa.String(255), nullable=False),
        sa.Column("rule_value",      postgresql.JSONB(), nullable=False),
        sa.Column("effective_date",  sa.Date(), nullable=False),
        sa.Column("expiry_date",     sa.Date(), nullable=True),
        sa.Column("source_document", sa.String(512), nullable=True),
        sa.Column("is_active",       sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at",      sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_rules_region",        "regulatory_rules", ["region"])
    op.create_index("ix_rules_is_active",     "regulatory_rules", ["is_active"])
    op.create_index("ix_rules_region_active", "regulatory_rules", ["region", "is_active", "effective_date"])

    # Enforce append-only audit trail at DB level
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_role') THEN
                CREATE ROLE app_role;
            END IF;
        END$$;
        GRANT INSERT, SELECT ON audit_events TO app_role;
        REVOKE UPDATE, DELETE ON audit_events FROM PUBLIC;
    """)


def downgrade() -> None:
    op.drop_table("regulatory_rules")
    op.drop_table("audit_events")
    op.drop_table("analysis_results")
    op.drop_table("analysis_jobs")
    op.drop_table("skus")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS rule_type")
    op.execute("DROP TYPE IF EXISTS audit_event_type")
    op.execute("DROP TYPE IF EXISTS workflow_state")
    op.execute("DROP TYPE IF EXISTS job_status")
    op.execute("DROP TYPE IF EXISTS user_role")
