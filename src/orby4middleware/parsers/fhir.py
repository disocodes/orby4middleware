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
        raise ValueError("FHIR payload must be a JSON object")
    return value


def _identifiers(resource: dict[str, Any]) -> list[str]:
    out = []
    for item in resource.get("identifier", []) or []:
        if isinstance(item, dict) and item.get("value"):
            out.append(str(item["value"]))
    return out


def _coding(resource: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    code_obj = resource.get("code") or {}
    codings = code_obj.get("coding") or []
    first = codings[0] if codings else {}
    code = first.get("code") or code_obj.get("text")
    display = first.get("display") or code_obj.get("text")
    loinc = first.get("code") if first.get("system") == "http://loinc.org" else None
    return code, display, loinc


def _value(resource: dict[str, Any]):
    q = resource.get("valueQuantity")
    if isinstance(q, dict):
        return q.get("value"), q.get("unit") or q.get("code")
    for key in ("valueString", "valueInteger", "valueDecimal", "valueBoolean"):
        if key in resource:
            return resource.get(key), None
    return None, None


def _reference_range(resource: dict[str, Any]) -> str | None:
    ranges = resource.get("referenceRange") or []
    if not ranges:
        return None
    first = ranges[0] or {}
    if first.get("text"):
        return str(first["text"])
    low = (first.get("low") or {}).get("value")
    high = (first.get("high") or {}).get("value")
    unit = (first.get("low") or first.get("high") or {}).get("unit")
    if low is None and high is None:
        return None
    return f"{'' if low is None else low}-{'' if high is None else high}{(' ' + unit) if unit else ''}"


def _parse_time(value: Any) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_fhir_bundle(payload, *, profile, device_key):
    bundle = _load(payload)
    if bundle.get("resourceType") != "Bundle":
        raise ValueError("FHIR parser currently expects a Bundle")

    resources = [
        entry.get("resource")
        for entry in bundle.get("entry", []) or []
        if isinstance(entry, dict) and isinstance(entry.get("resource"), dict)
    ]
    reports = [r for r in resources if r.get("resourceType") == "DiagnosticReport"]
    observations_src = [r for r in resources if r.get("resourceType") == "Observation"]

    accession = None
    for resource in reports + observations_src:
        ids = _identifiers(resource)
        if ids:
            accession = ids[0]
            break
    if not accession:
        accession = (bundle.get("identifier") or {}).get("value")
    if not accession:
        raise ValueError("FHIR accession/identifier not found")

    observations: list[Observation] = []
    observed_at = None
    for resource in observations_src:
        code, display, loinc = _coding(resource)
        if not code:
            continue
        value, unit = _value(resource)
        observations.append(
            Observation(
                code=str(code),
                display=display,
                loinc=loinc,
                value=value,
                unit=unit,
                flag=(resource.get("interpretation") or [{}])[0].get("text")
                if resource.get("interpretation")
                else None,
                reference_range=_reference_range(resource),
            )
        )
        observed_at = observed_at or resource.get("effectiveDateTime") or resource.get("issued")

    if not observations:
        raise ValueError("FHIR Bundle contained no Observation resources")

    return NormalizedResult(
        device_key=device_key,
        profile_id=profile["id"],
        accession=str(accession).strip(),
        observed_at=_parse_time(observed_at or (reports[0].get("effectiveDateTime") if reports else None)),
        observations=observations,
        source_meta={"protocol": profile.get("protocol", "FHIR-R4"), "fhir_bundle_type": bundle.get("type")},
        raw_payload=json.dumps(bundle, separators=(",", ":"), default=str),
    )
