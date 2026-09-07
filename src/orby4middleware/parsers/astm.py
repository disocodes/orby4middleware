from datetime import datetime, timezone
from ..schema import NormalizedResult, Observation


def parse_astm(payload, *, profile, device_key):
    raw = payload.decode("latin-1", errors="replace") if isinstance(payload, bytes) else payload
    clean = raw.replace("\x02", "").replace("\x03", "").replace("\x04", "")
    accession = None
    observations = []
    cfg = profile.get("config", {})
    for record in clean.replace("\n", "\r").split("\r"):
        record = record.strip()
        if not record:
            continue
        parts = record.split("|")
        rtype = parts[0][-1:]
        if rtype == "O":
            for idx in cfg.get("accession_candidate_indexes", [2, 3]):
                if len(parts) > idx and parts[idx].strip():
                    accession = parts[idx].strip(); break
        elif rtype == "R" and len(parts) >= 4:
            universal = parts[2]
            code = universal.split("^")[-1] or universal
            value = parts[3]
            unit = parts[4] if len(parts) > 4 else None
            flag = parts[6] if len(parts) > 6 else None
            observations.append(Observation(code=code, value=value, unit=unit, flag=flag))
    if not accession:
        raise ValueError("ASTM order/sample accession not found")
    return NormalizedResult(
        device_key=device_key, profile_id=profile["id"], accession=accession,
        observed_at=datetime.now(timezone.utc), observations=observations,
        source_meta={"protocol": "ASTM"}, raw_payload=raw,
    )
