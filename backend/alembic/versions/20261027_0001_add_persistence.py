"""Add WindSight persistence tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261027_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset", sa.String(length=16), nullable=False),
        sa.Column("requested_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("received_count", sa.Integer(), nullable=True),
        sa.Column("persisted_count", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_runs_dataset_started_at", "ingestion_runs", ["dataset", "started_at"]
    )
    op.create_table(
        "actual_generation_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("delivery_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generation", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source", "delivery_time", "generation", name="uq_actual_source_delivery_generation"
        ),
    )
    op.create_index(
        "ix_actual_generation_delivery_time", "actual_generation_records", ["delivery_time"]
    )
    op.create_table(
        "forecast_publication_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("delivery_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publication_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generation", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "delivery_time",
            "publication_time",
            "generation",
            name="uq_forecast_source_delivery_publication_generation",
        ),
    )
    op.create_index(
        "ix_forecast_publication_time", "forecast_publication_records", ["publication_time"]
    )
    op.create_index(
        "ix_forecast_delivery_publication_time",
        "forecast_publication_records",
        ["delivery_time", "publication_time"],
    )
    op.create_table(
        "saved_analysis_configurations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_identifier", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_identifier", "name", name="uq_saved_analysis_user_name"),
    )
    op.create_index(
        "ix_saved_analysis_user_identifier", "saved_analysis_configurations", ["user_identifier"]
    )


def downgrade() -> None:
    op.drop_index("ix_saved_analysis_user_identifier", table_name="saved_analysis_configurations")
    op.drop_table("saved_analysis_configurations")
    op.drop_index(
        "ix_forecast_delivery_publication_time", table_name="forecast_publication_records"
    )
    op.drop_index("ix_forecast_publication_time", table_name="forecast_publication_records")
    op.drop_table("forecast_publication_records")
    op.drop_index("ix_actual_generation_delivery_time", table_name="actual_generation_records")
    op.drop_table("actual_generation_records")
    op.drop_index("ix_ingestion_runs_dataset_started_at", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
