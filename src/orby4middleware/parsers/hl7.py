from datetime import datetime, timezone
from ..schema import NormalizedResult, Observation


def _parse_ts(value: str):
    for fmt, width in (("%Y%m%d%H%M%S", 14), ("%Y%m%d%H%M", 12), ("%Y%m%d", 8)):
        try:
            return datetime.strptime(value[:width], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def parse_hl7_oru(payload, *, profile, device_key):
    raw = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else payload
    raw = raw.strip("\x0b\x1c\r\n")
    segments = [s for s in raw.replace("\n", "\r").split("\r") if s]
    accession = None
    observed_at = datetime.now(timezone.utc)
    observations = []
    for seg in segments:
        f = seg.split("|")
        if f[0] == "OBR":
            accession = (f[3] if len(f) > 3 and f[3] else (f[2] if len(f) > 2 else None))
            if accession:
                accession = accession.split("^")[0]
            if len(f) > 7 and f[7]:
                observed_at = _parse_ts(f[7])
        elif f[0] == "OBX" and len(f) > 5:
            ident = f[3].split("^") if len(f) > 3 else ["UNKNOWN"]
            code = ident[0] or (ident[1] if len(ident) > 1 else "UNKNOWN")
            display = ident[1] if len(ident) > 1 else None
            unit = f[6].split("^")[0] if len(f) > 6 and f[6] else None
            ref = f[7] if len(f) > 7 and f[7] else None
            flag = f[8] if len(f) > 8 and f[8] else None
            observations.append(Observation(code=code, display=display, value=f[5], unit=unit,
                                            reference_range=ref, flag=flag))
    if not accession:
        raise ValueError("HL7 OBR accession/order number not found")
    return NormalizedResult(
        device_key=device_key, profile_id=profile["id"], accession=accession,
        observed_at=observed_at, observations=observations,
        source_meta={"protocol": "HL7v2"}, raw_payload=raw,
    )
