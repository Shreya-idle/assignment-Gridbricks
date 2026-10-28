import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (Index("ix_ingestion_runs_dataset_started_at", "dataset", "started_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[Literal["running", "succeeded", "failed"]] = mapped_column(
        String(16), nullable=False, default="running"
    )
    received_count: Mapped[int | None] = mapped_column(Integer)
    persisted_count: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))


class ActualGenerationRecordModel(Base):
    __tablename__ = "actual_generation_records"
    __table_args__ = (
        UniqueConstraint(
            "source", "delivery_time", "generation", name="uq_actual_source_delivery_generation"
        ),
        Index("ix_actual_generation_delivery_time", "delivery_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    delivery_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generation: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="FUELHH")
    ingestion_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ForecastPublicationRecordModel(Base):
    __tablename__ = "forecast_publication_records"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "delivery_time",
            "publication_time",
            "generation",
            name="uq_forecast_source_delivery_publication_generation",
        ),
        Index("ix_forecast_publication_time", "publication_time"),
        Index("ix_forecast_delivery_publication_time", "delivery_time", "publication_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    delivery_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    publication_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generation: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="WINDFOR")
    ingestion_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SavedAnalysisConfiguration(Base):
    __tablename__ = "saved_analysis_configurations"
    __table_args__ = (
        UniqueConstraint("user_identifier", "name", name="uq_saved_analysis_user_name"),
        Index("ix_saved_analysis_user_identifier", "user_identifier"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
