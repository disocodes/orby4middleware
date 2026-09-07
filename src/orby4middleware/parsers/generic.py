import re
from datetime import datetime, timezone
from ..schema import NormalizedResult, Observation


def _text(payload):
    return payload.decode("latin-1", errors="replace") if isinstance(payload, bytes) else payload


def _result(device_key, profile, accession, observations, raw, observed_at=None):
    return NormalizedResult(
        device_key=device_key,
        profile_id=profile["id"],
        accession=str(accession).strip(),
        observed_at=observed_at or datetime.now(timezone.utc),
        observations=observations,
        source_meta={"protocol": profile.get("protocol", "legacy")},
        raw_payload=raw,
    )


def parse_delimited(payload, *, profile, device_key):
    raw = _text(payload)
    cfg = profile.get("config", {})
    record_sep = cfg.get("record_separator", "\\r").encode().decode("unicode_escape")
    field_sep = cfg.get("field_separator", "|")
    result_record = cfg.get("result_record", "R")
    accession = None
    observations = []
    for line in [x for x in raw.split(record_sep) if x]:
        fields = line.split(field_sep)
        if fields[0] == cfg.get("sample_record", "S"):
            idx = int(cfg.get("accession_index", 1))
            if len(fields) > idx:
                accession = fields[idx]
        elif fields[0] == result_record:
            code_i = int(cfg.get("code_index", 1)); value_i = int(cfg.get("value_index", 2))
            unit_i = int(cfg.get("unit_index", 3)); flag_i = int(cfg.get("flag_index", 4))
            if len(fields) > value_i:
                observations.append(Observation(
                    code=fields[code_i], value=fields[value_i],
                    unit=fields[unit_i] if len(fields) > unit_i else None,
                    flag=fields[flag_i] if len(fields) > flag_i else None,
                ))
    if not accession:
        raise ValueError("accession not found")
    return _result(device_key, profile, accession, observations, raw)


def parse_fixed_width(payload, *, profile, device_key):
    raw = _text(payload)
    cfg = profile.get("config", {})
    accession_slice = cfg.get("accession_slice")
    if not accession_slice:
        raise ValueError("fixed-width profile requires accession_slice")
    accession = raw[int(accession_slice[0]):int(accession_slice[1])].strip()
    observations = []
    for field in cfg.get("fields", []):
        value = raw[int(field["start"]):int(field["end"])].strip()
        observations.append(Observation(
            code=field["code"], value=value, unit=field.get("unit"), loinc=field.get("loinc")
        ))
    return _result(device_key, profile, accession, observations, raw)


def parse_regex(payload, *, profile, device_key):
    raw = _text(payload)
    cfg = profile.get("config", {})
    accession_match = re.search(cfg["accession_regex"], raw, re.MULTILINE)
    if not accession_match:
        raise ValueError("accession not found")
    accession = accession_match.group(cfg.get("accession_group", 1))
    observations = []
    pattern = re.compile(cfg["result_regex"], re.MULTILINE)
    for match in pattern.finditer(raw):
        gd = match.groupdict()
        observations.append(Observation(
            code=gd["code"], value=gd["value"], unit=gd.get("unit"), flag=gd.get("flag")
        ))
    return _result(device_key, profile, accession, observations, raw)
