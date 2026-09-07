from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..schema import NormalizedResult, Observation


def _load(payload: bytes | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("JSON payload must be an object")
    return value


def _parse_datetime(value: Any) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_json_result(payload, *, profile, device_key):
    obj = _load(payload)
    cfg = profile.get("config", {}) or {}
    accession_field = cfg.get("accession_field", "accession")
    results_field = cfg.get("results_field", "results")
    observed_at_field = cfg.get("observed_at_field", "observed_at")
    accession = obj.get(accession_field) or obj.get("sample_id") or obj.get("specimen_id")
    if not accession:
        raise ValueError("accession not found in JSON payload")

    raw_results = obj.get(results_field)
    if raw_results is None:
        raw_results = obj.get("observations")
    if not isinstance(raw_results, list):
        raise ValueError("results/observations must be a list")

    observations: list[Observation] = []
    for item in raw_results:
        if not isinstance(item, dict):
            raise ValueError("each result must be an object")
        code = item.get("code") or item.get("name") or item.get("test")
        if not code:
            raise ValueError("result code is required")
        observations.append(
            Observation(
                code=str(code),
                value=item.get("value"),
                unit=item.get("unit"),
                display=item.get("display") or item.get("name"),
                loinc=item.get("loinc"),
                flag=item.get("flag"),
                reference_range=item.get("reference_range") or item.get("referenceRange"),
            )
        )

    return NormalizedResult(
        device_key=device_key,
        profile_id=profile["id"],
        accession=str(accession).strip(),
        observed_at=_parse_datetime(obj.get(observed_at_field) or obj.get("timestamp")),
        observations=observations,
        source_meta={"protocol": profile.get("protocol", "REST-JSON")},
        raw_payload=json.dumps(obj, separators=(",", ":"), default=str),
    )
