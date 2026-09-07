from orby4middleware.onboarding import (
    apply_observation_mapping,
    delivery_gate_reason,
    effective_profile,
    updated_preview_state,
)
from orby4middleware.parsers.fhir import parse_fhir_bundle
from orby4middleware.parsers.json_api import parse_json_result


def test_effective_profile_merges_saved_and_preview_overrides():
    base = {"id": "x", "parser": "generic-fixed-width", "config": {"a": 1, "nested": {"x": 1}}}
    device = {"parser_config": {"nested": {"y": 2}, "b": 2}}
    got = effective_profile(base, device, parser_config_override={"nested": {"x": 9}})
    assert got["config"] == {"a": 1, "b": 2, "nested": {"x": 9, "y": 2}}
    assert base["config"]["nested"]["x"] == 1


def test_delivery_gate_requires_preview_and_nonexperimental_status():
    assert delivery_gate_reason("experimental", {})
    assert delivery_gate_reason("vendor-documented", {})
    cfg = updated_preview_state({}, ok=True, accession="123", observation_count=2)
    assert delivery_gate_reason("vendor-documented", cfg) is None
    assert delivery_gate_reason("validated-lab", cfg) is None


def test_json_result_parser_and_mapping():
    profile = {"id": "json", "protocol": "REST-JSON", "config": {}}
    result = parse_json_result(
        {
            "accession": "A100",
            "observed_at": "2026-09-08T10:00:00Z",
            "results": [{"code": "HB", "value": 142, "unit": "g/L"}],
        },
        profile=profile,
        device_key="dev1",
    )
    mapped = apply_observation_mapping(
        result,
        {"HB": {"code": "HGB", "loinc": "718-7", "display": "Hemoglobin"}},
    )
    assert mapped.accession == "A100"
    assert mapped.observations[0].code == "HGB"
    assert mapped.observations[0].loinc == "718-7"
    assert mapped.source_meta["source_observation_codes"] == ["HB"]


def test_fhir_bundle_parser():
    profile = {"id": "fhir", "protocol": "FHIR-R4", "config": {}}
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "DiagnosticReport",
                    "identifier": [{"value": "ACC-9"}],
                    "effectiveDateTime": "2026-09-08T10:00:00Z",
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "identifier": [{"value": "ACC-9"}],
                    "code": {
                        "coding": [
                            {
                                "system": "http://loinc.org",
                                "code": "6690-2",
                                "display": "WBC",
                            }
                        ]
                    },
                    "valueQuantity": {"value": 6.2, "unit": "10^9/L"},
                }
            },
        ],
    }
    result = parse_fhir_bundle(bundle, profile=profile, device_key="fhir-dev")
    assert result.accession == "ACC-9"
    assert result.observations[0].loinc == "6690-2"
    assert result.observations[0].value == 6.2


def test_field_override_preserves_catalog_metadata_by_code():
    base = {
        "id": "x",
        "config": {
            "fields": [
                {
                    "code": "HGB",
                    "display": "Hemoglobin",
                    "scale": 0.1,
                    "start": 10,
                    "end": 15,
                }
            ]
        },
    }
    got = effective_profile(
        base,
        {"parser_config": {"fields": [{"code": "HGB", "start": 11, "end": 16}]}},
    )
    field = got["config"]["fields"][0]
    assert field["display"] == "Hemoglobin"
    assert field["scale"] == 0.1
    assert field["start"] == 11
    assert field["end"] == 16
