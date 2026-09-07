from datetime import datetime, timezone
from ..schema import NormalizedResult, Observation

# BC-3000 Plus field layouts can vary by software/protocol revision. This parser therefore uses
# an explicit profile field map and fails closed when the frame cannot be identified.


def parse_bc3000plus(payload, *, profile, device_key):
    raw = payload.decode("latin-1", errors="replace") if isinstance(payload, bytes) else payload
    printable = raw.replace("\x05", "").replace("\x06", "").replace("\x04", "").replace("\x03", "")
    cfg = profile.get("config", {})
    lines = [x for x in printable.replace("\n", "\r").split("\r") if x.strip()]
    sample_line = next((x for x in lines if x.startswith(cfg.get("sample_prefix", "A"))), None)
    if sample_line is None:
        sample_line = printable if printable.startswith(cfg.get("sample_prefix", "A")) else None
    if sample_line is None:
        raise ValueError("BC-3000 Plus sample record not found")

    acc = cfg.get("accession_slice", [1, 9])
    accession = sample_line[int(acc[0]):int(acc[1])].strip()
    if not accession:
        raise ValueError("BC-3000 Plus accession empty")

    observations = []
    for field in cfg.get("fields", []):
        start, end = int(field["start"]), int(field["end"])
        if len(sample_line) < start:
            continue
        raw_value = sample_line[start:end].strip()
        if not raw_value:
            continue
        scale = field.get("scale")
        value = raw_value
        if scale is not None:
            try:
                value = float(raw_value) * float(scale)
            except ValueError:
                value = raw_value
        observations.append(Observation(
            code=field["code"], display=field.get("display"), value=value,
            unit=field.get("unit"), loinc=field.get("loinc"),
        ))

    return NormalizedResult(
        device_key=device_key,
        profile_id=profile["id"],
        accession=accession,
        observed_at=datetime.now(timezone.utc),
        observations=observations,
        source_meta={"protocol": "Mindray BC-3000 Plus serial", "validation": profile.get("validation_status")},
        raw_payload=raw,
    )
