import hashlib
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import get_settings
from .models import AuditEvent, OrderMap, Result
from .schema import NormalizedResult


def _hash_result(result: NormalizedResult) -> str:
    raw = result.raw_payload or result.model_dump_json()
    identity = f"{result.device_key}\n{result.profile_id}\n{raw}".encode("utf-8", errors="replace")
    return hashlib.sha256(identity).hexdigest()


def persist_result(db: Session, incoming: NormalizedResult) -> tuple[Result, bool]:
    payload_hash = _hash_result(incoming)
    existing = db.scalar(select(Result).where(Result.payload_hash == payload_hash))
    if existing:
        return existing, False

    mapping = db.scalar(select(OrderMap).where(OrderMap.accession == incoming.accession))
    status = "MATCHED" if mapping else "UNMATCHED"
    raw_payload = incoming.raw_payload if get_settings().raw_retention_enabled else None
    obj = Result(
        device_key=incoming.device_key,
        profile_id=incoming.profile_id,
        accession=incoming.accession,
        patient_id=mapping.patient_id if mapping else None,
        observed_at=incoming.observed_at,
        status=status,
        payload_hash=payload_hash,
        observations=[o.model_dump() for o in incoming.observations],
        source_meta=incoming.source_meta,
        raw_payload=raw_payload,
    )
    db.add(obj)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Result).where(Result.payload_hash == payload_hash))
        return existing, False
    db.add(AuditEvent(event_type="RESULT_INGESTED", entity_type="result", entity_id=str(obj.id),
                      details={"accession": obj.accession, "status": status, "device_key": obj.device_key}))
    db.commit(); db.refresh(obj)
    return obj, True
