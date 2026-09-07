from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from .catalog import load_catalog, profile_by_id
from .db import SessionLocal
from .models import Device, DeliveryAttempt, OrderMap, Result
from .parsers import parse_with_profile
from .schema import DeviceIn, DeliveryRequest, NormalizedResult, Observation, OrderMapIn
from .security import require_api_key
from .service import persist_result
from .delivery import post_json, send_mllp, to_fhir_bundle, to_hl7_oru
from .config import get_settings

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/health")
def health():
    return {"status": "ok", "service": "orby4middleware"}


@router.get("/api/v1/catalog", dependencies=[Depends(require_api_key)])
def catalog():
    return load_catalog()


@router.post("/api/v1/devices", dependencies=[Depends(require_api_key)])
def create_device(item: DeviceIn, db: Session = Depends(get_db)):
    if not profile_by_id(item.profile_id):
        raise HTTPException(400, "unknown profile_id")
    existing = db.scalar(select(Device).where(Device.device_key == item.device_key))
    if existing:
        raise HTTPException(409, "device_key already exists")
    obj = Device(**item.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": obj.id, "device_key": obj.device_key}


@router.get("/api/v1/devices", dependencies=[Depends(require_api_key)])
def list_devices(db: Session = Depends(get_db)):
    return [{"id": d.id, "device_key": d.device_key, "manufacturer": d.manufacturer,
             "model": d.model, "profile_id": d.profile_id,
             "validation_status": d.validation_status, "enabled": d.enabled}
            for d in db.scalars(select(Device).order_by(Device.device_key)).all()]


@router.post("/api/v1/orders", dependencies=[Depends(require_api_key)])
def create_order(item: OrderMapIn, db: Session = Depends(get_db)):
    existing = db.scalar(select(OrderMap).where(OrderMap.accession == item.accession))
    if existing:
        existing.patient_id = item.patient_id
        existing.encounter_id = item.encounter_id
        existing.service_request_id = item.service_request_id
        db.commit(); db.refresh(existing)
        return {"id": existing.id, "updated": True}
    obj = OrderMap(**item.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": obj.id, "updated": False}


@router.post("/api/v1/results/normalized", dependencies=[Depends(require_api_key)])
def ingest_normalized(item: NormalizedResult, db: Session = Depends(get_db)):
    obj, created = persist_result(db, item)
    return {"id": obj.id, "created": created, "status": obj.status, "accession": obj.accession}


@router.post("/api/v1/results/raw/{device_key}", dependencies=[Depends(require_api_key)])
def ingest_raw(device_key: str, payload: dict, db: Session = Depends(get_db)):
    device = db.scalar(select(Device).where(Device.device_key == device_key, Device.enabled.is_(True)))
    if not device:
        raise HTTPException(404, "device not registered/enabled")
    profile = profile_by_id(device.profile_id)
    raw = payload.get("payload")
    if raw is None:
        raise HTTPException(400, "payload field required")
    try:
        normalized = parse_with_profile(raw, profile, device_key=device_key)
    except Exception as exc:
        raise HTTPException(422, f"parse failed: {exc}") from exc
    obj, created = persist_result(db, normalized)
    return {"id": obj.id, "created": created, "status": obj.status, "accession": obj.accession}


@router.post("/api/v1/results/{result_id}/deliver", dependencies=[Depends(require_api_key)])
async def deliver_result(result_id: int, request: DeliveryRequest, db: Session = Depends(get_db)):
    row = db.get(Result, result_id)
    if not row:
        raise HTTPException(404, "result not found")
    if row.status == "UNMATCHED" or not row.patient_id:
        raise HTTPException(409, "result is unmatched and cannot be delivered")
    mapping = db.scalar(select(OrderMap).where(OrderMap.accession == row.accession))
    normalized = NormalizedResult(
        device_key=row.device_key, profile_id=row.profile_id, accession=row.accession,
        observed_at=row.observed_at,
        observations=[Observation.model_validate(x) for x in row.observations],
        source_meta=row.source_meta or {}, raw_payload=row.raw_payload,
    )
    attempt = DeliveryAttempt(result_id=row.id, target_type=request.target_type.lower(), target=request.target,
                              status="PENDING")
    db.add(attempt); db.commit(); db.refresh(attempt)
    settings = get_settings()
    try:
        if attempt.target_type == "fhir":
            payload = to_fhir_bundle(normalized, patient_id=row.patient_id,
                                     service_request_id=mapping.service_request_id if mapping else None)
            code, text = await post_json(request.target, payload, timeout=settings.delivery_timeout_seconds)
            ok = 200 <= code < 300
            attempt.response_excerpt = f"HTTP {code}: {text[:1800]}"
        elif attempt.target_type == "rest":
            payload = {**normalized.model_dump(mode="json"), "patient_id": row.patient_id}
            code, text = await post_json(request.target, payload, timeout=settings.delivery_timeout_seconds)
            ok = 200 <= code < 300
            attempt.response_excerpt = f"HTTP {code}: {text[:1800]}"
        elif attempt.target_type == "hl7":
            if ":" not in request.target:
                raise ValueError("HL7 target must be host:port")
            host, port_s = request.target.rsplit(":", 1)
            ack = send_mllp(host, int(port_s), to_hl7_oru(normalized, patient_id=row.patient_id),
                            timeout=settings.delivery_timeout_seconds)
            ok = "MSA|AA" in ack or "MSA|CA" in ack
            attempt.response_excerpt = ack[:2000]
        else:
            raise ValueError("target_type must be one of: fhir, rest, hl7")
        attempt.status = "DELIVERED" if ok else "FAILED"
        if ok:
            row.status = "DELIVERED"
        db.commit()
        return {"attempt_id": attempt.id, "status": attempt.status, "result_status": row.status}
    except Exception as exc:
        attempt.status = "FAILED"
        attempt.response_excerpt = str(exc)[:2000]
        db.commit()
        raise HTTPException(502, f"delivery failed: {exc}") from exc


@router.get("/api/v1/results", dependencies=[Depends(require_api_key)])
def results(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Result).order_by(Result.id.desc()).limit(200)
    if status:
        stmt = stmt.where(Result.status == status)
    rows = db.scalars(stmt).all()
    return [{"id": r.id, "device_key": r.device_key, "accession": r.accession,
             "patient_id": r.patient_id, "status": r.status, "observed_at": r.observed_at,
             "observations": r.observations} for r in rows]


@router.get("/admin", response_class=HTMLResponse)
def admin():
    return """<!doctype html><html><head><title>orby4middleware</title>
    <style>body{font-family:system-ui;max-width:1000px;margin:40px auto;padding:0 20px}code{background:#eee;padding:2px 5px}
    .card{border:1px solid #ddd;border-radius:12px;padding:20px;margin:15px 0}</style></head><body>
    <h1>orby4middleware</h1><p>Vendor-neutral medical device integration gateway.</p>
    <div class=card><h2>Operator endpoints</h2><p>Use <code>/docs</code> for the authenticated API console.</p>
    <p>Configure devices via <code>/api/v1/devices</code>, map accessions via <code>/api/v1/orders</code>,
    and review results via <code>/api/v1/results</code>.</p></div>
    <div class=card><h2>Safety</h2><p>Unmatched accessions are held. Automatic name/fuzzy patient matching is not performed.</p></div>
    </body></html>"""
