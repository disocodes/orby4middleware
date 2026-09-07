import socket
from datetime import datetime, timezone
import httpx
from .schema import NormalizedResult


def to_fhir_bundle(result: NormalizedResult, *, patient_id: str, service_request_id: str | None = None) -> dict:
    entries = []
    observation_refs = []
    for i, obs in enumerate(result.observations, start=1):
        oid = f"orby-{result.accession}-{i}"
        coding = []
        if obs.loinc:
            coding.append({"system": "http://loinc.org", "code": obs.loinc, "display": obs.display})
        else:
            coding.append({"system": "urn:orby:local", "code": obs.code, "display": obs.display})
        resource = {
            "resourceType": "Observation",
            "id": oid,
            "status": "final",
            "code": {"coding": coding},
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": result.observed_at.isoformat(),
            "identifier": [{"system": "urn:orby:accession", "value": result.accession}],
        }
        if isinstance(obs.value, (int, float)):
            resource["valueQuantity"] = {"value": obs.value, **({"unit": obs.unit} if obs.unit else {})}
        else:
            resource["valueString"] = "" if obs.value is None else str(obs.value)
        if obs.reference_range:
            resource["referenceRange"] = [{"text": obs.reference_range}]
        entries.append({"fullUrl": f"urn:uuid:{oid}", "resource": resource, "request": {"method": "PUT", "url": f"Observation/{oid}"}})
        observation_refs.append({"reference": f"Observation/{oid}"})

    report_id = f"orby-report-{result.accession}"
    report = {
        "resourceType": "DiagnosticReport",
        "id": report_id,
        "status": "final",
        "code": {"text": "Device laboratory result"},
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": result.observed_at.isoformat(),
        "identifier": [{"system": "urn:orby:accession", "value": result.accession}],
        "result": observation_refs,
    }
    if service_request_id:
        report["basedOn"] = [{"reference": f"ServiceRequest/{service_request_id}"}]
    entries.append({"fullUrl": f"urn:uuid:{report_id}", "resource": report,
                    "request": {"method": "PUT", "url": f"DiagnosticReport/{report_id}"}})
    return {"resourceType": "Bundle", "type": "transaction", "entry": entries}


def to_hl7_oru(result: NormalizedResult, *, patient_id: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    observed = result.observed_at.strftime("%Y%m%d%H%M%S")
    lines = [
        f"MSH|^~\\&|ORBY4MIDDLEWARE|LAB|EMR|HOSPITAL|{ts}||ORU^R01|{result.accession}-{ts}|P|2.5.1",
        f"PID|||{patient_id}",
        f"OBR|1||{result.accession}|LAB^Device result|||{observed}",
    ]
    for i, obs in enumerate(result.observations, start=1):
        ident = f"{obs.loinc or obs.code}^{obs.display or obs.code}^{'LN' if obs.loinc else 'L'}"
        lines.append(f"OBX|{i}|ST|{ident}||{'' if obs.value is None else obs.value}|{obs.unit or ''}|{obs.reference_range or ''}|{obs.flag or ''}|||F")
    return "\r".join(lines) + "\r"


async def post_json(url: str, payload: dict, timeout: int = 15) -> tuple[int, str]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        return response.status_code, response.text[:2000]


def send_mllp(host: str, port: int, message: str, timeout: int = 15) -> str:
    framed = b"\x0b" + message.encode("utf-8") + b"\x1c\x0d"
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(framed)
        sock.settimeout(timeout)
        return sock.recv(65535).decode("utf-8", errors="replace")
