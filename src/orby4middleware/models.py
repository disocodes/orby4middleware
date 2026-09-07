from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    manufacturer: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(120))
    profile_id: Mapped[str] = mapped_column(String(160))
    validation_status: Mapped[str] = mapped_column(String(40), default="experimental")
    enabled: Mapped[bool] = mapped_column(default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OrderMap(Base):
    __tablename__ = "order_maps"
    id: Mapped[int] = mapped_column(primary_key=True)
    accession: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(120), index=True)
    encounter_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    service_request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Result(Base):
    __tablename__ = "results"
    __table_args__ = (UniqueConstraint("payload_hash", name="uq_result_payload_hash"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    device_key: Mapped[str] = mapped_column(String(120), index=True)
    profile_id: Mapped[str] = mapped_column(String(160))
    accession: Mapped[str] = mapped_column(String(120), index=True)
    patient_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), default="UNMATCHED", index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), unique=True)
    observations: Mapped[list] = mapped_column(JSON)
    source_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deliveries: Mapped[list["DeliveryAttempt"]] = relationship(back_populates="result")


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("results.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(40), default="PENDING")
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    response_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    result: Mapped[Result] = relationship(back_populates="deliveries")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    actor: Mapped[str] = mapped_column(String(120), default="system")
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(120))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
