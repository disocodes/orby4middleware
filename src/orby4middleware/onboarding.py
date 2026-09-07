from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .schema import NormalizedResult, Observation

VALIDATION_STATUSES = {"experimental", "vendor-documented", "validated-lab"}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _merge_parser_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge parser config and preserve catalog field metadata by result code."""
    out = _deep_merge(base, {k: v for k, v in (override or {}).items() if k != "fields"})
    if "fields" in (override or {}):
        base_fields = {
            str(item.get("code")): item
            for item in (base.get("fields") or [])
            if isinstance(item, dict) and item.get("code")
        }
        merged_fields = []
        for item in override.get("fields") or []:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "")
            merged_fields.append(_deep_merge(base_fields.get(code, {}), item))
        out["fields"] = merged_fields
    return out


def effective_profile(
    base_profile: dict[str, Any],
    device_config: dict[str, Any] | None,
    *,
    parser_config_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the runtime parser profile without mutating the catalog profile."""
    profile = deepcopy(base_profile)
    saved = (device_config or {}).get("parser_config") or {}
    merged = _merge_parser_config(profile.get("config", {}) or {}, saved)
    if parser_config_override:
        merged = _merge_parser_config(merged, parser_config_override)
    profile["config"] = merged
    return profile


def apply_observation_mapping(
    result: NormalizedResult,
    mapping: dict[str, dict[str, Any]] | None,
) -> NormalizedResult:
    """Apply per-device mapping metadata while preserving source codes for auditability."""
    mapping = mapping or {}
    observations: list[Observation] = []
    for obs in result.observations:
        rule = mapping.get(obs.code) or {}
        if rule.get("enabled") is False:
            continue
        new_code = str(rule.get("code") or obs.code)
        mapped = obs.model_copy(
            update={
                "code": new_code,
                "display": rule.get("display", obs.display),
                "loinc": rule.get("loinc", obs.loinc),
                "unit": rule.get("unit", obs.unit),
            }
        )
        observations.append(mapped)

    source_meta = dict(result.source_meta or {})
    source_meta["mapping_applied"] = bool(mapping)
    source_meta["source_observation_codes"] = [obs.code for obs in result.observations]
    return result.model_copy(update={"observations": observations, "source_meta": source_meta})


def updated_preview_state(
    config: dict[str, Any] | None,
    *,
    ok: bool,
    error: str | None = None,
    accession: str | None = None,
    observation_count: int | None = None,
) -> dict[str, Any]:
    out = deepcopy(config or {})
    onboarding = dict(out.get("onboarding") or {})
    onboarding.update(
        {
            "preview_ok": bool(ok),
            "last_preview_at": datetime.now(timezone.utc).isoformat(),
            "last_preview_error": error,
        }
    )
    if accession is not None:
        onboarding["last_preview_accession"] = accession
    if observation_count is not None:
        onboarding["last_preview_observation_count"] = int(observation_count)
    out["onboarding"] = onboarding
    return out


def delivery_gate_reason(validation_status: str, config: dict[str, Any] | None) -> str | None:
    if validation_status not in VALIDATION_STATUSES:
        return f"unknown validation status: {validation_status}"
    if validation_status == "experimental":
        return "device is still experimental"
    onboarding = (config or {}).get("onboarding") or {}
    if not onboarding.get("preview_ok"):
        return "a successful parse preview is required before enabling delivery"
    return None


def normalize_delivery_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(settings or {})
    target_type = str(raw.get("target_type") or "").strip().lower()
    target = str(raw.get("target") or "").strip()
    enabled = bool(raw.get("enabled", False))
    if target_type and target_type not in {"fhir", "rest", "hl7"}:
        raise ValueError("target_type must be one of: fhir, rest, hl7")
    if enabled and (not target_type or not target):
        raise ValueError("enabled delivery requires target_type and target")
    return {"enabled": enabled, "target_type": target_type, "target": target}
