from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .admin_ui import ADMIN_HTML
from .catalog import load_catalog, profile_by_id
from .config import get_settings
from .db import SessionLocal
from .delivery import post_json, send_mllp, to_fhir_bundle, to_hl7_oru
from .models import AuditEvent, Device, DeliveryAttempt, OrderMap, Result
from .onboarding import (
    VALIDATION_STATUSES,
    apply_observation_mapping,
    delivery_gate_reason,
    effective_profile,
    normalize_delivery_settings,
    updated_preview_state,
)
from .parsers import parse_with_profile
from .schema import (
    DeliveryRequest,
    DeliverySettingsIn,
    DeviceConfigurationIn,
    DeviceIn,
    DeviceValidationIn,
    NormalizedResult,
    Observation,
    OrderMapIn,
    ParsePreviewIn,
)
from .security import require_api_key
from .service import persist_result

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _audit(db: Session, event_type: str, entity_type: str, entity_id: str, details: dict[str, Any]):
    db.add(
        AuditEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )


def _device_view(device: Device) -> dict[str, Any]:
    profile = profile_by_id(device.profile_id) or {}
    config = device.config or {}
    return {
        "id": device.id,
        "device_key": device.device_key,
        "manufacturer": device.manufacturer,
        "model": device.model,
        "profile_id": device.profile_id,
        "protocol": profile.get("protocol"),
        "parser": profile.get("parser"),
        "validation_status": device.validation_status,
        "enabled": device.enabled,
        "config": config,
        "delivery_gate_reason": delivery_gate_reason(device.validation_status, config),
    }


def _get_device(db: Session, device_id: int) -> Device:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "device not found")
    return device


def _normalized_from_row(row: Result) -> NormalizedResult:
    return NormalizedResult(
        device_key=row.device_key,
        profile_id=row.profile_id,
        accession=row.accession,
        observed_at=row.observed_at,
        observations=[Observation.model_validate(x) for x in row.observations],
        source_meta=row.source_meta or {},
        raw_payload=row.raw_payload,
    )


async def _deliver_row(
    row: Result,
    request: DeliveryRequest,
    db: Session,
    *,
    raise_on_failure: bool = True,
) -> dict[str, Any]:
    if row.status == "UNMATCHED" or not row.patient_id:
        raise HTTPException(409, "result is unmatched and cannot be delivered")

    mapping = db.scalar(select(OrderMap).where(OrderMap.accession == row.accession))
    normalized = _normalized_from_row(row)
    target_type = request.target_type.lower().strip()
    target = request.target.strip()
    attempt_no = int(
        db.scalar(select(func.count(DeliveryAttempt.id)).where(DeliveryAttempt.result_id == row.id)) or 0
    ) + 1
    attempt = DeliveryAttempt(
        result_id=row.id,
        target_type=target_type,
        target=target,
        status="PENDING",
        attempt_no=attempt_no,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    settings = get_settings()

    try:
        if target_type == "fhir":
            payload = to_fhir_bundle(
                normalized,
                patient_id=row.patient_id,
                service_request_id=mapping.service_request_id if mapping else None,
            )
            code, text = await post_json(target, payload, timeout=settings.delivery_timeout_seconds)
            ok = 200 <= code < 300
            attempt.response_excerpt = f"HTTP {code}: {text[:1800]}"
        elif target_type == "rest":
            payload = {**normalized.model_dump(mode="json"), "patient_id": row.patient_id}
            code, text = await post_json(target, payload, timeout=settings.delivery_timeout_seconds)
            ok = 200 <= code < 300
            attempt.response_excerpt = f"HTTP {code}: {text[:1800]}"
        elif target_type == "hl7":
            if ":" not in target:
                raise ValueError("HL7 target must be host:port")
            host, port_s = target.rsplit(":", 1)
            ack = send_mllp(
                host,
                int(port_s),
                to_hl7_oru(normalized, patient_id=row.patient_id),
                timeout=settings.delivery_timeout_seconds,
            )
            ok = "MSA|AA" in ack or "MSA|CA" in ack
            attempt.response_excerpt = ack[:2000]
        else:
            raise ValueError("target_type must be one of: fhir, rest, hl7")

        attempt.status = "DELIVERED" if ok else "FAILED"
        if ok:
            row.status = "DELIVERED"
        _audit(
            db,
            "RESULT_DELIVERY",
            "result",
            str(row.id),
            {"attempt_id": attempt.id, "status": attempt.status, "target_type": target_type},
        )
        db.commit()
        response = {
            "attempt_id": attempt.id,
            "status": attempt.status,
            "result_status": row.status,
        }
        if not ok and raise_on_failure:
            raise HTTPException(502, f"delivery failed: {attempt.response_excerpt}")
        return response
    except HTTPException:
        raise
    except Exception as exc:
        attempt.status = "FAILED"
        attempt.response_excerpt = str(exc)[:2000]
        _audit(
            db,
            "RESULT_DELIVERY",
            "result",
            str(row.id),
            {"attempt_id": attempt.id, "status": "FAILED", "error": str(exc)[:500]},
        )
        db.commit()
        if raise_on_failure:
            raise HTTPException(502, f"delivery failed: {exc}") from exc
        return {"attempt_id": attempt.id, "status": "FAILED", "error": str(exc)}


async def _maybe_auto_deliver(device: Device | None, row: Result, created: bool, db: Session):
    if not device or not created or row.status != "MATCHED":
        return None
    delivery = (device.config or {}).get("delivery") or {}
    if not delivery.get("enabled"):
        return None
    reason = delivery_gate_reason(device.validation_status, device.config or {})
    if reason:
        return {"status": "BLOCKED", "reason": reason}
    request = DeliveryRequest(
        target_type=str(delivery.get("target_type") or ""),
        target=str(delivery.get("target") or ""),
    )
    return await _deliver_row(row, request, db, raise_on_failure=False)


@router.get("/health")
def health():
    return {"status": "ok", "service": "orby4middleware"}


@router.get("/api/v1/catalog", dependencies=[Depends(require_api_key)])
def catalog():
    return load_catalog()


@router.post("/api/v1/devices", dependencies=[Depends(require_api_key)])
def create_device(item: DeviceIn, db: Session = Depends(get_db)):
    profile = profile_by_id(item.profile_id)
    if not profile:
        raise HTTPException(400, "unknown profile_id")
    existing = db.scalar(select(Device).where(Device.device_key == item.device_key))
    if existing:
        raise HTTPException(409, "device_key already exists")
    validation_status = item.validation_status or profile.get("validation_status", "experimental")
    if validation_status not in VALIDATION_STATUSES:
        raise HTTPException(400, "invalid validation_status")
    obj = Device(
        device_key=item.device_key,
        manufacturer=item.manufacturer,
        model=item.model,
        profile_id=item.profile_id,
        validation_status=validation_status,
        config=item.config,
    )
    db.add(obj)
    db.flush()
    _audit(db, "DEVICE_CREATED", "device", str(obj.id), {"device_key": obj.device_key})
    db.commit()
    db.refresh(obj)
    return _device_view(obj)


@router.get("/api/v1/devices", dependencies=[Depends(require_api_key)])
def list_devices(db: Session = Depends(get_db)):
    return [_device_view(d) for d in db.scalars(select(Device).order_by(Device.device_key)).all()]


@router.get("/api/v1/devices/{device_id}", dependencies=[Depends(require_api_key)])
def get_device(device_id: int, db: Session = Depends(get_db)):
    return _device_view(_get_device(db, device_id))


@router.put("/api/v1/devices/{device_id}/configuration", dependencies=[Depends(require_api_key)])
def configure_device(device_id: int, item: DeviceConfigurationIn, db: Session = Depends(get_db)):
    device = _get_device(db, device_id)
    config = dict(device.config or {})
    changes = item.model_dump(exclude_none=True)
    if "delivery" in changes:
        try:
            changes["delivery"] = normalize_delivery_settings(changes["delivery"])
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if changes["delivery"].get("enabled"):
            candidate = {**config, **changes}
            reason = delivery_gate_reason(device.validation_status, candidate)
            if reason:
                raise HTTPException(409, reason)
    config.update(changes)
    device.config = config
    _audit(db, "DEVICE_CONFIG_UPDATED", "device", str(device.id), {"sections": sorted(changes)})
    db.commit()
    db.refresh(device)
    return _device_view(device)


@router.post("/api/v1/devices/{device_id}/preview", dependencies=[Depends(require_api_key)])
def preview_device(device_id: int, item: ParsePreviewIn, db: Session = Depends(get_db)):
    device = _get_device(db, device_id)
    base = profile_by_id(device.profile_id)
    if not base:
        raise HTTPException(400, "device profile is no longer available")
    profile = effective_profile(base, device.config or {}, parser_config_override=item.parser_config)
    mapping = item.mapping if item.mapping is not None else (device.config or {}).get("mapping") or {}
    try:
        normalized = parse_with_profile(item.payload, profile, device_key=device.device_key)
        normalized = apply_observation_mapping(normalized, mapping)
    except Exception as exc:
        if item.record_success:
            device.config = updated_preview_state(device.config, ok=False, error=str(exc)[:1000])
            db.commit()
        raise HTTPException(422, f"parse failed: {exc}") from exc

    if item.record_success:
        device.config = updated_preview_state(
            device.config,
            ok=True,
            accession=normalized.accession,
            observation_count=len(normalized.observations),
        )
        _audit(
            db,
            "DEVICE_PARSE_PREVIEW",
            "device",
            str(device.id),
            {"accession": normalized.accession, "observations": len(normalized.observations)},
        )
        db.commit()
    return {
        "ok": True,
        "profile_id": profile.get("id"),
        "parser": profile.get("parser"),
        "protocol": profile.get("protocol"),
        "normalized": normalized.model_dump(mode="json"),
    }


@router.post("/api/v1/devices/{device_id}/validation", dependencies=[Depends(require_api_key)])
def validate_device(device_id: int, item: DeviceValidationIn, db: Session = Depends(get_db)):
    device = _get_device(db, device_id)
    if item.status not in VALIDATION_STATUSES:
        raise HTTPException(400, f"status must be one of: {', '.join(sorted(VALIDATION_STATUSES))}")
    if item.status != "experimental" and not ((device.config or {}).get("onboarding") or {}).get("preview_ok"):
        raise HTTPException(409, "run a successful parse preview before promoting validation status")
    device.validation_status = item.status
    config = dict(device.config or {})
    onboarding = dict(config.get("onboarding") or {})
    onboarding.update(
        {
            "validated_by": item.validated_by,
            "validation_notes": item.notes,
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    config["onboarding"] = onboarding
    if item.status == "experimental" and (config.get("delivery") or {}).get("enabled"):
        delivery = dict(config["delivery"])
        delivery["enabled"] = False
        config["delivery"] = delivery
    device.config = config
    _audit(db, "DEVICE_VALIDATION_UPDATED", "device", str(device.id), {"status": item.status})
    db.commit()
    db.refresh(device)
    return _device_view(device)


@router.put("/api/v1/devices/{device_id}/delivery", dependencies=[Depends(require_api_key)])
def configure_delivery(device_id: int, item: DeliverySettingsIn, db: Session = Depends(get_db)):
    device = _get_device(db, device_id)
    try:
        settings = normalize_delivery_settings(item.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    candidate = dict(device.config or {})
    candidate["delivery"] = settings
    if settings["enabled"]:
        reason = delivery_gate_reason(device.validation_status, candidate)
        if reason:
            raise HTTPException(409, reason)
    device.config = candidate
    _audit(
        db,
        "DEVICE_DELIVERY_CONFIGURED",
        "device",
        str(device.id),
        {"enabled": settings["enabled"], "target_type": settings["target_type"]},
    )
    db.commit()
    db.refresh(device)
    return _device_view(device)


@router.post("/api/v1/orders", dependencies=[Depends(require_api_key)])
def create_order(item: OrderMapIn, db: Session = Depends(get_db)):
    existing = db.scalar(select(OrderMap).where(OrderMap.accession == item.accession))
    if existing:
        existing.patient_id = item.patient_id
        existing.encounter_id = item.encounter_id
        existing.service_request_id = item.service_request_id
        db.commit()
        db.refresh(existing)
        return {"id": existing.id, "updated": True}
    obj = OrderMap(**item.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return {"id": obj.id, "updated": False}


@router.get("/api/v1/orders", dependencies=[Depends(require_api_key)])
def list_orders(db: Session = Depends(get_db)):
    rows = db.scalars(select(OrderMap).order_by(OrderMap.id.desc()).limit(500)).all()
    return [
        {
            "id": r.id,
            "accession": r.accession,
            "patient_id": r.patient_id,
            "encounter_id": r.encounter_id,
            "service_request_id": r.service_request_id,
            "status": r.status,
        }
        for r in rows
    ]


@router.post("/api/v1/results/normalized", dependencies=[Depends(require_api_key)])
async def ingest_normalized(item: NormalizedResult, db: Session = Depends(get_db)):
    device = db.scalar(select(Device).where(Device.device_key == item.device_key, Device.enabled.is_(True)))
    normalized = item
    if device:
        normalized = apply_observation_mapping(item, (device.config or {}).get("mapping") or {})
    obj, created = persist_result(db, normalized)
    auto = await _maybe_auto_deliver(device, obj, created, db)
    return {
        "id": obj.id,
        "created": created,
        "status": obj.status,
        "accession": obj.accession,
        "auto_delivery": auto,
    }


@router.post("/api/v1/results/raw/{device_key}", dependencies=[Depends(require_api_key)])
async def ingest_raw(device_key: str, payload: dict, db: Session = Depends(get_db)):
    device = db.scalar(select(Device).where(Device.device_key == device_key, Device.enabled.is_(True)))
    if not device:
        raise HTTPException(404, "device not registered/enabled")
    base = profile_by_id(device.profile_id)
    if not base:
        raise HTTPException(400, "device profile is no longer available")
    raw = payload.get("payload")
    if raw is None:
        raise HTTPException(400, "payload field required")
    profile = effective_profile(base, device.config or {})
    try:
        normalized = parse_with_profile(raw, profile, device_key=device_key)
        normalized = apply_observation_mapping(normalized, (device.config or {}).get("mapping") or {})
    except Exception as exc:
        raise HTTPException(422, f"parse failed: {exc}") from exc
    obj, created = persist_result(db, normalized)
    auto = await _maybe_auto_deliver(device, obj, created, db)
    return {
        "id": obj.id,
        "created": created,
        "status": obj.status,
        "accession": obj.accession,
        "auto_delivery": auto,
    }


@router.post("/api/v1/results/{result_id}/deliver", dependencies=[Depends(require_api_key)])
async def deliver_result(result_id: int, request: DeliveryRequest, db: Session = Depends(get_db)):
    row = db.get(Result, result_id)
    if not row:
        raise HTTPException(404, "result not found")
    return await _deliver_row(row, request, db, raise_on_failure=True)


@router.get("/api/v1/results", dependencies=[Depends(require_api_key)])
def results(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Result).order_by(Result.id.desc()).limit(200)
    if status:
        stmt = stmt.where(Result.status == status)
    rows = db.scalars(stmt).all()
    return [
        {
            "id": r.id,
            "device_key": r.device_key,
            "accession": r.accession,
            "patient_id": r.patient_id,
            "status": r.status,
            "observed_at": r.observed_at,
            "observations": r.observations,
        }
        for r in rows
    ]


@router.get("/api/v1/deliveries", dependencies=[Depends(require_api_key)])
def deliveries(db: Session = Depends(get_db)):
    rows = db.scalars(select(DeliveryAttempt).order_by(DeliveryAttempt.id.desc()).limit(300)).all()
    return [
        {
            "id": r.id,
            "result_id": r.result_id,
            "target_type": r.target_type,
            "target": r.target,
            "status": r.status,
            "attempt_no": r.attempt_no,
            "response_excerpt": r.response_excerpt,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/api/v1/audit", dependencies=[Depends(require_api_key)])
def audit_events(db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(300)).all()
    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "actor": r.actor,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "details": r.details,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/admin", response_class=HTMLResponse)
def admin():
    return ADMIN_HTML
